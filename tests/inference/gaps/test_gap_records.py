"""D8.1 unit tests — GapRecord schema + serialization."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from src.context_foundry.inference.gaps import (
    GapRecord, GapSource, GapType, GapSeverity,
)
from src.context_foundry.inference.gaps.records import PLANNER_STAGE_GAP_TYPES


def test_gaprecord_minimum_fields_round_trip():
    g = GapRecord(
        run_id="run_abc",
        source=GapSource.PLANNER_PRESUPPOSITION,
        gap_type=GapType.GAP_TYPE_MISMATCH,
        trigger_stage="planner.presuppositions",
        explanation="test",
    )
    line = g.to_jsonl()
    back = GapRecord.model_validate_json(line)
    assert back.run_id == "run_abc"
    assert back.gap_type == GapType.GAP_TYPE_MISMATCH
    assert back.source == GapSource.PLANNER_PRESUPPOSITION
    assert back.severity == GapSeverity.MEDIUM
    assert back.id == g.id


def test_gaprecord_evidence_and_trace_refs_preserved():
    g = GapRecord(
        run_id="r1",
        question_id="q17",
        source=GapSource.GATHERER,
        gap_type=GapType.GAP_EVIDENCE_INSUFFICIENT,
        trigger_stage="synthesizer",
        explanation="gather had nothing useful",
        evidence_refs=[{"chunk_id": "c1"}, {"chunk_id": "c2"}],
        trace_refs=[{"trace_id": "t1", "span_id": "s1"}],
    )
    blob = json.loads(g.to_jsonl())
    assert blob["question_id"] == "q17"
    assert blob["evidence_refs"] == [{"chunk_id": "c1"}, {"chunk_id": "c2"}]
    assert blob["trace_refs"] == [{"trace_id": "t1", "span_id": "s1"}]


def test_planner_stage_taxonomy_membership():
    """The planner-stage taxonomy must contain exactly the 5 wired types."""
    assert PLANNER_STAGE_GAP_TYPES == frozenset({
        GapType.GAP_TYPE_MISMATCH,
        GapType.GAP_IDENTITY_AMBIGUITY,
        GapType.GAP_EVIDENCE_INSUFFICIENT,
        GapType.GAP_PLANNER_FAILED,
        GapType.GAP_PLANNER_PRESUPPOSITION_GATE,
    })


def test_all_required_enum_values_exist():
    """Spec'd enum values from the D8.1 brief must all be defined."""
    for name in ("GAP_TYPE_MISMATCH", "GAP_IDENTITY_AMBIGUITY",
                 "GAP_EVIDENCE_INSUFFICIENT", "GAP_PLANNER_FAILED",
                 "GAP_TEMPORAL_ATTRIBUTE", "GAP_SCALAR_METRIC",
                 "GAP_LIST_AGGREGATION", "GAP_COMPOSITE_ROLE_TARGET",
                 "GAP_QUANTITY_RANGE_TARGET", "GAP_MATERIAL_SPEC_TARGET",
                 "GAP_OWNERSHIP_RESPONSIBILITY", "GAP_AMBIGUOUS_SUBJECT",
                 "GAP_EVIDENCE_PIPELINE_DISCONNECT",
                 "GAP_EVALUATOR_REASONING_OR_PROMPT",
                 "GAP_PLANNER_PRESUPPOSITION_GATE",
                 "INFRA_TIMEOUT_CANCELLATION_FAILURE",
                 "INFRA_TRACE_CAPTURE_FAILURE",
                 "INFRA_VECTOR_GATHERER_AWAIT_BUG"):
        assert hasattr(GapType, name), f"missing GapType.{name}"
    for name in ("EXTRACTOR", "ENTITY_RESOLUTION", "PLANNER_PRESUPPOSITION",
                 "GATHERER", "EVALUATOR", "SYNTHESIZER", "INFRA"):
        assert hasattr(GapSource, name), f"missing GapSource.{name}"
    for name in ("INFO", "LOW", "MEDIUM", "HIGH", "BLOCKING"):
        assert hasattr(GapSeverity, name), f"missing GapSeverity.{name}"
