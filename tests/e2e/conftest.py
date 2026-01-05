"""
E2E Test Configuration - Pytest fixtures for end-to-end testing.

Week 4 Stabilization: Provides seeded test data fixtures for E2E tests
so they can exercise the full pipeline instead of skipping.
"""

import pytest
from uuid import UUID
from sqlalchemy.orm import Session

from src.context_foundry.models.schema import get_session

from tests.fixtures.knowledge_graph import (
    TEST_TENANT_ID,
    CANONICAL_ENTITIES,
    CANONICAL_RELATIONSHIPS,
    API_GATEWAY_ID,
    PAYMENT_SERVICE_ID,
    ORDER_SERVICE_ID,
    AUTH_DATABASE_ID,
    REDIS_CACHE_ID,
    SRE_TEAM_ID,
)
from tests.fixtures.seed_test_data import (
    seed_canonical_test_data,
    cleanup_test_data,
    check_canonical_entities_exist,
)


@pytest.fixture(scope="session")
def test_tenant_id():
    """The canonical test tenant ID used across all E2E tests."""
    return TEST_TENANT_ID


@pytest.fixture(scope="function")
def db_session():
    """Database session for tests."""
    session = get_session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def seeded_test_data(db_session, test_tenant_id):
    """
    Seed canonical IT service architecture for E2E tests.
    
    This fixture seeds:
    - 6 entities: API Gateway, Payment Service, Order Service, Auth Database, Redis Cache, SRE Team
    - 6 relationships: dependency and ownership relationships
    
    Tests using this fixture will have deterministic data to work with.
    If RLS prevents seeding, returns None and tests should skip.
    """
    data = seed_canonical_test_data(
        session=db_session,
        tenant_id=test_tenant_id,
        include_staging=True
    )
    
    if data is None:
        pytest.skip("RLS prevents test data seeding - need valid tenant context")
    
    yield data
    
    cleanup_test_data(db_session, data)


@pytest.fixture(scope="function")
def canonical_entities(seeded_test_data):
    """Get seeded entities keyed by fixture ID."""
    if seeded_test_data is None:
        pytest.skip("No seeded data available")
    return seeded_test_data.get("entities", {})


@pytest.fixture(scope="function")
def canonical_relationships(seeded_test_data):
    """Get seeded relationships keyed by fixture ID."""
    if seeded_test_data is None:
        pytest.skip("No seeded data available")
    return seeded_test_data.get("relationships", {})


@pytest.fixture(scope="function")
def api_gateway(canonical_entities):
    """Get the API Gateway entity."""
    return canonical_entities.get(API_GATEWAY_ID)


@pytest.fixture(scope="function")
def payment_service(canonical_entities):
    """Get the Payment Service entity."""
    return canonical_entities.get(PAYMENT_SERVICE_ID)


@pytest.fixture(scope="function")
def order_service(canonical_entities):
    """Get the Order Service entity."""
    return canonical_entities.get(ORDER_SERVICE_ID)


@pytest.fixture(scope="function")
def auth_database(canonical_entities):
    """Get the Auth Database entity."""
    return canonical_entities.get(AUTH_DATABASE_ID)


@pytest.fixture(scope="function")
def redis_cache(canonical_entities):
    """Get the Redis Cache entity."""
    return canonical_entities.get(REDIS_CACHE_ID)


@pytest.fixture(scope="function")
def sre_team(canonical_entities):
    """Get the SRE Team entity."""
    return canonical_entities.get(SRE_TEAM_ID)
