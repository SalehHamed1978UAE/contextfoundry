"""
Integration tests for RLM routing in ContextFoundry core.

Tests the integration between:
- QueryComplexityRouter
- ContextFoundry.query()
- RLM tier routing logic
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.context_foundry.core import ContextFoundry, DEFAULT_TENANT_ID
from src.context_foundry.rlm.router import QueryComplexityRouter, QueryTier
from src.context_foundry.rlm.schemas import RLMConfig


class TestRouterIntegration:
    """Test QueryComplexityRouter integration with ContextFoundry."""
    
    def test_router_initialized_in_context_foundry(self):
        """ContextFoundry should initialize with a router."""
        with patch('src.context_foundry.core.get_session'):
            cf = ContextFoundry(enable_rlm=True)
            assert cf.router is not None
            assert isinstance(cf.router, QueryComplexityRouter)
    
    def test_rlm_enabled_flag(self):
        """ContextFoundry should track RLM enabled state."""
        with patch('src.context_foundry.core.get_session'):
            cf_enabled = ContextFoundry(enable_rlm=True)
            assert cf_enabled.enable_rlm == True
            
            cf_disabled = ContextFoundry(enable_rlm=False)
            assert cf_disabled.enable_rlm == False
    
    def test_tenant_id_default(self):
        """ContextFoundry should use default tenant_id."""
        with patch('src.context_foundry.core.get_session'):
            cf = ContextFoundry()
            assert cf.tenant_id == DEFAULT_TENANT_ID
    
    def test_tenant_id_custom(self):
        """ContextFoundry should accept custom tenant_id."""
        with patch('src.context_foundry.core.get_session'):
            custom_tenant = "12345678-1234-1234-1234-123456789012"
            cf = ContextFoundry(tenant_id=custom_tenant)
            assert cf.tenant_id == custom_tenant
    
    def test_rlm_config_passed_through(self):
        """ContextFoundry should store custom RLM config."""
        with patch('src.context_foundry.core.get_session'):
            config = RLMConfig(max_iterations=5)
            cf = ContextFoundry(rlm_config=config)
            assert cf.rlm_config == config
            assert cf.rlm_config.max_iterations == 5


class TestTierRouting:
    """Test query tier routing logic."""
    
    def test_simple_query_routes_to_tier1(self):
        """Simple queries should route to Tier 1."""
        router = QueryComplexityRouter()
        
        simple_queries = [
            "What is the status of API Gateway?",
            "Who owns the Payment Service?",
            "When was this document uploaded?",
        ]
        
        for query in simple_queries:
            tier, signals = router.route(query)
            assert tier == QueryTier.TIER1_SIMPLE, f"Query '{query}' should route to tier1"
    
    def test_complex_query_routes_to_tier2(self):
        """Complex queries should route to Tier 2."""
        router = QueryComplexityRouter()
        
        complex_queries = [
            "Compare the dependencies of Service A and Service B",
            "What is the root cause of the failures and how do the affected services relate to each other?",
            "How many services depend on the message queue and what are their upstream and downstream connections?",
        ]
        
        for query in complex_queries:
            tier, signals = router.route(query)
            assert tier == QueryTier.TIER2_RLM, f"Query '{query}' should route to tier2, score={signals.complexity_score}"
    
    def test_force_tier_override(self):
        """force_tier parameter should override router decision."""
        with patch('src.context_foundry.core.get_session'):
            cf = ContextFoundry(enable_rlm=True)
            
            with patch.object(cf.retrieval, 'build_context_bundle') as mock_retrieval, \
                 patch.object(cf.reasoning, 'reason') as mock_reason, \
                 patch.object(cf.validation, 'validate_response') as mock_validate:
                
                mock_bundle = Mock()
                mock_bundle.target_entity_name = None
                mock_bundle.to_dict.return_value = {}
                mock_bundle.semantic_entities = []
                mock_bundle.semantic_relationships = []
                mock_bundle.episodic_documents = []
                mock_bundle.query_text = "test"
                mock_bundle.query_id = "123"
                
                mock_retrieval.return_value = mock_bundle
                mock_reason.return_value = {"answer": "test", "confidence": 0.8}
                mock_validate.return_value = {"answer": "test", "confidence": 0.8}
                
                result = cf.query("Compare all services", force_tier="tier1", save_to_log=False)
                
                mock_retrieval.assert_called_once()


class TestQueryTierLogging:
    """Test that tier information is logged correctly."""
    
    def test_tier_logged_in_query_events(self):
        """Query logger should receive tier information."""
        with patch('src.context_foundry.core.get_session'):
            cf = ContextFoundry(enable_rlm=True)
            
            with patch.object(cf.retrieval, 'build_context_bundle') as mock_retrieval, \
                 patch.object(cf.reasoning, 'reason') as mock_reason, \
                 patch.object(cf.validation, 'validate_response') as mock_validate:
                
                mock_bundle = Mock()
                mock_bundle.target_entity_name = None
                mock_bundle.to_dict.return_value = {}
                mock_bundle.semantic_entities = []
                mock_bundle.semantic_relationships = []
                mock_bundle.episodic_documents = []
                mock_bundle.query_text = "test"
                mock_bundle.query_id = "123"
                
                mock_retrieval.return_value = mock_bundle
                mock_reason.return_value = {"answer": "test", "confidence": 0.8}
                mock_validate.return_value = {"answer": "test", "confidence": 0.8}
                
                result = cf.query("What is service X?", save_to_log=False, display_output=False)
                
                assert "query_log" in result


class TestForceTierErrors:
    """Test force_tier error handling."""
    
    def test_force_tier2_with_rlm_disabled_returns_error(self):
        """force_tier='tier2' should return error response when RLM is disabled."""
        with patch('src.context_foundry.core.get_session'):
            cf = ContextFoundry(enable_rlm=False)
            
            result = cf.query("test query", force_tier="tier2", save_to_log=False)
            
            assert result.get("error") == True
            assert "Cannot force tier2 when RLM is disabled" in result.get("error_message", "")


class TestRLMDisabled:
    """Test behavior when RLM is disabled."""
    
    def test_complex_query_uses_tier1_when_rlm_disabled(self):
        """Complex queries should use Tier 1 when RLM is disabled."""
        with patch('src.context_foundry.core.get_session'):
            cf = ContextFoundry(enable_rlm=False)
            
            with patch.object(cf.retrieval, 'build_context_bundle') as mock_retrieval, \
                 patch.object(cf.reasoning, 'reason') as mock_reason, \
                 patch.object(cf.validation, 'validate_response') as mock_validate:
                
                mock_bundle = Mock()
                mock_bundle.target_entity_name = None
                mock_bundle.to_dict.return_value = {}
                mock_bundle.semantic_entities = []
                mock_bundle.semantic_relationships = []
                mock_bundle.episodic_documents = []
                mock_bundle.query_text = "test"
                mock_bundle.query_id = "123"
                
                mock_retrieval.return_value = mock_bundle
                mock_reason.return_value = {"answer": "test", "confidence": 0.8}
                mock_validate.return_value = {"answer": "test", "confidence": 0.8}
                
                result = cf.query("Compare all services and their dependencies", save_to_log=False)
                
                mock_retrieval.assert_called_once()
                mock_reason.assert_called_once()


class TestComplexityScoring:
    """Test complexity score calculation."""
    
    def test_threshold_boundary(self):
        """Test queries at the threshold boundary."""
        router = QueryComplexityRouter(complexity_threshold=0.19)
        
        tier_below, signals_below = router.route("What is X?")
        assert tier_below == QueryTier.TIER1_SIMPLE
        assert signals_below.complexity_score < 0.19
        
        tier_above, signals_above = router.route("Compare X and Y with their dependencies")
        assert tier_above == QueryTier.TIER2_RLM
        assert signals_above.complexity_score >= 0.19
    
    def test_custom_threshold(self):
        """Custom threshold should affect routing."""
        router_low = QueryComplexityRouter(complexity_threshold=0.05)
        router_high = QueryComplexityRouter(complexity_threshold=0.50)
        
        query = "What is the impact of service failure?"
        
        tier_low, _ = router_low.route(query)
        tier_high, _ = router_high.route(query)
        
        assert tier_low == QueryTier.TIER2_RLM
        assert tier_high == QueryTier.TIER1_SIMPLE
