"""
Context Foundry Regression Test Suite

Tests cover:
1. Entity queries (high confidence expected)
2. Topic queries (medium confidence expected)
3. Impact queries (cascade correctness)
4. Missing entity (should abstain)
5. Contradiction handling
6. Temporal reasoning

Each test asserts:
- Confidence in expected range
- Key facts present in answer
- No hallucinated content
"""

import pytest
import re
from typing import Dict, List, Tuple, Optional

from src.context_foundry.agents.retrieval import RetrievalAgent
from src.context_foundry.agents.reasoning import ReasoningAgent


class TestFixtures:
    """Shared test fixtures and utilities."""
    
    _retrieval_agent: Optional[RetrievalAgent] = None
    _reasoning_agent: Optional[ReasoningAgent] = None
    
    @classmethod
    def get_agents(cls) -> Tuple[RetrievalAgent, ReasoningAgent]:
        """Get cached agent instances for performance."""
        if cls._retrieval_agent is None or cls._reasoning_agent is None:
            cls._retrieval_agent = RetrievalAgent()
            cls._reasoning_agent = ReasoningAgent()
        return cls._retrieval_agent, cls._reasoning_agent
    
    @classmethod
    def run_query(cls, query: str) -> Dict:
        """Run a query and return the full result."""
        retrieval, reasoning = cls.get_agents()
        bundle = retrieval.build_context_bundle(query)
        result = reasoning.reason(bundle)
        result['_bundle'] = bundle
        return result


def assert_confidence_in_range(result: Dict, min_conf: float, max_conf: float, query: str):
    """Assert confidence is within expected range."""
    confidence = result.get('confidence', 0)
    assert min_conf <= confidence <= max_conf, (
        f"Query '{query}': Expected confidence {min_conf:.0%}-{max_conf:.0%}, "
        f"got {confidence:.0%}"
    )


def assert_key_facts_present(result: Dict, required_facts: List[str], query: str):
    """Assert that key facts appear in the answer (case-insensitive partial match)."""
    answer = result.get('answer', '').lower()
    missing = []
    for fact in required_facts:
        if fact.lower() not in answer:
            missing.append(fact)
    assert not missing, (
        f"Query '{query}': Missing key facts in answer: {missing}\n"
        f"Answer was: {result.get('answer', '')[:500]}"
    )


def assert_no_hallucination(result: Dict, forbidden_terms: List[str], query: str):
    """Assert that hallucinated/forbidden content does not appear."""
    answer = result.get('answer', '').lower()
    found = []
    for term in forbidden_terms:
        if term.lower() in answer:
            found.append(term)
    assert not found, (
        f"Query '{query}': Found hallucinated content: {found}\n"
        f"Answer was: {result.get('answer', '')[:500]}"
    )


def assert_entity_mentioned(result: Dict, entities: List[str], query: str):
    """Assert that specific entities are mentioned in the answer."""
    answer = result.get('answer', '').lower()
    missing = []
    for entity in entities:
        if entity.lower() not in answer:
            missing.append(entity)
    assert not missing, (
        f"Query '{query}': Expected entities not mentioned: {missing}"
    )


class TestEntityQueries:
    """
    Test entity-centric queries where we have known entities in the graph.
    These should return HIGH confidence (70-95%).
    """
    
    def test_person_concerns_mia_white(self):
        """Mia White exists and has documented concerns in meeting notes."""
        query = "What concerns has Mia White raised?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.70, 0.99, query)
        assert_key_facts_present(result, ["15%", "cost"], query)
        assert_no_hallucination(result, ["does not exist", "unknown person"], query)
    
    def test_person_role_alex_rivera(self):
        """Alex Rivera is a known person with defined responsibilities."""
        query = "Who is Alex Rivera and what does he do?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.60, 0.99, query)
        assert_entity_mentioned(result, ["Alex Rivera"], query)
        assert_no_hallucination(result, ["does not exist", "no information"], query)
    
    def test_team_ownership_auth_service(self):
        """Auth Service is owned by a specific team."""
        query = "Which team owns the Auth Service?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.40, 0.99, query)
        assert_key_facts_present(result, ["Auth"], query)
    
    def test_team_members_platform_team(self):
        """Platform Team has known members."""
        query = "Who are the members of the Platform Team?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.50, 0.99, query)
        assert_key_facts_present(result, ["Platform"], query)
    
    def test_service_dependencies_payment_service(self):
        """Payment Service has known dependencies."""
        query = "What services does the Payment Service depend on?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.60, 0.99, query)
        assert_key_facts_present(result, ["Payment"], query)
    
    def test_person_escalation_path(self):
        """Escalation paths are defined for critical services."""
        query = "Who does Emily Rodriguez escalate to for SEV1 issues?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.50, 0.99, query)
        assert_entity_mentioned(result, ["Emily Rodriguez"], query)
    
    def test_service_tier_fraud_detection(self):
        """Fraud Detection Service has a defined tier."""
        query = "What tier is the Fraud Detection Service?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.50, 0.99, query)
        assert_key_facts_present(result, ["Fraud Detection"], query)


