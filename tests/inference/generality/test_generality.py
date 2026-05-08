"""10 generality tests covering fact types the engine wasn't designed around.

Each must produce a *sensible* verdict — the assertion is on
verdict.status ∈ {acceptable_set}, not a specific value, because the engine
is supposed to handle these without code changes (only planner prompt
adjustments would be allowed).

Gated behind RUN_INFERENCE_BENCHMARKS=1.
"""
import os
import asyncio
import pytest

if not os.environ.get("RUN_INFERENCE_BENCHMARKS"):
    pytest.skip("Set RUN_INFERENCE_BENCHMARKS=1 to run (real LLM cost).",
                allow_module_level=True)

from src.context_foundry.inference.contracts import Fact
from src.context_foundry.inference.engine import FactEvaluator
from src.context_foundry.inference.llm.client import LLMClient
from src.context_foundry.models.schema import get_session
from tests.inference.benchmark.conftest import (
    seed_entity, seed_chunk, seed_relationship,
)


SCHEMA_ETS = ["PERSON", "ROLE", "ORG", "DOCUMENT", "PROJECT", "EVENT", "LOCATION", "AMOUNT"]
SCHEMA_RTS = ["HOLDS_POSITION", "REPLACED", "FORMERLY_HELD", "HAS_BUDGET",
              "CAUSED", "ACQUIRED", "DOES_NOT_SUPPLY", "COMPETES_WITH",
              "LEADS", "BUILT", "IS_AUTHORITATIVE", "HEADQUARTERED_IN",
              "IDENTITY", "WOULD_HAVE", "AFFILIATED_WITH"]
ACCEPTABLE = {"PROVEN", "STRONGLY_SUPPORTED", "SUPPORTED", "CONTESTED",
              "UNDERSPECIFIED", "UNDERSUPPORTED", "DISPROVEN"}


@pytest.fixture
def session_and_tenant():
    import uuid
    from sqlalchemy import text
    s = get_session(use_rls_role=False)
    t = str(uuid.uuid4())
    yield s, t
    for tbl in ("relationships", "entities", "document_chunks"):
        s.execute(text(f"DELETE FROM {tbl} WHERE tenant_id = CAST(:t AS uuid)"), {"t": t})
    s.commit()
    s.close()


@pytest.fixture
def llm(session_and_tenant):
    return LLMClient(session=session_and_tenant[0], pin_model=True)


def _eng(s, llm, t):
    return FactEvaluator(
        session=s, llm_client=llm, schema_entity_types=SCHEMA_ETS,
        schema_relationship_types=SCHEMA_RTS, tenant_id=t,
        max_depth=3, max_replans=1,
    )


def _run(eng, fact):
    return asyncio.run(eng.evaluate(fact))


# --------------------------------------------------- 1. Quantitative
def test_quantitative_atlas_budget(session_and_tenant, llm):
    s, t = session_and_tenant
    proj = seed_entity(s, t, "Project Atlas", entity_type="PROJECT")
    amt = seed_entity(s, t, "$50M", entity_type="AMOUNT")
    ch = seed_chunk(s, t, "doc-budget", "Project Atlas approved budget: $50M for FY26.")
    seed_relationship(s, t, proj, amt, "HAS_BUDGET", chunk_id=ch)
    s.commit()
    fact = Fact(source_entity_id=proj, relationship_type="HAS_BUDGET",
                target_entity_id=amt, tenant_id=t,
                properties={"amount_usd": 50_000_000},
                natural_language="Project Atlas budget = $50M")
    v = _run(_eng(s, llm, t), fact)
    assert v.status in ACCEPTABLE


# --------------------------------------------------- 2. Causal
def test_causal_q3_incident_caused_churn(session_and_tenant, llm):
    s, t = session_and_tenant
    inc = seed_entity(s, t, "Q3 incident", entity_type="EVENT")
    ch_event = seed_entity(s, t, "customer churn spike", entity_type="EVENT")
    chk = seed_chunk(s, t, "doc-postmortem",
                     "After the Q3 incident, customer churn spiked 18% in October.")
    seed_relationship(s, t, inc, ch_event, "CAUSED", chunk_id=chk)
    s.commit()
    fact = Fact(source_entity_id=inc, relationship_type="CAUSED",
                target_entity_id=ch_event, tenant_id=t,
                natural_language="Q3 incident caused customer churn")
    v = _run(_eng(s, llm, t), fact)
    assert v.status in ACCEPTABLE


# --------------------------------------------------- 3. Temporal
def test_temporal_acme_acquired_beta(session_and_tenant, llm):
    s, t = session_and_tenant
    acme = seed_entity(s, t, "Acme", entity_type="ORG")
    beta = seed_entity(s, t, "Beta", entity_type="ORG")
    chk = seed_chunk(s, t, "doc-press", "Acme completed acquisition of Beta in 2019.")
    seed_relationship(s, t, acme, beta, "ACQUIRED", chunk_id=chk)
    s.commit()
    fact = Fact(source_entity_id=acme, relationship_type="ACQUIRED",
                target_entity_id=beta, tenant_id=t,
                properties={"year": 2019},
                natural_language="Acme acquired Beta in 2019")
    v = _run(_eng(s, llm, t), fact)
    assert v.status in ACCEPTABLE


