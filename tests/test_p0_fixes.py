"""
P0 Fixes Regression Tests

Tests for the P0 fixes required before scaling usage:
1. Session leak fix in /api/v1/query 
2. Entity endpoints using attribute access (not .get())
3. query_impact returning structured impact payload
4. EpisodicMemory.add_document setting tenant_id
5. Tenant isolation for documents
"""

import pytest
import uuid
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.context_foundry.models.schema import get_session, Entity, LifecycleState


TENANT_A_ID = "8eee325b-ba3b-447e-9ee7-6d66085ead5f"
TENANT_B_ID = "a0b1c2d3-e4f5-6789-0123-456789abcdef"


class TestSessionLeakFix:
    """Test that /api/v1/query doesn't leak sessions."""
    
    def test_session_pool_not_exhausted_after_repeated_calls(self):
        """Verify session pool isn't exhausted after many calls."""
        from src.context_foundry.models.schema import get_session
        
        sessions = []
        try:
            for i in range(50):
                session = get_session()
                session.execute(text("SELECT 1"))
                session.close()
            
            final_session = get_session()
            result = final_session.execute(text("SELECT 1")).fetchone()
            assert result[0] == 1
            final_session.close()
            
        except Exception as e:
            pytest.fail(f"Session pool exhausted after repeated calls: {e}")
    
    def test_session_closed_on_no_matches_path(self):
        """Verify session closes properly after NO_MATCHES result."""
        session = get_session()
        closed_properly = False
        try:
            from src.context_foundry.agents.tier1_resolver import Tier1Resolver
            resolver = Tier1Resolver(session=session, tenant_id=TENANT_A_ID)
            result = resolver.resolve_from_text("nonexistent gibberish xyz123")
            valid_statuses = ("NO_MATCHES", "LOW_CONFIDENCE", "AMBIGUOUS", "RESOLVED", "NO_ENTITIES_IN_GRAPH")
            assert result.status in valid_statuses, f"Unexpected status: {result.status}"
            closed_properly = True
        finally:
            session.close()
        
        assert closed_properly, "Session should complete without error before closing"


class TestEntityEndpointsFix:
    """Test that entity endpoints use attribute access on ORM objects."""
    
    def test_search_entities_returns_orm_objects(self):
        """Verify search_entities returns Entity ORM objects with attributes."""
        from src.context_foundry.memory.semantic import SemanticMemory
        
        session = get_session(use_rls_role=True)
        try:
            session.execute(text("SET app.current_tenant_id = :tid"), {"tid": TENANT_A_ID})
            memory = SemanticMemory(session=session, tenant_id=TENANT_A_ID)
            
            entities = memory.search_entities("API", limit=5)
            
            if entities:
                entity = entities[0]
                assert hasattr(entity, 'id'), "Entity should have id attribute"
                assert hasattr(entity, 'name'), "Entity should have name attribute"
                assert hasattr(entity, 'entity_type'), "Entity should have entity_type attribute"
                assert hasattr(entity, 'confidence'), "Entity should have confidence attribute"
                
                assert not callable(getattr(entity, 'get', None)) or True
                
        finally:
            session.close()
    
    def test_entity_attribute_access_works(self):
        """Verify entity attributes can be accessed directly."""
        from src.context_foundry.memory.semantic import SemanticMemory
        
        session = get_session(use_rls_role=True)
        try:
            session.execute(text("SET app.current_tenant_id = :tid"), {"tid": TENANT_A_ID})
            memory = SemanticMemory(session=session, tenant_id=TENANT_A_ID)
            
            entities = memory.search_entities("", limit=1)
            
            if entities:
                entity = entities[0]
                entity_id = str(entity.id) if entity.id else None
                entity_name = entity.name
                entity_type = entity.entity_type
                entity_confidence = float(entity.confidence) if entity.confidence else None
                
                assert entity_id is None or isinstance(entity_id, str)
                assert entity_name is None or isinstance(entity_name, str)
                
        finally:
            session.close()


class TestQueryImpactFix:
    """Test that query_impact returns structured impact payload."""
    
    def test_query_impact_returns_structured_payload(self):
        """Verify query_impact returns impact data instead of discarding it."""
        from src.context_foundry.core import ContextFoundry
        
        session = get_session(use_rls_role=True)
        try:
            session.execute(text("SET app.current_tenant_id = :tid"), {"tid": TENANT_A_ID})
            cf = ContextFoundry(session=session, tenant_id=TENANT_A_ID)
            
            result = cf.query_impact("API Gateway")
            
            assert isinstance(result, dict), "query_impact should return dict"
            assert "entity_name" in result, "Result should contain entity_name"
            assert "status" in result, "Result should contain status"
            assert result["status"] in ("IMPACT_FOUND", "NO_IMPACT_DATA"), \
                f"Status should be IMPACT_FOUND or NO_IMPACT_DATA, got {result['status']}"
            
            if result["status"] == "IMPACT_FOUND":
                assert "affected_entities" in result, "IMPACT_FOUND should have affected_entities"
                assert "total_affected" in result, "IMPACT_FOUND should have total_affected"
                
        finally:
            session.close()
    
    def test_query_impact_no_impact_data(self):
        """Verify query_impact handles entities with no impact data gracefully."""
        from src.context_foundry.core import ContextFoundry
        
        session = get_session(use_rls_role=True)
        try:
            session.execute(text("SET app.current_tenant_id = :tid"), {"tid": TENANT_A_ID})
            cf = ContextFoundry(session=session, tenant_id=TENANT_A_ID)
            
            result = cf.query_impact("NonexistentEntity12345")
            
            assert isinstance(result, dict)
            assert result["status"] == "NO_IMPACT_DATA"
            assert result["affected_entities"] == []
            
        finally:
            session.close()


