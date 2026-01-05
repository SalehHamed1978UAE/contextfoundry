"""
RLM Parity Integration Tests.

Week 4 Stabilization: Tests that verify SymbolicMemoryAPI and SemanticMemory
return consistent results when querying the same data.

These tests exercise the actual database and verify the tenant_id type fix.
"""

import pytest
from uuid import UUID, uuid4
from sqlalchemy.orm import Session

from src.context_foundry.models.schema import (
    Entity, Relationship, LifecycleState, get_session
)
from src.context_foundry.memory.semantic import SemanticMemory
from src.context_foundry.rlm.memory_apis.symbolic import SymbolicMemoryAPI
from src.context_foundry.contracts.memory import verify_relationship_parity


@pytest.fixture
def test_tenant_id():
    """Generate a unique tenant ID for test isolation."""
    return str(uuid4())


@pytest.fixture
def db_session():
    """Get a database session."""
    session = get_session()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def seeded_test_data(db_session, test_tenant_id):
    """
    Seed test data for parity tests.
    
    NOTE: If RLS is enforced and we can't insert with a random tenant_id,
    this fixture will return None and tests should skip.
    """
    try:
        tenant_uuid = UUID(test_tenant_id)
        
        api_gateway = Entity(
            name="Test API Gateway",
            entity_type="SERVICE",
            tenant_id=tenant_uuid,
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.9
        )
        db_session.add(api_gateway)
        
        payment_service = Entity(
            name="Test Payment Service",
            entity_type="SERVICE",
            tenant_id=tenant_uuid,
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.9
        )
        db_session.add(payment_service)
        
        auth_db = Entity(
            name="Test Auth Database",
            entity_type="DATABASE",
            tenant_id=tenant_uuid,
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.9
        )
        db_session.add(auth_db)
        
        db_session.flush()
        
        rel1 = Relationship(
            source_id=api_gateway.id,
            target_id=payment_service.id,
            relationship_type="DEPENDS_ON",
            tenant_id=tenant_uuid,
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.85
        )
        db_session.add(rel1)
        
        rel2 = Relationship(
            source_id=payment_service.id,
            target_id=auth_db.id,
            relationship_type="DEPENDS_ON",
            tenant_id=tenant_uuid,
            lifecycle_state=LifecycleState.TRUSTED,
            confidence=0.85
        )
        db_session.add(rel2)
        
        db_session.flush()
        
        return {
            "tenant_id": test_tenant_id,
            "api_gateway": api_gateway,
            "payment_service": payment_service,
            "auth_db": auth_db,
            "relationships": [rel1, rel2]
        }
    except Exception as e:
        db_session.rollback()
        if "row-level security" in str(e).lower() or "insufficientprivilege" in str(e).lower():
            pytest.skip("RLS prevents test data seeding - need valid tenant context")
        raise


class TestSymbolicMemoryAPITenantIdFix:
    """Test that SymbolicMemoryAPI tenant_id conversion works correctly."""
    
    def test_symbolic_memory_converts_tenant_id_to_uuid(self, db_session, test_tenant_id):
        """SymbolicMemoryAPI should convert string tenant_id to UUID internally."""
        api = SymbolicMemoryAPI(tenant_id=test_tenant_id, session=db_session)
        
        assert api.tenant_id == test_tenant_id
        assert isinstance(api._tenant_id, UUID)
        assert str(api._tenant_id) == test_tenant_id
    
    def test_symbolic_memory_handles_uuid_tenant_id(self, db_session, test_tenant_id):
        """SymbolicMemoryAPI should handle UUID tenant_id passed directly."""
        tenant_uuid = UUID(test_tenant_id)
        api = SymbolicMemoryAPI(tenant_id=tenant_uuid, session=db_session)
        
        assert api._tenant_id == tenant_uuid


