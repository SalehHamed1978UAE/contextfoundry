"""
Intent classification and semantic resolution using DSPy.

Per v1.3 spec §4.3, we use DSPy Signatures to map natural language
to CAT structures, replacing fragile rule-based matching with
trainable, testable modules.
"""

import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

# DSPy import (optional - falls back to rule-based if not available)
try:
    import dspy
    DSPY_AVAILABLE = True
except ImportError:
    DSPY_AVAILABLE = False
    dspy = None

from .models import (
    AggIntent,
    IntentKind,
    CAT,
    AnchorEntity,
    Filter,
    TimeWindow,
    TimeMode,
    ClosurePolicy,
    DedupPolicy,
    TargetSource,
    TargetSpec,
    AggregationSpec,
)

logger = logging.getLogger(__name__)


# =============================================================================
# DSPy Signatures (when available)
# =============================================================================

if DSPY_AVAILABLE:
    
    class AggregationIntentSignature(dspy.Signature):
        """Map a user query to aggregation intent components."""
        
        user_query: str = dspy.InputField(desc="The user's natural language question")
        
        is_aggregation: bool = dspy.OutputField(
            desc="True if this is a counting/aggregation question"
        )
        intent_kind: str = dspy.OutputField(
            desc="One of: COUNT, COUNT_DISTINCT, SUM, AVG, MIN, MAX, GROUP_BY, TREND, TOP_K, GRAPH_COUNT, PROVENANCE_COUNT"
        )
        subject_phrase: str = dspy.OutputField(
            desc="What is being counted: jobs, incidents, approvals, etc."
        )
        time_reference: str = dspy.OutputField(
            desc="Time reference if any: 'last quarter', 'in 2024', etc. Empty if none."
        )
        filter_phrases: str = dspy.OutputField(
            desc="Filter conditions: 'with severity > 3', 'for service X', etc. Comma-separated."
        )
        ambiguity_score: float = dspy.OutputField(
            desc="0.0 to 1.0 indicating semantic clarity (1.0 = very clear)"
        )
    
    
    class SemanticResolutionSignature(dspy.Signature):
        """Resolve aggregation intent to canonical target."""
        
        intent_kind: str = dspy.InputField()
        subject_phrase: str = dspy.InputField()
        candidate_definitions: str = dspy.InputField(
            desc="JSON list of candidate definitions from registry"
        )
        
        selected_candidate_index: int = dspy.OutputField(
            desc="0-based index of best matching candidate"
        )
        grouping_key: str = dspy.OutputField(
            desc="Comma-separated list of attributes for uniqueness"
        )
        assumptions: str = dspy.OutputField(
            desc="Comma-separated list of assumptions being made"
        )
        confidence: float = dspy.OutputField(
            desc="0.0 to 1.0 confidence in this resolution"
        )


# =============================================================================
# Rule-Based Fallbacks
# =============================================================================

# Keywords that suggest aggregation queries
AGGREGATION_KEYWORDS = {
    "how many": IntentKind.COUNT,
    "count of": IntentKind.COUNT,
    "number of": IntentKind.COUNT,
    "total number": IntentKind.COUNT,
    "how much": IntentKind.SUM,
    "total amount": IntentKind.SUM,
    "sum of": IntentKind.SUM,
    "average": IntentKind.AVG,
    "avg": IntentKind.AVG,
    "mean": IntentKind.AVG,
    "minimum": IntentKind.MIN,
    "min": IntentKind.MIN,
    "lowest": IntentKind.MIN,
    "smallest": IntentKind.MIN,
    "least": IntentKind.MIN,
    "maximum": IntentKind.MAX,
    "max": IntentKind.MAX,
    "highest": IntentKind.MAX,
    "largest": IntentKind.MAX,
    "biggest": IntentKind.MAX,
    "greatest": IntentKind.MAX,
    "most ": IntentKind.MAX,
    "which division has the": IntentKind.MAX,
    "which has the most": IntentKind.MAX,
    "top": IntentKind.TOP_K,
    "ranking": IntentKind.TOP_K,
    "by category": IntentKind.GROUP_BY,
    "per": IntentKind.GROUP_BY,
    "breakdown": IntentKind.GROUP_BY,
    "trend": IntentKind.TREND,
    "change": IntentKind.TREND,
    "increase": IntentKind.TREND,
    "decrease": IntentKind.TREND,
    "depend on": IntentKind.GRAPH_COUNT,
    "connected to": IntentKind.GRAPH_COUNT,
    "downstream": IntentKind.GRAPH_COUNT,
    "upstream": IntentKind.GRAPH_COUNT,
    "documents mention": IntentKind.PROVENANCE_COUNT,
    "mentioned in": IntentKind.PROVENANCE_COUNT,
}

# Time reference patterns
TIME_PATTERNS = [
    (r"last\s+(quarter|month|week|year)", "relative"),
    (r"this\s+(quarter|month|week|year)", "relative"),
    (r"in\s+(\d{4})", "year"),
    (r"(Q[1-4])\s+(\d{4})", "quarter"),
    (r"(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})", "month"),
]


