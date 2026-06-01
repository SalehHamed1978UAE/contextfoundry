"""
Shared test fixtures for Context Foundry tests.

Uses real Docker PostgreSQL and Redis instances.
All fixtures are function-scoped to avoid event-loop mismatches.
The embedding model is cached in a module global (not async, loop-safe).
"""

from uuid import UUID

import pytest
import pytest_asyncio
import asyncpg
import redis.asyncio as aioredis

from src.config import settings
from src.utils.embeddings import EmbeddingService, DocumentEmbedder


# Fixed UUIDs for deterministic assertions
ENTITY_1_ID = UUID("00000000-0000-0000-0000-000000000001")
ENTITY_2_ID = UUID("00000000-0000-0000-0000-000000000002")
ENTITY_3_ID = UUID("00000000-0000-0000-0000-000000000003")
REL_1_ID = UUID("00000000-0000-0000-0000-0000000000a1")
DOC_CHUNK_1_ID = UUID("00000000-0000-0000-0000-0000000000b1")
DOC_CHUNK_2_ID = UUID("00000000-0000-0000-0000-0000000000b2")

# Module-level cache for the embedding model (not async, safe across loops)
_embedding_service_singleton = None


def _get_embedding_service():
    global _embedding_service_singleton
    if _embedding_service_singleton is None:
        _embedding_service_singleton = EmbeddingService(use_ollama=False)
    return _embedding_service_singleton


class TestDBManager:
    """Lightweight DB manager for tests that creates its own pool."""

    def __init__(self, pg_pool, redis_client):
        self.pg_pool = pg_pool
        self.redis_client = redis_client

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def get_postgres_connection(self):
        async with self.pg_pool.acquire() as conn:
            yield conn

    async def get_redis_client(self):
        return self.redis_client

    async def close(self):
        await self.pg_pool.close()
        if self.redis_client:
            await self.redis_client.aclose()


@pytest_asyncio.fixture()
async def initialized_db():
    """Create a test-only DB pool (fresh per test, same event loop)."""
    pg_pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=1,
        max_size=5,
        command_timeout=60,
    )
    redis_client = await aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
    mgr = TestDBManager(pg_pool, redis_client)
    yield mgr
    await mgr.close()


@pytest_asyncio.fixture()
async def embedding_service():
    """Local BGE-small embedding model (cached globally, returned per-test)."""
    return _get_embedding_service()


@pytest_asyncio.fixture()
async def document_embedder(initialized_db, embedding_service):
    """DocumentEmbedder backed by the real DB."""
    return DocumentEmbedder(initialized_db, embedding_service)


@pytest_asyncio.fixture()
async def test_app():
    """httpx AsyncClient talking to the live server at localhost:8000."""
    import httpx

    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        yield client


@pytest_asyncio.fixture()
async def seed_test_data(initialized_db, embedding_service):
    """
    Insert 3 entities, 1 relationship, 2 document chunks with embeddings.
    Cleans up after the test.
    """
    # Cleanup first in case of leftover data from a previous failed run
    async with initialized_db.get_postgres_connection() as conn:
        await conn.execute(
            "DELETE FROM relationship_metadata WHERE relationship_id = $1", REL_1_ID
        )
        await conn.execute(
            "DELETE FROM graph_lifecycle WHERE entity_id = ANY($1::uuid[])",
            [ENTITY_1_ID, ENTITY_2_ID, ENTITY_3_ID],
        )
        await conn.execute(
            "DELETE FROM document_embeddings WHERE id = ANY($1::uuid[])",
            [DOC_CHUNK_1_ID, DOC_CHUNK_2_ID],
        )

    async with initialized_db.get_postgres_connection() as conn:
        # Entities (canonical_name is stored in extracted_text column)
        await conn.execute("""
            INSERT INTO graph_lifecycle
                (entity_id, entity_type, lifecycle_state,
                 confidence, extracted_text, source_document_id)
            VALUES
                ($1, 'Service', 'TRUSTED', 0.92,
                 'PaymentService', 'doc-1'),
                ($2, 'Team', 'TRUSTED', 0.88,
                 'Platform', 'doc-1'),
                ($3, 'Database', 'STAGING', 0.55,
                 'OrdersDB', 'doc-2')
        """, ENTITY_1_ID, ENTITY_2_ID, ENTITY_3_ID)

        # Relationship
        await conn.execute("""
            INSERT INTO relationship_metadata
                (relationship_id, source_entity_id, target_entity_id,
                 relationship_type, confidence, lifecycle_state)
            VALUES ($1, $2, $3, 'OWNS', 0.85, 'TRUSTED')
        """, REL_1_ID, ENTITY_2_ID, ENTITY_1_ID)

        # Document chunks with embeddings
        emb1 = await embedding_service.embed_text("PaymentService processes credit card transactions")
        emb2 = await embedding_service.embed_text("OrdersDB schema includes orders and line_items tables")
        emb1_str = "[" + ",".join(map(str, emb1)) + "]"
        emb2_str = "[" + ",".join(map(str, emb2)) + "]"

        await conn.execute("""
            INSERT INTO document_embeddings
                (id, document_id, document_type, document_title,
                 chunk_text, chunk_index, embedding)
            VALUES
                ($1, 'doc-1', 'runbook', 'Payment Runbook',
                 'PaymentService processes credit card transactions via Stripe API.',
                 0, $3::vector),
                ($2, 'doc-1', 'runbook', 'Payment Runbook',
                 'In case of failure, retry with exponential backoff up to 3 times.',
                 1, $4::vector)
        """, DOC_CHUNK_1_ID, DOC_CHUNK_2_ID, emb1_str, emb2_str)

    yield  # test runs here

    # Cleanup
    async with initialized_db.get_postgres_connection() as conn:
        await conn.execute(
            "DELETE FROM relationship_metadata WHERE relationship_id = $1", REL_1_ID
        )
        await conn.execute(
            "DELETE FROM graph_lifecycle WHERE entity_id = ANY($1::uuid[])",
            [ENTITY_1_ID, ENTITY_2_ID, ENTITY_3_ID],
        )
        await conn.execute(
            "DELETE FROM document_embeddings WHERE id = ANY($1::uuid[])",
            [DOC_CHUNK_1_ID, DOC_CHUNK_2_ID],
        )
