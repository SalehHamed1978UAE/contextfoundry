"""Round-trip + key-stability tests for the pydantic contracts."""
import json
from src.context_foundry.inference.contracts import (
    Fact, Condition, EvidenceItem, EvaluationPlan, ProofAttempt,
    Challenge, MetaAudit, Verdict,
)


def test_fact_key_distinguishes_property_values():
    """Two facts about the same edge with different property values must NOT
    collide on key — they are distinct claims (e.g., budget = $50M vs $100M)."""
    f1 = Fact(source_entity_id="a", relationship_type="HAS_BUDGET", target_entity_id="b",
              properties={"amount_usd": 50_000_000})
    f2 = Fact(source_entity_id="a", relationship_type="HAS_BUDGET", target_entity_id="b",
              properties={"amount_usd": 100_000_000})
    f3 = Fact(source_entity_id="a", relationship_type="HAS_BUDGET", target_entity_id="b",
              properties={"amount_usd": 50_000_000})
    assert f1.key() != f2.key()
    assert f1.key() == f3.key()  # same properties → same key (deterministic)


def test_fact_key_property_order_insensitive():
    """Key is canonical — property dict insertion order doesn't matter."""
    f1 = Fact(source_entity_id="a", relationship_type="R", target_entity_id="b",
              properties={"x": 1, "y": 2})
    f2 = Fact(source_entity_id="a", relationship_type="R", target_entity_id="b",
              properties={"y": 2, "x": 1})
    assert f1.key() == f2.key()


def test_fact_is_frozen():
    f = Fact(source_entity_id="a", relationship_type="R", target_entity_id="b")
    try:
        f.source_entity_id = "z"
    except Exception:
        return
    assert False, "expected ValidationError on frozen Fact mutation"


def test_verdict_recursive_serialisation_roundtrips():
    inner = Verdict(
        status="SUPPORTED",
        fact=Fact(source_entity_id="ch-1", relationship_type="IS_AUTHORITATIVE_FOR",
                  target_entity_id="HOLDS_POSITION"),
    )
    ev = EvidenceItem(chunk_id="ch-1", content="x", speaks_to="t",
                      polarity="confirms", source_authority_verdict=inner)
    outer = Verdict(
        status="STRONGLY_SUPPORTED",
        fact=Fact(source_entity_id="vchen", relationship_type="HOLDS_POSITION",
                  target_entity_id="ceo-nexus"),
        evidence=[ev],
    )
    blob = outer.model_dump_json()
    parsed = Verdict.model_validate_json(blob)
    assert parsed.evidence[0].source_authority_verdict.status == "SUPPORTED"
    # Determinism
    assert parsed.model_dump_json() == blob


def test_evaluation_plan_defaults_are_empty():
    p = EvaluationPlan(fact_type="HOLDS_POSITION")
    assert p.truth_conditions == []
    assert p.falsifiers == []
    assert p.presuppositions == []


def test_meta_audit_required_fields():
    m = MetaAudit(
        plan_completeness_verdict="complete",
        evidence_thoroughness_verdict="thorough",
        proof_validity_verdict="valid",
    )
    assert m.recommend_replan is False
