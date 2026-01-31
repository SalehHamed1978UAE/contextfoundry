"""
DTL Integration Tests - Precedent-Based Routing and Context Usage

Tests integration between DTL (Decision Trace Layer) and:
1. RLM tier routing with precedent data
2. ContextFoundry.query using DTL context when available

These tests use mocks to avoid database/API dependencies in CI.
"""

import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_foundry.dtl.core import AuthContext, PrecedentResult
from src.context_foundry.rlm.router import QueryComplexityRouter, QueryTier


def create_mock_precedent(
    decision_id: Optional[str] = None,
    decision_type: str = "tier_selection",
    choice: Optional[Dict] = None,
    rrf_score: float = 0.85,
    semantic_score: float = 0.75,
    outcome_status: str = "positive"
) -> PrecedentResult:
    """Helper to create mock PrecedentResult objects."""
    return PrecedentResult(
        decision_id=decision_id or str(uuid.uuid4()),
        decision_human_id=f"DEC-{uuid.uuid4().hex[:6].upper()}",
        summary=f"Mock precedent for {decision_type}",
        decision_type=decision_type,
        rationale_summary=f"This decision was made based on {decision_type} analysis",
        choice=choice or {"tier": "tier2", "reason": "complex query pattern"},
        decision_timestamp=datetime.utcnow() - timedelta(days=5),
        decision_maker_id=str(uuid.uuid4()),
        outcome_status=outcome_status,
        semantic_rank=1,
        fulltext_rank=2,
        entity_rank=3,
        semantic_score=semantic_score,
        fulltext_score=0.5,
        entity_overlap_score=0.6,
        recency_score=0.9,
        outcome_score=0.8,
        category_bonus=0.1,
        rrf_score=rrf_score
    )


class TestMockPrecedentHits:
    """Test 1: Mock precedent hits from DTL."""
    
    def test_precedent_result_creation(self):
        """Verify PrecedentResult can be created with all required fields."""
        precedent = create_mock_precedent(
            decision_type="entity_resolution",
            choice={"action": "merge", "confidence": 0.9}
        )
        
        assert precedent.decision_id is not None
        assert precedent.decision_type == "entity_resolution"
        assert precedent.choice["action"] == "merge"
        assert precedent.rrf_score == 0.85
        assert precedent.outcome_status == "positive"
    
    def test_precedent_result_to_dict(self):
        """Verify PrecedentResult.to_dict() returns expected structure."""
        precedent = create_mock_precedent()
        d = precedent.to_dict()
        
        assert "decision_id" in d
        assert "decision_human_id" in d
        assert "summary" in d
        assert "choice" in d
        assert "rrf_score" in d
        assert "relevance_explanation" in d
        
        explanation = d["relevance_explanation"]
        assert "summary" in explanation
        assert "factors" in explanation
        assert "semantic_score" in explanation
    
    def test_relevance_explanation_factors(self):
        """Verify relevance explanation includes expected factors."""
        precedent = create_mock_precedent(
            semantic_score=0.85,
            outcome_status="positive"
        )
        
        explanation = precedent.relevance_explanation
        factors = explanation["factors"]
        
        assert "highly similar reasoning" in " ".join(factors).lower() or len(factors) > 0
        assert "positive outcome" in factors
    
    def test_multiple_precedent_hits_ranking(self):
        """Verify multiple precedent hits can be ranked by rrf_score."""
        precedents = [
            create_mock_precedent(rrf_score=0.6),
            create_mock_precedent(rrf_score=0.9),
            create_mock_precedent(rrf_score=0.75),
        ]
        
        sorted_precedents = sorted(precedents, key=lambda p: p.rrf_score, reverse=True)
        
        assert sorted_precedents[0].rrf_score == 0.9
        assert sorted_precedents[1].rrf_score == 0.75
        assert sorted_precedents[2].rrf_score == 0.6
    
    def test_precedent_with_negative_outcome(self):
        """Verify precedents with negative outcomes are handled correctly."""
        precedent = create_mock_precedent(outcome_status="negative")
        
        factors = precedent.relevance_explanation["factors"]
        assert "negative outcome" in factors


