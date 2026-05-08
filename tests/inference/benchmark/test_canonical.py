"""4 canonical benchmark tests from the spec.

Each test is end-to-end: real Postgres seeding, real Anthropic LLM. Gated
behind RUN_INFERENCE_BENCHMARKS=1 (see conftest.py).
"""
import asyncio
import pytest
from src.context_foundry.inference.contracts import Fact
from src.context_foundry.inference.engine import FactEvaluator
from .conftest import seed_entity, seed_chunk, seed_relationship


SCHEMA_ETS = ["PERSON", "ROLE", "ORG", "DOCUMENT"]
SCHEMA_RTS = ["HOLDS_POSITION", "AFFILIATED_WITH", "REPLACED",
              "REPORTS_TO", "FORMERLY_HELD"]


def _engine(benchmark_session, benchmark_llm, benchmark_tenant):
    return FactEvaluator(
        session=benchmark_session, llm_client=benchmark_llm,
        schema_entity_types=SCHEMA_ETS, schema_relationship_types=SCHEMA_RTS,
        tenant_id=benchmark_tenant, max_depth=3, max_replans=1,
    )


def test_canonical_1_victoria_chen_is_ceo(benchmark_session, benchmark_tenant, benchmark_llm):
    """Strong evidence with archival of prior CEO → PROVEN/STRONGLY_SUPPORTED."""
    s, t = benchmark_session, benchmark_tenant
    chen = seed_entity(s, t, "Victoria Chen")
    martinez = seed_entity(s, t, "Robert Martinez")
    ceo_role = seed_entity(s, t, "CEO of Nexus", entity_type="ROLE")
    ch1 = seed_chunk(s, t, "doc-board", "Board minutes: CEO Chen presented Q3 results.")
    ch2 = seed_chunk(s, t, "doc-allhands",
                      "All-hands memo from CEO Victoria Chen on company strategy.")
    seed_relationship(s, t, chen, ceo_role, "HOLDS_POSITION", chunk_id=ch1)
    seed_relationship(s, t, martinez, ceo_role, "HOLDS_POSITION", chunk_id=None,
                      lifecycle="ARCHIVED")
    s.commit()

    eng = _engine(s, benchmark_llm, t)
    fact = Fact(source_entity_id=chen, relationship_type="HOLDS_POSITION",
                target_entity_id=ceo_role, tenant_id=t,
                natural_language="Victoria Chen is CEO of Nexus")
    verdict = asyncio.run(eng.evaluate(fact))
    assert verdict.status in ("PROVEN", "STRONGLY_SUPPORTED"), \
        f"got {verdict.status}; trace={verdict.trace}"
    assert verdict.surviving_challenges == [], \
        f"expected no surviving challenges, got {[c.description for c in verdict.surviving_challenges]}"


def test_canonical_2_robert_kim_president_nds(benchmark_session, benchmark_tenant, benchmark_llm):
    s, t = benchmark_session, benchmark_tenant
    kim = seed_entity(s, t, "Robert Kim")
    anderson = seed_entity(s, t, "Thomas Anderson")
    role = seed_entity(s, t, "President of NDS", entity_type="ROLE")
    ch1 = seed_chunk(s, t, "doc-org",
                      "Organizational announcement: Robert Kim named President of NDS, "
                      "replacing Thomas Anderson effective Q1.")
    seed_relationship(s, t, kim, role, "HOLDS_POSITION", chunk_id=ch1)
    seed_relationship(s, t, anderson, role, "HOLDS_POSITION", lifecycle="ARCHIVED")
    s.commit()

    eng = _engine(s, benchmark_llm, t)
    fact = Fact(source_entity_id=kim, relationship_type="HOLDS_POSITION",
                target_entity_id=role, tenant_id=t,
                natural_language="Robert Kim is President of NDS")
    verdict = asyncio.run(eng.evaluate(fact))
    assert verdict.status in ("PROVEN", "STRONGLY_SUPPORTED"), \
        f"got {verdict.status}; trace={verdict.trace}"


def test_canonical_3_jennifer_walsh_ciso(benchmark_session, benchmark_tenant, benchmark_llm):
    s, t = benchmark_session, benchmark_tenant
    walsh = seed_entity(s, t, "Jennifer Walsh")
    kim = seed_entity(s, t, "Robert Kim")
    role = seed_entity(s, t, "CISO", entity_type="ROLE")
    ch1 = seed_chunk(s, t, "doc-orgtable",
                      "Organizational announcement table: CISO — Jennifer Walsh "
                      "(Former: Robert Kim).")
    seed_relationship(s, t, walsh, role, "HOLDS_POSITION", chunk_id=ch1)
    seed_relationship(s, t, kim, role, "HOLDS_POSITION", lifecycle="ARCHIVED")
    s.commit()

    eng = _engine(s, benchmark_llm, t)
    fact = Fact(source_entity_id=walsh, relationship_type="HOLDS_POSITION",
                target_entity_id=role, tenant_id=t,
                natural_language="Jennifer Walsh is CISO")
    verdict = asyncio.run(eng.evaluate(fact))
    assert verdict.status in ("PROVEN", "STRONGLY_SUPPORTED"), \
        f"got {verdict.status}; trace={verdict.trace}"


def test_canonical_4_two_active_ceos_contested(benchmark_session, benchmark_tenant, benchmark_llm):
    s, t = benchmark_session, benchmark_tenant
    alice = seed_entity(s, t, "Alice Apex", lifecycle="STAGING")
    bob = seed_entity(s, t, "Bob Briggs", lifecycle="STAGING")
    role = seed_entity(s, t, "CEO of TwoHeadCorp", entity_type="ROLE")
    ch_a = seed_chunk(s, t, "doc-A", "Alice Apex is CEO of TwoHeadCorp.")
    ch_b = seed_chunk(s, t, "doc-B", "Bob Briggs is CEO of TwoHeadCorp.")
    seed_relationship(s, t, alice, role, "HOLDS_POSITION", chunk_id=ch_a, lifecycle="STAGING")
    seed_relationship(s, t, bob, role, "HOLDS_POSITION", chunk_id=ch_b, lifecycle="STAGING")
    s.commit()

    eng = _engine(s, benchmark_llm, t)
    fact_alice = Fact(source_entity_id=alice, relationship_type="HOLDS_POSITION",
                      target_entity_id=role, tenant_id=t,
                      natural_language="Alice Apex is CEO of TwoHeadCorp")
    fact_bob = Fact(source_entity_id=bob, relationship_type="HOLDS_POSITION",
                    target_entity_id=role, tenant_id=t,
                    natural_language="Bob Briggs is CEO of TwoHeadCorp")
    v_alice = asyncio.run(eng.evaluate(fact_alice))
    v_bob = asyncio.run(eng.evaluate(fact_bob))
    assert v_alice.status == "CONTESTED", \
        f"Alice: got {v_alice.status}; trace={v_alice.trace}"
    assert v_bob.status == "CONTESTED", \
        f"Bob: got {v_bob.status}; trace={v_bob.trace}"
    assert v_alice.surviving_challenges, "Alice: expected surviving challenge referencing Bob"
    bob_referenced = any("bob" in c.description.lower()
                         for c in v_alice.surviving_challenges)
    assert bob_referenced, \
        f"Alice's surviving challenges should reference Bob: " \
        f"{[c.description for c in v_alice.surviving_challenges]}"
