"""
Standalone driver to run a question set against an existing populated vault,
bypassing the runner's outer verify_extraction_complete check.

Usage:
    python -u scripts/run_questions_only_stage1j.py \
        --vault-id <uuid> \
        --questions-file <path> \
        --out-dir test_results/stage1j_questions_only/ \
        [--workers 4] [--tree-based-retrieval true|false]
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__) + "/.."))

from src.test_runner.vault_manager import VaultManager
from src.test_runner.evaluator import FuzzyEvaluator
from src.test_runner.test_executor import TestExecutor


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault-id", required=True)
    ap.add_argument("--questions-file", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--api", default="http://localhost:5000/api")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--tree-based-retrieval", default="true",
                    choices=["true", "false"])
    ap.add_argument("--corpus-name", default="stage1j_questions_only")
    ap.add_argument("--min-chunks", type=int, default=50)
    args = ap.parse_args()

    tree = args.tree_based_retrieval == "true"
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    qfile = Path(args.questions_file)
    questions = json.loads(qfile.read_text())
    if not isinstance(questions, list):
        raise SystemExit(f"Questions file must be a JSON array; got {type(questions)}")

    norm = []
    for i, q in enumerate(questions, start=1):
        text = q.get("question") or q.get("q") or q.get("prompt")
        expected = (q.get("expected") or q.get("expected_answer")
                    or q.get("answer") or q.get("gold"))
        if not text or expected is None:
            raise SystemExit(f"Question {i} missing 'question' or 'expected': {q}")
        norm.append({
            "id": q.get("id", i),
            "question": text,
            "expected_answer": expected,
            "category": q.get("category"),
            "difficulty": q.get("difficulty"),
        })

    print(f"[driver] Loaded {len(norm)} questions from {qfile}")
    print(f"[driver] Vault: {args.vault_id}")
    print(f"[driver] API: {args.api}")
    print(f"[driver] Tree retrieval: {tree}")
    print(f"[driver] Workers: {args.workers}")
    print(f"[driver] Output: {out_dir}")

    vm = VaultManager(args.api)

    print("[driver] Auth (no tenant)...")
    if not vm.authenticate_dev():
        raise SystemExit("Initial dev auth failed")

    print(f"[driver] Auth (tenant_id={args.vault_id})...")
    if not vm.authenticate_dev(tenant_id=args.vault_id):
        raise SystemExit("Tenant-context auth failed")

    stats = vm.get_vault_stats(args.vault_id)
    print(f"[driver] Vault stats: chunks={stats.get('chunk_count')}, "
          f"entities={stats.get('entity_count')}, "
          f"relationships={stats.get('relationship_count')}")

    evaluator = FuzzyEvaluator()
    executor = TestExecutor(vm, evaluator)

    started = time.time()
    results = executor.run_test(
        vault_id=args.vault_id,
        questions_data=norm,
        results_dir=out_dir,
        corpus_name=args.corpus_name,
        min_chunks=args.min_chunks,
        resume=False,
        test_run_id=None,
        enable_tracing=True,
        tree_based_retrieval=tree,
        parallel_workers=args.workers,
    )
    elapsed = int(time.time() - started)

    summary = results.get("results", {})
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    total = summary.get("total", len(norm))
    pct = summary.get("accuracy_pct", round(100.0 * passed / max(total, 1), 1))

    print("\n" + "=" * 70)
    print(f"DONE in {elapsed}s — {passed}/{total} passed ({pct}%) — failed={failed}")
    print("=" * 70)

    failures = []
    for r in results.get("results_list", []) or results.get("details", []) or []:
        if not r.get("passed", False):
            failures.append({
                "id": r.get("q") or r.get("id"),
                "question": r.get("question"),
                "expected": r.get("expected") or r.get("expected_answer"),
                "actual": r.get("actual") or r.get("answer"),
                "error_type": r.get("error_type"),
            })

    out_summary = {
        "vault_id": args.vault_id,
        "questions_file": str(qfile),
        "tree_based_retrieval": tree,
        "workers": args.workers,
        "elapsed_sec": elapsed,
        "score": {"passed": passed, "failed": failed, "total": total, "pct": pct},
        "failures": failures,
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    summary_path = out_dir / f"summary_{args.vault_id[:8]}_{int(started)}.json"
    summary_path.write_text(json.dumps(out_summary, indent=2, default=str))
    print(f"[driver] Summary written to {summary_path}")
    print(f"[driver] Progress JSONL in {out_dir} (per-question detail)")


if __name__ == "__main__":
    main()
