"""
Semantic Cache for Context Foundry

Two-tier caching:
  Tier 1 - Redis exact match (SHA-256 hash of normalized query)
  Tier 2 - PostgreSQL hash match (Redis expired but PG still has it)
  Tier 3 - pgvector semantic match (cosine similarity >= threshold)
"""

import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from uuid import uuid4

from src.config import settings


class SemanticCache:
    """Two-tier cache: Redis exact-match + pgvector semantic similarity."""

    def __init__(self, db_manager, embedding_service, redis_client=None):
        self.db = db_manager
        self.embedding_service = embedding_service
        self.redis = redis_client
        self.ttl = settings.cache_ttl_seconds
        self.similarity_threshold = settings.cache_similarity_threshold

    async def ensure_table(self):
        """Create the query_cache table if it doesn't exist."""
        async with self.db.get_postgres_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS query_cache (
                    id UUID PRIMARY KEY,
                    query_text TEXT NOT NULL,
                    query_hash VARCHAR(64) NOT NULL,
                    query_embedding vector(384),
                    response_json JSONB NOT NULL,
                    confidence FLOAT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)
            # Index on hash for fast exact lookups
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_cache_hash
                ON query_cache (query_hash)
            """)

    @staticmethod
    def _normalize(query: str) -> str:
        return query.strip().lower()

    @staticmethod
    def _hash(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    async def get(self, query: str) -> Optional[Dict[str, Any]]:
        """Three-tier lookup: Redis exact -> PG exact -> pgvector semantic."""
        if not settings.cache_enabled:
            return None

        normalized = self._normalize(query)
        query_hash = self._hash(normalized)

        # Tier 1: Redis exact match
        if self.redis:
            try:
                cached = await self.redis.get(f"cache:{query_hash}")
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        # Tier 2: PG hash match (Redis may have expired but PG still has it)
        async with self.db.get_postgres_connection() as conn:
            row = await conn.fetchrow(
                """SELECT response_json FROM query_cache
                   WHERE query_hash = $1 AND expires_at > NOW()
                   ORDER BY created_at DESC LIMIT 1""",
                query_hash,
            )
            if row:
                data = json.loads(row["response_json"])
                # Re-populate Redis
                if self.redis:
                    try:
                        await self.redis.setex(
                            f"cache:{query_hash}", self.ttl, row["response_json"]
                        )
                    except Exception:
                        pass
                return data

        # Tier 3: pgvector semantic match
        try:
            embedding = await self.embedding_service.embed_text(normalized)
            embedding_str = "[" + ",".join(map(str, embedding)) + "]"

            async with self.db.get_postgres_connection() as conn:
                row = await conn.fetchrow(
                    """SELECT response_json,
                              1 - (query_embedding <=> $1::vector) AS similarity
                       FROM query_cache
                       WHERE expires_at > NOW()
                         AND query_embedding IS NOT NULL
                       ORDER BY query_embedding <=> $1::vector
                       LIMIT 1""",
                    embedding_str,
                )
                if row and float(row["similarity"]) >= self.similarity_threshold:
                    return json.loads(row["response_json"])
        except Exception:
            pass

        return None

    async def put(
        self,
        query: str,
        response_dict: Dict[str, Any],
        confidence: float = None,
    ):
        """Store in both Redis and PG."""
        if not settings.cache_enabled:
            return

        normalized = self._normalize(query)
        query_hash = self._hash(normalized)
        response_json = json.dumps(response_dict, default=str)
        expires_at = datetime.utcnow() + timedelta(seconds=self.ttl)

        # Redis
        if self.redis:
            try:
                await self.redis.setex(
                    f"cache:{query_hash}", self.ttl, response_json
                )
            except Exception:
                pass

        # PG with embedding
        try:
            embedding = await self.embedding_service.embed_text(normalized)
            embedding_str = "[" + ",".join(map(str, embedding)) + "]"

            async with self.db.get_postgres_connection() as conn:
                await conn.execute(
                    """INSERT INTO query_cache
                       (id, query_text, query_hash, query_embedding,
                        response_json, confidence, expires_at)
                       VALUES ($1, $2, $3, $4::vector, $5::jsonb, $6, $7)""",
                    uuid4(),
                    normalized,
                    query_hash,
                    embedding_str,
                    response_json,
                    confidence,
                    expires_at,
                )
        except Exception:
            pass

    async def cleanup_expired(self):
        """Delete expired rows from PG."""
        async with self.db.get_postgres_connection() as conn:
            result = await conn.execute(
                "DELETE FROM query_cache WHERE expires_at < NOW()"
            )
            return result
