#!/usr/bin/env python3
"""Oracle-candidate v2 experiment.

For each FAILED question in a v1 baseline run, build a candidate Fact from the
EXPECTED answer (the verifiable correct answer) instead of from v1's wrong
actual answer. Run FactEvaluator and record whether v2 endorses the true fact.

This isolates "evaluator works" from "candidate generation works": every
candidate is true by construction. v2 should return PROVEN /
STRONGLY_SUPPORTED / SUPPORTED on the cases where its evaluator logic is
sound; UNDERSUPPORTED / DISPROVEN / TIMEOUT / ERROR otherwise.

See docs/v2_oracle_candidate_experiment_scope_2026-05.md for the design and
decision matrix.
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
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.context_foundry.inference.engine import FactEvaluator
from src.context_foundry.inference.contracts import Fact, Verdict
from src.context_foundry.inference.llm.client import LLMClient
from src.context_foundry.inference.observability import trace as _trace_module

# Reuse the parallel runner's helpers — same schema load, same entity
# resolution, same extractor prompt, same verdict→answer mapping.
from scripts.run_v2_parallel import (
    VAULT_ID, DEFAULT_BASELINE, PER_QUESTION_CEILING_S, TOTAL_BUDGET_S,
    EMBED_MODEL, load_schema_from_vault, resolve_entity,
    extract_candidate_fact, derive_answer, _CounterCapture, reset_tracer,
)
from src.test_runner.evaluator import FuzzyEvaluator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("v2_oracle")


async def run_one_oracle(qid: int, question: str, expected: str,
                          v1_answer: str, v1_correct: bool,
                          llm: LLMClient, engine_factory,
                          evaluator: FuzzyEvaluator, session, tenant_id: str,
                          rel_types: List[str]) -> Dict[str, Any]:
    """Same shape as run_v2_parallel.run_one but feeds EXPECTED to extractor."""
    rec: Dict[str, Any] = {
        "q": qid, "question": question, "expected": expected,
        "v1_answer": v1_answer, "v1_correct": v1_correct,
        "oracle_input": expected,  # what we fed the extractor
        "v2_status": None, "v2_derived_answer": None,
        "v2_correct": None, "v2_wall_time_s": None,
        "v2_timeout": False, "v2_error": None,
        "v2_extractable": None, "v2_subject_id": None, "v2_target_id": None,
        "v2_relationship_type": None, "v2_subject_name": None,
        "v2_target_name": None, "v2_diagnostics": None,
    }
    t0 = time.monotonic()

    # Step 1: extract candidate fact from (question, EXPECTED)
    try:
        ext = await asyncio.wait_for(
            extract_candidate_fact(llm, question, expected, rel_types),
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
        rec["v2_derived_answer"] = "v2 not invoked: " + (
            ext.get("reason_if_not_extractable") or "no extractable fact")
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
        rec["v2_derived_answer"] = (
            f"v2 not invoked: relationship_type {rel_type!r} not in schema")
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
            verdict = await asyncio.wait_for(
                eng.evaluate(fact), timeout=PER_QUESTION_CEILING_S)
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

    summary = next((e for e in cap.events if e.get("event") == "evaluate_summary"), None)
    if summary:
        rec["v2_diagnostics"] = {k: v for k, v in summary.items()
                                  if k not in ("event", "ts", "level", "logger")}

    rec["v2_derived_answer"] = derive_answer(verdict, targ_name, expected)
    try:
        passed, _ = evaluator.evaluate(question, expected, rec["v2_derived_answer"])
        rec["v2_correct"] = bool(passed)
    except Exception as e:
        rec["v2_correct"] = None
        rec["v2_error"] = f"grade_error: {e}"

    # ---- diagnostic record (post-vector-fix oracle protocol) ----
    rec["diag"] = _build_diag_record(cap.events, rec)
    return rec


def _build_diag_record(events: List[Dict[str, Any]], rec: Dict[str, Any]) -> Dict[str, Any]:
    """Aggregate trace events into the per-question diagnostic record
    specified in the post-vector-fix oracle protocol."""
    from src.context_foundry.inference.llm.client import REASONING_ENGINE_VERSION
    diag: Dict[str, Any] = {
        "qid": rec.get("q"),
        "reasoning_engine_version": REASONING_ENGINE_VERSION,
        "extractable": rec.get("v2_extractable"),
        "entity_resolution_status": (
            "resolved" if rec.get("v2_subject_id") and rec.get("v2_target_id")
            else "missing_subject" if not rec.get("v2_subject_id")
            else "missing_target"),
        "planner_reached": False,
        "planner_cache_hit": None,
        "plan_hash": None,
        "presupposition_count": 0,
        "presupposition_results": [],
        "any_presupposition_disproven": False,
        "gather_reached": False,
        "gatherer_strategy_counts": {
            "graph_endpoint": 0, "fts_chunks": 0,
            "vector_chunks": 0, "vector_entities_to_rels": 0,
        },
        "chunks_retrieved": 0,
        "chunks_passed_to_polarity": 0,
        "chunks_passed_to_prover": None,  # not separately instrumented
        "polarity_llm_cache_hits": 0,
        "polarity_llm_cache_misses": 0,
        "prover_llm_cache_hits": 0,
        "prover_llm_cache_misses": 0,
        "planner_llm_cache_hits": 0,
        "planner_llm_cache_misses": 0,
        "polarity_verdicts_distribution": {
            "confirms": 0, "disconfirms": 0, "neutral": 0, "unset": 0,
        },
        "wall_seconds": rec.get("v2_wall_time_s"),
        "final_verdict": rec.get("v2_status"),
    }
    # planner_complete event (depth=0 only; replans tagged as such)
    for ev in events:
        if ev.get("event") == "planner_complete" and ev.get("depth", 0) == 0:
            diag["planner_reached"] = True
            diag["plan_hash"] = ev.get("plan_hash")
            diag["presupposition_count"] = ev.get("presupposition_count", 0)
            break
    # presuppositions_complete
    for ev in events:
        if ev.get("event") == "presuppositions_complete" and ev.get("depth", 0) == 0:
            diag["presupposition_results"] = ev.get("results", [])
            diag["any_presupposition_disproven"] = bool(ev.get("any_disproven"))
            break
    # gather_reached + strategy aggregation
    strategy_totals = diag["gatherer_strategy_counts"]
    polarity_chunks = 0
    for ev in events:
        et = ev.get("event")
        if et == "evidence_query_results":
            for s in ev.get("strategies", []):
                name = s.get("strategy")
                if name in strategy_totals:
                    strategy_totals[name] += s.get("items_returned", 0)
            diag["gather_reached"] = True
        elif et == "evidence_gathered" and ev.get("depth", 0) == 0:
            diag["chunks_retrieved"] = ev.get("count", 0)
        elif et == "polarity_classified":
            polarity_chunks += 1
            pol = ev.get("polarity") or "unset"
            if pol not in diag["polarity_verdicts_distribution"]:
                diag["polarity_verdicts_distribution"][pol] = 0
            diag["polarity_verdicts_distribution"][pol] += 1
    diag["chunks_passed_to_polarity"] = polarity_chunks
    # span_end events carry per-stage llm_cache_hit/miss counts.
    for ev in events:
        if ev.get("event") != "span_end":
            continue
        stage = ev.get("stage")
        hits = ev.get("llm_cache_hit_count", 0) or 0
        misses = ev.get("llm_cache_miss_count", 0) or 0
        if stage == "planner":
            diag["planner_llm_cache_hits"] += hits
            diag["planner_llm_cache_misses"] += misses
        elif stage == "gatherer":
            # polarity calls happen inside the gatherer span
            diag["polarity_llm_cache_hits"] += hits
            diag["polarity_llm_cache_misses"] += misses
        elif stage == "prover":
            diag["prover_llm_cache_hits"] += hits
            diag["prover_llm_cache_misses"] += misses
    # planner_cache_hit boolean: True iff planner span had only cache hits
    if diag["planner_reached"]:
        diag["planner_cache_hit"] = (
            diag["planner_llm_cache_misses"] == 0
            and diag["planner_llm_cache_hits"] > 0
        )
    # case_classification per protocol
    diag["case_classification"] = _classify_case(rec, diag)
    return diag


def _classify_case(rec: Dict[str, Any], diag: Dict[str, Any]) -> str:
    """Apply the named case classifications from the post-vector-fix
    oracle protocol (Cases A-E)."""
    if rec.get("v2_timeout"):
        return "INFRA_TIMEOUT_CANCELLATION_FAILURE"
    if rec.get("v2_status") in ("PROVEN", "STRONGLY_SUPPORTED", "SUPPORTED"):
        return "VECTOR_GATHERER_RECOVERY"
    # Did the engine short-circuit before gather?
    if diag.get("planner_reached") and not diag.get("gather_reached"):
        # planner_complete fired but evidence_query_results didn't
        # — engine bailed out at presupposition gate (or similar)
        return "GAP_PLANNER_PRESUPPOSITION_GATE"
    # Gather reached. Did fresh evidence reach polarity?
    new_chunks = (diag["gatherer_strategy_counts"]["vector_chunks"]
                  + diag["gatherer_strategy_counts"]["vector_entities_to_rels"])
    polarity_total = sum(diag["polarity_verdicts_distribution"].values())
    if diag.get("gather_reached") and new_chunks > 0 and polarity_total == 0:
        return "GAP_EVIDENCE_PIPELINE_DISCONNECT"
    if (diag.get("gather_reached") and polarity_total > 0
            and rec.get("v2_status") in ("UNDERSPECIFIED", "UNDERSUPPORTED",
                                          "UNKNOWN", "DISPROVEN", "CONTESTED")):
        return "GAP_EVALUATOR_REASONING_OR_PROMPT"
    return "UNCLASSIFIED"


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline", default=DEFAULT_BASELINE,
                     help="v1 baseline results JSON (filter to failures)")
    ap.add_argument("--vault-id", default=VAULT_ID)
    ap.add_argument("--out", required=True, help="output JSONL path")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--qids", default=None,
                    help="Comma-separated question IDs to run (filter applied "
                         "after FAILED filter). Diagnostic mode.")
    ap.add_argument("--include-passed", action="store_true",
                     help="oracle-test ALL 100 questions, not just failures")
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    log.info(f"baseline={args.baseline} out={out_path} vault={args.vault_id}")

    with open(args.baseline) as f:
        baseline = json.load(f)
    questions = baseline["all_results"]
    if not args.include_passed:
        questions = [q for q in questions if not q.get("passed")]
        log.info(f"filtered to {len(questions)} FAILED questions (oracle scope)")
    if args.qids:
        wanted = {int(x.strip()) for x in args.qids.split(",") if x.strip()}
        questions = [q for q in questions if int(q.get("q")) in wanted]
        log.info(f"--qids filter: kept {len(questions)} of {len(wanted)} requested")
    if args.limit:
        questions = questions[: args.limit]
    log.info(f"running {len(questions)} questions")

    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    session = Session()

    reset_tracer()
    ents, rels = load_schema_from_vault(session, args.vault_id)
    log.info(f"schema: {len(ents)} entity types, {len(rels)} relationship types")

    llm = LLMClient(session=session, pin_model=True)
    log.info(f"llm: {llm.model}")

    # Async embedder — gatherer awaits it. See run_v2_parallel.py for the bug
    # this fixes (sync def silently disabled vector strategies).
    try:
        from openai import OpenAI
        oai = OpenAI()
        async def embedder(text_in: str) -> list:
            def _call():
                r = oai.embeddings.create(model=EMBED_MODEL, input=text_in)
                return r.data[0].embedding
            return await asyncio.to_thread(_call)
    except Exception as e:
        log.warning(f"embedder unavailable: {e}")
        embedder = None

    def engine_factory():
        return FactEvaluator(
            session=session, llm_client=llm,
            schema_entity_types=ents, schema_relationship_types=rels,
            tenant_id=args.vault_id, embedder=embedder,
            max_depth=3, max_replans=1,
        )

    evaluator = FuzzyEvaluator()
    fout = open(out_path, "w")
    summary = {
        "total": len(questions), "v1_passed": 0, "oracle_correct": 0,
        "v2_no_candidate": 0, "v2_timeout": 0, "v2_error": 0,
        "v2_disproven": 0, "v2_undersupported": 0,
        "v2_proven_or_supported": 0, "v2_contested": 0,
        "started_at": datetime.utcnow().isoformat() + "Z",
    }
    t_start = time.monotonic()

    for i, q in enumerate(questions, 1):
        elapsed = time.monotonic() - t_start
        remaining = TOTAL_BUDGET_S - elapsed
        if remaining <= PER_QUESTION_CEILING_S:
            log.warning(f"budget exhausted at q{q['q']} ({elapsed:.0f}s)")
            for j in range(i - 1, len(questions)):
                qj = questions[j]
                fout.write(json.dumps({
                    "q": qj["q"], "question": qj["query"],
                    "expected": qj["expected"], "v1_answer": qj["actual"],
                    "v1_correct": qj["passed"],
                    "v2_status": "V2_BUDGET_EXHAUSTED",
                }) + "\n")
                fout.flush()
            break

        log.info(f"--- Q{q['q']} ({i}/{len(questions)}) — elapsed={elapsed:.0f}s ---")
        try:
            rec = await run_one_oracle(
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

        # Tally — oracle decision matrix from scope doc
        if rec.get("v1_correct"): summary["v1_passed"] += 1
        if rec.get("v2_correct"): summary["oracle_correct"] += 1
        st = rec.get("v2_status")
        if st == "V2_NO_CANDIDATE": summary["v2_no_candidate"] += 1
        if rec.get("v2_timeout"): summary["v2_timeout"] += 1
        if st in ("V2_ERROR", "V2_RUNNER_ERROR", "EXTRACTION_ERROR",
                  "EXTRACTION_TIMEOUT"): summary["v2_error"] += 1
        if st == "DISPROVEN": summary["v2_disproven"] += 1
        if st in ("UNDERSUPPORTED", "UNKNOWN", "UNDERSPECIFIED"):
            summary["v2_undersupported"] += 1
        if st in ("PROVEN", "STRONGLY_SUPPORTED", "SUPPORTED"):
            summary["v2_proven_or_supported"] += 1
        if st == "CONTESTED": summary["v2_contested"] += 1

        fout.write(json.dumps(rec) + "\n")
        fout.flush()
        log.info(
            f"Q{q['q']}: oracle_input={(q['expected'] or '')[:60]!r} "
            f"v2={st} v2_correct={rec.get('v2_correct')} "
            f"wall={rec.get('v2_wall_time_s')}s"
        )

    summary["wall_time_s"] = round(time.monotonic() - t_start, 1)
    summary["finished_at"] = datetime.utcnow().isoformat() + "Z"
    fout.write(json.dumps({"_summary": summary}) + "\n")
    fout.close()

    log.info("=== ORACLE FINAL SUMMARY ===")
    log.info(json.dumps(summary, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