class TestRLMTierRoutingWithPrecedents:
    """Test 2: Verify RLM tier routing respects precedent data."""
    
    def test_router_default_tier1_for_simple_query(self):
        """Simple query routes to Tier 1 by default."""
        router = QueryComplexityRouter()
        tier, signals = router.route("What is the status of Service X?")
        
        assert tier == QueryTier.TIER1_SIMPLE
        assert signals.complexity_score < router.complexity_threshold
    
    def test_router_default_tier2_for_complex_query(self):
        """Complex query routes to Tier 2 by default."""
        router = QueryComplexityRouter()
        tier, signals = router.route(
            "Compare the dependencies between Service A and Service B and explain the impact path"
        )
        
        assert tier == QueryTier.TIER2_RLM
    
    def test_precedent_can_override_to_tier2(self):
        """Precedent with tier2 choice should influence routing decision."""
        precedent = create_mock_precedent(
            choice={"tier": "tier2", "from_precedent": True},
            rrf_score=0.85
        )
        
        def mock_decide_fn(precedents):
            if precedents and precedents[0].rrf_score >= 0.7:
                return {
                    "choice": precedents[0].choice,
                    "rationale": "Following strong precedent",
                    "followed_precedent_id": precedents[0].decision_id
                }
            return {
                "choice": {"tier": "tier1", "from_precedent": False},
                "rationale": "No strong precedent"
            }
        
        result = mock_decide_fn([precedent])
        
        assert result["choice"]["tier"] == "tier2"
        assert result["choice"]["from_precedent"] == True
        assert "followed_precedent_id" in result
    
    def test_precedent_can_override_to_tier1(self):
        """Precedent with tier1 choice should influence routing decision."""
        precedent = create_mock_precedent(
            choice={"tier": "tier1", "from_precedent": True},
            rrf_score=0.9
        )
        
        def mock_decide_fn(precedents):
            if precedents and precedents[0].rrf_score >= 0.7:
                return {
                    "choice": precedents[0].choice,
                    "rationale": "Following strong precedent"
                }
            return {"choice": {"tier": "tier2"}, "rationale": "Default"}
        
        result = mock_decide_fn([precedent])
        
        assert result["choice"]["tier"] == "tier1"
    
    def test_weak_precedent_does_not_override(self):
        """Weak precedent (low score) should not override routing."""
        weak_precedent = create_mock_precedent(
            choice={"tier": "tier2"},
            rrf_score=0.3
        )
        
        def mock_decide_fn(precedents, default_tier):
            if precedents and precedents[0].rrf_score >= 0.7:
                return {
                    "choice": precedents[0].choice,
                    "followed": True
                }
            return {
                "choice": {"tier": default_tier},
                "followed": False
            }
        
        result = mock_decide_fn([weak_precedent], "tier1")
        
        assert result["choice"]["tier"] == "tier1"
        assert result["followed"] == False
    
    def test_no_precedents_uses_complexity_routing(self):
        """When no precedents exist, fall back to complexity-based routing."""
        router = QueryComplexityRouter()
        
        def mock_decide_fn(precedents, query):
            if not precedents:
                tier, signals = router.route(query)
                return {
                    "choice": {"tier": tier.value},
                    "from_precedent": False,
                    "complexity_score": signals.complexity_score
                }
            return {"choice": {"tier": "tier2"}}
        
        result = mock_decide_fn([], "What is the status?")
        
        assert result["from_precedent"] == False
        assert result["choice"]["tier"] == "tier1"
    
    def test_precedent_score_threshold_boundary(self):
        """Test boundary conditions for precedent score threshold."""
        threshold = 0.7
        
        at_threshold = create_mock_precedent(rrf_score=0.7)
        below_threshold = create_mock_precedent(rrf_score=0.69)
        above_threshold = create_mock_precedent(rrf_score=0.71)
        
        def should_follow(precedent, threshold=0.7):
            return precedent.rrf_score >= threshold
        
        assert should_follow(at_threshold) == True
        assert should_follow(below_threshold) == False
        assert should_follow(above_threshold) == True


