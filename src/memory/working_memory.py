"""
Working Memory — per-session scratchpad for intermediate reasoning steps.

Provides a key-value store scoped by session_id with automatic TTL expiry.
Two-tier: Redis for hot reads, PostgreSQL for persistence.
"""

import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4


class WorkingMemory:
    """Per-session scratchpad with Redis caching and PG persistence."""

    def __init__(self, db_manager, redis_client=None, ttl_seconds: int = 3600):
        self.db = db_manager
        self.redis = redis_client
        self.ttl = ttl_seconds

    async def ensure_table(self) -> None:
        """Create the working_memory table if it doesn't exist."""
        async with self.db.get_postgres_connection() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS working_memory (
                    id UUID PRIMARY KEY,
                    session_id UUID NOT NULL,
                    key VARCHAR(255) NOT NULL,
                    value JSONB NOT NULL,
                    agent VARCHAR(100),
                    step_number INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    UNIQUE(session_id, key)
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_wm_session
                ON working_memory(session_id)
            """)

    def _redis_key(self, session_id: UUID, key: str) -> str:
        return f"wm:{session_id}:{key}"

    async def put(
        self,
        session_id: UUID,
        key: str,
        value: Any,
        agent: str = None,
        step: int = 0,
    ) -> None:
        """Store a value in working memory (upserts on session_id+key)."""
        expires_at = datetime.utcnow() + timedelta(seconds=self.ttl)
        value_json = json.dumps(value, default=str)

        # Write to PG
        async with self.db.get_postgres_connection() as conn:
            await conn.execute(
                """INSERT INTO working_memory
                       (id, session_id, key, value, agent, step_number, expires_at)
                   VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7)
                   ON CONFLICT (session_id, key) DO UPDATE
                   SET value = EXCLUDED.value,
                       agent = EXCLUDED.agent,
                       step_number = EXCLUDED.step_number,
                       expires_at = EXCLUDED.expires_at""",
                uuid4(),
                session_id,
                key,
                value_json,
                agent,
                step,
                expires_at,
            )

        # Write to Redis
        if self.redis:
            try:
                await self.redis.setex(
                    self._redis_key(session_id, key), self.ttl, value_json
                )
            except Exception:
                pass

    async def get(self, session_id: UUID, key: str) -> Optional[Any]:
        """Retrieve a value. Checks Redis first, falls back to PG."""
        # Tier 1: Redis
        if self.redis:
            try:
                cached = await self.redis.get(self._redis_key(session_id, key))
                if cached is not None:
                    return json.loads(cached)
            except Exception:
                pass

        # Tier 2: PG
        async with self.db.get_postgres_connection() as conn:
            row = await conn.fetchrow(
                """SELECT value FROM working_memory
                   WHERE session_id = $1 AND key = $2 AND expires_at > NOW()""",
                session_id,
                key,
            )
            if row:
                data = json.loads(row["value"])
                # Re-populate Redis
                if self.redis:
                    try:
                        await self.redis.setex(
                            self._redis_key(session_id, key),
                            self.ttl,
                            row["value"],
                        )
                    except Exception:
                        pass
                return data

        return None

    async def get_all(self, session_id: UUID) -> List[Dict]:
        """Retrieve all working memory entries for a session."""
        async with self.db.get_postgres_connection() as conn:
            rows = await conn.fetch(
                """SELECT key, value, agent, step_number, created_at
                   FROM working_memory
                   WHERE session_id = $1 AND expires_at > NOW()
                   ORDER BY step_number, created_at""",
                session_id,
            )
            return [
                {
                    "key": r["key"],
                    "value": json.loads(r["value"]),
                    "agent": r["agent"],
                    "step_number": r["step_number"],
                    "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                }
                for r in rows
            ]

    async def delete(self, session_id: UUID, key: str) -> None:
        """Delete a single key from working memory."""
        async with self.db.get_postgres_connection() as conn:
            await conn.execute(
                "DELETE FROM working_memory WHERE session_id = $1 AND key = $2",
                session_id,
                key,
            )
        if self.redis:
            try:
                await self.redis.delete(self._redis_key(session_id, key))
            except Exception:
                pass

    async def clear_session(self, session_id: UUID) -> int:
        """Clear all working memory for a session. Returns rows deleted."""
        async with self.db.get_postgres_connection() as conn:
            result = await conn.execute(
                "DELETE FROM working_memory WHERE session_id = $1",
                session_id,
            )
            count = int(result.split()[-1]) if result else 0

        # Clear Redis keys (best-effort scan)
        if self.redis:
            try:
                pattern = f"wm:{session_id}:*"
                cursor = 0
                while True:
                    cursor, keys = await self.redis.scan(cursor, match=pattern, count=100)
                    if keys:
                        await self.redis.delete(*keys)
                    if cursor == 0:
                        break
            except Exception:
                pass

        return count

    async def cleanup_expired(self) -> str:
        """Remove expired rows from PG."""
        async with self.db.get_postgres_connection() as conn:
            result = await conn.execute(
                "DELETE FROM working_memory WHERE expires_at < NOW()"
            )
            return result
