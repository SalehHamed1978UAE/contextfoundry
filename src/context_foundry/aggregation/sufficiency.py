"""
SufficiencyGate - Determines result kind based on evidence quality.

Per v1.3 spec §5, the gate evaluates:
- Closure policy (AUTHORITATIVE → EXACT possible)
- Semantic confidence
- Coverage
- Conflict/dedup penalties

And outputs one of: EXACT, LOWER_BOUND, RANGE, INSUFFICIENT
"""

import logging
from typing import Optional

from .models import (
    CAT,
    ResultKind,
    ClosurePolicy,
    SufficiencyDecision,
    ConfidenceComponents,
    BoundedCount,
    EvidenceEnvelope,
)
from .planner import ExecutionPlan
from .executor import RawAggregationResult

logger = logging.getLogger(__name__)


class SufficiencyGate:
    """
    Numeric sufficiency gate for aggregation results.
    
    Stricter than descriptive sufficiency, but non-brittle:
    - Allows exact counts when closed-world + good data
    - Allows safe bounds when open-world or partial
    - Avoids early-return that blocks synthesis
    """
    
    # Thresholds (tunable)
    EXACT_THRESHOLD = 0.80
    BOUNDED_THRESHOLD = 0.55
    
    # Closure factor weights
    CLOSURE_FACTORS = {
        ClosurePolicy.AUTHORITATIVE: 1.0,
        ClosurePolicy.PARTIAL: 0.7,
        ClosurePolicy.OPEN_WORLD: 0.4,
    }
    
    def evaluate(
        self,
        cat: CAT,
        plan: ExecutionPlan,
        raw_result: RawAggregationResult,
        evidence: EvidenceEnvelope,
    ) -> SufficiencyDecision:
        """
        Evaluate sufficiency of aggregation result.
        
        Returns:
            SufficiencyDecision with result_kind, confidence, bounds, reasons
        """
        # Compute confidence components
        components = self._compute_confidence_components(cat, raw_result)
        
        # Composite confidence score
        confidence = self._compute_composite_confidence(components)
        
        logger.info(f"Sufficiency evaluation: confidence={confidence:.2f}, closure={cat.closure_policy}")
        
        # Determine result kind based on confidence and closure
        result_kind, reasons = self._determine_result_kind(
            confidence, cat.closure_policy, raw_result
        )
        
        # Compute bounds if RANGE
        bounds = None
        if result_kind == ResultKind.RANGE:
            bounds = self._compute_bounds(raw_result, components)
        elif result_kind == ResultKind.LOWER_BOUND:
            bounds = BoundedCount(
                lower=raw_result.value if isinstance(raw_result.value, int) else int(raw_result.value),
                upper=None,
                method="lower_bound_only",
            )
        
        return SufficiencyDecision(
            result_kind=result_kind,
            confidence=confidence,
            confidence_components=components,
            bounds=bounds,
            reasons=reasons,
            assumptions=cat.assumptions,
            next_best_actions=self._suggest_actions(result_kind, reasons),
        )
    
    def _compute_confidence_components(
        self,
        cat: CAT,
        raw_result: RawAggregationResult,
    ) -> ConfidenceComponents:
        """Compute individual confidence components."""
        return ConfidenceComponents(
            semantic_clarity=cat.semantic_confidence,
            closure_factor=self.CLOSURE_FACTORS.get(cat.closure_policy, 0.5),
            coverage=self._estimate_coverage(raw_result),
            conflict_penalty=self._estimate_conflict_penalty(raw_result),
            entity_resolution_penalty=self._estimate_er_penalty(raw_result),
        )
    
    def _compute_composite_confidence(
        self,
        components: ConfidenceComponents,
    ) -> float:
        """
        Compute composite confidence score.
        
        Formula per §5.2:
        confidence = semantic_clarity 
                   × closure_factor 
                   × coverage 
                   × (1 - conflict_penalty) 
                   × (1 - entity_resolution_penalty)
        """
        confidence = (
            components.semantic_clarity
            * components.closure_factor
            * components.coverage
            * (1 - components.conflict_penalty)
            * (1 - components.entity_resolution_penalty)
        )
        return max(0.0, min(1.0, confidence))
    
    def _determine_result_kind(
        self,
        confidence: float,
        closure_policy: ClosurePolicy,
        raw_result: RawAggregationResult,
    ) -> tuple:
        """
        Determine result kind based on confidence and closure.
        
        Decision rules per §5.3:
        - AUTHORITATIVE + confidence ≥ 0.80 → EXACT
        - confidence ≥ 0.55 + open-world → LOWER_BOUND
        - confidence ≥ 0.55 + conflicts → RANGE
        - confidence < 0.55 → INSUFFICIENT
        """
        reasons = []
        
        # AUTHORITATIVE path - handle both EXACT and LOWER_BOUND
        if closure_policy == ClosurePolicy.AUTHORITATIVE:
            if confidence >= self.EXACT_THRESHOLD:
                return ResultKind.EXACT, []
            if confidence >= self.BOUNDED_THRESHOLD:
                reasons.append({
                    "code": "AUTHORITATIVE_LOW_CONF",
                    "detail": "Authoritative source but below exact threshold"
                })
                return ResultKind.LOWER_BOUND, reasons
        
        # BOUNDED paths for other closure policies
        if confidence >= self.BOUNDED_THRESHOLD:
            if closure_policy == ClosurePolicy.OPEN_WORLD:
                reasons.append({
                    "code": "OPEN_WORLD",
                    "detail": "Data source may not be complete; returning lower bound"
                })
                return ResultKind.LOWER_BOUND, reasons
            
            if raw_result.has_multiple_sources:
                reasons.append({
                    "code": "MULTI_SOURCE",
                    "detail": "Multiple sources with potential conflicts; returning range"
                })
                return ResultKind.RANGE, reasons
            
            # Default to LOWER_BOUND for partial closure
            if closure_policy == ClosurePolicy.PARTIAL:
                reasons.append({
                    "code": "PARTIAL_COVERAGE",
                    "detail": "Known data gaps; returning lower bound"
                })
                return ResultKind.LOWER_BOUND, reasons
        
        # INSUFFICIENT path
        reasons.append({
            "code": "LOW_CONFIDENCE",
            "detail": f"Confidence ({confidence:.2f}) below threshold ({self.BOUNDED_THRESHOLD})"
        })
        return ResultKind.INSUFFICIENT, reasons
    
    def _compute_bounds(
        self,
        raw_result: RawAggregationResult,
        components: ConfidenceComponents,
    ) -> BoundedCount:
        """Compute bounds for RANGE result."""
        value = raw_result.value if isinstance(raw_result.value, int) else int(raw_result.value or 0)
        
        # Simple heuristic: widen bounds based on confidence
        uncertainty = 1 - components.coverage
        margin = int(value * uncertainty * 0.5)
        
        return BoundedCount(
            lower=max(0, value - margin),
            upper=value + margin,
            expected=value,
            method="confidence_based",
        )
    
    def _estimate_coverage(self, raw_result: RawAggregationResult) -> float:
        """Estimate data coverage (0-1)."""
        # In production, would check for NULL values, missing timestamps, etc.
        return 0.9  # Placeholder
    
    def _estimate_conflict_penalty(self, raw_result: RawAggregationResult) -> float:
        """Estimate penalty from conflicting sources (0-1)."""
        if not raw_result.has_multiple_sources:
            return 0.0
        # In production, would compare source values
        return 0.1  # Placeholder
    
    def _estimate_er_penalty(self, raw_result: RawAggregationResult) -> float:
        """Estimate penalty from entity resolution uncertainty (0-1)."""
        # In production, would check entity_dedup_hints
        return 0.05  # Placeholder
    
    def _suggest_actions(
        self,
        result_kind: ResultKind,
        reasons: list,
    ) -> list:
        """Suggest next actions for the user."""
        actions = []
        
        if result_kind == ResultKind.INSUFFICIENT:
            actions.append("Refine query with more specific filters")
            actions.append("Check if data exists in the system")
        elif result_kind == ResultKind.LOWER_BOUND:
            actions.append("This is a lower bound; actual count may be higher")
        elif result_kind == ResultKind.RANGE:
            actions.append("Review breakdown to understand range")
        
        return actions
