#!/usr/bin/env python3
"""Task 2 — run v2 (FactEvaluator) alongside v1 results on the Nexus 100.

For each question:
  1. Read v1 answer + correctness from a baseline run JSON.
  2. Extract a candidate Fact(s, r, t) from (question, v1_answer) via a small
     LLM call. If no fact can be extracted, mark V2_NO_CANDIDATE.
  3. Run FactEvaluator.evaluate(fact) under a 5-minute wall-clock ceiling.
  4. Map verdict -> derived answer; fuzzy-evaluate against expected.
  5. Capture per-question stats (verdict, derived answer, wall-time, LLM call
     counts, timeout flag, any error) and stream to JSONL.

A 6-hour absolute total budget caps the run; remaining questions are tagged
V2_BUDGET_EXHAUSTED.

NO auto-fixes during the run. Just measure.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# CF inference engine
from src.context_foundry.inference.engine import FactEvaluator
from src.context_foundry.inference.contracts import Fact, Verdict
from src.context_foundry.inference.llm.client import LLMClient
from src.context_foundry.inference.observability import trace as _trace_module

# Use the same fuzzy evaluator the test runner uses for v1 grading
from src.test_runner.evaluator import FuzzyEvaluator

VAULT_ID = "176a4fb2-0bb4-4da3-9068-0e26268fca71"
DEFAULT_BASELINE = "test_results/claudecode_nexus_industries_20260509_073740.json"
PER_QUESTION_CEILING_S = 5 * 60        # 5 minutes
TOTAL_BUDGET_S = 6 * 60 * 60           # 6 hours
EMBED_MODEL = "text-embedding-3-small"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("v2_parallel")


# --------------------------------------------------------------- schema load
def load_schema_from_vault(session, tenant_id: str) -> Tuple[List[str], List[str]]:
    ents = [r[0] for r in session.execute(text(
        "SELECT DISTINCT entity_type FROM entities "
        "WHERE tenant_id = CAST(:t AS uuid) AND entity_type IS NOT NULL"
    ), {"t": tenant_id}).fetchall()]
    rels = [r[0] for r in session.execute(text(
        "SELECT DISTINCT relationship_type FROM relationships "
        "WHERE tenant_id = CAST(:t AS uuid) AND relationship_type IS NOT NULL"
    ), {"t": tenant_id}).fetchall()]
    return ents, rels


# --------------------------------------------------------- entity resolution
def resolve_entity(session, tenant_id: str, name: str) -> Optional[str]:
    """Best-effort name -> entity_id lookup. Case-insensitive exact then ILIKE."""
    if not name:
        return None
    row = session.execute(text(
        "SELECT id::text FROM entities "
        "WHERE tenant_id = CAST(:t AS uuid) AND lower(name) = lower(:n) "
        "ORDER BY id ASC LIMIT 1"
    ), {"t": tenant_id, "n": name}).fetchone()
    if row:
        return row[0]
    row = session.execute(text(
        "SELECT id::text FROM entities "
        "WHERE tenant_id = CAST(:t AS uuid) AND name ILIKE :n "
        "ORDER BY id ASC LIMIT 1"
    ), {"t": tenant_id, "n": f"%{name}%"}).fetchone()
    return row[0] if row else None


# --------------------------------------------------- LLM-based fact extractor
FACT_EXTRACTION_SYSTEM = """You convert a natural-language question + a candidate answer into a single structured Fact triple of the form (subject_entity, relationship_type, target_entity).

Output ONLY a JSON object with these keys (no prose):
{
  "extractable": true | false,
  "subject_name": "<entity name as it would appear in a KG, or null>",
  "relationship_type": "<UPPER_SNAKE_CASE rel from the allowed list, or null>",
  "target_name": "<entity name or value, or null>",
  "reason_if_not_extractable": "<short reason, or null>"
}