class IntentClassifier:
    """
    Classifies whether a query is an aggregation and extracts intent.
    
    Uses DSPy when available, falls back to rule-based matching.
    """
    
    def __init__(self, use_dspy: bool = True):
        self.use_dspy = use_dspy and DSPY_AVAILABLE
        
        if self.use_dspy:
            self.dspy_classifier = dspy.Predict(AggregationIntentSignature)
            logger.info("Using DSPy for intent classification")
        else:
            logger.info("Using rule-based intent classification")
    
    def is_aggregation(self, question: str) -> bool:
        """Quick check if question is likely an aggregation query."""
        question_lower = question.lower()
        return any(kw in question_lower for kw in AGGREGATION_KEYWORDS.keys())
    
    def classify(self, question: str) -> Optional[AggIntent]:
        """
        Classify question into AggIntent.
        
        Returns None if not an aggregation query.
        """
        if self.use_dspy:
            return self._classify_dspy(question)
        else:
            return self._classify_rules(question)
    
    def _classify_dspy(self, question: str) -> Optional[AggIntent]:
        """Classify using DSPy."""
        try:
            result = self.dspy_classifier(user_query=question)
            
            if not result.is_aggregation:
                return None
            
            intent_kind = IntentKind(result.intent_kind.upper())
            
            return AggIntent(
                kind=intent_kind,
                subject_phrase=result.subject_phrase,
                time_window=self._parse_time_reference(result.time_reference),
                filters=self._parse_filter_phrases(result.filter_phrases),
                raw_query=question,
            )
        except Exception as e:
            logger.warning(f"DSPy classification failed, falling back to rules: {e}")
            return self._classify_rules(question)
    
    def _classify_rules(self, question: str) -> Optional[AggIntent]:
        """Rule-based classification fallback."""
        question_lower = question.lower()
        
        # Find matching intent kind
        intent_kind = None
        for keyword, kind in AGGREGATION_KEYWORDS.items():
            if keyword in question_lower:
                intent_kind = kind
                break
        
        if intent_kind is None:
            return None
        
        # Extract subject phrase (word after aggregation keyword)
        subject = self._extract_subject(question_lower)
        
        # Extract time reference
        time_window = None
        for pattern, time_type in TIME_PATTERNS:
            match = re.search(pattern, question_lower)
            if match:
                time_window = TimeWindow(
                    mode=TimeMode.EVENT_TIME,
                    inferred=True,
                )
                break
        
        return AggIntent(
            kind=intent_kind,
            subject_phrase=subject,
            time_window=time_window,
            raw_query=question,
        )
    
    def _extract_subject(self, question: str) -> str:
        """Extract the subject being counted."""
        # Simple heuristic: find noun after "how many" or "number of"
        patterns = [
            r"how many\s+(\w+)",
            r"number of\s+(\w+)",
            r"count of\s+(\w+)",
            r"total\s+(\w+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, question.lower())
            if match:
                return match.group(1)
        return "items"
    
    def _parse_time_reference(self, time_ref: str) -> Optional[TimeWindow]:
        """Parse time reference string into TimeWindow."""
        if not time_ref or time_ref.strip() == "":
            return None
        return TimeWindow(mode=TimeMode.EVENT_TIME, inferred=True)
    
    def _parse_filter_phrases(self, filter_str: str) -> List[Filter]:
        """Parse comma-separated filter phrases into Filter objects."""
        if not filter_str or filter_str.strip() == "":
            return []
        
        filters = []
        for phrase in filter_str.split(","):
            phrase = phrase.strip()
            if phrase:
                filters.append(Filter(
                    path="",  # To be resolved by semantic resolver
                    op="=",
                    value=phrase,
                    raw=phrase,
                ))
        return filters


class SemanticResolver:
    """
    Resolves AggIntent to CAT using registry definitions.
    
    Per v1.3 spec §4.4, the resolution flow:
    1. Load candidates from agg_definitions
    2. Score candidates (lexical, structural, anchor compatibility)
    3. Compute ambiguity
    4. Generate CAT with assumptions
    """
    
    def __init__(self, registry: "AggDefinitionRegistry"):
        self.registry = registry
        
        if DSPY_AVAILABLE:
            self.dspy_resolver = dspy.Predict(SemanticResolutionSignature)
    
    def resolve(
        self,
        intent: AggIntent,
        tenant_id: UUID,
    ) -> Tuple[CAT, List[CAT], float]:
        """
        Resolve intent to CAT.
        
        Returns:
            Tuple of (primary CAT, alternative CATs, ambiguity score)
        """
        # Load candidate definitions from registry
        candidates = self.registry.get_candidates(
            concept_key=intent.subject_phrase,
            intent_kind=intent.kind,
        )
        
        if not candidates:
            # No registered definition; create minimal CAT
            logger.warning(f"No candidates for '{intent.subject_phrase}'; using default")
            return self._create_default_cat(intent, tenant_id), [], 0.9
        
        # Score candidates
        scored = self._score_candidates(intent, candidates)
        
        # Compute ambiguity
        if len(scored) >= 2:
            ambiguity = 1 - (scored[0][1] - scored[1][1])
        else:
            ambiguity = 0.0
        
        # Build primary CAT
        primary_candidate = scored[0][0]
        primary_cat = self._build_cat(intent, primary_candidate, tenant_id)
        primary_cat.semantic_confidence = scored[0][1]
        
        # Build alternatives
        alternatives = []
        for candidate, score in scored[1:3]:  # Top 2 alternatives
            alt_cat = self._build_cat(intent, candidate, tenant_id)
            alt_cat.semantic_confidence = score
            alt_cat.alternative_reason = candidate.get("name", "Alternative interpretation")
            alternatives.append(alt_cat)
        
        return primary_cat, alternatives, ambiguity
    
    def _score_candidates(
        self,
        intent: AggIntent,
        candidates: List[Dict[str, Any]],
    ) -> List[Tuple[Dict[str, Any], float]]:
        """Score candidates for the given intent."""
        scored = []
        
        for candidate in candidates:
            score = 0.0
            
            # Lexical match on synonyms
            if intent.subject_phrase.lower() in [
                s.lower() for s in candidate.get("synonyms", [])
            ]:
                score += 0.3
            
            # Intent kind compatibility
            if intent.kind.value in candidate.get("intent_kinds", []):
                score += 0.4
            
            # Disambiguation hints
            hints = candidate.get("disambiguation_hints", {})
            boost_words = hints.get("boost", [])
            lower_words = hints.get("lower", [])
            
            query_lower = intent.raw_query.lower() if intent.raw_query else ""
            for word in boost_words:
                if word.lower() in query_lower:
                    score += 0.1
            for word in lower_words:
                if word.lower() in query_lower:
                    score -= 0.1
            
            # Baseline confidence
            score += candidate.get("confidence_baseline", 0.5) * 0.2
            
            scored.append((candidate, min(1.0, max(0.0, score))))
        
        # Sort by score descending
        scored.sort(key=lambda x: -x[1])
        return scored
    
    def _build_cat(
        self,
        intent: AggIntent,
        candidate: Dict[str, Any],
        tenant_id: UUID,
    ) -> CAT:
        """Build CAT from intent and candidate definition."""
        target_def = candidate.get("target", {})
        agg_def = candidate.get("aggregation", {})
        
        return CAT(
            tenant_id=tenant_id,
            anchor=intent.anchor_entities[0] if intent.anchor_entities else None,
            target=TargetSpec(
                source=TargetSource(target_def.get("source", "ENTITY_TABLE")),
                entity_type=target_def.get("target_entity_type"),
                relationship_type=target_def.get("relationship_type"),
            ),
            aggregation=AggregationSpec(
                op=intent.kind,
                grouping_key=agg_def.get("grouping_key", []),
            ),
            filters=self._convert_filters(intent.filters, candidate.get("filters", [])),
            time=intent.time_window,
            closure_policy=ClosurePolicy(candidate.get("closure_policy", "PARTIAL")),
            dedup_policy=DedupPolicy(candidate.get("dedup_policy", "CANONICAL_ID")),
            assumptions=self._generate_assumptions(intent, candidate),
        )
    
    def _create_default_cat(self, intent: AggIntent, tenant_id: UUID) -> CAT:
        """Create minimal CAT when no registry definition exists."""
        return CAT(
            tenant_id=tenant_id,
            anchor=intent.anchor_entities[0] if intent.anchor_entities else None,
            target=TargetSpec(
                source=TargetSource.ENTITY_TABLE,
                entity_type=intent.subject_phrase,
            ),
            aggregation=AggregationSpec(op=intent.kind),
            filters=intent.filters,
            time=intent.time_window,
            closure_policy=ClosurePolicy.OPEN_WORLD,
            dedup_policy=DedupPolicy.EXACT,
            assumptions=[
                f"No definition registered for '{intent.subject_phrase}'",
                "Using default entity table lookup",
                "Results may be incomplete (open-world)",
            ],
        )
    
    def _convert_filters(
        self,
        intent_filters: List[Filter],
        candidate_filters: List[Dict[str, Any]],
    ) -> List[Filter]:
        """Merge intent filters with candidate's predefined filters."""
        filters = []
        
        # Add candidate's required filters
        for cf in candidate_filters:
            if cf.get("required", True):
                filters.append(Filter(
                    path=cf.get("path", ""),
                    op=cf.get("op", "="),
                    value=cf.get("value"),
                    required=True,
                ))
        
        # Add intent filters (need resolution)
        filters.extend(intent_filters)
        
        return filters
    
    def _generate_assumptions(
        self,
        intent: AggIntent,
        candidate: Dict[str, Any],
    ) -> List[str]:
        """Generate explicit assumptions for this resolution."""
        assumptions = []
        
        name = candidate.get("name", "Unknown definition")
        assumptions.append(f"Using definition: {name}")
        
        grouping_key = candidate.get("aggregation", {}).get("grouping_key", [])
        if grouping_key:
            assumptions.append(f"Counting distinct by: {', '.join(grouping_key)}")
        
        if intent.time_window and intent.time_window.inferred:
            assumptions.append("Time window inferred from query")
        
        return assumptions
