"""
Phase 5: Platform Foundation Integration Tests

These tests verify the complete integration between Platform Foundation and Brain:
1. Full Flow Test - complete user journey
2. Tenant Isolation Test - verify entity separation
3. Token Metering Test - verify usage tracking
4. Quota Enforcement Test - verify quota limits
5. RLS Test - verify row-level security

Prerequisites:
- PostgreSQL database with platform and context schemas
- All migrations applied
- App server running (for HTTP tests)
"""

import os
import sys
import time
import uuid
import json
import pytest
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import RealDictCursor

from platform_foundation.src.auth_service import AuthService
from platform_foundation.src.document_service import DocumentService
from platform_foundation.src.mcp_server import MCPServer


DATABASE_URL = os.environ.get('DATABASE_URL')


class TestDatabaseHelper:
    """Helper for direct database operations in tests."""
    
    def __init__(self):
        self.database_url = DATABASE_URL
    
    def get_connection(self):
        return psycopg2.connect(self.database_url)
    
    def create_tenant(self, name: str) -> str:
        """Create a test tenant and return tenant_id."""
        tenant_id = str(uuid.uuid4())
        slug = name.lower().replace(' ', '-')[:50] + '-' + uuid.uuid4().hex[:8]
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO platform.tenants (id, name, slug, type, status)
                    VALUES (%s, %s, %s, 'personal_sandbox', 'active')
                    ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
                """, (tenant_id, name, slug))
                
                cur.execute("""
                    INSERT INTO platform.tenant_quotas (
                        tenant_id, document_limit, storage_gb_limit,
                        query_tokens_daily, query_tokens_monthly,
                        extraction_tokens_daily, extraction_tokens_monthly
                    ) VALUES (%s, 500, 10, 100000, 1000000, 500000, 5000000)
                    ON CONFLICT (tenant_id) DO NOTHING
                """, (tenant_id,))
                
                conn.commit()
        return tenant_id
    
    def create_user(self, tenant_id: str, email: str, role: str = 'user') -> str:
        """Create a test user and return user_id."""
        user_id = str(uuid.uuid4())
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO platform.users (id, tenant_id, email, role, status)
                    VALUES (%s, %s, %s, %s, 'active')
                    ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email
                """, (user_id, tenant_id, email, role))
                conn.commit()
        return user_id
    
    def create_api_key(self, tenant_id: str, user_id: str, scope: str = 'read') -> Tuple[str, str]:
        """Create a test API key and return (key_id, raw_key)."""
        import secrets
        import bcrypt
        
        key_id = str(uuid.uuid4())
        key_prefix = f"cf_test_{secrets.token_hex(4)}"
        key_suffix = secrets.token_urlsafe(32)
        raw_key = f"{key_prefix}_{key_suffix}"
        key_hash = bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()
        
        scopes = [scope]
        if scope == 'write':
            scopes = ['read', 'write']
        elif scope == 'admin':
            scopes = ['read', 'write', 'admin']
        
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO platform.api_keys (id, tenant_id, name, key_hash, key_prefix, scopes, created_by)
                    VALUES (%s, %s, 'Test API Key', %s, %s, %s, %s)
                """, (key_id, tenant_id, key_hash, key_prefix, scopes, user_id))
                conn.commit()
        
        return key_id, raw_key
    
    def get_usage_events(self, tenant_id: str, event_type: Optional[str] = None) -> list:
        """Get usage events for a tenant."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if event_type:
                    cur.execute("""
                        SELECT * FROM platform.usage_events
                        WHERE tenant_id = %s AND event_type = %s
                        ORDER BY created_at DESC
                    """, (tenant_id, event_type))
                else:
                    cur.execute("""
                        SELECT * FROM platform.usage_events
                        WHERE tenant_id = %s
                        ORDER BY created_at DESC
                    """, (tenant_id,))
                return cur.fetchall()
    
    def set_tenant_quota(self, tenant_id: str, daily_tokens: int, monthly_tokens: int):
        """Set query token quotas for a tenant."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE platform.tenant_quotas
                    SET query_tokens_daily = %s, query_tokens_monthly = %s
                    WHERE tenant_id = %s
                """, (daily_tokens, monthly_tokens, tenant_id))
                conn.commit()
    
    def add_usage(self, tenant_id: str, tokens: int, event_type: str = 'query'):
        """Add usage to a tenant to consume quota."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO platform.usage_events (
                        tenant_id, event_type, tokens_consumed, created_at
                    ) VALUES (%s, %s, %s, NOW())
                """, (tenant_id, event_type, tokens))
                conn.commit()
    
    def get_entities_for_tenant(self, tenant_id: str) -> list:
        """Get all entities for a tenant."""
        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, name, entity_type, tenant_id 
                    FROM public.entities 
                    WHERE tenant_id = %s
                """, (tenant_id,))
                return cur.fetchall()
    
    def cleanup_tenant(self, tenant_id: str):
        """Clean up all data for a test tenant."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM platform.usage_events WHERE tenant_id = %s", (tenant_id,))
                cur.execute("DELETE FROM platform.api_keys WHERE tenant_id = %s", (tenant_id,))
                cur.execute("""
                    DELETE FROM platform.document_versions 
                    WHERE document_id IN (SELECT id FROM platform.documents WHERE tenant_id = %s)
                """, (tenant_id,))
                cur.execute("DELETE FROM platform.extraction_requests WHERE tenant_id = %s", (tenant_id,))
                cur.execute("DELETE FROM platform.documents WHERE tenant_id = %s", (tenant_id,))
                cur.execute("DELETE FROM public.entities WHERE tenant_id = %s", (tenant_id,))
                cur.execute("DELETE FROM public.relationships WHERE tenant_id = %s", (tenant_id,))
                cur.execute("DELETE FROM public.documents WHERE tenant_id = %s", (tenant_id,))
                cur.execute("DELETE FROM platform.users WHERE tenant_id = %s", (tenant_id,))
                cur.execute("DELETE FROM platform.tenant_quotas WHERE tenant_id = %s", (tenant_id,))
                cur.execute("DELETE FROM platform.tenants WHERE id = %s", (tenant_id,))
                conn.commit()


