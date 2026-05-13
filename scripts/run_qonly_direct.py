"""Stage 2D — direct in-process validation harness.

Imports ToolAgent directly (no HTTP, no /api/vault/chat) so the running
Start All gunicorn process is not involved and need not be restarted.
For each question:

  1. Call ToolAgent.query(tree_based_retrieval=False).
  2. If result is no_data / "I don't know" AND query is an attribute query,
     invoke document_evidence_fallback.attempt_document_evidence_fallback().
  3. Tag final answer with `answer_source` ∈ {TRUSTED_GRAPH_FACT,
     STAGING_GRAPH_FACT, DOCUMENT_EVIDENCE, GAP}.
  4. Score with FuzzyEvaluator.
  5. Append result to JSONL (resumable).

Read-only with respect to entities/relationships/documents/document_chunks/
extraction_requests. Conversation history writes via ConversationStore are
inherited from ToolAgent and are append-only side-effects (documented in
Stage 2C findings).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from src.test_runner.evaluator import FuzzyEvaluator  # noqa: E402
from src.context_foundry.retrieval.document_evidence_fallback import (  # noqa: E402
    ANSWER_SOURCE_DOCUMENT_EVIDENCE,
    ANSWER_SOURCE_GAP,
    ANSWER_SOURCE_TRUSTED_GRAPH,
    attempt_document_evidence_fallback,
    is_attribute_query,
    looks_like_no_data,
)


def already_done(jsonl_path: Path):
    done = set()
    if not jsonl_path.exists():
        return done
    with jsonl_path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
                done.add(int(rec.get("q")))
            except Exception:
                continue
    return done


def normalize_questions(raw):
    norm = []
    for i, q in enumerate(raw, start=1):
        text = q.get("question") or q.get("q") or q.get("prompt")
        expected = (q.get("expected") or q.get("expected_answer")
                    or q.get("answer") or q.get("gold"))
        if not text or expected is None:
            raise SystemExit(f"Q{i} missing question/expected: {q}")
        norm.append({
            "id": q.get("id", i),
            "question": text,
            "expected_answer": expected,
            "category": q.get("category"),
        })
    return norm


def _classify_kg_answer_source(response: Dict[str, Any]) -> str:
    """Classify the ToolAgent response's KG-side answer source.

    We treat NOT_FOUND / direct_no_data / "I don't know" responses as GAP,
    and any other response as TRUSTED_GRAPH_FACT (the live system today
    doesn't distinguish STAGING vs TRUSTED in its API surface).
    """
    if not response:
        return ANSWER_SOURCE_GAP
    extra = response.get("extra") or {}
    if extra.get("not_found_response"):
        return ANSWER_SOURCE_GAP
    answer = response.get("answer") or response.get("response") or ""
    if not answer or looks_like_no_data(answer):
        return ANSWER_SOURCE_GAP
    return ANSWER_SOURCE_TRUSTED_GRAPH


def _build_session(database_url: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(database_url, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


def _build_agent(vault_id: str, session):
    from src.context_foundry.agents.tool_agent import ToolAgent
    return ToolAgent(session=session, tenant_id=vault_id)


def _ask_agent(agent, question: str, tree: bool, timeout: int = 60) -> Dict[str, Any]:
    """Call ToolAgent.query with hard wall-clock timeout (signal-based)."""
    import signal

    class _TimeoutErr(Exception):
        pass

    def _handler(signum, frame):
        raise _TimeoutErr(f"agent timeout after {timeout}s")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(int(timeout))
    try:
        return agent.query(
            question=question,
            tree_based_retrieval=tree,
        )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault-id", required=True)
    ap.add_argument("--questions-file", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--corpus-name", default="stage2d_direct")
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--per-q-timeout", type=int, default=45)
    ap.add_argument("--tree-based-retrieval", default="false", choices=["true", "false"])
    ap.add_argument("--enable-fallback", default="true", choices=["true", "false"],
                    help="Enable DOCUMENT_EVIDENCE fallback (Stage 2D Part B)")
    ap.add_argument("--top-k", type=int, default=5)
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set")

    tree = args.tree_based_retrieval == "true"
    fallback_on = args.enable_fallback == "true"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = out_dir / f"{args.corpus_name}_{args.vault_id[:8]}_progress.jsonl"

    raw = json.loads(Path(args.questions_file).read_text())
    questions = normalize_questions(raw)
    total = len(questions)

    done = already_done(jsonl)
    pending = [q for q in questions if int(q["id"]) not in done]
    print(
        f"[direct] total={total}  done={len(done)}  pending={len(pending)}  "
        f"batch={args.batch}  tree={tree}  fallback={fallback_on}",
        flush=True,
    )
    if not pending:
        # Final tally
        passed = 0
        failed = 0
        de_count = 0
        with jsonl.open() as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if r.get("passed"):
                        passed += 1
                    else:
                        failed += 1
                    if r.get("answer_source") == ANSWER_SOURCE_DOCUMENT_EVIDENCE:
                        de_count += 1
                except Exception:
                    pass
        print(
            f"[direct] ALL DONE — passed={passed}/{total}  failed={failed}  "
            f"DOCUMENT_EVIDENCE={de_count}  pct={round(100*passed/total,1)}%",
            flush=True,
        )
        return

    session = _build_session(db_url)
    agent = _build_agent(args.vault_id, session)
    evaluator = FuzzyEvaluator()
    print(f"[direct] in-process agent ready", flush=True)

    processed = 0
    batch_start = time.time()
    for q in pending:
        if processed >= args.batch:
            break
        qid = int(q["id"])
        question = q["question"]
        expected = q["expected_answer"]
        t0 = time.time()
        kg_answer = ""
        kg_source = ANSWER_SOURCE_GAP
        final_answer = ""
        answer_source = ANSWER_SOURCE_GAP
        fallback_fired = False
        fallback_category = None
        fallback_chunks_count = 0
        err_type: Optional[str] = None
        citations = []

        try:
            response = _ask_agent(agent, question, tree=tree, timeout=args.per_q_timeout)
            kg_answer = response.get("answer") or response.get("response") or ""
            kg_source = _classify_kg_answer_source(response)
            final_answer = kg_answer
            answer_source = kg_source

            if (
                fallback_on
                and kg_source != ANSWER_SOURCE_TRUSTED_GRAPH
                and is_attribute_query(question)
            ):
                # Use a fresh session for the fallback so any session state
                # mutated by the agent does not contaminate provenance lookups.
                fb_session = _build_session(db_url)
                try:
                    fb = attempt_document_evidence_fallback(
                        session=fb_session,
                        tenant_id=args.vault_id,
                        query=question,
                        kg_answer=kg_answer,
                        kg_answer_source=kg_source,
                        top_k=args.top_k,
                    )
                finally:
                    fb_session.close()

                if fb is not None:
                    final_answer = fb.answer
                    answer_source = fb.answer_source
                    fallback_fired = True
                    fallback_category = fb.attribute_category
                    fallback_chunks_count = len(fb.chunks)
                    citations = fb.citations
        except Exception as e:
            err_type = f"exception:{type(e).__name__}:{str(e)[:200]}"
            traceback.print_exc()
            try:
                session.rollback()
            except Exception:
                pass

        dt = time.time() - t0

        if err_type:
            passed = False
            match_type = "error"
            failure_reason = err_type
            failure_category = "ERROR"
        else:
            ev = evaluator.evaluate_with_details(expected, final_answer or "", question)
            passed = bool(ev.get("passed"))
            match_type = ev.get("match_type")
            failure_reason = ev.get("failure_reason")
            failure_category = ev.get("failure_category")

        rec = {
            "q": qid,
            "passed": passed,
            "match_type": match_type,
            "query": question,
            "expected": expected,
            "actual": final_answer,
            "kg_answer": kg_answer,
            "kg_source": kg_source,
            "answer_source": answer_source,
            "fallback_fired": fallback_fired,
            "fallback_category": fallback_category,
            "fallback_chunks_count": fallback_chunks_count,
            "citations": citations[:5],
            "error_type": err_type,
            "failure_reason": failure_reason,
            "failure_category": failure_category,
            "elapsed_sec": round(dt, 2),
        }
        with jsonl.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        processed += 1
        marker = "PASS" if passed else f"FAIL({match_type})"
        fb_marker = f" [DE:{fallback_category}]" if fallback_fired else ""
        print(f"[direct] Q{qid:>3}: {marker:<22}  src={answer_source:<22}{fb_marker}  t={dt:.1f}s", flush=True)

    elapsed = time.time() - batch_start
    done_after = already_done(jsonl)
    remain = total - len(done_after)
    print(f"[direct] batch done: processed={processed} elapsed={elapsed:.1f}s  remain={remain}/{total}", flush=True)

    try:
        session.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