class TestParityWithRealData:
    """Test parity between SemanticMemory and SymbolicMemoryAPI with real database data."""
    
    def test_both_apis_return_relationships_for_same_entity(
        self, db_session, seeded_test_data
    ):
        """
        CRITICAL PARITY TEST: Both APIs should return the same relationships.
        
        This test verifies the Week 4 fix for the tenant_id type mismatch bug.
        Before the fix, SymbolicMemoryAPI would return 0 relationships while
        SemanticMemory returned the correct data.
        """
        tenant_id = seeded_test_data["tenant_id"]
        payment_service = seeded_test_data["payment_service"]
        
        semantic = SemanticMemory(session=db_session, tenant_id=tenant_id)
        semantic_rels = semantic.get_entity_relationships(
            entity_id=payment_service.id,
            direction="both",
            trusted_only=True
        )
        
        symbolic = SymbolicMemoryAPI(tenant_id=tenant_id, session=db_session)
        symbolic_rels = symbolic.get_relationships(
            entity_id=str(payment_service.id),
            direction="both",
            include_staging=False
        )
        
        parity_result = verify_relationship_parity(
            semantic_relationships=semantic_rels,
            symbolic_relationships=symbolic_rels,
            entity_id=str(payment_service.id)
        )
        
        assert parity_result["semantic_count"] > 0, "SemanticMemory should return relationships"
        assert parity_result["symbolic_count"] > 0, "SymbolicMemoryAPI should return relationships (parity fix)"
        assert parity_result["parity"] is True, (
            f"Parity failed! Semantic: {parity_result['semantic_count']}, "
            f"Symbolic: {parity_result['symbolic_count']}, "
            f"Missing in symbolic: {parity_result['missing_in_symbolic']}"
        )
    
    def test_outgoing_relationships_parity(self, db_session, seeded_test_data):
        """Both APIs should return same outgoing relationships."""
        tenant_id = seeded_test_data["tenant_id"]
        api_gateway = seeded_test_data["api_gateway"]
        
        semantic = SemanticMemory(session=db_session, tenant_id=tenant_id)
        semantic_rels = semantic.get_entity_relationships(
            entity_id=api_gateway.id,
            direction="outgoing",
            trusted_only=True
        )
        
        symbolic = SymbolicMemoryAPI(tenant_id=tenant_id, session=db_session)
        symbolic_rels = symbolic.get_relationships(
            entity_id=str(api_gateway.id),
            direction="outgoing",
            include_staging=False
        )
        
        parity_result = verify_relationship_parity(
            semantic_relationships=semantic_rels,
            symbolic_relationships=symbolic_rels,
            entity_id=str(api_gateway.id)
        )
        
        assert parity_result["parity"] is True
        assert parity_result["semantic_count"] == 1
        assert parity_result["symbolic_count"] == 1
    
    def test_incoming_relationships_parity(self, db_session, seeded_test_data):
        """Both APIs should return same incoming relationships."""
        tenant_id = seeded_test_data["tenant_id"]
        auth_db = seeded_test_data["auth_db"]
        
        semantic = SemanticMemory(session=db_session, tenant_id=tenant_id)
        semantic_rels = semantic.get_entity_relationships(
            entity_id=auth_db.id,
            direction="incoming",
            trusted_only=True
        )
        
        symbolic = SymbolicMemoryAPI(tenant_id=tenant_id, session=db_session)
        symbolic_rels = symbolic.get_relationships(
            entity_id=str(auth_db.id),
            direction="incoming",
            include_staging=False
        )
        
        parity_result = verify_relationship_parity(
            semantic_relationships=semantic_rels,
            symbolic_relationships=symbolic_rels,
            entity_id=str(auth_db.id)
        )
        
        assert parity_result["parity"] is True
        assert parity_result["semantic_count"] == 1
        assert parity_result["symbolic_count"] == 1


class TestTenantIsolation:
    """Test that both APIs properly isolate data by tenant."""
    
    def test_symbolic_memory_respects_tenant_isolation(
        self, db_session, seeded_test_data
    ):
        """SymbolicMemoryAPI should not return data from other tenants."""
        different_tenant_id = str(uuid4())
        payment_service = seeded_test_data["payment_service"]
        
        symbolic = SymbolicMemoryAPI(tenant_id=different_tenant_id, session=db_session)
        
        from src.context_foundry.rlm.schemas import StaleEntityError
        
        with pytest.raises(StaleEntityError):
            symbolic.get_relationships(
                entity_id=str(payment_service.id),
                direction="both"
            )
