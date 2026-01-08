"""
AggregationService - Main orchestrator for quantitative queries.

This service is called from ContextFoundry.query() after intent classification
when an aggregation query is detected. It owns:
- Semantic resolution (intent → CAT)
- Planning (CAT → execution plan)
- Execution (plan → raw result)
- Sufficiency gating (raw → result kind)
- Answer composition

The existing tri-memory pipeline stays untouched for descriptive queries.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from sqlalchemy.orm import Session

from .models import (
    AggIntent,
    AnchorEntity,
    CAT,
    AggregationResult,
    ResultKind,
    EvidenceEnvelope,
    SufficiencyDecision,
)
from .intent import IntentClassifier, SemanticResolver
from .registry import AggDefinitionRegistry
from .planner import AggregationPlanner, ExecutionPlan
from .executor import AggregationExecutor
from .sufficiency import SufficiencyGate
from .crc import CaptureRecaptureEstimator
from .formatter import AnswerFormatter

logger = logging.getLogger(__name__)

# Stopwords for entity extraction
STOPWORDS = {
    'how', 'many', 'what', 'where', 'when', 'who', 'which', 'why', 'is', 'are',
    'the', 'a', 'an', 'has', 'have', 'had', 'does', 'do', 'did', 'done', 'been',
    'with', 'for', 'from', 'by', 'on', 'in', 'at', 'to', 'of', 'and', 'or', 'not',
    'all', 'any', 'each', 'every', 'some', 'most', 'total', 'count', 'number',
}


class AggregationService:
    """
    Main entry point for aggregation queries.
    
    Usage:
        service = AggregationService(session, tenant_ctx)
        result = service.handle_query(question, user_ctx)
        
        if result is None:
            # Not an aggregation query; route to normal Q/A
            pass
        elif result.is_success:
            # We have a count/aggregation
            print(result.display_text)
        else:
            # INSUFFICIENT; offer fallback
            print(result.fallback_message)
    """
    
    # Thresholds (tunable)
    ASK_THRESHOLD = 0.65       # Ambiguity above this triggers disambiguation
    MULTI_RESULT_THRESHOLD = 0.45  # Run top 2 candidates if above this
    
    def __init__(
        self,
        session: Session,
        tenant_id: UUID,
        feature_flags: Optional[Dict[str, bool]] = None,
    ):
        """
        Initialize aggregation service.
        
        Args:
            session: SQLAlchemy session (RLS context must be set)
            tenant_id: Current tenant UUID
            feature_flags: Optional feature flag overrides
        """
        self.session = session
        self.tenant_id = tenant_id
        self.flags = feature_flags or {}
        
        # Initialize components
        self.intent_classifier = IntentClassifier()
        self.registry = AggDefinitionRegistry(session, tenant_id)
        self.semantic_resolver = SemanticResolver(self.registry)
        self.planner = AggregationPlanner()
        self.executor = AggregationExecutor(session, tenant_id)
        self.sufficiency_gate = SufficiencyGate()
        self.crc_estimator = CaptureRecaptureEstimator()
        self.formatter = AnswerFormatter()
    
    def is_aggregation_query(self, question: str) -> bool:
        """
        Quick check if question is an aggregation query.
        
        Called early in ContextFoundry.query() to decide routing.
        """
        enabled = self._is_enabled()
        logger.info(f"[AGG-SVC-1] is_aggregation_query: enabled={enabled}")
        if not enabled:
            return False
        result = self.intent_classifier.is_aggregation(question)
        logger.info(f"[AGG-SVC-1] intent_classifier.is_aggregation() = {result}")
        return result
    
    def handle_query(
        self,
        question: str,
        user_ctx: Optional[Dict[str, Any]] = None,
        anchor_entities: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[AggregationResult]:
        """
        Handle an aggregation query end-to-end.
        
        Args:
            question: User's natural language question
            user_ctx: User context (permissions, preferences)
            anchor_entities: Pre-resolved entities from CF entity resolution
            
        Returns:
            AggregationResult if this is an aggregation query, None otherwise.
            On error, returns INSUFFICIENT result with explanation.
        """
        logger.info(f"[AGG-SVC-2] handle_query ENTRY: '{question[:80]}'")
        
        if not self._is_enabled():
            logger.info("[AGG-SVC-2] RETURNING None - not enabled")
            return None
        
        try:
            # Step 1: Classify intent
            logger.info("[AGG-SVC-3] Calling intent_classifier.classify()...")
            intent = self.intent_classifier.classify(question)
            logger.info(f"[AGG-SVC-3] classify() returned: {intent}")
            
            if intent is None:
                logger.info("[AGG-SVC-3] RETURNING None - intent is None")
                return None  # Not an aggregation query
            
            logger.info(f"[AGG-SVC-4] Intent: kind={intent.kind.value}, subject='{intent.subject_phrase}', anchors={intent.anchor_entities}")
            
            # Step 2: Resolve anchor entities (if not provided)
            if anchor_entities:
                intent.anchor_entities = self._convert_anchor_entities(anchor_entities)
            elif not intent.anchor_entities:
                # Try to extract and resolve entity names from the query
                resolved_anchors = self._resolve_anchor_entities(question, intent.subject_phrase)
                if resolved_anchors:
                    intent.anchor_entities = resolved_anchors
                    logger.info(f"[AGG-SVC-4b] Resolved anchors: {[a.name for a in resolved_anchors]}")
            
            # Step 3: Semantic resolution → CAT
            logger.info(f"[AGG-SVC-5] Calling semantic_resolver.resolve()...")
            cat, alternatives, ambiguity = self.semantic_resolver.resolve(
                intent=intent,
                tenant_id=self.tenant_id,
            )
            logger.info(f"[AGG-SVC-5] resolve() returned: cat={cat}, ambiguity={ambiguity}, alternatives={len(alternatives) if alternatives else 0}")
            
            if cat:
                logger.info(f"[AGG-SVC-6] CAT details: target_source={cat.target.source if cat.target else None}, rel_type={cat.target.relationship_type if cat.target else None}")
            
            # Handle high ambiguity
            if ambiguity >= self.ASK_THRESHOLD:
                logger.info(f"[AGG-SVC-6] High ambiguity ({ambiguity:.2f}); running multiple candidates")
            
            # Step 4: Build and execute plans
            cats_to_run = self._select_cats_to_run(cat, alternatives, ambiguity)
            logger.info(f"[AGG-SVC-7] cats_to_run count: {len(cats_to_run)}")
            results = []
            
            for i, cat_i in enumerate(cats_to_run):
                logger.info(f"[AGG-SVC-8] Executing CAT {i+1}/{len(cats_to_run)}...")
                result = self._execute_single_cat(cat_i, question)
                logger.info(f"[AGG-SVC-8] Result: kind={result.result_kind.value}, value={result.value}")
                results.append((cat_i, result))
            
            # Step 5: Select primary result and format
            primary_cat, primary_result = results[0]
            
            # Add alternatives if we ran multiple
            if len(results) > 1:
                primary_result.alternatives = [
                    {
                        "label": f"If you meant: {alt_cat.alternative_reason or 'alternative interpretation'}",
                        "kind": alt_result.result_kind.value,
                        "value": alt_result.value,
                        "bounds": alt_result.bounds,
                    }
                    for alt_cat, alt_result in results[1:]
                ]
            
            # Step 6: Log and return
            self._log_result(question, primary_cat, primary_result)
            
            return primary_result
            
        except Exception as e:
            logger.exception(f"Aggregation query failed: {e}")
            return self._create_error_result(question, str(e))
    
    def _execute_single_cat(self, cat: CAT, question: str) -> AggregationResult:
        """Execute a single CAT through plan → execute → sufficiency pipeline."""
        
        # Build execution plan
        logger.info(f"[AGG-EXEC-1] Building plan for CAT...")
        plan = self.planner.build_plan(cat)
        logger.info(f"[AGG-EXEC-1] Plan: {plan}")
        
        # Execute (deterministic SQL/graph)
        logger.info(f"[AGG-EXEC-2] Executing plan...")
        raw_result, evidence = self.executor.execute(plan)
        logger.info(f"[AGG-EXEC-2] raw_result: value={getattr(raw_result, 'value', None)}, count={getattr(raw_result, 'count', None)}")
        
        # Evaluate sufficiency
        logger.info(f"[AGG-EXEC-3] Evaluating sufficiency...")
        sufficiency = self.sufficiency_gate.evaluate(
            cat=cat,
            plan=plan,
            raw_result=raw_result,
            evidence=evidence,
        )
        logger.info(f"[AGG-EXEC-3] sufficiency: kind={sufficiency.result_kind.value}, confidence={sufficiency.confidence}, bounds={sufficiency.bounds}")
        
        # Apply Lincoln-Petersen if RANGE and multi-source
        if (sufficiency.result_kind == ResultKind.RANGE 
            and raw_result.has_multiple_sources
            and self._is_crc_enabled()):
            crc_bounds = self.crc_estimator.estimate(raw_result.sources)
            if crc_bounds:
                sufficiency.bounds = crc_bounds
        
        # Format result
        return self.formatter.format(
            cat=cat,
            raw_result=raw_result,
            sufficiency=sufficiency,
            evidence=evidence,
            question=question,
        )
    
    def _select_cats_to_run(
        self,
        primary: CAT,
        alternatives: List[CAT],
        ambiguity: float,
    ) -> List[CAT]:
        """Select which CATs to execute based on ambiguity."""
        if ambiguity >= self.MULTI_RESULT_THRESHOLD and alternatives:
            # Run primary + top alternative
            return [primary] + alternatives[:1]
        return [primary]
    
    def _convert_anchor_entities(
        self,
        entities: List[Dict[str, Any]],
    ) -> List:
        """Convert CF entity format to AnchorEntity."""
        from .models import AnchorEntity
        return [
            AnchorEntity(
                entity_id=e.get("entity_id") or e.get("id"),
                entity_type=e.get("entity_type") or e.get("type"),
                name=e.get("name"),
            )
            for e in entities
        ]
    
    def _create_error_result(self, question: str, error: str) -> AggregationResult:
        """Create INSUFFICIENT result for error cases."""
        return AggregationResult(
            result_kind=ResultKind.INSUFFICIENT,
            value=None,
            confidence=0.0,
            confidence_label="Failed",
            assumptions=[f"Query failed: {error}"],
            raw_query=question,
        )
    
    def _log_result(self, question: str, cat: CAT, result: AggregationResult) -> None:
        """Log aggregation result for telemetry and DTL."""
        # TODO: Integrate with QueryLogger and DTL trace
        logger.info(
            f"Aggregation complete: "
            f"kind={result.result_kind.value}, "
            f"value={result.value}, "
            f"confidence={result.confidence:.2f}"
        )
    
    def _resolve_anchor_entities(
        self, 
        question: str, 
        subject_phrase: str
    ) -> List[AnchorEntity]:
        """
        Extract and resolve entity names from the query.
        
        Uses simple heuristics to find proper nouns (capitalized words that
        aren't the subject or common stopwords) and resolves them via EntityResolver.
        """
        import re
        from ..agents.entity_resolver import EntityResolver
        
        anchors = []
        
        # Extract potential entity names (capitalized words not at sentence start)
        words = question.split()
        subject_words = set(subject_phrase.lower().split())
        
        potential_names = []
        for i, word in enumerate(words):
            # Clean punctuation
            clean_word = re.sub(r'[^\w]', '', word)
            if not clean_word:
                continue
            
            # Skip if it's the subject phrase
            if clean_word.lower() in subject_words:
                continue
            
            # Skip common stopwords
            if clean_word.lower() in STOPWORDS:
                continue
            
            # Look for capitalized words (not at sentence start)
            if clean_word[0].isupper() and (i > 0 or clean_word.lower() not in {'how', 'what', 'who', 'where', 'when', 'why'}):
                # Also check it's not following common question starters
                if i > 0 or question.strip()[0].isupper():
                    potential_names.append(clean_word)
        
        if not potential_names:
            logger.debug(f"[AGG-SVC-ANCHOR] No potential entity names found in: '{question}'")
            return []
        
        logger.info(f"[AGG-SVC-ANCHOR] Potential entity names: {potential_names}")
        
        # Resolve each potential name
        try:
            resolver = EntityResolver(session=self.session, tenant_id=str(self.tenant_id))
            
            for name in potential_names:
                result = resolver.resolve(name, entity_type_hint="Person")
                
                if result.entity and result.confidence >= 0.7:
                    logger.info(f"[AGG-SVC-ANCHOR] Resolved '{name}' -> {result.entity.name} (id={result.entity.entity_id}, conf={result.confidence:.2f})")
                    anchors.append(AnchorEntity(
                        entity_id=result.entity.entity_id,
                        entity_type=result.entity.entity_type,
                        name=result.entity.name,
                    ))
                else:
                    logger.debug(f"[AGG-SVC-ANCHOR] Could not resolve '{name}' (conf={result.confidence:.2f if result else 0})")
        except Exception as e:
            logger.warning(f"[AGG-SVC-ANCHOR] Entity resolution failed: {e}")
        
        return anchors
    
    def _is_enabled(self) -> bool:
        """Check if aggregation framework is enabled."""
        return self.flags.get("aggregation.enabled", True)
    
    def _is_crc_enabled(self) -> bool:
        """Check if Lincoln-Petersen CRC estimation is enabled."""
        return self.flags.get("aggregation.crc_estimation.enabled", True)


# Convenience function for integration with ContextFoundry.query()
def try_aggregation_query(
    session: Session,
    tenant_id: UUID,
    question: str,
    user_ctx: Optional[Dict[str, Any]] = None,
    anchor_entities: Optional[List[Dict[str, Any]]] = None,
    feature_flags: Optional[Dict[str, bool]] = None,
) -> Optional[AggregationResult]:
    """
    Attempt to handle question as aggregation query.
    
    Returns None if not an aggregation query (route to normal Q/A).
    Returns AggregationResult if handled (even if INSUFFICIENT).
    
    Usage in ContextFoundry.query():
        # After intent classification
        agg_result = try_aggregation_query(session, tenant_id, question, ...)
        if agg_result is not None:
            return format_aggregation_response(agg_result)
        # Continue with normal tri-memory pipeline
    """
    service = AggregationService(session, tenant_id, feature_flags)
    
    if not service.is_aggregation_query(question):
        return None
    
    return service.handle_query(question, user_ctx, anchor_entities)