Rules:
- The relationship_type MUST be drawn from the provided allowed list. If no allowed type fits, set extractable=false.
- If the candidate answer is a refusal ("not found", "I don't have enough information"), set extractable=false.
- Aggregations and date arithmetic are not extractable as a single triple — set extractable=false.
- Use the candidate answer to populate target/subject when the question is asking "who/what is X" — the answer fills the slot the question asks about.
- Subject is the named entity the question is anchored to (e.g. "Nexus Industries", "GreenHydrogen facility").
"""


async def extract_candidate_fact(llm: LLMClient, question: str, v1_answer: str,
                                  rel_types: List[str]) -> Dict[str, Any]:
    user = (
        f"QUESTION: {question}\n"
        f"CANDIDATE ANSWER: {v1_answer[:600]}\n\n"
        f"ALLOWED RELATIONSHIP TYPES: {', '.join(sorted(rel_types))}\n"
    )
    raw = await llm.call(FACT_EXTRACTION_SYSTEM, user, output_schema=None)
    # LLMClient with output_schema=None returns {"text": "<raw>"}; unwrap.
    candidate: str
    if isinstance(raw, dict) and "extractable" in raw:
        return raw  # already-parsed dict (legacy / cache)
    if isinstance(raw, dict) and "text" in raw:
        candidate = raw["text"]
    elif isinstance(raw, str):
        candidate = raw
    else:
        return {"extractable": False,
                "reason_if_not_extractable":
                    f"extractor returned {type(raw).__name__}: {repr(raw)[:120]}"}
    # Strip ```json ... ``` or ``` fences if present.
    s = candidate.strip()
    if s.startswith("```"):
        s = s.lstrip("`")
        if s.lower().startswith("json"):
            s = s[4:]
        s = s.strip()
        if s.endswith("```"):
            s = s[:-3].strip()
    try:
        parsed = json.loads(s)
    except json.JSONDecodeError as e:
        return {"extractable": False,
                "reason_if_not_extractable":
                    f"extractor returned non-JSON: {e}; head={s[:120]!r}"}
    if not isinstance(parsed, dict):
        return {"extractable": False,
                "reason_if_not_extractable":
                    f"extractor returned {type(parsed).__name__}, want dict"}
    return parsed


# ---------------------------------------------------- verdict -> answer map
def derive_answer(verdict: Verdict, target_name: Optional[str],
                  v1_answer: str) -> str:
    s = verdict.status
    if s in ("PROVEN", "STRONGLY_SUPPORTED", "SUPPORTED"):
        return target_name or v1_answer  # endorse v1
    if s == "DISPROVEN":
        return "DISPROVEN — v2 contradicts v1 candidate"
    if s == "CONTESTED":
        return f"CONTESTED — v2 surfaces competing facts; v1 said: {target_name or v1_answer}"
    if s in ("UNDERSUPPORTED", "UNKNOWN", "UNDERSPECIFIED"):
        return "v2 cannot confirm (NOT_FOUND)"
    return f"v2 status={s}"


# --------------------------------------------------------- tracer counters
class _CounterCapture(logging.Handler):
    """Reads tracer counters via the trace JSON events. We snapshot the
    bumped counter dict directly from the tracer's ContextVar instead.
    """
    def __init__(self):
        super().__init__()
        self.events: List[Dict[str, Any]] = []

    def emit(self, record):
        try:
            msg = record.getMessage()
            if msg.startswith("{") and '"event"' in msg:
                self.events.append(json.loads(msg))
        except Exception:
            pass


def reset_tracer():
    """Force the trace module to re-configure on next use (avoids stale BoundLogger)."""
    try:
        _trace_module._configured = False
    except AttributeError:
        pass


# --------------------------------------------------------- per-question run
async def run_one(qid: int, question: str, expected: str, v1_answer: str,
                  v1_correct: bool, llm: LLMClient, engine_factory,
                  evaluator: FuzzyEvaluator, session, tenant_id: str,
                  rel_types: List[str]) -> Dict[str, Any]:
    rec: Dict[str, Any] = {
        "q": qid, "question": question, "expected": expected,
        "v1_answer": v1_answer, "v1_correct": v1_correct,
        "v2_status": None, "v2_derived_answer": None,
        "v2_correct": None, "v2_wall_time_s": None,
        "v2_llm_calls": None, "v2_cache_hits": None, "v2_cache_misses": None,
        "v2_timeout": False, "v2_error": None,
        "v2_extractable": None, "v2_subject_id": None, "v2_target_id": None,
        "v2_relationship_type": None, "v2_subject_name": None,
        "v2_target_name": None, "v2_diagnostics": None,
    }
    t0 = time.monotonic()

    # Step 1: extract candidate fact (60s ceiling — extractor is one LLM call)
    try:
        ext = await asyncio.wait_for(
            extract_candidate_fact(llm, question, v1_answer, rel_types),
            timeout=60,
        )
    except asyncio.TimeoutError:
        rec["v2_status"] = "EXTRACTION_TIMEOUT"
        rec["v2_error"] = "extractor LLM call exceeded 60s"
        rec["v2_wall_time_s"] = round(time.monotonic() - t0, 2)
        return rec
    except Exception as e:
        rec["v2_status"] = "EXTRACTION_ERROR"
        rec["v2_error"] = f"{type(e).__name__}: {e}"
        rec["v2_wall_time_s"] = round(time.monotonic() - t0, 2)
        return rec

    rec["v2_extractable"] = bool(ext.get("extractable"))
    if not rec["v2_extractable"]:
        rec["v2_status"] = "V2_NO_CANDIDATE"
        rec["v2_derived_answer"] = "v2 not invoked: " + (ext.get("reason_if_not_extractable") or "no extractable fact")
        rec["v2_wall_time_s"] = round(time.monotonic() - t0, 2)
        return rec

    subj_name = ext.get("subject_name") or ""
    targ_name = ext.get("target_name") or ""
    rel_type = (ext.get("relationship_type") or "").upper()
    rec["v2_subject_name"] = subj_name
    rec["v2_target_name"] = targ_name
    rec["v2_relationship_type"] = rel_type

    if rel_type not in {r.upper() for r in rel_types}:
        rec["v2_status"] = "V2_NO_CANDIDATE"
        rec["v2_derived_answer"] = f"v2 not invoked: relationship_type {rel_type!r} not in schema"
        rec["v2_wall_time_s"] = round(time.monotonic() - t0, 2)
        return rec

    subj_id = resolve_entity(session, tenant_id, subj_name)
    targ_id = resolve_entity(session, tenant_id, targ_name)
    rec["v2_subject_id"] = subj_id
    rec["v2_target_id"] = targ_id
    if not subj_id or not targ_id:
        rec["v2_status"] = "V2_NO_CANDIDATE"
        rec["v2_derived_answer"] = (
            f"v2 not invoked: could not resolve "
            f"{'subject' if not subj_id else 'target'} entity "
            f"{(subj_name if not subj_id else targ_name)!r}"
        )
        rec["v2_wall_time_s"] = round(time.monotonic() - t0, 2)
        return rec

    fact = Fact(
        source_entity_id=subj_id,
        relationship_type=rel_type,
        target_entity_id=targ_id,
        tenant_id=tenant_id,
        natural_language=f"{subj_name} {rel_type} {targ_name}",
    )

    # Step 2: evaluate under per-question ceiling
    eng = engine_factory()
    cap = _CounterCapture()
    cap.setLevel(logging.INFO)
    cf_logger = logging.getLogger("cf.inference")
    cf_logger.addHandler(cap)
    try:
        try:
            verdict = await asyncio.wait_for(eng.evaluate(fact),
                                             timeout=PER_QUESTION_CEILING_S)
        except asyncio.TimeoutError:
            rec["v2_timeout"] = True
            rec["v2_status"] = "V2_TIMEOUT"
            rec["v2_derived_answer"] = "v2 timed out at 5min ceiling"
            rec["v2_wall_time_s"] = round(time.monotonic() - t0, 2)
            return rec
        except Exception as e:
            rec["v2_status"] = "V2_ERROR"
            rec["v2_error"] = f"{type(e).__name__}: {str(e)[:300]}"
            rec["v2_wall_time_s"] = round(time.monotonic() - t0, 2)
            return rec
    finally:
        cf_logger.removeHandler(cap)

    rec["v2_wall_time_s"] = round(time.monotonic() - t0, 2)
    rec["v2_status"] = verdict.status

    # Counters from tracer events: llm_call_count, llm_cache_hit_count are
    # rolled up onto the evaluate_summary event by trace.py.
    summary = next((e for e in cap.events if e.get("event") == "evaluate_summary"), None)
    if summary:
        rec["v2_diagnostics"] = {k: v for k, v in summary.items()
                                  if k not in ("event", "ts", "level", "logger")}
    # Fall-back counters if summary missing — count from per-span events
    cache_hits = sum(1 for e in cap.events if e.get("event") == "llm_cache_hit")
    cache_misses = sum(1 for e in cap.events if e.get("event") == "llm_call_made")
    # The tracer aggregates these as counters on the root summary; pull from
    # diagnostics if present.
    if summary:
        rec["v2_llm_calls"] = summary.get("llm_call_count")
    rec["v2_cache_hits"] = cache_hits or None
    rec["v2_cache_misses"] = cache_misses or None

    # Derive answer + fuzzy-grade
    rec["v2_derived_answer"] = derive_answer(verdict, targ_name, v1_answer)
    try:
        passed, _ = evaluator.evaluate(question, expected, rec["v2_derived_answer"])
        rec["v2_correct"] = bool(passed)
    except Exception as e:
        rec["v2_correct"] = None
        rec["v2_error"] = f"grade_error: {e}"

    return rec


# --------------------------------------------------------------- main
async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default=DEFAULT_BASELINE,
                     help="v1 baseline results JSON")
    ap.add_argument("--vault-id", default=VAULT_ID)
    ap.add_argument("--out", required=True, help="output JSONL path")
    ap.add_argument("--limit", type=int, default=None,
                     help="run only first N questions (smoke test)")
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    log.info(f"baseline={args.baseline} out={out_path} vault={args.vault_id}")

    # Load v1 baseline
    with open(args.baseline) as f:
        baseline = json.load(f)
    questions = baseline["all_results"]
    if args.limit:
        questions = questions[: args.limit]
    log.info(f"loaded {len(questions)} questions from baseline")

    # DB setup
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Reset tracer (avoid stale BoundLogger)
    reset_tracer()

    # Schema types
    ents, rels = load_schema_from_vault(session, args.vault_id)
    log.info(f"schema: {len(ents)} entity types, {len(rels)} relationship types")

    # LLM client
    llm = LLMClient(session=session, pin_model=True)
    log.info(f"llm: {llm.model}")

    # Embedder for the gatherer (OpenAI text-embedding-3-small)
    try:
        from openai import OpenAI
        oai = OpenAI()

        def embedder(text_in: str) -> list:
            r = oai.embeddings.create(model=EMBED_MODEL, input=text_in)
            return r.data[0].embedding
    except Exception as e:
        log.warning(f"embedder unavailable, gatherer vector strategies will degrade: {e}")
        embedder = None

    def engine_factory():
        # Fresh engine per question to avoid recursion-guard / authority-cache leak
        return FactEvaluator(
            session=session, llm_client=llm,
            schema_entity_types=ents, schema_relationship_types=rels,
            tenant_id=args.vault_id, embedder=embedder,
            max_depth=3, max_replans=1,
        )

    evaluator = FuzzyEvaluator()

    # Stream output
    fout = open(out_path, "w")
    summary = {
        "total": len(questions), "v1_passed": 0, "v2_passed": 0,
        "v2_no_candidate": 0, "v2_timeout": 0, "v2_error": 0,
        "v2_recovered": 0, "v2_regressed": 0,
        "started_at": datetime.utcnow().isoformat() + "Z",
    }
    t_start = time.monotonic()

    for i, q in enumerate(questions, 1):
        elapsed = time.monotonic() - t_start
        remaining = TOTAL_BUDGET_S - elapsed
        if remaining <= PER_QUESTION_CEILING_S:
            log.warning(f"budget exhausted at q{q['q']} ({elapsed:.0f}s elapsed)")
            for j in range(i - 1, len(questions)):
                qj = questions[j]
                fout.write(json.dumps({
                    "q": qj["q"], "question": qj["query"],
                    "expected": qj["expected"], "v1_answer": qj["actual"],
                    "v1_correct": qj["passed"],
                    "v2_status": "V2_BUDGET_EXHAUSTED",
                    "v2_derived_answer": "skipped — total budget hit",
                }) + "\n")
                fout.flush()
            break

        log.info(f"--- Q{q['q']} ({i}/{len(questions)}) — elapsed={elapsed:.0f}s ---")
        try:
            rec = await run_one(
                qid=q["q"], question=q["query"], expected=q["expected"],
                v1_answer=q["actual"] or "", v1_correct=bool(q["passed"]),
                llm=llm, engine_factory=engine_factory, evaluator=evaluator,
                session=session, tenant_id=args.vault_id, rel_types=rels,
            )
        except Exception as e:
            log.error(f"Q{q['q']} failed: {e}\n{traceback.format_exc()}")
            rec = {
                "q": q["q"], "question": q["query"],
                "expected": q["expected"], "v1_answer": q["actual"],
                "v1_correct": bool(q["passed"]),
                "v2_status": "V2_RUNNER_ERROR",
                "v2_error": f"{type(e).__name__}: {str(e)[:400]}",
            }

        # Tally
        if rec.get("v1_correct"): summary["v1_passed"] += 1
        if rec.get("v2_correct"): summary["v2_passed"] += 1
        if rec.get("v2_status") == "V2_NO_CANDIDATE": summary["v2_no_candidate"] += 1
        if rec.get("v2_timeout"): summary["v2_timeout"] += 1
        if rec.get("v2_status") in ("V2_ERROR", "V2_RUNNER_ERROR", "EXTRACTION_ERROR"):
            summary["v2_error"] += 1
        if rec.get("v2_correct") and not rec.get("v1_correct"):
            summary["v2_recovered"] += 1
        if rec.get("v1_correct") and rec.get("v2_correct") is False:
            summary["v2_regressed"] += 1

        fout.write(json.dumps(rec) + "\n")
        fout.flush()
        log.info(
            f"Q{q['q']}: v1={'PASS' if rec.get('v1_correct') else 'FAIL'} "
            f"v2={rec.get('v2_status')} v2_correct={rec.get('v2_correct')} "
            f"wall={rec.get('v2_wall_time_s')}s"
        )

    summary["wall_time_s"] = round(time.monotonic() - t_start, 1)
    summary["finished_at"] = datetime.utcnow().isoformat() + "Z"
    fout.write(json.dumps({"_summary": summary}) + "\n")
    fout.close()

    log.info("=== FINAL SUMMARY ===")
    log.info(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
