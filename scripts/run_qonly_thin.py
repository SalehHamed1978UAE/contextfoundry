"""Thin resumable driver: question -> /api/vault/chat -> FuzzyEvaluator -> JSONL.

Each invocation processes up to --batch questions and exits. Re-running picks up
from the last completed question (by index) using the JSONL file for state.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from src.test_runner.vault_manager import VaultManager
from src.test_runner.evaluator import FuzzyEvaluator


def already_done(jsonl_path: Path) -> set:
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
            "difficulty": q.get("difficulty"),
        })
    return norm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault-id", required=True)
    ap.add_argument("--questions-file", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--api", default="http://localhost:5000/api")
    ap.add_argument("--tree-based-retrieval", default="true", choices=["true", "false"])
    ap.add_argument("--batch", type=int, default=8, help="max questions this call")
    ap.add_argument("--corpus-name", default="stage1j_qonly")
    ap.add_argument("--per-q-timeout", type=int, default=60)
    args = ap.parse_args()

    tree = args.tree_based_retrieval == "true"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl = out_dir / f"{args.corpus_name}_{args.vault_id[:8]}_progress.jsonl"

    raw = json.loads(Path(args.questions_file).read_text())
    questions = normalize_questions(raw)
    total = len(questions)

    done = already_done(jsonl)
    pending = [q for q in questions if int(q["id"]) not in done]
    print(f"[thin] total={total}  done={len(done)}  pending={len(pending)}  batch={args.batch}", flush=True)
    if not pending:
        # final tally
        passed = 0
        failed = 0
        with jsonl.open() as f:
            for line in f:
                try:
                    r = json.loads(line)
                    if r.get("passed"):
                        passed += 1
                    else:
                        failed += 1
                except Exception:
                    pass
        print(f"[thin] ALL DONE — passed={passed}/{total} failed={failed}  pct={round(100*passed/total,1)}%", flush=True)
        return

    vm = VaultManager(args.api)
    if not vm.authenticate_dev():
        raise SystemExit("auth(no tenant) failed")
    if not vm.authenticate_dev(tenant_id=args.vault_id):
        raise SystemExit("auth(tenant) failed")
    print(f"[thin] auth OK", flush=True)

    evaluator = FuzzyEvaluator()

    processed = 0
    batch_start = time.time()
    for q in pending:
        if processed >= args.batch:
            break
        qid = int(q["id"])
        question = q["question"]
        expected = q["expected_answer"]
        t0 = time.time()
        try:
            answer, err_type = vm.query(
                args.vault_id, question,
                timeout=args.per_q_timeout,
                tree_based_retrieval=tree,
            )
        except Exception as e:
            answer = ""
            err_type = f"exception:{type(e).__name__}:{e}"
        dt = time.time() - t0

        if err_type:
            passed = False
            match_type = "error"
            failure_reason = str(err_type)
            failure_category = "ERROR"
        else:
            ev = evaluator.evaluate_with_details(expected, answer or "", question)
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
            "actual": answer,
            "error_type": err_type,
            "failure_reason": failure_reason,
            "failure_category": failure_category,
            "elapsed_sec": round(dt, 2),
        }
        with jsonl.open("a") as f:
            f.write(json.dumps(rec, default=str) + "\n")
        processed += 1
        marker = "PASS" if passed else f"FAIL({match_type})"
        print(f"[thin] Q{qid:>3}: {marker:<22}  t={dt:.1f}s", flush=True)

    elapsed = time.time() - batch_start
    done_after = already_done(jsonl)
    remain = total - len(done_after)
    print(f"[thin] batch done: processed={processed} elapsed={elapsed:.1f}s  remain={remain}/{total}", flush=True)


if __name__ == "__main__":
    main()
