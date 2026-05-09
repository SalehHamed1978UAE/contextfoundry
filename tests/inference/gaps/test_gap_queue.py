"""D8.1 unit tests — GapQueue: enqueue, query, JSONL persistence, contextvars."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.context_foundry.inference.gaps import (
    GapQueue, GapRecord, GapSource, GapType, GapSeverity,
    gap_context, current_gap_queue, current_run_id, current_question_id,
)


def _mk_gap(run_id="r", question_id=None,
            gap_type=GapType.GAP_TYPE_MISMATCH,
            source=GapSource.PLANNER_PRESUPPOSITION):
    return GapRecord(
        run_id=run_id, question_id=question_id,
        source=source, gap_type=gap_type,
        trigger_stage="planner.presuppositions",
        explanation="test",
    )


def test_enqueue_writes_jsonl_line(tmp_path: Path):
    q = GapQueue(output_dir=str(tmp_path))
    g = _mk_gap(run_id="r1", question_id="q1")
    q.enqueue(g)
    out = tmp_path / "r1.jsonl"
    assert out.exists()
    line = out.read_text().strip()
    blob = json.loads(line)
    assert blob["run_id"] == "r1"
    assert blob["question_id"] == "q1"
    assert blob["gap_type"] == "GAP_TYPE_MISMATCH"


def test_list_by_run_and_by_question(tmp_path: Path):
    q = GapQueue(output_dir=str(tmp_path))
    q.enqueue(_mk_gap(run_id="r1", question_id="q1"))
    q.enqueue(_mk_gap(run_id="r1", question_id="q2"))
    q.enqueue(_mk_gap(run_id="r2", question_id="q1"))
    assert len(q.list_by_run("r1")) == 2
    assert len(q.list_by_run("r2")) == 1
    by_q1 = q.list_by_question("q1")
    assert len(by_q1) == 2
    runs = {g.run_id for g in by_q1}
    assert runs == {"r1", "r2"}


def test_jsonl_appends_deterministically(tmp_path: Path):
    q = GapQueue(output_dir=str(tmp_path))
    for i in range(5):
        q.enqueue(_mk_gap(run_id="rdet", question_id=f"q{i}"))
    lines = (tmp_path / "rdet.jsonl").read_text().splitlines()
    assert len(lines) == 5
    qids = [json.loads(l)["question_id"] for l in lines]
    assert qids == ["q0", "q1", "q2", "q3", "q4"]


def test_same_input_same_gap_type(tmp_path: Path):
    """Mapping is deterministic — same trigger ⇒ same gap_type."""
    q = GapQueue(output_dir=str(tmp_path))
    for _ in range(3):
        q.enqueue(_mk_gap(run_id="r", gap_type=GapType.GAP_IDENTITY_AMBIGUITY))
    types = {g.gap_type for g in q.list_by_run("r")}
    assert types == {GapType.GAP_IDENTITY_AMBIGUITY}


def test_gap_context_sets_and_clears_contextvars(tmp_path: Path):
    q = GapQueue(output_dir=str(tmp_path))
    assert current_gap_queue() is None
    assert current_run_id() is None
    assert current_question_id() is None
    with gap_context(q, run_id="run_X", question_id="q_42"):
        assert current_gap_queue() is q
        assert current_run_id() == "run_X"
        assert current_question_id() == "q_42"
    # Reset on exit
    assert current_gap_queue() is None
    assert current_run_id() is None
    assert current_question_id() is None


# ---------------------------------------------------------------------------
# Architect-requested D8.1 fix: graph_fact-only disproven path must surface
# actionable sub-fact_keys in the aggregate gap's evidence_refs.
# ---------------------------------------------------------------------------

def test_graph_fact_disproven_refs_payload_shape():
    """Ensure GapRecord can carry the {kind, sub_fact_key, trigger_verdict}
    payload shape that engine._emit_presupposition_gaps emits for graph_fact
    disprovals when no type/identity check disproved."""
    g = GapRecord(
        run_id="r_gf",
        question_id="q_gf",
        source=GapSource.PLANNER_PRESUPPOSITION,
        gap_type=GapType.GAP_PLANNER_PRESUPPOSITION_GATE,
        severity=GapSeverity.HIGH,
        trigger_stage="planner.presuppositions",
        trigger_rule="any_presup_DISPROVEN",
        trigger_verdict="UNDERSPECIFIED",
        explanation="graph_fact-only disproven",
        evidence_refs=[
            {"kind": "graph_fact",
             "sub_fact_key": "X|REL|Y|{}",
             "trigger_verdict": "DISPROVEN"},
            {"kind": "graph_fact",
             "sub_fact_key": "A|REL|B|{}",
             "trigger_verdict": "DISPROVEN"},
        ],
    )
    blob = json.loads(g.to_jsonl())
    assert blob["gap_type"] == "GAP_PLANNER_PRESUPPOSITION_GATE"
    assert len(blob["evidence_refs"]) == 2
    for ref in blob["evidence_refs"]:
        assert ref["kind"] == "graph_fact"
        assert "sub_fact_key" in ref
        assert ref["trigger_verdict"] == "DISPROVEN"
