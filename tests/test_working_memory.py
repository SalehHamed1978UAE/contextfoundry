"""Tests for Working Memory (Gap 1)."""

import asyncio
from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio

from src.memory.working_memory import WorkingMemory


SESSION_ID = uuid4()


@pytest_asyncio.fixture()
async def wm(initialized_db):
    """WorkingMemory backed by real DB + Redis, with table created."""
    redis = await initialized_db.get_redis_client()
    mem = WorkingMemory(initialized_db, redis_client=redis, ttl_seconds=3600)
    await mem.ensure_table()

    yield mem

    # Cleanup this session's rows
    async with initialized_db.get_postgres_connection() as conn:
        await conn.execute(
            "DELETE FROM working_memory WHERE session_id = $1", SESSION_ID
        )
    # Flush Redis keys for this session
    if redis:
        try:
            cursor = 0
            while True:
                cursor, keys = await redis.scan(
                    cursor, match=f"wm:{SESSION_ID}:*", count=100
                )
                if keys:
                    await redis.delete(*keys)
                if cursor == 0:
                    break
        except Exception:
            pass


@pytest.mark.asyncio
async def test_put_and_get(wm):
    await wm.put(SESSION_ID, "step_result", {"answer": 42})
    result = await wm.get(SESSION_ID, "step_result")
    assert result == {"answer": 42}


@pytest.mark.asyncio
async def test_get_nonexistent(wm):
    result = await wm.get(SESSION_ID, "does_not_exist")
    assert result is None


@pytest.mark.asyncio
async def test_get_all_session(wm):
    await wm.put(SESSION_ID, "k1", "v1", agent="agent_a", step=0)
    await wm.put(SESSION_ID, "k2", "v2", agent="agent_b", step=1)
    items = await wm.get_all(SESSION_ID)
    keys = {item["key"] for item in items}
    assert "k1" in keys
    assert "k2" in keys
    assert len(items) >= 2


@pytest.mark.asyncio
async def test_upsert_overwrites(wm):
    await wm.put(SESSION_ID, "counter", 1)
    await wm.put(SESSION_ID, "counter", 2)
    result = await wm.get(SESSION_ID, "counter")
    assert result == 2


@pytest.mark.asyncio
async def test_clear_session(wm):
    await wm.put(SESSION_ID, "a", 1)
    await wm.put(SESSION_ID, "b", 2)
    deleted = await wm.clear_session(SESSION_ID)
    assert deleted >= 2
    assert await wm.get(SESSION_ID, "a") is None
    assert await wm.get(SESSION_ID, "b") is None


@pytest.mark.asyncio
async def test_cleanup_expired(wm):
    # Insert with very short TTL
    short_wm = WorkingMemory(wm.db, redis_client=wm.redis, ttl_seconds=1)
    sid = uuid4()
    await short_wm.put(sid, "temp", "gone_soon")

    # Wait for expiry
    await asyncio.sleep(2)

    result = await short_wm.cleanup_expired()
    # cleanup_expired returns the DELETE result string
    assert result is not None

    # Value should be gone from PG (even without cleanup, the get filters by expires_at)
    val = await short_wm.get(sid, "temp")
    assert val is None

    # Final cleanup
    async with wm.db.get_postgres_connection() as conn:
        await conn.execute("DELETE FROM working_memory WHERE session_id = $1", sid)
