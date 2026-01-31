"""
RLS (Row-Level Security) Verification Tests

CRITICAL: These tests MUST pass before deployment.
They verify that tenant isolation is enforced at the database level.
"""

import os
import sys
import uuid
import pytest
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_foundry.models.schema import (
    get_session, tenant_session, get_tenant_session, 
    set_tenant_context, reset_tenant_context
)


TENANT_A = str(uuid.uuid4())
TENANT_B = str(uuid.uuid4())
MAIN_TENANT = "f3dd3201-7225-4a55-9264-445f99d0eba3"


class TestRLSFailClosed:
    """Test that RLS policies return NO rows when tenant context is not set."""
    
    def test_entities_fail_closed_no_context(self):
        """Without tenant context, entities query should return zero rows."""
        session = get_session()
        try:
            result = session.execute(text("SELECT COUNT(*) FROM public.entities"))
            count = result.scalar()
            assert count == 0, f"SECURITY BREACH: Got {count} entities without tenant context (expected 0)"
        finally:
            session.close()
    
    def test_relationships_fail_closed_no_context(self):
        """Without tenant context, relationships query should return zero rows."""
        session = get_session()
        try:
            result = session.execute(text("SELECT COUNT(*) FROM public.relationships"))
            count = result.scalar()
            assert count == 0, f"SECURITY BREACH: Got {count} relationships without tenant context (expected 0)"
        finally:
            session.close()
    
    def test_documents_fail_closed_no_context(self):
        """Without tenant context, documents query should return zero rows."""
        session = get_session()
        try:
            result = session.execute(text("SELECT COUNT(*) FROM public.documents"))
            count = result.scalar()
            assert count == 0, f"SECURITY BREACH: Got {count} documents without tenant context (expected 0)"
        finally:
            session.close()


class TestTenantIsolation:
    """Test that tenants can only see their own data."""
    
    def test_entities_tenant_isolation(self):
        """Tenant A cannot see Tenant B's entities."""
        with tenant_session(MAIN_TENANT) as session:
            result = session.execute(text("SELECT COUNT(*) FROM public.entities"))
            main_count = result.scalar()
        
        with tenant_session(TENANT_B) as session:
            result = session.execute(text("SELECT COUNT(*) FROM public.entities"))
            other_count = result.scalar()
        
        assert other_count == 0, f"SECURITY BREACH: Random tenant saw {other_count} entities (expected 0)"
        print(f"Main tenant has {main_count} entities, random tenant sees 0")
    
    def test_entities_with_valid_tenant(self):
        """Tenant session should return entities for that tenant only."""
        with tenant_session(MAIN_TENANT) as session:
            result = session.execute(text("SELECT COUNT(*) FROM public.entities"))
            count = result.scalar()
            
            result = session.execute(
                text("SELECT COUNT(*) FROM public.entities WHERE tenant_id = :tid"),
                {"tid": MAIN_TENANT}
            )
            filtered_count = result.scalar()
            
            assert count == filtered_count, f"RLS mismatch: RLS returned {count}, WHERE returned {filtered_count}"


class TestTenantContextManager:
    """Test the tenant context manager functions correctly."""
    
    def test_tenant_session_sets_context(self):
        """tenant_session() should set app.current_tenant_id."""
        with tenant_session(MAIN_TENANT) as session:
            result = session.execute(
                text("SELECT current_setting('app.current_tenant_id', true)")
            )
            setting = result.scalar()
            assert setting == MAIN_TENANT, f"Expected {MAIN_TENANT}, got {setting}"
    
    def test_tenant_session_resets_context(self):
        """tenant_session() should reset context after exiting."""
        with tenant_session(MAIN_TENANT) as session:
            pass
        
        session = get_session()
        try:
            result = session.execute(
                text("SELECT current_setting('app.current_tenant_id', true)")
            )
            setting = result.scalar()
            assert setting in (None, ''), f"Context not reset: got {setting}"
        finally:
            session.close()
    
    def test_admin_role_bypass(self):
        """Admin role should bypass RLS restrictions."""
        with tenant_session(None, role='admin') as session:
            result = session.execute(text("SELECT COUNT(*) FROM public.entities"))
            count = result.scalar()
            print(f"Admin role sees {count} entities across all tenants")


class TestSetTenantContext:
    """Test the set_tenant_context helper function."""
    
    def test_set_tenant_context_on_existing_session(self):
        """set_tenant_context() should work on an existing session."""
        session = get_session()
        try:
            set_tenant_context(session, MAIN_TENANT)
            
            result = session.execute(
                text("SELECT current_setting('app.current_tenant_id', true)")
            )
            setting = result.scalar()
            assert setting == MAIN_TENANT, f"Expected {MAIN_TENANT}, got {setting}"
            
            reset_tenant_context(session)
        finally:
            session.close()


