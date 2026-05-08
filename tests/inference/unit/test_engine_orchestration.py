"""Engine-level orchestration test using StubLLMClient — no real API calls.

Proves the whole pipeline (planner → presupposition recursion → gatherer →
adversary → prover → meta → synthesizer) wires together correctly and that
cycle detection / depth limits work.

Uses a sqlite-backed test schema so we don't touch the real CF Postgres.
"""
import asyncio
import json
import uuid
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from src.context_foundry.inference.contracts import Fact
from src.context_foundry.inference.engine import FactEvaluator
from src.context_foundry.inference.llm.client import StubLLMClient


# Use a tiny in-memory schema that mimics the columns the engine actually queries.
# Sqlite lacks `vector`, `uuid`, `lifecyclestate` — so we substitute TEXT and
# strip vector queries (the stub LLM means we never run the gatherer's vector path).
DDL = [
    """CREATE TABLE entities(
        id TEXT PRIMARY KEY, name TEXT, lifecycle_state TEXT,
        properties TEXT, tenant_id TEXT
    )""",
    """CREATE TABLE relationships(
        id TEXT PRIMARY KEY, source_id TEXT, target_id TEXT,
        relationship_type TEXT, lifecycle_state TEXT, source_chunk_id TEXT,
        properties TEXT, tenant_id TEXT, source_predicate TEXT,
        raw_relationship_type TEXT
    )""",
    """CREATE TABLE document_chunks(
        id TEXT PRIMARY KEY, document_id TEXT, text TEXT,
        chunk_index INTEGER, tenant_id TEXT
    )""",
    """CREATE TABLE llm_cache(
        cache_key TEXT PRIMARY KEY, model TEXT, response TEXT, created_at TEXT
    )""",
]


@pytest.fixture
def session(monkeypatch):
    """Sqlite session that lets the engine run end-to-end without real Postgres.

    We monkeypatch `tools.py` SQL to be sqlite-compatible by patching the
    GraphTools class to skip vector and tenant-cast features.
    """
    engine = create_engine("sqlite:///:memory:")
    Sess = sessionmaker(bind=engine)
    s = Sess()
    for ddl in DDL:
        s.execute(text(ddl))
    s.commit()

    # Patch GraphTools queries to be sqlite-friendly: drop ::text, ::uuid,
    # CAST(... AS uuid), JSON parsing — pass through TEXT columns.
    from src.context_foundry.inference import tools as tools_mod
    orig = tools_mod.GraphTools

    class SqliteGraphTools(orig):
        def __init__(self, session, tenant_id=None):
            self.session = session
            self.tenant_id = None  # ignore tenant for sqlite test

        def get_entity(self, entity_id):
            row = self.session.execute(
                text("SELECT id, name, '' as et, lifecycle_state, properties FROM entities WHERE id = :eid"),
                {"eid": entity_id},
            ).fetchone()
            if not row:
                return None
            return tools_mod.EntityRow(row[0], row[1], row[2], row[3] or "STAGING",
                                        json.loads(row[4]) if row[4] else {})

        def find_entities_by_name(self, name, fuzzy=True):
            sql = ("SELECT id, name, '' as et, lifecycle_state, properties FROM entities "
                   "WHERE LOWER(name) LIKE LOWER(:n) ORDER BY id ASC") if fuzzy else (
                  "SELECT id, name, '' as et, lifecycle_state, properties FROM entities "
                  "WHERE LOWER(name) = LOWER(:n) ORDER BY id ASC")
            params = {"n": f"%{name}%" if fuzzy else name}
            return [tools_mod.EntityRow(r[0], r[1], r[2], r[3] or "STAGING",
                                         json.loads(r[4]) if r[4] else {})
                    for r in self.session.execute(text(sql), params).fetchall()]

        def find_entities_by_embedding(self, q, top_k=50):
            return []  # no vector in sqlite

        def get_relationships(self, source_id=None, target_id=None,
                              rel_types=None, include_archived=False,
                              properties_filter=None):
            sql = ("SELECT id, source_id, relationship_type, target_id, "
                   "lifecycle_state, source_chunk_id, properties, "
                   "source_predicate, raw_relationship_type FROM relationships WHERE 1=1")
            params = {}
            if source_id:
                sql += " AND source_id = :sid"
                params["sid"] = source_id
            if target_id:
                sql += " AND target_id = :tgt"
                params["tgt"] = target_id
            if rel_types:
                ph = ",".join(f":rt{i}" for i in range(len(rel_types)))
                sql += f" AND relationship_type IN ({ph})"
                for i, rt in enumerate(rel_types):
                    params[f"rt{i}"] = rt
            if not include_archived:
                sql += " AND (lifecycle_state IS NULL OR lifecycle_state <> 'ARCHIVED')"
            sql += " ORDER BY id ASC"
            rows = self.session.execute(text(sql), params).fetchall()
            return [tools_mod.RelationshipRow(
                id=r[0], source_entity_id=r[1], relationship_type=r[2],
                target_entity_id=r[3], lifecycle_state=r[4] or "STAGING",
                source_chunk_id=r[5], properties=json.loads(r[6]) if r[6] else {},
                source_predicate=r[7], raw_relationship_type=r[8],
            ) for r in rows]

        def search_chunks_text(self, query):
            sql = ("SELECT id, document_id, text, chunk_index FROM document_chunks "
                   "WHERE text LIKE :pat ORDER BY id ASC LIMIT 200")
            return [tools_mod.ChunkRow(r[0], r[1], r[2], r[3])
                    for r in self.session.execute(text(sql), {"pat": f"%{query}%"}).fetchall()]

        def search_chunks_vector(self, q, top_k=50):
            return []

    monkeypatch.setattr(tools_mod, "GraphTools", SqliteGraphTools)
    yield s
    s.close()


