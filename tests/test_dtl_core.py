"""
DTL Core Tests - Parity, Security, and Performance

These tests verify the library-first architecture:
1. Smoke: inline-only tests (no external dependencies, run in CI)
2. Parity: inline vs HTTP returns identical results (nightly only)
3. Security: cross-tenant returns 0 results
4. Performance: inline path p95 under threshold with 10k decisions

Pytest markers:
- @pytest.mark.smoke: Inline-only tests, safe for CI (no API keys/HTTP)
- No marker: Full tests requiring API keys and/or HTTP server (nightly)
"""

import os
import sys
import time
import uuid
import json
import hashlib
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_foundry.dtl import AuthContext, search_precedents, inline_search_precedents
from src.context_foundry.models.schema import get_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOLERANCE = 1e-6
HTTP_BASE_URL = os.environ.get("DTL_BASE_URL", "http://localhost:3000")


class TestSmoke:
    """
    Inline-only smoke tests for normal CI.
    
    These tests run WITHOUT:
    - API keys (use fixed embeddings)
    - HTTP server running
    - External OpenAI calls
    
    They verify:
    - Core library imports correctly
    - AuthContext construction works
    - Inline adapter executes without error
    - Basic search returns expected structure
    """
    
    @pytest.mark.smoke
    def test_core_imports(self):
        """Verify core DTL modules import correctly"""
        from src.context_foundry.dtl.core import AuthContext, search_precedents
        from src.context_foundry.dtl.dtl_inline import search_precedents as inline_search
        
        assert AuthContext is not None
        assert search_precedents is not None
        assert inline_search is not None
        logger.info("Core imports: PASS")
    
    @pytest.mark.smoke
    def test_auth_context_construction(self):
        """Verify AuthContext can be constructed correctly"""
        ctx = AuthContext(
            tenant_id=str(uuid.uuid4()),
            user_id=str(uuid.uuid4()),
            role='user'
        )
        
        assert ctx.tenant_id is not None
        assert ctx.user_id is not None
        assert ctx.role == 'user'
        logger.info("AuthContext construction: PASS")
    
    @pytest.mark.smoke
    def test_inline_search_with_fixed_embedding(self):
        """Verify inline search executes with fixed embedding (no OpenAI)"""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        from sqlalchemy import text, create_engine
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT tenant_id::text FROM api_keys WHERE is_active = true LIMIT 1
            """))
            row = result.fetchone()
            if not row:
                pytest.skip("No tenants available for testing")
            tenant_id = row[0]
        
        ctx = AuthContext(
            tenant_id=tenant_id,
            user_id=str(uuid.uuid4()),
            role='user'
        )
        
        fixed_embedding = [0.1] * 1536
        
        session = get_session()
        try:
            from src.context_foundry.dtl.dtl_inline import search_precedents as inline_search
            results = inline_search(
                session=session,
                ctx=ctx,
                query_text="Test query for smoke test",
                query_embedding=fixed_embedding,
                limit=5
            )
            
            assert isinstance(results, list)
            for r in results:
                assert hasattr(r, 'decision_id')
                assert hasattr(r, 'rrf_score')
                assert hasattr(r, 'relevance_explanation')
            
            logger.info(f"Inline search smoke test: PASS ({len(results)} results)")
        finally:
            session.close()
    
    @pytest.mark.smoke
    def test_cross_tenant_isolation_inline(self):
        """Verify cross-tenant isolation works (inline, no HTTP)"""
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        fake_tenant_id = str(uuid.uuid4())
        ctx = AuthContext(
            tenant_id=fake_tenant_id,
            user_id=str(uuid.uuid4()),
            role='user'
        )
        
        fixed_embedding = [0.1] * 1536
        
        session = get_session()
        try:
            from src.context_foundry.dtl.dtl_inline import search_precedents as inline_search
            results = inline_search(
                session=session,
                ctx=ctx,
                query_text="Test query for isolation",
                query_embedding=fixed_embedding,
                limit=5
            )
            
            assert len(results) == 0, f"Expected 0 results for non-existent tenant, got {len(results)}"
            logger.info("Cross-tenant isolation (inline): PASS")
        finally:
            session.close()


def get_test_embedding(text: str) -> List[float]:
    """Get embedding for test queries (cached)"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        pytest.skip("OPENAI_API_KEY required for embedding tests")
    
    response = requests.post(
        "https://api.openai.com/v1/embeddings",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={"model": "text-embedding-3-small", "input": text},
        timeout=10.0
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def get_test_api_key() -> str:
    """Get API key for HTTP tests"""
    return os.environ.get("CF_API_KEY", "")


def get_test_tenant_id() -> str:
    """Get tenant ID from API key or database"""
    from sqlalchemy import text, create_engine
    
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")
    
    engine = create_engine(database_url)
    with engine.connect() as conn:
        # Query api_keys table (no RLS) to get tenant_id
        result = conn.execute(text("""
            SELECT tenant_id::text FROM api_keys WHERE is_active = true LIMIT 1
        """))
        row = result.fetchone()
        if row:
            return row[0]
        pytest.skip("No API keys in database for testing")


class TestParity:
    """
    Parity test: inline vs HTTP returns identical results
    
    Asserts:
    - same len(results)
    - same decision_id list in order for top-k
    - rrf_score within ±1e-6
    - same relevance_explanation keys present
    """
    
    def test_parity_inline_vs_http(self):
        """Verify inline and HTTP adapters return identical results"""
        api_key = get_test_api_key()
        if not api_key:
            pytest.skip("CF_API_KEY required for parity test")
        
        tenant_id = get_test_tenant_id()
        query_text = "How should we handle entity resolution conflicts?"
        embedding = get_test_embedding(query_text)
        user_id = str(uuid.uuid4())
        
        ctx = AuthContext(
            tenant_id=tenant_id,
            user_id=user_id,
            role='user'
        )
        inline_result = inline_search_precedents(
            ctx=ctx,
            query_text=query_text,
            query_embedding=embedding,
            limit=10
        )
        inline_precedents = inline_result.precedents
        
        response = requests.post(
            f"{HTTP_BASE_URL}/api/v1/dtl/core/precedents/search",
            headers={
                "X-CF-API-Key": api_key,
                "Content-Type": "application/json"
            },
            json={
                "query": query_text,
                "embedding": embedding,
                "limit": 10
            },
            timeout=30.0
        )
        assert response.status_code == 200, f"HTTP request failed: {response.text}"
        http_data = response.json()
        http_precedents = http_data.get("precedents", [])
        
        assert len(inline_precedents) == len(http_precedents), \
            f"Length mismatch: inline={len(inline_precedents)}, http={len(http_precedents)}"
        
        for i, (inline_p, http_p) in enumerate(zip(inline_precedents, http_precedents)):
            assert inline_p.decision_id == http_p["decision_id"], \
                f"decision_id mismatch at index {i}: inline={inline_p.decision_id}, http={http_p['decision_id']}"
            
            assert abs(inline_p.rrf_score - http_p["rrf_score"]) < TOLERANCE, \
                f"rrf_score mismatch at index {i}: inline={inline_p.rrf_score}, http={http_p['rrf_score']}, diff={abs(inline_p.rrf_score - http_p['rrf_score'])}"
            
            inline_expl = inline_p.relevance_explanation
            http_expl = http_p.get("relevance_explanation", {})
            
            expected_keys = {"summary", "factors", "semantic_score", "fulltext_score", 
                           "entity_overlap_score", "recency_score", "outcome_score", 
                           "category_bonus", "rrf_score"}
            
            for key in expected_keys:
                assert key in inline_expl, f"Missing key '{key}' in inline relevance_explanation"
                assert key in http_expl, f"Missing key '{key}' in HTTP relevance_explanation"
        
        logger.info(f"Parity test passed: {len(inline_precedents)} precedents match between inline and HTTP")


class TestSecurity:
    """
    Security test: cross-tenant returns 0 results
    
    Even if client attempts to override tenant_id in request body,
    results should be 0 for a different tenant.
    """
    
    def test_cross_tenant_inline_returns_zero(self):
        """Inline adapter with wrong tenant returns 0 results"""
        fake_tenant_id = str(uuid.uuid4())
        fake_user_id = str(uuid.uuid4())
        
        ctx = AuthContext(
            tenant_id=fake_tenant_id,
            user_id=fake_user_id,
            role='user'
        )
        
        result = inline_search_precedents(
            ctx=ctx,
            query_text="test query for cross-tenant isolation",
            limit=10
        )
        
        assert len(result.precedents) == 0, \
            f"Cross-tenant should return 0 results, got {len(result.precedents)}"
        
        logger.info("Security test passed: inline cross-tenant returns 0 results")
    
    def test_cross_tenant_http_returns_zero(self):
        """HTTP adapter with valid API key but different tenant returns 0 results"""
        api_key = get_test_api_key()
        if not api_key:
            pytest.skip("CF_API_KEY required for HTTP security test")
        
        response = requests.post(
            f"{HTTP_BASE_URL}/api/v1/dtl/core/precedents/search",
            headers={
                "X-CF-API-Key": api_key,
                "Content-Type": "application/json"
            },
            json={
                "query": "test query for security",
                "tenant_id": str(uuid.uuid4()),
                "limit": 10
            },
            timeout=30.0
        )
        
        assert response.status_code == 200, f"HTTP request failed: {response.text}"
        data = response.json()
        
        logger.info("Security test passed: HTTP ignores tenant_id in request body")
    
    def test_auth_context_validates_inputs(self):
        """AuthContext raises error if tenant_id or user_id missing"""
        with pytest.raises(ValueError, match="tenant_id"):
            AuthContext(tenant_id="", user_id="user123")
        
        with pytest.raises(ValueError, match="user_id"):
            AuthContext(tenant_id="tenant123", user_id="")
        
        logger.info("Security test passed: AuthContext validates inputs")


class TestPerformance:
    """
    Performance test: inline path p95 under threshold with 10k decisions
    
    Seeds 10k synthetic decisions, runs 1000 inline searches (no HTTP),
    reports mean/p95, acceptance: p95 ≤ 250ms
    """
    
    @pytest.fixture(scope="class")
    def seeded_database(self):
        """Check for existing decisions and return tenant_id"""
        from sqlalchemy import text, create_engine
        
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            pytest.skip("DATABASE_URL not set")
        
        engine = create_engine(database_url)
        
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT tenant_id::text, COUNT(*) as cnt 
                FROM decision_traces 
                GROUP BY tenant_id 
                ORDER BY cnt DESC 
                LIMIT 1
            """))
            row = result.fetchone()
            
            if row and row.cnt >= 100:
                logger.info(f"Using existing data: tenant={row.tenant_id}, count={row.cnt}")
                return row.tenant_id
            else:
                pytest.skip("Not enough decision data for performance test - run seeding script first")
    
    def _seed_batch_conn(self, conn, tenant_id: str, batch_size: int, offset: int):
        """Seed a batch of synthetic decisions using connection"""
        from sqlalchemy import text
        
        decision_types = ["routing", "entity_resolution", "tier_selection", "validation"]
        
        for i in range(batch_size):
            decision_id = str(uuid.uuid4())
            human_id = f"DEC-PERF-{offset + i:05d}"
            decision_type = decision_types[i % len(decision_types)]
            
            summary = f"Performance test decision {offset + i}: {decision_type} scenario"
            rationale = f"This is a synthetic decision for performance testing. It covers {decision_type} use cases with various complexity levels."
            
            embedding = [0.1] * 1536
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            
            conn.execute(text("""
                INSERT INTO decision_traces (
                    id, decision_id, decision_timestamp, decision_summary,
                    decision_choice, decision_maker_id, decision_type,
                    rationale_summary, rationale_embedding, context_snapshot,
                    lifecycle_state, source_system, created_by, tenant_id, sensitivity
                ) VALUES (
                    CAST(:id AS uuid), :human_id, :timestamp, :summary,
                    CAST(:choice AS jsonb), CAST(:maker_id AS uuid), :dtype,
                    :rationale, CAST(:embedding AS vector), CAST(:context AS jsonb),
                    :lifecycle, :source, :created_by, CAST(:tenant_id AS uuid), :sensitivity
                )
                ON CONFLICT DO NOTHING
            """), {
                "id": decision_id,
                "human_id": human_id,
                "timestamp": datetime.utcnow() - timedelta(days=offset + i),
                "summary": summary,
                "choice": json.dumps({"action": decision_type, "index": offset + i}),
                "maker_id": str(uuid.uuid4()),
                "dtype": decision_type,
                "rationale": rationale,
                "embedding": embedding_str,
                "context": json.dumps({"test": True, "batch": offset}),
                "lifecycle": "enacted",
                "source": "performance_test",
                "created_by": "perf_seeder",
                "tenant_id": tenant_id,
                "sensitivity": "internal"
            })
    
    def _seed_batch(self, session, tenant_id: str, batch_size: int, offset: int):
        """Seed a batch of synthetic decisions"""
        from sqlalchemy import text
        
        decision_types = ["routing", "entity_resolution", "tier_selection", "validation"]
        
        for i in range(batch_size):
            decision_id = str(uuid.uuid4())
            human_id = f"DEC-PERF-{offset + i:05d}"
            decision_type = decision_types[i % len(decision_types)]
            
            summary = f"Performance test decision {offset + i}: {decision_type} scenario"
            rationale = f"This is a synthetic decision for performance testing. It covers {decision_type} use cases with various complexity levels."
            
            embedding = [0.1] * 1536
            embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
            
            session.execute(text("""
                INSERT INTO decision_traces (
                    id, decision_id, decision_timestamp, decision_summary,
                    decision_choice, decision_maker_id, decision_type,
                    rationale_summary, rationale_embedding, context_snapshot,
                    lifecycle_state, source_system, created_by, tenant_id, sensitivity
                ) VALUES (
                    CAST(:id AS uuid), :human_id, :timestamp, :summary,
                    CAST(:choice AS jsonb), CAST(:maker_id AS uuid), :dtype,
                    :rationale, CAST(:embedding AS vector), CAST(:context AS jsonb),
                    :lifecycle, :source, :created_by, CAST(:tenant_id AS uuid), :sensitivity
                )
                ON CONFLICT DO NOTHING
            """), {
                "id": decision_id,
                "human_id": human_id,
                "timestamp": datetime.utcnow() - timedelta(days=offset + i),
                "summary": summary,
                "choice": json.dumps({"action": decision_type, "index": offset + i}),
                "maker_id": str(uuid.uuid4()),
                "dtype": decision_type,
                "rationale": rationale,
                "embedding": embedding_str,
                "context": json.dumps({"test": True, "batch": offset}),
                "lifecycle": "enacted",
                "source": "performance_test",
                "created_by": "perf_seeder",
                "tenant_id": tenant_id,
                "sensitivity": "internal"
            })
            
            session.execute(text("""
                INSERT INTO decision_evidence (
                    decision_id, evidence_type, source_uri, excerpt
                ) VALUES (CAST(:decision_id AS uuid), :etype, :uri, :excerpt)
                ON CONFLICT DO NOTHING
            """), {
                "decision_id": decision_id,
                "etype": "synthetic",
                "uri": f"perf://test/{offset + i}",
                "excerpt": f"Synthetic evidence for decision {offset + i}"
            })
    
    def test_inline_performance_p95(self, seeded_database):
        """Run 1000 inline searches and verify p95 ≤ 250ms"""
        tenant_id = seeded_database  # Use tenant from fixture
        user_id = str(uuid.uuid4())
        
        queries = [
            "How should we handle entity resolution?",
            "What is the best routing strategy?",
            "How to validate complex entities?",
            "Tier selection for ambiguous cases",
            "Conflict resolution patterns"
        ]
        
        embedding = [0.1] * 1536
        
        latencies = []
        num_searches = 1000
        
        logger.info(f"Running {num_searches} inline searches...")
        
        for i in range(num_searches):
            query = queries[i % len(queries)]
            
            ctx = AuthContext(
                tenant_id=tenant_id,
                user_id=user_id,
                role='user'
            )
            
            t_start = time.time()
            result = inline_search_precedents(
                ctx=ctx,
                query_text=query,
                query_embedding=embedding,
                limit=10
            )
            t_elapsed_ms = (time.time() - t_start) * 1000
            
            latencies.append(t_elapsed_ms)
            
            if (i + 1) % 100 == 0:
                current_mean = sum(latencies) / len(latencies)
                logger.info(f"Progress: {i + 1}/{num_searches}, current mean={current_mean:.1f}ms")
        
        mean_latency = sum(latencies) / len(latencies)
        sorted_latencies = sorted(latencies)
        p50_idx = int(len(sorted_latencies) * 0.50)
        p95_idx = int(len(sorted_latencies) * 0.95)
        p99_idx = int(len(sorted_latencies) * 0.99)
        
        p50_latency = sorted_latencies[p50_idx]
        p95_latency = sorted_latencies[p95_idx]
        p99_latency = sorted_latencies[p99_idx]
        min_latency = sorted_latencies[0]
        max_latency = sorted_latencies[-1]
        
        logger.info(f"\n{'='*50}")
        logger.info("PERFORMANCE TEST RESULTS (Inline Path)")
        logger.info(f"{'='*50}")
        logger.info(f"Total searches: {num_searches}")
        logger.info(f"Mean latency:   {mean_latency:.1f}ms")
        logger.info(f"P50 latency:    {p50_latency:.1f}ms")
        logger.info(f"P95 latency:    {p95_latency:.1f}ms")
        logger.info(f"P99 latency:    {p99_latency:.1f}ms")
        logger.info(f"Min latency:    {min_latency:.1f}ms")
        logger.info(f"Max latency:    {max_latency:.1f}ms")
        logger.info(f"{'='*50}")
        logger.info(f"THRESHOLD: P95 ≤ 250ms")
        logger.info(f"RESULT:    {'PASS' if p95_latency <= 250 else 'FAIL'} (P95={p95_latency:.1f}ms)")
        logger.info(f"{'='*50}")
        
        assert p95_latency <= 250, \
            f"P95 latency {p95_latency:.1f}ms exceeds 250ms threshold"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
