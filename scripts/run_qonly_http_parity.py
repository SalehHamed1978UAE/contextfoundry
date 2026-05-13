"""Stage 2E-1 — HTTP-parity in-process harness.

Replicates the EXACT post-agent processing of `web_app.py /api/vault/chat`
without restarting the live gunicorn (Start All) and without starting any
worker threads. The plan explicitly authorizes this approach:

    "Use the closest-to-production path available without restarting Start All.
     Preferred: Flask test_client or in-process route call"

Sequence per question (mirrors web_app.py L4343-4490):
  1. set_tenant_context(db_session, tenant_id)
  2. ToolAgent.query(resolved_query, vault_context=..., tree_based_retrieval=False)
  3. QA verifier — replaces answer when verdict ∈ {OFF_TOPIC, INSUFFICIENT,
     UNSUPPORTED, SUSPICIOUS}, exactly as the route does.
  4. STAGE 2E-1 hook — apply_to_agent_result(...) with the feature flag.
  5. Construct the response_data dict in the same shape as web_app.py L4460-4490.
  6. Score with FuzzyEvaluator and append to JSONL.

Read-only contract (standing): no writes to entities/relationships/documents/
document_chunks/extraction_requests. Conversation messages are NOT written
here (we skip ConversationStore.add_message because the route's only need for
it is multi-turn pronoun resolution, and the test set has no pronouns).
"""
from __future__ import annotations

import argparse
import json
import os
import signal
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
    apply_to_agent_result,
    classify_agent_kg_source,
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
                done.add(int(json.loads(line).get("q")))
            except Exception:
                continue
    return done


def normalize_questions(raw):
    out = []
    for i, q in enumerate(raw, start=1):
        text = q.get("question") or q.get("q") or q.get("prompt")
        expected = (q.get("expected") or q.get("expected_answer")
                    or q.get("answer") or q.get("gold"))
        if not text or expected is None:
            raise SystemExit(f"Q{i} malformed: {q}")
        out.append({
            "id": q.get("id", i),
            "question": text,
            "expected_answer": expected,
        })
    return out


def _build_session(db_url: str):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    engine = create_engine(db_url, pool_pre_ping=True)
    return sessionmaker(bind=engine)()


def _route_post_agent_processing(
    *,
    agent_result: Dict[str, Any],
    db_session,
    tenant_id: str,
    resolved_query: str,
    fallback_payload_value: Any,
):
    """Replicate web_app.py L4406-4485 verbatim (QA verifier + Stage 2E-1 hook)."""
    qa_verdict_dict = agent_result.get("qa_verdict")
    qa_replacement_applied = False

    if not qa_verdict_dict:
        try:
            from src.context_foundry.agents.qa_verifier import AnswerVerifierAgent
            verifier = AnswerVerifierAgent()
            qa_verdict = verifier.verify_from_retrieval_result(
                question=resolved_query,
                answer=agent_result.get("answer", ""),
                retrieval_result=agent_result.get("pipeline_result"),
                tool_calls=agent_result.get("tool_calls", []),
            )
            qa_verdict_dict = qa_verdict.to_dict()
            agent_result["qa_verdict"] = qa_verdict_dict

            # Match web_app.py L4438-4447 verbatim
            status = qa_verdict.status
            if status in ("OFF_TOPIC", "INSUFFICIENT", "UNSUPPORTED", "SUSPICIOUS"):
                if status == "OFF_TOPIC":
                    agent_result["answer"] = (
                        "I found related information but it doesn't directly answer your "
                        "question. Could you rephrase?"
                    )
                elif status == "INSUFFICIENT":
                    agent_result["answer"] = (
                        f"I have partial information but cannot fully answer this. "
                        f"{qa_verdict.reason}"
                    )
                elif status == "SUSPICIOUS":
                    agent_result["answer"] = (
                        "I couldn't find reliable data. Could you try rephrasing your question?"
                    )
                else:  # UNSUPPORTED
                    agent_result["answer"] = (
                        "I don't have verified information to answer this question."
                    )
                qa_replacement_applied = True
        except Exception:
            pass

    # Stage 2E-1 hook
    apply_to_agent_result(
        agent_result,
        session=db_session,
        tenant_id=tenant_id,
        query=resolved_query,
        request_payload_value=fallback_payload_value,
        qa_verdict=qa_verdict_dict,
    )
    agent_result["_qa_replacement_applied"] = qa_replacement_applied
    return agent_result