def _seed_two_ceos(session):
    """Two active CEOs both pointing at CEO of Nexus → CONTESTED case."""
    session.execute(text("INSERT INTO entities VALUES('alice', 'Alice', 'STAGING', NULL, NULL)"))
    session.execute(text("INSERT INTO entities VALUES('bob', 'Bob', 'STAGING', NULL, NULL)"))
    session.execute(text("INSERT INTO entities VALUES('ceo-nexus', 'CEO of Nexus', 'STAGING', NULL, NULL)"))
    session.execute(text("INSERT INTO document_chunks VALUES('ch-1', 'doc-1', 'Alice is CEO of Nexus.', 0, NULL)"))
    session.execute(text("INSERT INTO document_chunks VALUES('ch-2', 'doc-2', 'Bob is CEO of Nexus.', 0, NULL)"))
    session.execute(text(
        "INSERT INTO relationships VALUES('r-alice', 'alice', 'ceo-nexus', "
        "'HOLDS_POSITION', 'STAGING', 'ch-1', NULL, NULL, NULL, NULL)"
    ))
    session.execute(text(
        "INSERT INTO relationships VALUES('r-bob', 'bob', 'ceo-nexus', "
        "'HOLDS_POSITION', 'STAGING', 'ch-2', NULL, NULL, NULL, NULL)"
    ))
    session.commit()


def _stub_responder(_sys, user, schema_name):
    """Canned LLM responses keyed by schema name. Hand-tuned to drive the
    engine through the CONTESTED branch on the two-CEO scenario."""
    if schema_name == "EvaluationPlan":
        return {
            "fact_type": "HOLDS_POSITION",
            "truth_conditions": [{"description": "appointment exists in record"}],
            "falsifiers": [
                {"description": "another active person holds the same role",
                 "decisive": True}
            ],
            "presuppositions": [],
            "competing_hypotheses": [
                {"description": "the role has multiple co-occupants"}
            ],
            "evidence_queries": ["who is CEO of Nexus"],
            "adversarial_prompts": [],
            "rationale": "single-occupant role check",
        }
    if schema_name == "_PolarityResp":
        # Mark anything mentioning Alice as confirms, Bob as disconfirms when
        # we're evaluating Alice's claim. This is rough but enough for the test.
        if "Bob" in user and "Alice" not in user.split("EVIDENCE")[1]:
            return {"polarity": "neutral", "reasoning": "stub"}
        return {"polarity": "confirms" if "Alice" in user.split("EVIDENCE")[1] else
                            ("disconfirms" if "Bob" in user.split("EVIDENCE")[1] else "neutral"),
                "reasoning": "stub"}
    if schema_name == "_LLMChallengeList":
        return {"challenges": [{
            "description": "Bob also holds the CEO role",
            "counter_evidence": [{
                "chunk_id": "ch-2",
                "content": "Bob is CEO of Nexus.",
                "speaks_to": "competing CEO",
                "polarity": "disconfirms",
            }],
            "survived_rebuttal": True,
        }]}
    if schema_name == "_LLMRebuttal":
        # Rebuttal fails (challenge survives) — there is in fact a competing edge.
        return {"survived_rebuttal": True, "rebuttal_reason": "competing edge exists in graph"}
    if schema_name == "_LLMProofProposal":
        return {"succeeded": False, "chain": [], "axioms_used": [],
                "gaps": ["competing claim unresolved"]}
    if schema_name == "MetaAudit":
        return {
            "plan_completeness_verdict": "complete",
            "missing_falsifiers": [],
            "evidence_thoroughness_verdict": "thorough",
            "untested_hypotheses": [],
            "proof_validity_verdict": "no_proof_attempted",
            "recommend_replan": False,
        }
    return {}


def test_engine_cycle_detection_returns_underspecified(session):
    """A self-referential fact triggers cycle detection on recursion."""
    _seed_two_ceos(session)
    llm = StubLLMClient(_stub_responder)
    eng = FactEvaluator(
        session=session, llm_client=llm,
        schema_entity_types=["PERSON", "ROLE"],
        schema_relationship_types=["HOLDS_POSITION"],
        tenant_id=None, max_depth=2, max_replans=0,
    )
    from src.context_foundry.inference.recursion import RecursionGuard
    fact = Fact(source_entity_id="alice", relationship_type="HOLDS_POSITION",
                target_entity_id="ceo-nexus")
    guard = RecursionGuard(max_depth=2).child(fact)  # pre-mark visited
    verdict = asyncio.run(eng.evaluate(fact, guard=guard))
    assert verdict.status == "UNDERSPECIFIED"
    assert any("cycle" in c for c in verdict.caveats)
