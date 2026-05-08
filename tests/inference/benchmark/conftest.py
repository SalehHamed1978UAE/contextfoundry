"""Benchmark fixtures — real Postgres + real Anthropic LLM.

Gated behind RUN_INFERENCE_BENCHMARKS=1 because each test costs real money
(N >= 5 adversary stances × multiple rounds × meta + planner + polarity per
evidence item ≈ 30-100 LLM calls per fact at Sonnet 4.5 prices).

Each test isolates state in a fresh tenant_id, seeds entities/relationships/
chunks, and rolls back on teardown.
"""
import os
import uuid
import pytest
from sqlalchemy import text

if not os.environ.get("RUN_INFERENCE_BENCHMARKS"):
    pytest.skip("Set RUN_INFERENCE_BENCHMARKS=1 to run (costs real Anthropic API calls).",
                allow_module_level=True)

from src.context_foundry.models.schema import SessionLocal
from src.context_foundry.inference.engine import FactEvaluator
from src.context_foundry.inference.llm.client import LLMClient


@pytest.fixture
def benchmark_session():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def benchmark_tenant(benchmark_session):
    """Per-test isolated tenant. Cleans up all rows on teardown."""
    tid = str(uuid.uuid4())
    yield tid
    for table in ("relationships", "entities", "document_chunks"):
        benchmark_session.execute(
            text(f"DELETE FROM {table} WHERE tenant_id = CAST(:t AS uuid)"),
            {"t": tid},
        )
    benchmark_session.commit()


@pytest.fixture
def benchmark_llm(benchmark_session):
    """Pinned to claude-sonnet-4-5 — env override doesn't apply."""
    return LLMClient(session=benchmark_session, pin_model=True)


def seed_entity(session, tenant_id: str, name: str, entity_type: str = "PERSON",
                lifecycle: str = "TRUSTED") -> str:
    eid = str(uuid.uuid4())
    session.execute(text("""
        INSERT INTO entities(id, name, lifecycle_state, properties, tenant_id, created_at)
        VALUES(CAST(:id AS uuid), :n, CAST(:ls AS lifecyclestate),
               CAST(:p AS json), CAST(:t AS uuid), NOW())
    """), {"id": eid, "n": name, "ls": lifecycle,
           "p": '{"entity_type": "' + entity_type + '"}', "t": tenant_id})
    return eid


def seed_chunk(session, tenant_id: str, document_id: str, text_content: str,
               chunk_index: int = 0) -> str:
    cid = str(uuid.uuid4())
    session.execute(text("""
        INSERT INTO document_chunks(id, document_id, tenant_id, chunk_index, text, created_at)
        VALUES(CAST(:id AS uuid), CAST(:d AS uuid), CAST(:t AS uuid),
               :i, :tx, NOW())
    """), {"id": cid, "d": document_id, "t": tenant_id,
           "i": chunk_index, "tx": text_content})
    return cid


def seed_relationship(session, tenant_id: str, source_id: str, target_id: str,
                      rel_type: str, chunk_id: str = None,
                      lifecycle: str = "TRUSTED") -> str:
    rid = str(uuid.uuid4())
    session.execute(text("""
        INSERT INTO relationships(id, source_id, target_id, relationship_type,
            lifecycle_state, source_chunk_id, tenant_id, created_at)
        VALUES(CAST(:id AS uuid), CAST(:s AS uuid), CAST(:tg AS uuid), :rt,
               CAST(:ls AS lifecyclestate),
               CAST(:cid AS uuid) IF :cid IS NOT NULL ELSE NULL,
               CAST(:t AS uuid), NOW())
    """) if False else text("""
        INSERT INTO relationships(id, source_id, target_id, relationship_type,
            lifecycle_state, source_chunk_id, tenant_id, created_at)
        VALUES(CAST(:id AS uuid), CAST(:s AS uuid), CAST(:tg AS uuid), :rt,
               CAST(:ls AS lifecyclestate),
               CASE WHEN :cid IS NULL THEN NULL ELSE CAST(:cid AS uuid) END,
               CAST(:t AS uuid), NOW())
    """), {"id": rid, "s": source_id, "tg": target_id, "rt": rel_type,
           "ls": lifecycle, "cid": chunk_id, "t": tenant_id})
    return rid
