"""D8.1 Gap Detector — typed gaps emitted by the inference engine.

Distinct from `extraction/gap_detector.py` (extraction-time graph hygiene)
and `learning/gap_detector.py` (query-gap learning queue). This module owns
the typed gaps the FactEvaluator engine emits during a reasoning run, with
direct method-call enqueue (NOT a log-subscriber pattern — structlog bypasses
stdlib logging in this codebase; see audit in design doc §10.6).
"""
from .records import GapRecord, GapSource, GapType, GapSeverity
from .queue import (GapQueue, gap_context, current_gap_queue,
                     current_run_id, current_question_id)

__all__ = [
    "GapRecord", "GapSource", "GapType", "GapSeverity",
    "GapQueue", "gap_context",
    "current_gap_queue", "current_run_id", "current_question_id",
]