def _ask_route(agent, db_session, tenant_id, question, *, tree, fallback, vault_context, timeout):
    """One in-process call mirroring /api/vault/chat tool_agent branch."""
    class _TimeoutErr(Exception):
        pass
    def _h(s, f): raise _TimeoutErr(f"agent timeout {timeout}s")
    old = signal.signal(signal.SIGALRM, _h)
    signal.alarm(int(timeout))
    try:
        agent_result = agent.query(
            question=question,
            tree_based_retrieval=tree,
            vault_context=vault_context,
        )
        return _route_post_agent_processing(
            agent_result=agent_result,
            db_session=db_session,
            tenant_id=tenant_id,
            resolved_query=question,
            fallback_payload_value=fallback,
        )
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault-id", required=True)
    ap.add_argument("--questions-file", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--corpus-name", default="stage2e1_http")
    ap.add_argument("--batch", type=int, default=12)
    ap.add_argument("--per-q-timeout", type=int, default=50)
    ap.add_argument("--tree-based-retrieval", default="false", choices=["true", "false"])
    ap.add_argument("--enable-fallback", default="true", choices=["true", "false"])
    ap.add_argument("--qids", default=None, help="comma-separated subset, e.g. 14,32,40")
    args = ap.parse_args()

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise SystemExit("DATABASE_URL not set")

    tree = args.tree_based_retrieval == "true"
    fallback_payload = True if args.enable_fallback == "true" else False
    qid_filter = None
    if args.qids:
        qid_filter = set(int(x) for x in args.qids.split(","))

    out_dir = Path(args.out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = out_dir / f"{args.corpus_name}_{args.vault_id[:8]}_progress.jsonl"

    raw = json.loads(Path(args.questions_file).read_text())
    questions = normalize_questions(raw)
    if qid_filter:
        questions = [q for q in questions if int(q["id"]) in qid_filter]
    total = len(questions)

    done = already_done(jsonl)
    pending = [q for q in questions if int(q["id"]) not in done]
    print(f"[http_parity] total={total} done={len(done)} pending={len(pending)} "
          f"batch={args.batch} tree={tree} fallback_payload={fallback_payload}", flush=True)
    if not pending:
        # Final summary
        recs = [json.loads(l) for l in jsonl.open()]
        passed = sum(1 for r in recs if r.get("passed"))
        de = sum(1 for r in recs if r.get("answer_source") == ANSWER_SOURCE_DOCUMENT_EVIDENCE)
        print(f"[http_parity] ALL DONE — passed={passed}/{total} DOCUMENT_EVIDENCE={de}", flush=True)
        return

    # Build session + agent + grab vault_context like web_app.py does
    from sqlalchemy import text
    from src.context_foundry.models.schema import set_tenant_context
    from src.context_foundry.agents.tool_agent import ToolAgent

    session = _build_session(db_url)
    set_tenant_context(session, args.vault_id)
    vault_context = None
    try:
        row = session.execute(
            text("SELECT name FROM platform.tenants WHERE id = :tid"),
            {"tid": args.vault_id},
        ).fetchone()
        if row:
            vault_context = row[0]
    except Exception:
        pass
    agent = ToolAgent(session, args.vault_id)
    evaluator = FuzzyEvaluator()
    print(f"[http_parity] in-process route ready  vault_context={vault_context!r}", flush=True)

    processed = 0
    t_batch = time.time()
    for q in pending:
        if processed >= args.batch:
            break
        qid = int(q["id"])
        question = q["question"]
        expected = q["expected_answer"]
        t0 = time.time()
        err = None
        agent_result: Optional[Dict[str, Any]] = None
        try:
            agent_result = _ask_route(
                agent, session, args.vault_id, question,
                tree=tree, fallback=fallback_payload, vault_context=vault_context,
                timeout=args.per_q_timeout,
            )
        except Exception as e:
            err = f"exception:{type(e).__name__}:{str(e)[:200]}"
            traceback.print_exc()
            try: session.rollback()
            except Exception: pass
        dt = time.time() - t0

        ans = (agent_result or {}).get("answer", "") if not err else ""
        diag = (agent_result or {}).get("document_evidence_diagnostics") or {}
        answer_source = (agent_result or {}).get("answer_source") or "semantic"
        # Translate plain semantic back to TRUSTED_GRAPH_FACT vs GAP for reporting
        if answer_source not in (ANSWER_SOURCE_DOCUMENT_EVIDENCE,):
            kg_src = classify_agent_kg_source(agent_result, (agent_result or {}).get("qa_verdict"))
            answer_source_report = kg_src
        else:
            answer_source_report = ANSWER_SOURCE_DOCUMENT_EVIDENCE

        if err:
            passed = False; mt = "error"; fr = err; fc = "ERROR"
        else:
            ev = evaluator.evaluate_with_details(expected, ans, question)
            passed = bool(ev.get("passed"))
            mt = ev.get("match_type"); fr = ev.get("failure_reason"); fc = ev.get("failure_category")

        rec = {
            "q": qid,
            "passed": passed,
            "match_type": mt,
            "query": question,
            "expected": expected,
            "actual": ans,
            "answer_source": answer_source_report,
            "qa_replacement_applied": (agent_result or {}).get("_qa_replacement_applied"),
            "qa_verdict_status": ((agent_result or {}).get("qa_verdict") or {}).get("status"),
            "doc_ev_diagnostics": diag,
            "doc_ev_citations": (agent_result or {}).get("document_evidence", [])[:5],
            "error_type": err,
            "failure_reason": fr,
            "failure_category": fc,
            "elapsed_sec": round(dt, 2),
        }
        with jsonl.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        processed += 1
        marker = "PASS" if passed else f"FAIL({mt})"
        de_tag = " [DE]" if answer_source_report == ANSWER_SOURCE_DOCUMENT_EVIDENCE else ""
        gate = f" gate={diag.get('gate_block_reason')}" if diag.get("flag_enabled") and not diag.get("fallback_used") else ""
        print(f"[http_parity] Q{qid:>3}: {marker:<22} src={answer_source_report:<22}{de_tag}{gate}  t={dt:.1f}s", flush=True)

    elapsed = time.time() - t_batch
    after = already_done(jsonl)
    remain = total - len(after)
    print(f"[http_parity] batch done: processed={processed} elapsed={elapsed:.1f}s remain={remain}/{total}", flush=True)

    try: session.close()
    except Exception: pass


if __name__ == "__main__":
    main()
