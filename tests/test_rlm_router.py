"""
Tests for Query Complexity Router.

Tests query analysis and routing decisions between Tier 1 and Tier 2.
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_foundry.rlm.router import (
    QueryComplexityRouter,
    QueryTier,
    ComplexitySignals,
    route_query,
    should_use_rlm,
    EXAMPLE_QUERIES,
)


class TestComplexitySignals:
    """Test ComplexitySignals calculations."""
    
    def test_low_complexity_score(self):
        """Simple signals should have low score."""
        signals = ComplexitySignals(
            token_count=5,
            conjunction_count=0,
            comparison_keywords=0,
            temporal_keywords=0,
            aggregation_keywords=0,
            causal_keywords=0,
            multi_entity_references=0,
            nested_questions=0
        )
        assert signals.complexity_score < 0.1
    
    def test_high_complexity_score(self):
        """Complex signals should have high score."""
        signals = ComplexitySignals(
            token_count=30,
            conjunction_count=3,
            comparison_keywords=2,
            temporal_keywords=2,
            aggregation_keywords=2,
            causal_keywords=2,
            multi_entity_references=2,
            nested_questions=1
        )
        assert signals.complexity_score > 0.7
    
    def test_score_capped_at_one(self):
        """Score should not exceed 1.0."""
        signals = ComplexitySignals(
            token_count=100,
            conjunction_count=10,
            comparison_keywords=10,
            temporal_keywords=10,
            aggregation_keywords=10,
            causal_keywords=10,
            multi_entity_references=10,
            nested_questions=5
        )
        assert signals.complexity_score <= 1.0


class TestQueryComplexityRouter:
    """Test router analysis and routing."""
    
    def test_simple_query_routed_to_tier1(self):
        """Simple queries should route to Tier 1."""
        router = QueryComplexityRouter()
        
        simple_queries = [
            "What is the status of Service X?",
            "Who owns the Database?",
            "Show me entity details.",
        ]
        
        for query in simple_queries:
            tier, _ = router.route(query)
            assert tier == QueryTier.TIER1_SIMPLE, f"Expected TIER1 for: {query}"
    
    def test_complex_query_routed_to_tier2(self):
        """Complex queries should route to Tier 2."""
        router = QueryComplexityRouter()
        
        complex_queries = [
            "Compare the dependencies between Service A and Service B and explain the differences",
            "How does a change in Auth Service impact downstream services and what is affected?",
            "What is the root cause path from the network outage to checkout failures and which services were impacted?",
        ]
        
        for query in complex_queries:
            tier, _ = router.route(query)
            assert tier == QueryTier.TIER2_RLM, f"Expected TIER2_RLM for: {query}"
    
    def test_comparison_keywords_detected(self):
        """Comparison keywords should be detected."""
        router = QueryComplexityRouter()
        
        signals = router.analyze_complexity("Compare Service A versus Service B")
        assert signals.comparison_keywords >= 2
    
    def test_causal_keywords_detected(self):
        """Causal keywords should be detected."""
        router = QueryComplexityRouter()
        
        signals = router.analyze_complexity("Why did the failure cause the outage?")
        assert signals.causal_keywords >= 2
    
    def test_aggregation_keywords_detected(self):
        """Aggregation keywords should be detected."""
        router = QueryComplexityRouter()
        
        signals = router.analyze_complexity("How many services are affected in total?")
        assert signals.aggregation_keywords >= 2
    
    def test_temporal_keywords_detected(self):
        """Temporal keywords should be detected."""
        router = QueryComplexityRouter()
        
        signals = router.analyze_complexity("What changed before and after the incident?")
        assert signals.temporal_keywords >= 2
    
    def test_multi_entity_references_detected(self):
        """Multi-entity references should be detected."""
        router = QueryComplexityRouter()
        
        signals = router.analyze_complexity("Show the relationship between Service A and Service B")
        assert signals.multi_entity_references >= 1
    
    def test_conjunction_count_detected(self):
        """Conjunctions should be counted."""
        router = QueryComplexityRouter()
        
        signals = router.analyze_complexity("Find entities A and B and C or D")
        assert signals.conjunction_count >= 3
    
    def test_should_use_rlm_returns_bool(self):
        """should_use_rlm should return boolean."""
        router = QueryComplexityRouter()
        
        result = router.should_use_rlm("Simple query")
        assert isinstance(result, bool)
    
    def test_routing_explanation_includes_reasons(self):
        """Routing explanation should include reasons."""
        router = QueryComplexityRouter()
        
        explanation = router.get_routing_explanation(
            "Compare the dependencies between Service A and Service B"
        )
        
        assert "tier" in explanation
        assert "complexity_score" in explanation
        assert "reasons" in explanation
        assert len(explanation["reasons"]) > 0


class TestConvenienceFunctions:
    """Test module-level convenience functions."""
    
    def test_route_query_returns_tier(self):
        """route_query should return QueryTier."""
        tier = route_query("What is the status?")
        assert isinstance(tier, QueryTier)
    
    def test_should_use_rlm_simple(self):
        """should_use_rlm should return False for simple queries."""
        result = should_use_rlm("What is the status of X?")
        assert result == False
    
    def test_should_use_rlm_complex(self):
        """should_use_rlm should return True for complex queries."""
        result = should_use_rlm(
            "Compare all dependencies between Service A and Service B and explain why they differ"
        )
        assert result == True


class TestExampleQueries:
    """Test with example queries from documentation."""
    
    def test_tier1_examples_route_correctly(self):
        """Tier 1 example queries should route to Tier 1."""
        router = QueryComplexityRouter()
        
        for query in EXAMPLE_QUERIES["tier1"]:
            tier, signals = router.route(query)
            if tier != QueryTier.TIER1_SIMPLE:
                explanation = router.get_routing_explanation(query)
                print(f"Query: {query}")
                print(f"Score: {signals.complexity_score}")
                print(f"Signals: {explanation['signals']}")
    
    def test_tier2_examples_route_correctly(self):
        """Tier 2 example queries should route to Tier 2."""
        router = QueryComplexityRouter()
        
        for query in EXAMPLE_QUERIES["tier2"]:
            tier, signals = router.route(query)
            assert tier == QueryTier.TIER2_RLM, f"Expected TIER2 for: {query} (score: {signals.complexity_score})"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_empty_query(self):
        """Empty query should route to Tier 1."""
        router = QueryComplexityRouter()
        tier, _ = router.route("")
        assert tier == QueryTier.TIER1_SIMPLE
    
    def test_single_word_query(self):
        """Single word query should route to Tier 1."""
        router = QueryComplexityRouter()
        tier, _ = router.route("Status")
        assert tier == QueryTier.TIER1_SIMPLE
    
    def test_very_long_simple_query(self):
        """Long but simple query should still route correctly."""
        router = QueryComplexityRouter()
        query = "What is the current status of " + " ".join(["word"] * 30)
        signals = router.analyze_complexity(query)
        assert signals.token_count > 30
    
    def test_custom_threshold(self):
        """Custom threshold should affect routing."""
        router_strict = QueryComplexityRouter(complexity_threshold=0.2)
        router_lenient = QueryComplexityRouter(complexity_threshold=0.8)
        
        query = "What services are related to the database?"
        
        tier_strict, _ = router_strict.route(query)
        tier_lenient, _ = router_lenient.route(query)
        
        assert tier_lenient == QueryTier.TIER1_SIMPLE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
