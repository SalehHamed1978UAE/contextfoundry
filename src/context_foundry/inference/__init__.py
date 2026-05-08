"""Logical Inference Engine v2 — deterministic, recursive, adversarial fact evaluator.

See `docs/CF_MASTER_REFERENCE.md` and `attached_assets/#_Context_Foundry-_Logical_Inference_Engine_v2_*.docx` for the full spec.

The public entry point is `FactEvaluator` (see `engine.py`). All cross-stage data
flows through the pydantic contracts in `contracts.py`. The synthesiser is the
ONLY place categorical thresholds live, and they are structural (count of
distinct sources, etc.), never weighted scores.
"""
from .contracts import (
    Fact, Condition, Hypothesis, EvidenceItem, EvaluationPlan,
    ProofAttempt, Challenge, MetaAudit, Verdict, VerdictStatus,
)

__all__ = [
    "Fact", "Condition", "Hypothesis", "EvidenceItem", "EvaluationPlan",
    "ProofAttempt", "Challenge", "MetaAudit", "Verdict", "VerdictStatus",
]
