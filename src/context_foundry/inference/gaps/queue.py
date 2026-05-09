"""GapQueue — in-memory + JSONL-backed sink for GapRecord.

D8.1 scope: append-only JSONL at test_results/gaps/<run_id>.jsonl, plus
in-memory list grouped by run_id and question_id for fast filter queries.
Persistence beyond JSONL (Postgres-backed durable queue) is D8.2.

A `current_gap_queue()` accessor + `gap_context()` context manager are the
direct-call hooks the engine uses. NO log subscription — see design doc
§10.6 for why (structlog bypasses stdlib logging).
"""
from __future__ import annotations

import contextvars
import json
import logging
import os
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Optional, Iterator

from .records import GapRecord

logger = logging.getLogger(__name__)


class GapQueue:
    """Thread-safe append-only sink. JSONL writes flush per enqueue."""

    def __init__(self, output_dir: str = "test_results/gaps") -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._by_run: Dict[str, List[GapRecord]] = {}
        self._by_question: Dict[str, List[GapRecord]] = {}

    def enqueue(self, gap: GapRecord) -> None:
        path = self.output_dir / f"{gap.run_id}.jsonl"
        line = gap.to_jsonl()
        with self._lock:
            self._by_run.setdefault(gap.run_id, []).append(gap)
            if gap.question_id is not None:
                self._by_question.setdefault(gap.question_id, []).append(gap)
            with open(path, "a") as f:
                f.write(line + "\n")
        logger.debug(
            "[GapQueue] enqueued %s/%s for q=%s rule=%s",
            gap.source.value, gap.gap_type.value,
            gap.question_id, gap.trigger_rule,
        )

    def list_by_run(self, run_id: str) -> List[GapRecord]:
        with self._lock:
            return list(self._by_run.get(run_id, []))

    def list_by_question(self, question_id: str) -> List[GapRecord]:
        with self._lock:
            return list(self._by_question.get(question_id, []))


# ---------------------------------------------------------------------------
# Direct-call wiring — context-var accessor used by engine.py
# ---------------------------------------------------------------------------

_queue_var: contextvars.ContextVar[Optional[GapQueue]] = contextvars.ContextVar(
    "cf_gap_queue", default=None,
)
_run_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "cf_gap_run_id", default=None,
)
_question_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "cf_gap_question_id", default=None,
)


def current_gap_queue() -> Optional[GapQueue]:
    return _queue_var.get()


def current_run_id() -> Optional[str]:
    return _run_id_var.get()


def current_question_id() -> Optional[str]:
    return _question_id_var.get()


@contextmanager
def gap_context(queue: GapQueue, run_id: str,
                question_id: Optional[str] = None) -> Iterator[GapQueue]:
    """Bind a GapQueue + run/question identifiers for the duration of an
    evaluate() call. Emit sites read these via the contextvars accessors."""
    tok_q = _queue_var.set(queue)
    tok_r = _run_id_var.set(run_id)
    tok_qid = _question_id_var.set(question_id)
    try:
        yield queue
    finally:
        _queue_var.reset(tok_q)
        _run_id_var.reset(tok_r)
        _question_id_var.reset(tok_qid)
