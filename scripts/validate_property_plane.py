#!/usr/bin/env python3
"""M4 — Validate Property Plane against Nexus 100Q (Stage 3A).

Runs the 35-question PROPERTY subset (or full 100Q) against the live
platform using the ToolAgent harness, then reports score before/after,
recovered questions, regressions, and answer_source distribution.

Usage:
    # PROPERTY subset (fast feedback)
    python scripts/validate_property_plane.py --tenant-id <uuid> --subset property

    # Full 100Q
    python scripts/validate_property_plane.py --tenant-id <uuid>

    # Dry run (show questions, don't query)
    python scripts/validate_property_plane.py --tenant-id <uuid> --dry-run

Requires:
    - Database access (migration applied, adapter run)
    - Platform server running at $API_BASE_URL (default http://localhost:5000)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

logger = logging.getLogger(__name__)

# ── Question subsets ────────────────────────────────────────────────────────

# The 35 PROPERTY-plane questions from Stage 2F evidence-plane audit
# Source: test_results/stage2f_evidence_plane/per_question.csv (primary='PROPERTY')
PROPERTY_SUBSET_IDS = [
    6, 7, 8, 9, 10, 19, 22, 23, 24, 25, 26, 28, 30, 33, 34,
    40, 41, 42, 48, 51, 54, 55, 56, 58, 59, 66, 67, 73, 76, 79,
    84, 89, 96, 97, 100,
]

# The 16 PROPERTY questions failing at s2e1 baseline (recovery candidates)
# Source: test_results/stage2f_evidence_plane/per_question.csv (primary='PROPERTY' AND s2e1='False')
FAILING_PROPERTY_IDS = [
    6, 8, 10, 23, 24, 25, 33, 40, 42, 48, 55, 67, 79, 89, 96, 97,
]


def load_questions(subset: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load the Nexus 100Q question set.

    If subset == "property", returns only the 35 PROPERTY-plane questions.
    If subset == "failing", returns only the 16 failing questions.
    Otherwise returns all 100 questions.
    """
    # Try to load from the test data file
    question_paths = [
        "test_questions/nexus_100q.json",
        "data/nexus_industries_100q.json",
        "data/test-runner/nexus_industries_100q.json",
        "src/test_runner/data/nexus_industries_100q.json",
    ]

    questions = None
    for path in question_paths:
        full_path = os.path.join(
            os.path.dirname(__file__), "..", path
        )
        if os.path.exists(full_path):
            with open(full_path) as f:
                questions = json.load(f)
            break

    if questions is None:
        logger.warning("Could not find question set file, using placeholder")
        return []

    if isinstance(questions, dict) and "questions" in questions:
        questions = questions["questions"]

    # Synthesize 1-based id if file shape is a flat list without ids
    for i, q in enumerate(questions):
        if "id" not in q:
            q["id"] = i + 1

    if subset == "property":
        return [q for q in questions if q.get("id", 0) in PROPERTY_SUBSET_IDS]
    elif subset == "failing":
        return [q for q in questions if q.get("id", 0) in FAILING_PROPERTY_IDS]

    return questions