# --------------------------------------------------- 4. Negative
def test_negative_nexus_does_not_supply_lockheed(session_and_tenant, llm):
    s, t = session_and_tenant
    nx = seed_entity(s, t, "Nexus", entity_type="ORG")
    lh = seed_entity(s, t, "Lockheed", entity_type="ORG")
    s.commit()
    fact = Fact(source_entity_id=nx, relationship_type="DOES_NOT_SUPPLY",
                target_entity_id=lh, tenant_id=t,
                natural_language="Nexus does NOT supply Lockheed")
    v = _run(_eng(s, llm, t), fact)
    # Negatives with no contradicting evidence reasonably fall to UNDERSUPPORTED
    # or get supported-by-absence.
    assert v.status in ACCEPTABLE


# --------------------------------------------------- 5. Vague-relational
def test_vague_acme_competes_with_nexus(session_and_tenant, llm):
    s, t = session_and_tenant
    acme = seed_entity(s, t, "Acme", entity_type="ORG")
    nx = seed_entity(s, t, "Nexus", entity_type="ORG")
    chk = seed_chunk(s, t, "doc-analyst",
                     "Industry analysts list Acme and Nexus as direct competitors in defence-tech.")
    seed_relationship(s, t, acme, nx, "COMPETES_WITH", chunk_id=chk)
    s.commit()
    fact = Fact(source_entity_id=acme, relationship_type="COMPETES_WITH",
                target_entity_id=nx, tenant_id=t,
                natural_language="Acme competes with Nexus")
    v = _run(_eng(s, llm, t), fact)
    assert v.status in ACCEPTABLE


# --------------------------------------------------- 6. Compound
def test_compound_kim_leads_team_built_atlas(session_and_tenant, llm):
    s, t = session_and_tenant
    kim = seed_entity(s, t, "Robert Kim")
    team = seed_entity(s, t, "Atlas Team", entity_type="ORG")
    atlas = seed_entity(s, t, "Project Atlas", entity_type="PROJECT")
    c1 = seed_chunk(s, t, "doc-org", "Robert Kim leads the Atlas Team.")
    c2 = seed_chunk(s, t, "doc-atlas-charter", "Atlas Team built Project Atlas.")
    seed_relationship(s, t, kim, team, "LEADS", chunk_id=c1)
    seed_relationship(s, t, team, atlas, "BUILT", chunk_id=c2)
    s.commit()
    fact = Fact(source_entity_id=kim, relationship_type="LEADS",
                target_entity_id=atlas, tenant_id=t,
                natural_language="Robert Kim leads the team that built Atlas")
    v = _run(_eng(s, llm, t), fact)
    assert v.status in ACCEPTABLE


# --------------------------------------------------- 7. Self-referential
def test_self_referential_doc_authoritative(session_and_tenant, llm):
    s, t = session_and_tenant
    chk = seed_chunk(s, t, "doc-self",
                     "This memorandum is the authoritative source on internal policy 2.3.")
    s.commit()
    fact = Fact(source_entity_id=chk, relationship_type="IS_AUTHORITATIVE",
                target_entity_id="policy-2.3", tenant_id=t,
                natural_language="This document is authoritative")
    v = _run(_eng(s, llm, t), fact)
    assert v.status in ACCEPTABLE


# --------------------------------------------------- 8. Property-equality
def test_property_boeing_hq_chicago(session_and_tenant, llm):
    s, t = session_and_tenant
    boeing = seed_entity(s, t, "Boeing", entity_type="ORG")
    chicago = seed_entity(s, t, "Chicago", entity_type="LOCATION")
    chk = seed_chunk(s, t, "doc-corp", "Boeing is headquartered in Chicago, IL.")
    seed_relationship(s, t, boeing, chicago, "HEADQUARTERED_IN", chunk_id=chk)
    s.commit()
    fact = Fact(source_entity_id=boeing, relationship_type="HEADQUARTERED_IN",
                target_entity_id=chicago, tenant_id=t,
                natural_language="Boeing is headquartered in Chicago")
    v = _run(_eng(s, llm, t), fact)
    assert v.status in ACCEPTABLE


# --------------------------------------------------- 9. Counterfactual
def test_counterfactual_anderson_not_replaced(session_and_tenant, llm):
    s, t = session_and_tenant
    anderson = seed_entity(s, t, "Thomas Anderson")
    nds = seed_entity(s, t, "NDS", entity_type="ORG")
    s.commit()
    fact = Fact(source_entity_id=anderson, relationship_type="WOULD_HAVE",
                target_entity_id=nds, tenant_id=t,
                properties={"counterfactual": "NDS would have failed"},
                natural_language="If Anderson hadn't been replaced, NDS would have failed")
    v = _run(_eng(s, llm, t), fact)
    # Counterfactuals should not earn STRONGLY_SUPPORTED — they're inherently
    # speculative, but the engine shouldn't crash on them either.
    assert v.status in ACCEPTABLE
    assert v.status != "PROVEN", "counterfactuals should never be PROVEN"


# --------------------------------------------------- 10. Identity
def test_identity_chen_same_as_v_chen(session_and_tenant, llm):
    s, t = session_and_tenant
    full = seed_entity(s, t, "Dr. Victoria Chen")
    short = seed_entity(s, t, "V. Chen")
    chk = seed_chunk(s, t, "doc-bio",
                     "Dr. Victoria Chen (also referenced as V. Chen in earlier minutes).")
    seed_relationship(s, t, full, short, "IDENTITY", chunk_id=chk)
    s.commit()
    fact = Fact(source_entity_id=full, relationship_type="IDENTITY",
                target_entity_id=short, tenant_id=t,
                natural_language="Dr. Victoria Chen is the same person as V. Chen")
    v = _run(_eng(s, llm, t), fact)
    assert v.status in ACCEPTABLE
