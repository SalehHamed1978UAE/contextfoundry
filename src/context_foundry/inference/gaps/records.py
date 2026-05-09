"""GapRecord schema + GapSource / GapType / GapSeverity enums.

Per D8.1 spec. Pydantic-backed for JSONL round-trip parity with the rest of
the inference contracts (see ../contracts.py).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class GapSource(str, Enum):
    EXTRACTOR = "EXTRACTOR"
    ENTITY_RESOLUTION = "ENTITY_RESOLUTION"
    PLANNER_PRESUPPOSITION = "PLANNER_PRESUPPOSITION"
    GATHERER = "GATHERER"
    EVALUATOR = "EVALUATOR"
    SYNTHESIZER = "SYNTHESIZER"
    INFRA = "INFRA"


class GapType(str, Enum):
    # Planner-stage gaps (D8.1 — wired)
    GAP_TYPE_MISMATCH = "GAP_TYPE_MISMATCH"
    GAP_IDENTITY_AMBIGUITY = "GAP_IDENTITY_AMBIGUITY"
    GAP_EVIDENCE_INSUFFICIENT = "GAP_EVIDENCE_INSUFFICIENT"
    GAP_PLANNER_FAILED = "GAP_PLANNER_FAILED"
    GAP_PLANNER_PRESUPPOSITION_GATE = "GAP_PLANNER_PRESUPPOSITION_GATE"

    # Question-shape gaps (future D8.2-D8.4 routing targets)
    GAP_TEMPORAL_ATTRIBUTE = "GAP_TEMPORAL_ATTRIBUTE"
    GAP_SCALAR_METRIC = "GAP_SCALAR_METRIC"
    GAP_LIST_AGGREGATION = "GAP_LIST_AGGREGATION"
    GAP_COMPOSITE_ROLE_TARGET = "GAP_COMPOSITE_ROLE_TARGET"
    GAP_QUANTITY_RANGE_TARGET = "GAP_QUANTITY_RANGE_TARGET"
    GAP_MATERIAL_SPEC_TARGET = "GAP_MATERIAL_SPEC_TARGET"
    GAP_OWNERSHIP_RESPONSIBILITY = "GAP_OWNERSHIP_RESPONSIBILITY"
    GAP_AMBIGUOUS_SUBJECT = "GAP_AMBIGUOUS_SUBJECT"

    # Evaluator-stage gaps
    GAP_EVIDENCE_PIPELINE_DISCONNECT = "GAP_EVIDENCE_PIPELINE_DISCONNECT"
    GAP_EVALUATOR_REASONING_OR_PROMPT = "GAP_EVALUATOR_REASONING_OR_PROMPT"

    # Infra failures (NOT semantic gaps — surfaced separately for the
    # human-completion UI to filter out)
    INFRA_TIMEOUT_CANCELLATION_FAILURE = "INFRA_TIMEOUT_CANCELLATION_FAILURE"
    INFRA_TRACE_CAPTURE_FAILURE = "INFRA_TRACE_CAPTURE_FAILURE"
    INFRA_VECTOR_GATHERER_AWAIT_BUG = "INFRA_VECTOR_GATHERER_AWAIT_BUG"


class GapSeverity(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    BLOCKING = "BLOCKING"


# Convenience: which gap types are "planner-stage" — used by routing config
# and by the design doc taxonomy. Kept here so it's the single source of truth.
PLANNER_STAGE_GAP_TYPES = frozenset({
    GapType.GAP_TYPE_MISMATCH,
    GapType.GAP_IDENTITY_AMBIGUITY,
    GapType.GAP_EVIDENCE_INSUFFICIENT,
    GapType.GAP_PLANNER_FAILED,
    GapType.GAP_PLANNER_PRESUPPOSITION_GATE,
})


class GapRecord(BaseModel):
    """A single typed gap emitted by some stage of the inference engine.

    `evidence_refs` and `trace_refs` are list[dict] (free-form) so each
    emitter can include the most useful pointer (e.g. {"chunk_id": "..."}
    or {"trace_id": "...", "span_id": "..."}). They are the audit-trail
    backbone — keep them populated.
    """
    id: str = Field(default_factory=lambda: uuid4().hex)
    run_id: str
    question_id: Optional[str] = None

    source: GapSource
    gap_type: GapType
    severity: GapSeverity = GapSeverity.MEDIUM

    fact_key: Optional[str] = None
    candidate_type: Optional[str] = None

    trigger_stage: str
    trigger_rule: Optional[str] = None
    trigger_verdict: Optional[str] = None

    explanation: str
    evidence_refs: List[dict] = Field(default_factory=list)
    trace_refs: List[dict] = Field(default_factory=list)

    remediation_hint: Optional[str] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    def to_jsonl(self) -> str:
        """Single-line JSON for append-only writes."""
        return self.model_dump_json()