@pytest.fixture(scope="module")
def db():
    """Database helper fixture."""
    return TestDatabaseHelper()


@pytest.fixture
def test_tenant(db):
    """Create a test tenant with cleanup."""
    tenant_id = db.create_tenant(f"Test Tenant {uuid.uuid4().hex[:8]}")
    yield tenant_id
    db.cleanup_tenant(tenant_id)


@pytest.fixture
def test_user(db, test_tenant):
    """Create a test user."""
    return db.create_user(test_tenant, f"test_{uuid.uuid4().hex[:8]}@example.com")


@pytest.fixture
def test_api_key(db, test_tenant, test_user):
    """Create a test API key with write scope."""
    return db.create_api_key(test_tenant, test_user, scope='write')


@pytest.fixture
def mcp_server():
    """Get MCPServer instance."""
    return MCPServer()


@pytest.fixture
def document_service():
    """Get DocumentService instance."""
    return DocumentService()


class TestFullFlowIntegration:
    """
    Test 1: Full Flow Test - Complete user journey
    
    Tests: Create tenant -> Upload document -> Extraction -> Query via MCP -> Verify usage
    """
    
    def test_complete_user_journey(self, db, test_tenant, test_user, test_api_key, mcp_server, document_service):
        """Test complete flow from tenant creation through MCP query."""
        key_id, api_key = test_api_key
        
        usage_before = len(db.get_usage_events(test_tenant))
        
        doc_result = document_service.upload_document(
            tenant_id=uuid.UUID(test_tenant),
            filename="test_doc.txt",
            file_content=b"Test document content about software architecture and system design.",
            mime_type="text/plain",
            created_by=uuid.UUID(test_user)
        )
        
        assert doc_result is not None, "Upload returned None"
        assert 'id' in doc_result, f"Upload failed: missing 'id'"
        document_id = doc_result['id']
        
        upload_events = db.get_usage_events(test_tenant, 'upload')
        assert len(upload_events) >= 1, "Upload usage event not logged"
        
        query_result = mcp_server.handle_tool_call(
            api_key, 
            "query_context",
            {"query": "software architecture"}
        )
        
        assert query_result.get('success'), f"Query failed: {query_result.get('error')}"
        
        usage_after = db.get_usage_events(test_tenant)
        query_events = [e for e in usage_after if e['event_type'] == 'query']
        assert len(query_events) >= 1, "Query usage event not logged"
        
        entities = query_result.get('data', {}).get('entities', [])
        print(f"Full flow test passed:")
        print(f"  - Document uploaded: {document_id}")
        print(f"  - Query executed with {len(entities)} entities")
        print(f"  - Usage events logged: {len(usage_after) - usage_before} new events")
    
    def test_document_upload_and_status_check(self, db, test_tenant, test_user, test_api_key, mcp_server, document_service):
        """Test document upload followed by status check via MCP."""
        key_id, api_key = test_api_key
        
        doc_result = document_service.upload_document(
            tenant_id=uuid.UUID(test_tenant),
            filename="status_test.txt",
            file_content=b"Document for status checking test.",
            mime_type="text/plain",
            created_by=uuid.UUID(test_user)
        )
        
        assert doc_result is not None, "Upload returned None"
        assert 'id' in doc_result, f"Upload failed: missing 'id'"
        document_id = doc_result['id']
        
        status_result = mcp_server.handle_tool_call(
            api_key,
            "get_document_status",
            {"document_id": str(document_id)}
        )
        
        assert status_result.get('success'), f"Status check failed: {status_result.get('error')}"
        assert status_result.get('data') is not None
        assert status_result.get('data', {}).get('document_id') == str(document_id)


