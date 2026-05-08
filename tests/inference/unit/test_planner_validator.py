"""Unit tests for EvaluationPlanner._validate — Condition variants + self-loop."""
from src.context_foundry.inference.contracts import (
    Fact, Condition, EvaluationPlan,
)
from src.context_foundry.inference.planner import EvaluationPlanner


def _planner():
    return EvaluationPlanner(
        llm=None,
        schema_entity_types=["PERSON", "ROLE", "ORG"],
        schema_relationship_types=["HOLDS_POSITION", "AFFILIATED_WITH"],
    )


def _plan(presups):
    return EvaluationPlan(fact_type="HOLDS_POSITION", presuppositions=presups)


U1 = "11111111-1111-1111-1111-111111111111"
U2 = "22222222-2222-2222-2222-222222222222"


def test_validator_rejects_self_loop_graph_fact():
    p = _planner()
    bad = Condition(
        description="self-loop AFFILIATED_WITH",
        kind="graph_fact",
        fact=Fact(source_entity_id=U1, relationship_type="AFFILIATED_WITH",
                  target_entity_id=U1),
    )
    problems = p._validate(_plan([bad]))
    assert any("self-loop" in s for s in problems), problems


def test_validator_accepts_type_check_with_required_fields():
    p = _planner()
    ok = Condition(
        description="x is ORG",
        kind="type_check",
        entity_id=U1,
        expected_entity_type="ORG",
    )
    assert p._validate(_plan([ok])) == []


def test_validator_rejects_type_check_missing_fields():
    p = _planner()
    bad = Condition(description="missing", kind="type_check")
    problems = p._validate(_plan([bad]))
    assert any("missing entity_id" in s for s in problems), problems


def test_validator_rejects_type_check_with_fact():
    p = _planner()
    bad = Condition(
        description="hybrid", kind="type_check",
        entity_id=U1, expected_entity_type="ORG",
        fact=Fact(source_entity_id=U1, relationship_type="HOLDS_POSITION",
                  target_entity_id=U2),
    )
    problems = p._validate(_plan([bad]))
    assert any("must NOT carry a fact" in s for s in problems), problems


def test_validator_rejects_type_check_with_unknown_type():
    p = _planner()
    bad = Condition(
        description="bad type", kind="type_check",
        entity_id=U1, expected_entity_type="UFO",
    )
    problems = p._validate(_plan([bad]))
    assert any("UFO" in s for s in problems), problems


def test_validator_accepts_custom_without_fact():
    p = _planner()
    ok = Condition(description="role is single-occupant", kind="custom")
    assert p._validate(_plan([ok])) == []


def test_validator_rejects_custom_with_fact():
    p = _planner()
    bad = Condition(
        description="bad custom", kind="custom",
        fact=Fact(source_entity_id=U1, relationship_type="HOLDS_POSITION",
                  target_entity_id=U2),
    )
    problems = p._validate(_plan([bad]))
    assert any("kind=custom" in s for s in problems), problems


def test_validator_rejects_graph_fact_without_fact():
    p = _planner()
    bad = Condition(description="missing fact", kind="graph_fact", fact=None)
    problems = p._validate(_plan([bad]))
    assert any("has no fact" in s for s in problems), problems


def test_validator_accepts_normal_graph_fact():
    p = _planner()
    ok = Condition(
        description="legit edge", kind="graph_fact",
        fact=Fact(source_entity_id=U1, relationship_type="HOLDS_POSITION",
                  target_entity_id=U2),
    )
    assert p._validate(_plan([ok])) == []


def test_validator_rejects_type_check_with_placeholder_entity_id():
    """LLM-emitted placeholder text like '<NEXUS_ORG_ENTITY_ID>' must be
    rejected before it reaches the DB and poisons the txn."""
    p = _planner()
    bad = Condition(
        description="placeholder", kind="type_check",
        entity_id="<NEXUS_ORG_ENTITY_ID>", expected_entity_type="ORG",
    )
    problems = p._validate(_plan([bad]))
    assert any("not a valid UUID" in s for s in problems), problems


def test_validator_rejects_graph_fact_with_placeholder_endpoint():
    p = _planner()
    bad = Condition(
        description="placeholder edge", kind="graph_fact",
        fact=Fact(source_entity_id="<NEXUS_ORG_ENTITY_ID>",
                  relationship_type="HOLDS_POSITION",
                  target_entity_id="11111111-2222-3333-4444-555555555555"),
    )
    problems = p._validate(_plan([bad]))
    assert any("not a valid UUID" in s and "source_entity_id" in s
               for s in problems), problems


def test_validator_default_kind_is_graph_fact():
    """Back-compat: omitting kind defaults to graph_fact behavior."""
    p = _planner()
    ok = Condition(
        description="legit edge",
        fact=Fact(source_entity_id=U1, relationship_type="HOLDS_POSITION",
                  target_entity_id=U2),
    )
    assert ok.kind == "graph_fact"
    assert p._validate(_plan([ok])) == []