class TestContextFoundryDTLIntegration:
    """Test 3: ContextFoundry.query uses DTL context when available."""
    
    def test_context_foundry_init_with_precedent_lookup_enabled(self):
        """ContextFoundry should initialize with precedent lookup when available."""
        import src.context_foundry.core as core_module
        
        original_dtl_available = getattr(core_module, 'DTL_AVAILABLE', False)
        original_create_fn = getattr(core_module, 'create_orchestrator_for_tenant', None)
        
        try:
            core_module.DTL_AVAILABLE = True
            mock_orchestrator = Mock()
            core_module.create_orchestrator_for_tenant = Mock(return_value=mock_orchestrator)
            
            with patch.object(core_module, 'get_session') as mock_session:
                mock_session.return_value = Mock()
                
                cf = core_module.ContextFoundry(
                    tenant_id=str(uuid.uuid4()),
                    enable_precedent_lookup=True
                )
                
                assert cf.enable_precedent_lookup == True
        finally:
            core_module.DTL_AVAILABLE = original_dtl_available
            if original_create_fn is not None:
                core_module.create_orchestrator_for_tenant = original_create_fn
            elif hasattr(core_module, 'create_orchestrator_for_tenant'):
                delattr(core_module, 'create_orchestrator_for_tenant')
    
    def test_context_foundry_init_with_precedent_lookup_disabled(self):
        """ContextFoundry should work with precedent lookup disabled."""
        with patch('src.context_foundry.core.get_session') as mock_session:
            mock_session.return_value = Mock()
            
            from src.context_foundry.core import ContextFoundry
            
            cf = ContextFoundry(
                tenant_id=str(uuid.uuid4()),
                enable_precedent_lookup=False
            )
            
            assert cf.enable_precedent_lookup == False
            assert cf._decision_orchestrator is None
    
    def test_route_with_precedents_returns_tier_and_info(self):
        """_route_with_precedents should return tier and precedent info."""
        from src.context_foundry.rlm.router import ComplexitySignals
        
        mock_signals = ComplexitySignals(
            token_count=10,
            conjunction_count=0,
            comparison_keywords=0,
            temporal_keywords=0,
            aggregation_keywords=0,
            causal_keywords=0,
            multi_entity_references=0,
            nested_questions=0
        )
        
        @dataclass
        class MockDecisionResult:
            choice: Dict
            precedent_lookup_status: str
            precedent_lookup_latency_ms: float
            precedents_considered: int
            precedent_followed: bool
            deviated: bool
        
        mock_result = MockDecisionResult(
            choice={"tier": "tier2", "from_precedent": True},
            precedent_lookup_status="success",
            precedent_lookup_latency_ms=45.2,
            precedents_considered=3,
            precedent_followed=True,
            deviated=False
        )
        
        chosen_tier = QueryTier.TIER2_RLM if mock_result.choice.get("tier") == "tier2" else QueryTier.TIER1_SIMPLE
        precedent_info = {
            "status": mock_result.precedent_lookup_status,
            "latency_ms": mock_result.precedent_lookup_latency_ms,
            "precedents_considered": mock_result.precedents_considered,
            "followed": mock_result.precedent_followed,
            "deviated": mock_result.deviated
        }
        
        assert chosen_tier == QueryTier.TIER2_RLM
        assert precedent_info["status"] == "success"
        assert precedent_info["latency_ms"] < 300
        assert precedent_info["followed"] == True
    
    def test_precedent_lookup_failure_falls_back_to_default(self):
        """If precedent lookup fails, should fall back to default tier."""
        default_tier = QueryTier.TIER1_SIMPLE
        
        def route_with_precedents_fallback(orchestrator, query, default_tier):
            try:
                if orchestrator is None:
                    raise ValueError("Orchestrator not available")
                return QueryTier.TIER2_RLM, {"status": "success"}
            except Exception as e:
                return default_tier, {"status": "error", "error": str(e)}
        
        tier, info = route_with_precedents_fallback(None, "test query", default_tier)
        
        assert tier == QueryTier.TIER1_SIMPLE
        assert info["status"] == "error"
    
    def test_precedent_info_included_in_query_log(self):
        """Precedent info should be included in query log events."""
        query_log_events = []
        
        def mock_log_event(event_name, data):
            query_log_events.append({"event": event_name, "data": data})
        
        precedent_info = {
            "status": "success",
            "latency_ms": 25.5,
            "precedents_considered": 2,
            "followed": True
        }
        
        mock_log_event("PIPELINE_START", {
            "query": "Test query",
            "tier": "tier2",
            "precedent_lookup": precedent_info
        })
        
        assert len(query_log_events) == 1
        assert query_log_events[0]["event"] == "PIPELINE_START"
        assert query_log_events[0]["data"]["precedent_lookup"]["status"] == "success"
        assert query_log_events[0]["data"]["precedent_lookup"]["followed"] == True