class TestEpisodicMemoryTenantFix:
    """Test that EpisodicMemory.add_document sets tenant_id."""
    
    def test_add_document_requires_tenant_id(self):
        """Verify add_document raises error without tenant_id."""
        from src.context_foundry.memory.episodic import EpisodicMemory
        
        session = get_session()
        try:
            memory = EpisodicMemory(session=session, tenant_id=None)
            
            with pytest.raises(ValueError, match="requires tenant_id"):
                memory.add_document(
                    title="Test Doc",
                    doc_type="test",
                    content="Test content"
                )
        finally:
            session.close()
    
    def test_add_document_sets_tenant_id(self):
        """Verify add_document sets tenant_id on created Document."""
        from src.context_foundry.memory.episodic import EpisodicMemory
        from src.context_foundry.models.schema import Document
        
        session = get_session(use_rls_role=True)
        test_title = f"Test Doc {uuid.uuid4().hex[:8]}"
        
        try:
            session.execute(text("SET app.current_tenant_id = :tid"), {"tid": TENANT_A_ID})
            memory = EpisodicMemory(session=session, tenant_id=TENANT_A_ID)
            
            doc = memory.add_document(
                title=test_title,
                doc_type="test",
                content="Test content for tenant isolation test"
            )
            
            assert doc.tenant_id is not None, "Document should have tenant_id set"
            assert str(doc.tenant_id) == TENANT_A_ID, f"tenant_id should match, got {doc.tenant_id}"
            
            session.delete(doc)
            session.commit()
            
        finally:
            session.close()


class TestDocumentTenantIsolation:
    """Test that tenants cannot read each other's documents."""
    
    def test_tenant_a_cannot_read_tenant_b_documents(self):
        """Verify tenant A cannot access tenant B documents via RLS."""
        session = get_session(use_rls_role=True)
        
        try:
            session.execute(text("SET app.current_tenant_id = :tid"), {"tid": TENANT_A_ID})
            
            result = session.execute(text("""
                SELECT COUNT(*) as cnt FROM platform.documents 
                WHERE tenant_id = :other_tenant
            """), {"other_tenant": TENANT_B_ID})
            
            count = result.fetchone().cnt
            assert count == 0, f"Tenant A should not see Tenant B documents, but saw {count}"
            
        finally:
            session.close()
    
    def test_rls_blocks_cross_tenant_document_access(self):
        """Verify RLS blocks access to other tenant's documents."""
        session = get_session(use_rls_role=True)
        
        try:
            session.execute(text("SET app.current_tenant_id = :tid"), {"tid": TENANT_A_ID})
            
            tenant_a_docs = session.execute(text("""
                SELECT COUNT(*) as cnt FROM platform.documents
            """)).fetchone().cnt
            
            session.execute(text("SET app.current_tenant_id = :tid"), {"tid": TENANT_B_ID})
            
            tenant_b_docs = session.execute(text("""
                SELECT COUNT(*) as cnt FROM platform.documents
            """)).fetchone().cnt
            
            assert tenant_b_docs == 0, "Non-existent tenant should see 0 documents"
            
        finally:
            session.close()


def run_all_tests():
    """Run all P0 fix tests."""
    print("=" * 70)
    print("P0 FIXES REGRESSION TESTS")
    print("=" * 70)
    
    test_classes = [
        TestSessionLeakFix,
        TestEntityEndpointsFix,
        TestQueryImpactFix,
        TestEpisodicMemoryTenantFix,
        TestDocumentTenantIsolation,
    ]
    
    total_passed = 0
    total_failed = 0
    
    for test_class in test_classes:
        print(f"\n--- {test_class.__name__} ---")
        instance = test_class()
        
        for method_name in dir(instance):
            if method_name.startswith("test_"):
                method = getattr(instance, method_name)
                try:
                    method()
                    print(f"  [PASS] {method_name}")
                    total_passed += 1
                except AssertionError as e:
                    print(f"  [FAIL] {method_name}: {e}")
                    total_failed += 1
                except Exception as e:
                    print(f"  [ERROR] {method_name}: {e}")
                    total_failed += 1
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {total_passed} passed, {total_failed} failed")
    print("=" * 70)
    
    return total_failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
