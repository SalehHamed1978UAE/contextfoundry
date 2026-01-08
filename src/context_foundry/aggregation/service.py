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
        if not self._is_enabled():
            return False
        return self.intent_classifier.is_aggregation(question)
    
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
        if not self._is_enabled():
            return None
        
        try:
            # Step 1: Classify intent
            intent = self.intent_classifier.classify(question)
            if intent is None:
                return None  # Not an aggregation query
            
            logger.info(f"Aggregation intent detected: {intent.kind.value}")
            
            # Step 2: Resolve anchor entities (if not provided)
            if anchor_entities:
                intent.anchor_entities = self._convert_anchor_entities(anchor_entities)
            
            # Step 3: Semantic resolution → CAT
            cat, alternatives, ambiguity = self.semantic_resolver.resolve(
                intent=intent,
                tenant_id=self.tenant_id,
            )
            
            # Handle high ambiguity
            if ambiguity >= self.ASK_THRESHOLD:
                # In interactive mode, we'd return disambiguation UI
                # For now, we'll run multiple and return alternatives
                logger.info(f"High ambiguity ({ambiguity:.2f}); running multiple candidates")
            
            # Step 4: Build and execute plans
            cats_to_run = self._select_cats_to_run(cat, alternatives, ambiguity)
            results = []
            
            for cat_i in cats_to_run:
                result = self._execute_single_cat(cat_i, question)
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
        plan = self.planner.build_plan(cat)
        
        # Execute (deterministic SQL/graph)
        raw_result, evidence = self.executor.execute(plan)
        
        # Evaluate sufficiency
        sufficiency = self.sufficiency_gate.evaluate(
            cat=cat,
            plan=plan,
            raw_result=raw_result,
            evidence=evidence,
        )
        
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