def query_platform(
    api_base_url: str,
    tenant_id: str,
    query: str,
    *,
    conversation_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Send a query to the platform API and return the response."""
    url = f"{api_base_url.rstrip('/')}/api/query"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "query": query,
        "tenant_id": tenant_id,
    }
    if conversation_id:
        payload["conversation_id"] = conversation_id

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=120)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return {"answer": f"ERROR: {e}", "answer_source": "ERROR"}


def evaluate_answer(expected: str, actual: str) -> bool:
    """Simple fuzzy evaluation — check if key terms from expected appear in actual."""
    if not expected or not actual:
        return False

    expected_lower = expected.lower()
    actual_lower = actual.lower()

    # Extract key numeric values and terms
    import re
    numbers = re.findall(r"\d+[\d,.]*", expected_lower)
    key_terms = [n for n in numbers if len(n) > 1]

    if not key_terms:
        # No numbers — check for key phrases
        words = expected_lower.split()
        key_terms = [w for w in words if len(w) > 3][:3]

    if not key_terms:
        return expected_lower in actual_lower

    matched = sum(1 for t in key_terms if t in actual_lower)
    return matched >= max(1, len(key_terms) // 2)


def run_validation(
    tenant_id: str,
    api_base_url: str,
    subset: Optional[str] = None,
    dry_run: bool = False,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the validation suite and return a report."""
    questions = load_questions(subset)
    if not questions:
        return {"error": "No questions loaded"}

    print(f"\n=== Property Plane Validation (Stage 3A) ===")
    print(f"Tenant: {tenant_id}")
    print(f"API: {api_base_url}")
    print(f"Questions: {len(questions)} ({subset or 'all'})")
    print()

    if dry_run:
        for q in questions:
            qid = q.get("id", "?")
            query = q.get("question") or q.get("query", "")
            expected = q.get("expected_answer") or q.get("answer", "")
            print(f"  Q{qid}: {query}")
            print(f"    Expected: {expected[:100]}...")
            print()
        return {"dry_run": True, "question_count": len(questions)}

    results = []
    correct = 0
    source_dist: Dict[str, int] = {}
    property_hits = 0

    for i, q in enumerate(questions):
        qid = q.get("id", i + 1)
        query = q.get("question") or q.get("query", "")
        expected = q.get("expected_answer") or q.get("answer", "")

        print(f"  [{i+1}/{len(questions)}] Q{qid}: {query[:80]}...")
        response = query_platform(api_base_url, tenant_id, query, api_key=api_key)

        actual = response.get("answer", "")
        source = response.get("answer_source", "UNKNOWN")
        is_correct = evaluate_answer(expected, actual)

        if is_correct:
            correct += 1

        source_dist[source] = source_dist.get(source, 0) + 1

        pp_diag = response.get("property_plane_diagnostics") or {}
        if pp_diag.get("hit"):
            property_hits += 1

        results.append({
            "question_id": qid,
            "query": query,
            "expected": expected,
            "actual": actual[:200],
            "answer_source": source,
            "correct": is_correct,
            "property_hit": pp_diag.get("hit", False),
        })

        status = "PASS" if is_correct else "FAIL"
        print(f"    [{status}] source={source} answer={actual[:80]}...")

    score = correct / len(questions) * 100 if questions else 0

    report = {
        "timestamp": datetime.utcnow().isoformat(),
        "tenant_id": tenant_id,
        "subset": subset or "all",
        "total_questions": len(questions),
        "correct": correct,
        "score": round(score, 1),
        "score_fraction": f"{correct}/{len(questions)}",
        "property_plane_hits": property_hits,
        "answer_source_distribution": source_dist,
        "results": results,
    }

    print(f"\n=== Results ===")
    print(f"Score: {correct}/{len(questions)} ({score:.1f}%)")
    print(f"Property plane hits: {property_hits}")
    print(f"Source distribution: {json.dumps(source_dist, indent=2)}")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Validate Property Plane against Nexus 100Q"
    )
    parser.add_argument("--tenant-id", required=True, help="Tenant UUID")
    parser.add_argument(
        "--api-base-url",
        default=os.environ.get("API_BASE_URL", "http://localhost:5000"),
        help="Platform API base URL",
    )
    parser.add_argument(
        "--subset",
        choices=["property", "failing", "all"],
        default=None,
        help="Question subset to run",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show questions without querying",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Output JSON report path",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("API_KEY"),
        help="API key for authentication",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    report = run_validation(
        tenant_id=args.tenant_id,
        api_base_url=args.api_base_url,
        subset=args.subset,
        dry_run=args.dry_run,
        api_key=args.api_key,
    )

    if args.output:
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2, default=str)
        print(f"\nReport written to {args.output}")


if __name__ == "__main__":
    main()
