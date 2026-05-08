"""Structured tracing for the FactEvaluator.

Each `evaluate()` call gets a trace_id. Each stage method opens a span via
`tracer.span(stage_name)` which logs entry, exit, duration, and any counters
incremented within (llm_call_count, db_query_count).

Usage:
    from .observability.trace import tracer, configure

    configure()  # one-shot, JSON to stderr; safe to call repeatedly

    async def evaluate(self, fact):
        with tracer.trace(fact_key=fact.key(), depth=guard.depth):
            with tracer.span("planner"):
                plan = await self.planner.plan(...)
            ...

LLM and DB primitives bump counters via tracer.bump("llm_call_count") /
tracer.bump("db_query_count"). The active span absorbs them; on exit the
counts are emitted as part of the span_end event.
"""
from __future__ import annotations

import contextvars
import logging
import os
import sys
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import structlog


_configured = False


def configure(level: str = None, json_output: bool = True) -> None:
    """Idempotent structlog setup. JSON to stderr by default; toggle pretty
    console rendering by setting CF_INFERENCE_TRACE_PRETTY=1."""
    global _configured
    if _configured:
        return
    level = level or os.environ.get("CF_INFERENCE_TRACE_LEVEL", "INFO")
    pretty = os.environ.get("CF_INFERENCE_TRACE_PRETTY") == "1" or not json_output

    # Stream stdlib logs through structlog so logger.warning() also gets the
    # trace_id/span_id added to it automatically.
    logging.basicConfig(
        format="%(message)s", stream=sys.stderr,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    processors: List = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
    ]
    if pretty:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))
    else:
        processors.append(structlog.processors.JSONRenderer(sort_keys=True))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )
    _configured = True


@dataclass
class _Span:
    span_id: str
    parent_span_id: Optional[str]
    stage_name: str
    started_at: float
    counters: Dict[str, int] = field(default_factory=dict)
    extra: Dict[str, object] = field(default_factory=dict)


# Per-async-context state
_trace_id_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "cf_inference_trace_id", default=None,
)
_fact_key_var: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "cf_inference_fact_key", default=None,
)
_depth_var: contextvars.ContextVar[int] = contextvars.ContextVar(
    "cf_inference_depth", default=0,
)
_span_stack_var: contextvars.ContextVar[Optional[List[_Span]]] = contextvars.ContextVar(
    "cf_inference_span_stack", default=None,
)


class _Tracer:
    """Thin façade — never instantiate directly; use the module-level `tracer`."""

    @property
    def log(self) -> structlog.stdlib.BoundLogger:
        configure()  # lazy
        return structlog.get_logger("cf.inference")

    @contextmanager
    def trace(self, fact_key: str, depth: int = 0,
              trace_id: Optional[str] = None):
        """Outermost context for a single evaluate() call."""
        configure()
        tid = trace_id or uuid.uuid4().hex[:12]
        tok_t = _trace_id_var.set(tid)
        tok_f = _fact_key_var.set(fact_key)
        tok_d = _depth_var.set(depth)
        tok_s = _span_stack_var.set([])
        ctx_tokens = structlog.contextvars.bind_contextvars(
            trace_id=tid, fact_key=fact_key, depth=depth,
        )
        self.log.info("trace_start")
        t0 = time.perf_counter()
        try:
            yield tid
        finally:
            self.log.info("trace_end", duration_ms=int((time.perf_counter() - t0) * 1000))
            structlog.contextvars.unbind_contextvars(*ctx_tokens.keys())
            _trace_id_var.reset(tok_t)
            _fact_key_var.reset(tok_f)
            _depth_var.reset(tok_d)
            _span_stack_var.reset(tok_s)

    @contextmanager
    def span(self, stage_name: str, **extra):
        """Open a span. Increments to llm_call_count / db_query_count made
        inside this span (and not inside a deeper span) accrue here."""
        stack = _span_stack_var.get() or []
        parent = stack[-1] if stack else None
        sp = _Span(
            span_id=uuid.uuid4().hex[:8],
            parent_span_id=parent.span_id if parent else None,
            stage_name=stage_name,
            started_at=time.perf_counter(),
            extra=dict(extra),
        )
        stack = stack + [sp]
        tok = _span_stack_var.set(stack)
        ctx_tok = structlog.contextvars.bind_contextvars(
            span_id=sp.span_id,
            parent_span_id=sp.parent_span_id or "",
            stage=stage_name,
        )
        self.log.info("span_start", **extra)
        try:
            yield sp
        except Exception as e:
            sp.extra["error"] = repr(e)
            self.log.warning("span_error", error=repr(e))
            raise
        finally:
            duration_ms = int((time.perf_counter() - sp.started_at) * 1000)
            self.log.info(
                "span_end", duration_ms=duration_ms,
                llm_call_count=sp.counters.get("llm_call_count", 0),
                db_query_count=sp.counters.get("db_query_count", 0),
                **{k: v for k, v in sp.extra.items() if k != "error"},
            )
            structlog.contextvars.unbind_contextvars(*ctx_tok.keys())
            _span_stack_var.reset(tok)

    def bump(self, counter: str, n: int = 1) -> None:
        """Increment a counter on the innermost open span (no-op outside one)."""
        stack = _span_stack_var.get() or []
        if not stack:
            return
        sp = stack[-1]
        sp.counters[counter] = sp.counters.get(counter, 0) + n

    def event(self, event: str, **fields) -> None:
        """Emit a free-floating structured event under the active context."""
        configure()
        self.log.info(event, **fields)


tracer = _Tracer()
