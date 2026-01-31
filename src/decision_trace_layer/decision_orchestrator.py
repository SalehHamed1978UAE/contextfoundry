"""
Unified Decision Orchestrator
==============================

Single entry point for all CF agent decision points.
Integrates precedent lookup with no-block guarantees.

Integration points:
- Query routing
- Entity resolution  
- Sufficiency assessment
- Any other decision function

GUARDRAILS:
- 600ms timeout on precedent lookup
- No-block: always proceeds even if DTL is down
- Single hook - no duplicated logic across decision points
"""

import os
import logging
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass
from enum import Enum

from src.decision_trace_layer.precedent_middleware import (
    PrecedentMiddleware,
    Precedent,
    DecisionResult,
    PrecedentLookupMetrics
)

logger = logging.getLogger(__name__)


class DecisionType(str, Enum):
    """Standard decision types in CF"""
    QUERY_ROUTING = "query_routing"
    ENTITY_RESOLUTION = "entity_resolution"
    SUFFICIENCY_ASSESSMENT = "sufficiency_assessment"
    TIER_SELECTION = "tier_selection"
    CONFIDENCE_THRESHOLD = "confidence_threshold"
    CUSTOM = "custom"


@dataclass
class OrchestratorConfig:
    """Configuration for the decision orchestrator"""
    precedent_timeout_seconds: float = 0.6  # 600ms (aligned with PrecedentMiddleware)
    strong_precedent_threshold: float = 0.7
    auto_log_decisions: bool = True
    enable_precedent_lookup: bool = True


class DecisionOrchestrator:
    """
    Unified orchestrator for all agent decision points.
    
    This is the single integration point that wraps all decision functions
    with precedent lookup. Eliminates duplicated precedent logic across
    different decision functions.
    
    Usage:
        orchestrator = DecisionOrchestrator(tenant_id, decision_maker_id)
        
        # Method 1: Direct wrapper
        result = orchestrator.make_decision(
            decision_type=DecisionType.QUERY_ROUTING,
            situation="Complex multi-hop query about service dependencies",
            decide_fn=lambda prec: route_query_with_precedents(query, prec)
        )
        
        # Method 2: Decorator
        @orchestrator.decision_point(DecisionType.ENTITY_RESOLUTION)
        def resolve_entity(name, candidates, *, precedents, context):
            ...
    """
    
    def __init__(
        self,
        tenant_id: str,
        decision_maker_id: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        config: Optional[OrchestratorConfig] = None
    ):
        self.tenant_id = tenant_id
        self.decision_maker_id = decision_maker_id
        self.config = config or OrchestratorConfig()
        
        self._middleware = PrecedentMiddleware(
            tenant_id=tenant_id,
            decision_maker_id=decision_maker_id,
            api_key=api_key,
            base_url=base_url,
            timeout_seconds=self.config.precedent_timeout_seconds
        )
        
        self._enabled = self.config.enable_precedent_lookup
    
    @classmethod
    def get_metrics(cls) -> PrecedentLookupMetrics:
        """Get accumulated metrics across all orchestrator instances"""
        return PrecedentMiddleware.get_metrics()
    
    @classmethod
    def reset_metrics(cls):
        """Reset accumulated metrics"""
        PrecedentMiddleware.reset_metrics()
    
    def make_decision(
        self,
        decision_type: DecisionType,
        situation: str,
        decide_fn: Callable[[List[Precedent]], Dict[str, Any]],
        entity_ids: Optional[List[str]] = None
    ) -> DecisionResult:
        """
        Make a decision with precedent lookup.
        
        This is the unified entry point for all agent decisions.
        
        Args:
            decision_type: Type of decision being made
            situation: Natural language description for precedent matching
            decide_fn: Function that takes precedents and returns decision dict:
                {
                    "choice": {...},
                    "rationale": "...",
                    "followed_precedent_id": "..." or None,
                    "deviated_from_id": "..." or None,
                    "deviation_reason": "..." or None
                }
            entity_ids: Optional related entity IDs
        
        Returns:
            DecisionResult with decision and precedent tracking
        
        GUARDRAIL: No-block - always returns a decision even on failure
        """
        if not self._enabled:
            decision = decide_fn([])
            return DecisionResult(
                decision_id="precedents_disabled",
                choice=decision.get("choice", {}),
                rationale=decision.get("rationale", ""),
                precedents_considered=0,
                precedent_followed=None,
                deviated=False,
                deviation_reason=None,
                precedent_lookup_status="disabled",
                precedent_lookup_latency_ms=0.0
            )
        
        return self._middleware.decide_with_precedents(
            situation=situation,
            decision_type=decision_type.value,
            decide_fn=decide_fn,
            entity_ids=entity_ids,
            auto_log=self.config.auto_log_decisions
        )
    
    def decision_point(
        self,
        decision_type: DecisionType,
        situation_builder: Optional[Callable[..., str]] = None
    ):
        """
        Decorator for decision functions.
        
        The decorated function receives `precedents` and `context` as kwargs.
        
        Usage:
            @orchestrator.decision_point(DecisionType.QUERY_ROUTING)
            def route_query(query: str, *, precedents, context):
                if precedents and precedents[0].score > 0.7:
                    return precedents[0].choice.get("tier")
                return "TIER1_SIMPLE"
        """
        return self._middleware.with_precedents(
            decision_type=decision_type.value,
            situation_builder=situation_builder
        )
    
    def follow_precedent(
        self,
        precedent_id: str,
        choice: Dict[str, Any],
        rationale: str
    ) -> Optional[str]:
        """Log a decision that follows a precedent"""
        return self._middleware.follow(precedent_id, choice, rationale)
    
    def deviate_from_precedent(
        self,
        precedent_id: Optional[str],
        reason: str,
        choice: Dict[str, Any],
        rationale: str
    ) -> Optional[str]:
        """Log a decision that deviates from a precedent"""
        return self._middleware.deviate(precedent_id, reason, choice, rationale)


def create_orchestrator_for_tenant(
    tenant_id: str,
    decision_maker_id: str = "cf-agent",
    enabled: bool = True
) -> DecisionOrchestrator:
    """
    Factory function to create orchestrator with standard config.
    
    Args:
        tenant_id: Tenant UUID
        decision_maker_id: Agent/system ID making decisions
        enabled: Whether to enable precedent lookup
    
    Returns:
        Configured DecisionOrchestrator
    """
    config = OrchestratorConfig(
        precedent_timeout_seconds=0.3,
        strong_precedent_threshold=0.7,
        auto_log_decisions=True,
        enable_precedent_lookup=enabled
    )
    
    return DecisionOrchestrator(
        tenant_id=tenant_id,
        decision_maker_id=decision_maker_id,
        config=config
    )