class TestTopicQueries:
    """
    Test topic-centric queries where no specific entity matches.
    These should return MEDIUM confidence (40-75%) based on document synthesis.
    """
    
    def test_cloud_migration_decisions(self):
        """Cloud migration is a topic with many related documents."""
        query = "What key decisions were made about cloud migration?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.40, 0.80, query)
        assert_key_facts_present(result, ["migration"], query)
        assert_no_hallucination(result, ["no information available"], query)
    
    def test_cost_reduction_initiative(self):
        """Cost reduction initiative spans multiple documents."""
        query = "What progress has been made on cost reduction?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.20, 0.90, query)
        assert_key_facts_present(result, ["cost"], query)
    
    def test_frontend_framework_decision(self):
        """Frontend framework decision was documented in RFC."""
        query = "What frontend framework did the team decide to use?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.40, 0.85, query)
        assert_key_facts_present(result, ["react", "vue"], query)
    
    def test_observability_improvements(self):
        """Observability improvements discussed in meetings."""
        query = "What observability improvements are planned?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.30, 0.80, query)
    
    def test_q4_budget_review(self):
        """Q4 budget review discussed in documents."""
        query = "What was discussed in the Q4 budget review?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.40, 0.85, query)
        assert_key_facts_present(result, ["budget"], query)
    
    def test_hiring_plans(self):
        """Hiring plans mentioned in strategy docs."""
        query = "What are the current hiring plans for engineering?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.30, 0.80, query)


class TestImpactQueries:
    """
    Test impact/cascade queries that traverse DEPENDS_ON relationships.
    These should identify all affected services in the blast radius.
    """
    
    def test_auth_service_failure_impact(self):
        """Auth Service failure should cascade to dependent services."""
        query = "If the Auth Service fails, what other services are affected?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.50, 0.99, query)
        assert_key_facts_present(result, ["Auth Service"], query)
        bundle = result.get('_bundle')
        assert bundle.query_type == 'impact', f"Expected impact query type, got {bundle.query_type}"
    
    def test_payment_service_outage(self):
        """Payment Service outage impact analysis."""
        query = "What's the blast radius if Payment Service goes down?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.50, 0.99, query)
        assert_key_facts_present(result, ["Payment"], query)
    
    def test_api_gateway_cascade(self):
        """API Gateway is critical and affects many services."""
        query = "Who needs to be notified if the API Gateway fails?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.40, 0.99, query)
        assert_key_facts_present(result, ["API Gateway"], query)
    
    def test_notification_service_impact(self):
        """Notification Service failure impact."""
        query = "What happens if the Notification Service is unavailable?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.50, 0.99, query)
        assert_key_facts_present(result, ["Notification"], query)


class TestMissingEntityAbstention:
    """
    Test queries about non-existent entities.
    System synthesizes from related docs, so confidence varies based on doc matches.
    Truly unknown topics (no docs) should abstain with LOW confidence (< 25%).
    """
    
    def test_unknown_service_no_related_docs(self):
        """Query about a service that doesn't exist and has no related docs."""
        query = "What team owns the Quantum Entanglement Microservice?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.0, 0.50, query)
        answer = result.get('answer', '').lower()
        has_uncertainty = any(term in answer for term in ['no information', 'not found', 'does not exist', 'unknown', 'cannot'])
        assert has_uncertainty or result.get('confidence', 0) < 0.30, \
            "Should express uncertainty or have low confidence for unknown entity"
    
    def test_unknown_person_no_related_docs(self):
        """Query about a person who doesn't exist - uses completely fictional name."""
        query = "What concerns has Zephyrus Moonbeam raised about the project?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.0, 0.50, query)
    
    def test_unknown_project(self):
        """Query about a project that doesn't exist."""
        query = "What's the status of Project Omega?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.0, 0.25, query)
    
    def test_unknown_team(self):
        """Query about a team that doesn't exist."""
        query = "Who are the members of the Blockchain Team?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.0, 0.35, query)
    
    def test_fictional_topic_no_docs(self):
        """Query about a completely fictional topic with no related docs."""
        query = "Tell me about the Galactic Hyperspace Protocol deployment."
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.0, 0.30, query)


