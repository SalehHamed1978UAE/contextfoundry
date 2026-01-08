"""
Pytest configuration for Context Foundry regression tests.

This module provides shared pytest fixtures for:
- Contract testing (QueryParser, EntityResolver, Memory systems)
- Integration testing (RetrievalAgent, ReasoningAgent)
- Knowledge graph fixtures for consistent test data

Pytest markers:
- smoke: Inline-only tests, safe for CI (no API keys/HTTP server required)
"""

import pytest
import sys
import os


def pytest_configure(config):
    """Register custom pytest markers for regression testing."""
    config.addinivalue_line(
        "markers",
        "smoke: mark test as inline-only smoke test (no external dependencies)"
    )
    config.addinivalue_line(
        "markers",
        "fast_regression: mark test as fast regression test (mocked LLM, <3 min)"
    )
    config.addinivalue_line(
        "markers",
        "component: mark test as component integration test (<5 min)"
    )
    config.addinivalue_line(
        "markers",
        "integration: mark test as full E2E integration test (nightly only)"
    )

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_foundry.agents.retrieval import RetrievalAgent
from src.context_foundry.agents.reasoning import ReasoningAgent
from src.context_foundry.contracts.query_parser import (
    QueryParserContract,
    PatternBasedQueryParser,
    QueryIntent,
    QueryType,
)
from src.context_foundry.contracts.entity_resolver import (
    EntityResolverContract,
    EntityCandidate,
    ResolveResult,
    MatchStage,
)
from src.context_foundry.contracts.memory import (
    SemanticMemoryContract,
    SymbolicMemoryAPIContract,
    EntityRecord,
    RelationshipRecord,
    LifecycleState,
    verify_relationship_parity,
)
from tests.fixtures.knowledge_graph import (
    CANONICAL_ENTITIES,
    CANONICAL_RELATIONSHIPS,
    STAGING_ENTITY,
    STAGING_RELATIONSHIP,
    TEST_TENANT_ID,
    get_entity_by_id,
    get_entity_by_name,
    get_relationships_for_entity,
    get_impact_chain,
    expected_auth_database_impact,
    expected_payment_service_impact,
    expected_redis_cache_impact,
    QUERY_TEST_CASES,
)


@pytest.fixture(scope="session")
def retrieval_agent():
    """Create a single RetrievalAgent for all tests."""
    return RetrievalAgent()


@pytest.fixture(scope="session")
def reasoning_agent():
    """Create a single ReasoningAgent for all tests."""
    return ReasoningAgent()


@pytest.fixture(scope="session")
def run_query(retrieval_agent, reasoning_agent):
    """Factory fixture for running queries."""
    def _run(query: str):
        bundle = retrieval_agent.build_context_bundle(query)
        result = reasoning_agent.reason(bundle)
        result['_bundle'] = bundle
        return result
    return _run


@pytest.fixture(scope="function")
def query_parser() -> QueryParserContract:
    """Create a fresh QueryParser for each test."""
    return PatternBasedQueryParser()


@pytest.fixture(scope="session")
def test_tenant_id() -> str:
    """Return the canonical test tenant ID."""
    return TEST_TENANT_ID


@pytest.fixture(scope="session")
def canonical_entities():
    """Return list of canonical test entities."""
    return CANONICAL_ENTITIES


@pytest.fixture(scope="session")
def canonical_relationships():
    """Return list of canonical test relationships."""
    return CANONICAL_RELATIONSHIPS


@pytest.fixture(scope="session")
def staging_entity():
    """Return a staging (not yet trusted) entity for testing lifecycle filtering."""
    return STAGING_ENTITY


@pytest.fixture(scope="session")
def staging_relationship():
    """Return a staging relationship for testing lifecycle filtering."""
    return STAGING_RELATIONSHIP


@pytest.fixture(scope="session")
def query_test_cases():
    """Return list of query test cases with expected results."""
    return QUERY_TEST_CASES


@pytest.fixture(scope="function")
def entity_lookup():
    """Factory fixture for looking up entities by ID or name."""
    def _lookup(identifier: str):
        entity = get_entity_by_id(identifier)
        if entity:
            return entity
        return get_entity_by_name(identifier)
    return _lookup


@pytest.fixture(scope="function")
def relationship_lookup():
    """Factory fixture for getting relationships for an entity."""
    def _lookup(entity_id: str, direction: str = "both", include_staging: bool = False):
        return get_relationships_for_entity(entity_id, direction, include_staging)
    return _lookup


@pytest.fixture(scope="function")
def impact_chain_lookup():
    """Factory fixture for computing impact chains."""
    def _lookup(entity_name: str, max_depth: int = 3):
        return get_impact_chain(entity_name, max_depth)
    return _lookup


@pytest.fixture(scope="session")
def expected_impacts():
    """Return dict of expected impact chains for key entities."""
    return {
        "Auth Database": expected_auth_database_impact(),
        "Payment Service": expected_payment_service_impact(),
        "Redis Cache": expected_redis_cache_impact(),
    }


@pytest.fixture(scope="function")
def parity_verifier():
    """Factory fixture for verifying memory parity."""
    def _verify(semantic_results, symbolic_results, entity_id):
        return verify_relationship_parity(semantic_results, symbolic_results, entity_id)
    return _verify