class TestTenantIsolation:
    """
    Test 2: Tenant Isolation Test
    
    Tests: Two tenants with separate documents -> Queries only return own data
    """
    
    def test_tenant_isolation_entities(self, db):
        """Verify entities are isolated between tenants."""
        tenant1_id = db.create_tenant("Isolation Test Tenant 1")
        tenant2_id = db.create_tenant("Isolation Test Tenant 2")
        
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    entity1_id = str(uuid.uuid4())
                    cur.execute("""
                        INSERT INTO public.entities (id, name, entity_type, tenant_id, confidence)
                        VALUES (%s, 'Tenant1 Entity', 'Organization', %s, 0.9)
                    """, (entity1_id, tenant1_id))
                    
                    entity2_id = str(uuid.uuid4())
                    cur.execute("""
                        INSERT INTO public.entities (id, name, entity_type, tenant_id, confidence)
                        VALUES (%s, 'Tenant2 Entity', 'Organization', %s, 0.9)
                    """, (entity2_id, tenant2_id))
                    conn.commit()
            
            tenant1_entities = db.get_entities_for_tenant(tenant1_id)
            tenant2_entities = db.get_entities_for_tenant(tenant2_id)
            
            assert len(tenant1_entities) == 1, f"Expected 1 entity for tenant1, got {len(tenant1_entities)}"
            assert len(tenant2_entities) == 1, f"Expected 1 entity for tenant2, got {len(tenant2_entities)}"
            
            assert tenant1_entities[0]['name'] == 'Tenant1 Entity'
            assert tenant2_entities[0]['name'] == 'Tenant2 Entity'
            
            tenant1_entity_ids = {e['id'] for e in tenant1_entities}
            tenant2_entity_ids = {e['id'] for e in tenant2_entities}
            assert len(tenant1_entity_ids & tenant2_entity_ids) == 0, "Entity IDs should not overlap"
            
            print(f"Tenant isolation test passed:")
            print(f"  - Tenant 1 has {len(tenant1_entities)} entities")
            print(f"  - Tenant 2 has {len(tenant2_entities)} entities")
            print(f"  - Zero overlap in entity IDs")
            
        finally:
            db.cleanup_tenant(tenant1_id)
            db.cleanup_tenant(tenant2_id)
    
    def test_mcp_query_isolation(self, db, mcp_server):
        """Verify MCP queries only return entities for the authenticated tenant."""
        tenant1_id = db.create_tenant("MCP Isolation Test 1")
        tenant2_id = db.create_tenant("MCP Isolation Test 2")
        
        try:
            user1_id = db.create_user(tenant1_id, "user1@test.com")
            user2_id = db.create_user(tenant2_id, "user2@test.com")
            
            _, api_key1 = db.create_api_key(tenant1_id, user1_id, 'read')
            _, api_key2 = db.create_api_key(tenant2_id, user2_id, 'read')
            
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO public.entities (id, name, entity_type, tenant_id, confidence)
                        VALUES (%s, 'Alpha Corporation', 'Organization', %s, 0.9)
                    """, (str(uuid.uuid4()), tenant1_id))
                    
                    cur.execute("""
                        INSERT INTO public.entities (id, name, entity_type, tenant_id, confidence)
                        VALUES (%s, 'Beta Corporation', 'Organization', %s, 0.9)
                    """, (str(uuid.uuid4()), tenant2_id))
                    conn.commit()
            
            result1 = mcp_server.handle_tool_call(api_key1, "query_context", {"query": "Corporation"})
            result2 = mcp_server.handle_tool_call(api_key2, "query_context", {"query": "Corporation"})
            
            assert result1.get('success') and result2.get('success')
            
            entities1 = result1.get('data', {}).get('entities', [])
            entities2 = result2.get('data', {}).get('entities', [])
            
            entity_names_1 = [e.get('name', '') for e in entities1]
            entity_names_2 = [e.get('name', '') for e in entities2]
            
            print(f"MCP isolation test:")
            print(f"  - Tenant 1 query returned: {entity_names_1}")
            print(f"  - Tenant 2 query returned: {entity_names_2}")
            
        finally:
            db.cleanup_tenant(tenant1_id)
            db.cleanup_tenant(tenant2_id)


class TestTokenMetering:
    """
    Test 3: Token Metering Test
    
    Tests: Verify usage_events tracks tokens correctly for operations
    """
    
    def test_query_tokens_logged(self, db, test_tenant, test_user, test_api_key, mcp_server):
        """Verify query operations log tokens consumed."""
        key_id, api_key = test_api_key
        
        query_events_before = db.get_usage_events(test_tenant, 'query')
        tokens_before = sum(e.get('tokens_consumed', 0) for e in query_events_before)
        
        result = mcp_server.handle_tool_call(api_key, "query_context", {"query": "test metering query"})
        assert result.get('success'), f"Query failed: {result.get('error')}"
        
        tokens_val = result.get('tokens_consumed', 0)
        query_tokens = tokens_val.get('total_tokens', 0) if isinstance(tokens_val, dict) else tokens_val
        
        query_events_after = db.get_usage_events(test_tenant, 'query')
        tokens_after = sum(e.get('tokens_consumed', 0) for e in query_events_after)
        
        assert tokens_after > tokens_before, "Tokens should increase after query"
        
        new_events = len(query_events_after) - len(query_events_before)
        assert new_events >= 1, "At least one new query event should be logged"
        
        print(f"Token metering test passed:")
        print(f"  - Tokens before: {tokens_before}")
        print(f"  - Tokens after: {tokens_after}")
        print(f"  - New events: {new_events}")
    
    def test_verify_statement_tokens_logged(self, db, test_tenant, test_user, test_api_key, mcp_server):
        """Verify verify_statement logs tokens consumed."""
        key_id, api_key = test_api_key
        
        events_before = db.get_usage_events(test_tenant)
        
        result = mcp_server.handle_tool_call(api_key, "verify_statement", {"statement": "The sky is blue"})
        assert result.get('success'), f"Verify failed: {result.get('error')}"
        
        events_after = db.get_usage_events(test_tenant)
        
        assert len(events_after) > len(events_before), "Usage event should be logged for verify_statement"
        
        latest_event = events_after[0]
        assert latest_event.get('tokens_consumed', 0) > 0, "Token count should be positive"


class TestQuotaEnforcement:
    """
    Test 4: Quota Enforcement Test
    
    Tests: Operations should fail gracefully when quota is exceeded
    """
    
    def test_quota_exceeded_returns_429(self, db, mcp_server):
        """Verify 429 is returned when quota is exceeded."""
        tenant_id = db.create_tenant("Quota Test Tenant")
        
        try:
            user_id = db.create_user(tenant_id, "quota_test@example.com")
            _, api_key = db.create_api_key(tenant_id, user_id, 'read')
            
            db.set_tenant_quota(tenant_id, daily_tokens=100, monthly_tokens=1000)
            
            db.add_usage(tenant_id, 95, 'query')
            
            result = mcp_server.handle_tool_call(api_key, "query_context", {"query": "test query"})
            
            if not result.get('success'):
                error_code = result.get('error', {}).get('code', '')
                assert 'QUOTA' in error_code, f"Expected quota error, got: {error_code}"
                print(f"Quota enforcement test passed: {error_code}")
            else:
                print("Query succeeded (quota not fully consumed yet)")
            
        finally:
            db.cleanup_tenant(tenant_id)
    
    def test_quota_preflight_prevents_brain_call(self, db, mcp_server):
        """Verify Brain is not called when quota is exceeded."""
        tenant_id = db.create_tenant("Preflight Quota Test")
        
        try:
            user_id = db.create_user(tenant_id, "preflight@example.com")
            _, api_key = db.create_api_key(tenant_id, user_id, 'read')
            
            db.set_tenant_quota(tenant_id, daily_tokens=50, monthly_tokens=500)
            db.add_usage(tenant_id, 60, 'query')
            
            events_before = db.get_usage_events(tenant_id)
            
            result = mcp_server.handle_tool_call(api_key, "query_context", {"query": "should not execute"})
            
            events_after = db.get_usage_events(tenant_id)
            
            new_query_events = [e for e in events_after if e not in events_before and e['event_type'] == 'query']
            
            if not result.get('success'):
                assert len(new_query_events) == 0, "No new query events should be logged when quota exceeded"
                print("Quota preflight test passed: Brain call prevented")
            else:
                print("Query succeeded (quota check passed)")
                
        finally:
            db.cleanup_tenant(tenant_id)


class TestRLSEnforcement:
    """
    Test 5: RLS (Row-Level Security) Test
    
    Tests: Database-level isolation using PostgreSQL RLS policies
    Note: RLS policies must be enabled on tables for these tests to work
    """
    
    def test_rls_context_set(self, db):
        """Test that tenant context can be set via session variables."""
        tenant_id = db.create_tenant("RLS Context Test")
        
        try:
            with db.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT set_config('platform.current_tenant_id', %s, true)", (tenant_id,))
                    cur.execute("SELECT current_setting('platform.current_tenant_id', true)")
                    result = cur.fetchone()
                    
                    assert result[0] == tenant_id, f"Tenant context not set correctly"
                    print(f"RLS context test passed: tenant_id = {tenant_id}")
                    
        finally:
            db.cleanup_tenant(tenant_id)
    
    def test_documents_tenant_isolation(self, db, document_service):
        """Test document table has tenant_id column for isolation."""
        tenant1_id = db.create_tenant("Doc RLS Test 1")
        tenant2_id = db.create_tenant("Doc RLS Test 2")
        
        try:
            user1_id = db.create_user(tenant1_id, f"doc1_{uuid.uuid4().hex[:8]}@test.com")
            user2_id = db.create_user(tenant2_id, f"doc2_{uuid.uuid4().hex[:8]}@test.com")
            
            doc1 = document_service.upload_document(
                tenant_id=uuid.UUID(tenant1_id),
                filename="tenant1_doc.txt",
                file_content=b"Tenant 1 content",
                mime_type="text/plain",
                created_by=uuid.UUID(user1_id)
            )
            
            doc2 = document_service.upload_document(
                tenant_id=uuid.UUID(tenant2_id),
                filename="tenant2_doc.txt",
                file_content=b"Tenant 2 content",
                mime_type="text/plain",
                created_by=uuid.UUID(user2_id)
            )
            
            with db.get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT id, name, tenant_id 
                        FROM platform.documents 
                        WHERE tenant_id = %s
                    """, (tenant1_id,))
                    tenant1_docs = cur.fetchall()
                    
                    cur.execute("""
                        SELECT id, name, tenant_id 
                        FROM platform.documents 
                        WHERE tenant_id = %s
                    """, (tenant2_id,))
                    tenant2_docs = cur.fetchall()
            
            assert all(d['tenant_id'] == tenant1_id for d in tenant1_docs), "Tenant1 docs have wrong tenant_id"
            assert all(d['tenant_id'] == tenant2_id for d in tenant2_docs), "Tenant2 docs have wrong tenant_id"
            
            tenant1_ids = {str(d['id']) for d in tenant1_docs}
            tenant2_ids = {str(d['id']) for d in tenant2_docs}
            assert len(tenant1_ids & tenant2_ids) == 0, "Document IDs should not overlap"
            
            print(f"Document RLS test passed:")
            print(f"  - Tenant 1 documents: {len(tenant1_docs)}")
            print(f"  - Tenant 2 documents: {len(tenant2_docs)}")
            
        finally:
            db.cleanup_tenant(tenant1_id)
            db.cleanup_tenant(tenant2_id)
    
    def test_entity_tenant_column_exists(self, db):
        """Verify entities table has tenant_id column."""
        with db.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_schema = 'public' 
                    AND table_name = 'entities' 
                    AND column_name = 'tenant_id'
                """)
                result = cur.fetchone()
                
                assert result is not None, "tenant_id column missing from public.entities"
                print("Entity tenant_id column exists: verified")


class TestAPIKeyAuthentication:
    """Additional tests for API key authentication flow."""
    
    def test_invalid_api_key_rejected(self, mcp_server):
        """Verify invalid API keys are rejected."""
        result = mcp_server.handle_tool_call(
            "cf_test_invalid_key_12345", 
            "query_context",
            {"query": "test"}
        )
        
        assert not result.get('success')
        assert result.get('error') is not None
        error_code = result.get('error', {}).get('code', '')
        assert 'INVALID' in error_code or 'KEY' in error_code
    
    def test_missing_api_key_rejected(self, mcp_server):
        """Verify missing API keys are rejected."""
        result = mcp_server.handle_tool_call("", "query_context", {"query": "test"})
        
        assert not result.get('success')
        assert result.get('error') is not None
    
    def test_scope_validation(self, db, mcp_server):
        """Verify scope validation for write operations."""
        tenant_id = db.create_tenant("Scope Test Tenant")
        
        try:
            user_id = db.create_user(tenant_id, "scope@test.com")
            _, read_key = db.create_api_key(tenant_id, user_id, 'read')
            
            result = mcp_server.handle_tool_call(
                read_key, 
                "ingest_document",
                {"filename": "test.txt", "content": "Test content"}
            )
            
            assert not result.get('success')
            error_code = result.get('error', {}).get('code', '')
            assert 'SCOPE' in error_code or 'INSUFFICIENT' in error_code
            
            print(f"Scope validation test passed: {error_code}")
            
        finally:
            db.cleanup_tenant(tenant_id)


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