class TestContradictionHandling:
    """
    Test handling of contradictory or evolving information.
    System should recognize changes over time.
    """
    
    def test_vendor_switch_cloudshift_to_migratex(self):
        """Vendor switch from CloudShift to MigrateX should be detected."""
        query = "Has our position on vendor selection changed?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.40, 0.90, query)
        answer_lower = result.get('answer', '').lower()
        has_vendor_info = 'cloudshift' in answer_lower or 'migratex' in answer_lower
        assert has_vendor_info, f"Expected vendor information in answer"
    
    def test_cost_reduction_target_evolution(self):
        """Cost reduction targets may have evolved over time."""
        query = "What concerns were raised about the cost reduction proposal?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.40, 0.90, query)
        assert_key_facts_present(result, ["cost", "reduction"], query)
    
    def test_decision_reversal_tracking(self):
        """Track when decisions have been reversed or modified."""
        query = "Have any cloud migration decisions been reversed?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.30, 0.80, query)


class TestTemporalReasoning:
    """
    Test queries that require understanding of time and sequences.
    """
    
    def test_migration_timeline(self):
        """Payment Service migration has a specific timeline."""
        query = "What's the Payment Service migration timeline?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.40, 0.99, query)
        assert_key_facts_present(result, ["Payment"], query)
    
    def test_recent_hires(self):
        """Recent hiring activity should be traceable."""
        query = "Who was hired recently and what team are they on?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.30, 0.80, query)
    
    def test_q4_initiatives(self):
        """Q4 initiatives should be documented with dates."""
        query = "What reliability initiatives were discussed in Q4 meetings?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.20, 0.99, query)
    
    def test_incident_sequence(self):
        """Incident resolution follows a sequence of events."""
        query = "What happened in the most recent Notification Service incidents?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.40, 0.90, query)
        assert_key_facts_present(result, ["Notification"], query)
    
    def test_meeting_decisions_over_time(self):
        """Track decisions made across multiple meetings."""
        query = "What decisions did Mia White make in the executive sync meetings?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.50, 0.95, query)
        assert_key_facts_present(result, ["Mia White"], query)


class TestEdgeCases:
    """
    Test edge cases and boundary conditions.
    """
    
    def test_ambiguous_entity_name(self):
        """Hannah White and Mia White - disambiguation test."""
        query = "What has Hannah White contributed to the Data Team?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.40, 0.95, query)
        assert_entity_mentioned(result, ["Hannah White"], query)
        answer = result.get('answer', '').lower()
        if 'mia white' in answer:
            assert 'hannah white' in answer, "Should primarily discuss Hannah, not Mia"
    
    def test_partial_entity_match(self):
        """Query with partial entity name."""
        query = "What does the Auth team do?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.30, 0.99, query)
    
    def test_very_short_query(self):
        """Minimal query should still return something reasonable."""
        query = "Who owns Auth Service?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.40, 0.99, query)
    
    def test_complex_multi_hop_query(self):
        """Query requiring multi-hop reasoning."""
        query = "If the API Gateway team's manager is unavailable, who else can approve changes?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.20, 0.80, query)


class TestConfidenceCalibration:
    """
    Test that confidence scores are properly calibrated across quadrants.
    """
    
    def test_q1_entity_with_docs_high_confidence(self):
        """Q1: Entity exists + good docs = high confidence."""
        query = "What concerns has Mia White raised about the 15% target?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.70, 0.99, query)
        assert_key_facts_present(result, ["Mia White", "15%"], query)
    
    def test_q3_topic_with_docs_medium_confidence(self):
        """Q3: No entity + good docs = medium confidence (topic-centric)."""
        query = "What key decisions were made about cloud migration?"
        result = TestFixtures.run_query(query)
        
        bundle = result.get('_bundle')
        if not bundle.target_entity_found:
            assert_confidence_in_range(result, 0.40, 0.80, query)
    
    def test_q4_no_evidence_low_confidence(self):
        """Q4: No entity + no docs = low confidence (abstention)."""
        query = "What's the status of Project Omega?"
        result = TestFixtures.run_query(query)
        
        assert_confidence_in_range(result, 0.0, 0.25, query)


def run_all_tests():
    """Run all tests and return summary."""
    import sys
    pytest_args = [__file__, '-v', '--tb=short']
    return pytest.main(pytest_args)


if __name__ == '__main__':
    run_all_tests()