class TestRLSWithApplicationFiltering:
    """Test that RLS works together with application-level WHERE clauses (defense-in-depth)."""
    
    def test_double_protection(self):
        """Both RLS and WHERE clause should filter correctly."""
        with tenant_session(MAIN_TENANT) as session:
            rls_result = session.execute(text("SELECT COUNT(*) FROM public.entities"))
            rls_count = rls_result.scalar()
            
            where_result = session.execute(
                text("SELECT COUNT(*) FROM public.entities WHERE tenant_id = :tid"),
                {"tid": MAIN_TENANT}
            )
            where_count = where_result.scalar()
            
            assert rls_count == where_count, f"RLS ({rls_count}) != WHERE ({where_count})"
    
    def test_cross_tenant_attack_blocked(self):
        """Attempting to query another tenant's data should fail even with WHERE."""
        with tenant_session(TENANT_A) as session:
            result = session.execute(
                text("SELECT COUNT(*) FROM public.entities WHERE tenant_id = :tid"),
                {"tid": MAIN_TENANT}
            )
            count = result.scalar()
            assert count == 0, f"SECURITY BREACH: Cross-tenant WHERE returned {count} rows"


class TestMemoryClassDefenseInDepth:
    """Test that memory classes properly filter by tenant_id (defense-in-depth)."""
    
    def test_semantic_memory_with_tenant_id(self):
        """SemanticMemory with tenant_id should apply filtering."""
        from src.context_foundry.memory.semantic import SemanticMemory
        
        with tenant_session(MAIN_TENANT) as session:
            sm = SemanticMemory(session, tenant_id=MAIN_TENANT)
            entities = sm.search_entities("test", limit=10)
            
            for entity in entities:
                entity_tenant = str(entity.tenant_id) if hasattr(entity, 'tenant_id') and entity.tenant_id else None
                if entity_tenant:
                    assert entity_tenant == MAIN_TENANT, \
                        f"SECURITY BREACH: SemanticMemory returned entity with tenant_id={entity_tenant}"
    
    def test_semantic_memory_stores_tenant_id(self):
        """SemanticMemory should store tenant_id for use in queries."""
        from src.context_foundry.memory.semantic import SemanticMemory
        
        with tenant_session(MAIN_TENANT) as session:
            sm = SemanticMemory(session, tenant_id=MAIN_TENANT)
            assert sm.tenant_id == MAIN_TENANT, "SemanticMemory should store tenant_id"
            
            sm_no_tenant = SemanticMemory(session)
            assert sm_no_tenant.tenant_id is None, "SemanticMemory without tenant_id should be None"
    
    def test_episodic_memory_with_tenant_id(self):
        """EpisodicMemory with tenant_id should store it for filtering."""
        from src.context_foundry.memory.episodic import EpisodicMemory
        
        with tenant_session(MAIN_TENANT) as session:
            em = EpisodicMemory(session, tenant_id=MAIN_TENANT)
            assert em.tenant_id == MAIN_TENANT, "EpisodicMemory should store tenant_id"
            
            em_no_tenant = EpisodicMemory(session)
            assert em_no_tenant.tenant_id is None, "EpisodicMemory without tenant_id should be None"
    
    def test_inference_engine_with_tenant_id(self):
        """InferenceEngine with tenant_id should pass it to internal memory classes."""
        from src.context_foundry.memory.inference import InferenceEngine
        
        with tenant_session(MAIN_TENANT) as session:
            ie = InferenceEngine(session, tenant_id=MAIN_TENANT)
            assert ie.tenant_id == MAIN_TENANT, "InferenceEngine should store tenant_id"
    
    def test_retrieval_agent_with_tenant_id(self):
        """RetrievalAgent with tenant_id should pass it to all memory classes."""
        from src.context_foundry.agents.retrieval import RetrievalAgent
        
        with tenant_session(MAIN_TENANT) as session:
            ra = RetrievalAgent(session, tenant_id=MAIN_TENANT)
            assert ra.tenant_id == MAIN_TENANT, "RetrievalAgent should store tenant_id"
            assert ra.semantic.tenant_id == MAIN_TENANT, "SemanticMemory should have tenant_id"
            assert ra.episodic.tenant_id == MAIN_TENANT, "EpisodicMemory should have tenant_id"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