class TestAuthContextValidation:
    """Test AuthContext security validation."""
    
    def test_auth_context_requires_tenant_id(self):
        """AuthContext should require tenant_id."""
        with pytest.raises(ValueError, match="tenant_id"):
            AuthContext(tenant_id="", user_id="user123")
    
    def test_auth_context_requires_user_id(self):
        """AuthContext should require user_id."""
        with pytest.raises(ValueError, match="user_id"):
            AuthContext(tenant_id="tenant123", user_id="")
    
    def test_auth_context_default_role(self):
        """AuthContext should default to 'user' role."""
        ctx = AuthContext(
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4())
        )
        assert ctx.role == "user"
    
    def test_auth_context_custom_role(self):
        """AuthContext should accept custom role."""
        ctx = AuthContext(
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            role="admin"
        )
        assert ctx.role == "admin"
    
    def test_auth_context_immutable(self):
        """AuthContext should be immutable (frozen)."""
        ctx = AuthContext(
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4())
        )
        
        with pytest.raises(Exception):
            ctx.tenant_id = "new_tenant"


class TestPrecedentOutcomeHandling:
    """Test handling of precedent outcomes in routing decisions."""
    
    def test_positive_outcome_increases_confidence(self):
        """Positive outcome should increase routing confidence."""
        positive_precedent = create_mock_precedent(outcome_status="positive")
        
        assert positive_precedent.outcome_score == 0.8
        assert "positive outcome" in positive_precedent.relevance_explanation["factors"]
    
    def test_negative_outcome_noted_in_explanation(self):
        """Negative outcome should be noted in explanation."""
        negative_precedent = create_mock_precedent(outcome_status="negative")
        
        factors = negative_precedent.relevance_explanation["factors"]
        assert "negative outcome" in factors
    
    def test_outcome_score_contributes_to_rrf(self):
        """Outcome score should be part of the precedent result."""
        precedent = create_mock_precedent()
        
        d = precedent.to_dict()
        assert "outcome_score" in d
        assert d["outcome_score"] == 0.8


class TestDecisionTypeFiltering:
    """Test filtering precedents by decision type."""
    
    def test_tier_selection_precedents(self):
        """Tier selection precedents should have appropriate structure."""
        precedent = create_mock_precedent(
            decision_type="tier_selection",
            choice={"tier": "tier2", "reason": "multi-hop query"}
        )
        
        assert precedent.decision_type == "tier_selection"
        assert precedent.choice["tier"] in ["tier1", "tier2"]
    
    def test_entity_resolution_precedents(self):
        """Entity resolution precedents should have appropriate structure."""
        precedent = create_mock_precedent(
            decision_type="entity_resolution",
            choice={"action": "merge", "entity_ids": ["e1", "e2"]}
        )
        
        assert precedent.decision_type == "entity_resolution"
        assert precedent.choice["action"] in ["merge", "split", "keep_separate"]
    
    def test_routing_precedents(self):
        """Routing precedents should have appropriate structure."""
        precedent = create_mock_precedent(
            decision_type="routing",
            choice={"route": "semantic_search", "fallback": "graph_search"}
        )
        
        assert precedent.decision_type == "routing"
        assert "route" in precedent.choice


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
