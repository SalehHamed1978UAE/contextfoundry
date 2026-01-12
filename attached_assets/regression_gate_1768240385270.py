#!/usr/bin/env python3
"""
REGRESSION GATE SCRIPT

Deterministic go/no-go validation.
Run this before any deployment or after any significant change.

Exit codes:
    0 = PASS (safe to proceed)
    1 = FAIL (do NOT proceed)

Usage:
    python scripts/regression_gate.py           # Run all regression tests
    python scripts/regression_gate.py --quick   # Run only critical tests
    python scripts/regression_gate.py --verbose # Show detailed output
"""

import subprocess
import sys
import argparse
import time
from datetime import datetime


RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def print_banner(text: str, color: str = ""):
    """Print a banner."""
    width = 70
    print(f"\n{color}{'=' * width}")
    print(f"{text.center(width)}")
    print(f"{'=' * width}{RESET}\n")


def run_tests(markers: str = "regression", verbose: bool = False, stop_on_fail: bool = True) -> tuple:
    """Run pytest with specified markers. Returns (exit_code, output)."""
    cmd = [
        sys.executable, "-m", "pytest",
        "tests/test_deterministic_regression.py",
        "-m", markers,
        "--tb=short",
    ]

    if verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    if stop_on_fail:
        cmd.append("-x")  # Stop on first failure

    print(f"Running: {' '.join(cmd)}\n")

    result = subprocess.run(cmd, capture_output=True, text=True)

    return result.returncode, result.stdout + result.stderr


def run_quick_checks() -> list:
    """Run quick deterministic checks without pytest."""
    results = []

    # Check 1: Database connection
    try:
        import os
        from sqlalchemy import create_engine, text

        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            results.append(("Database URL", False, "DATABASE_URL not set"))
        else:
            engine = create_engine(db_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            results.append(("Database Connection", True, "OK"))
    except Exception as e:
        results.append(("Database Connection", False, str(e)[:50]))

    # Check 2: Critical imports
    try:
        from src.context_foundry.ontology.candidate_store import CandidateStore
        from src.context_foundry.ontology.normalizer import CandidateNormalizer
        results.append(("Ontology Imports", True, "OK"))
    except Exception as e:
        results.append(("Ontology Imports", False, str(e)[:50]))

    # Check 3: Schema loader
    try:
        from src.context_foundry.config.domain_schema import get_schema_loader
        loader = get_schema_loader()
        types = loader.schema.get_relationship_type_names()
        if "HOLDS_POSITION" in types and "WORKS_AT" in types:
            results.append(("Schema Types", True, f"{len(types)} types loaded"))
        else:
            results.append(("Schema Types", False, "Missing critical types"))
    except Exception as e:
        results.append(("Schema Types", False, str(e)[:50]))

    # Check 4: Known types not in candidates (CRITICAL)
    try:
        import os
        from sqlalchemy import create_engine, text

        db_url = os.environ.get("DATABASE_URL")
        if db_url:
            engine = create_engine(db_url)
            known_types = [
                "WORKS_AT", "HOLDS_POSITION", "HAS_COMPENSATION",
                "REPORTS_TO", "FOUNDED", "INVESTED_IN"
            ]
            with engine.connect() as conn:
                result = conn.execute(text("""
                    SELECT COUNT(*) FROM ontology_candidates
                    WHERE normalized_name = ANY(:types)
                      AND status = 'PENDING'
                """), {"types": known_types})
                count = result.scalar()

                if count == 0:
                    results.append(("Ontology Guard", True, "No known types in candidates"))
                else:
                    results.append(("Ontology Guard", False, f"{count} known types incorrectly in candidates!"))
        else:
            results.append(("Ontology Guard", False, "No DB connection"))
    except Exception as e:
        results.append(("Ontology Guard", False, str(e)[:50]))

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Regression Gate - Deterministic go/no-go validation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/regression_gate.py           # Full regression suite
    python scripts/regression_gate.py --quick   # Quick checks only
    python scripts/regression_gate.py -v        # Verbose output
"""
    )

    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Run quick checks only (no full pytest suite)"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show detailed test output"
    )
    parser.add_argument(
        "--critical-only", "-c",
        action="store_true",
        help="Run only critical tests"
    )
    parser.add_argument(
        "--no-stop",
        action="store_true",
        help="Don't stop on first failure"
    )

    args = parser.parse_args()

    print_banner("REGRESSION GATE", BOLD)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Mode: {'Quick checks' if args.quick else 'Full suite'}")

    start_time = time.time()

    # Always run quick checks first
    print_banner("QUICK CHECKS", YELLOW)
    quick_results = run_quick_checks()

    quick_passed = 0
    quick_failed = 0

    for check_name, passed, message in quick_results:
        status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  [{status}] {check_name}: {message}")
        if passed:
            quick_passed += 1
        else:
            quick_failed += 1

    print(f"\nQuick checks: {quick_passed} passed, {quick_failed} failed")

    # If quick mode or quick checks failed, stop here
    if args.quick or quick_failed > 0:
        elapsed = time.time() - start_time

        if quick_failed > 0:
            print_banner("GATE: FAIL", RED + BOLD)
            print(f"{RED}Quick checks failed. DO NOT PROCEED.{RESET}")
            print(f"Time: {elapsed:.1f}s")
            return 1
        else:
            print_banner("GATE: PASS (quick)", GREEN + BOLD)
            print(f"{GREEN}Quick checks passed.{RESET}")
            print(f"Time: {elapsed:.1f}s")
            print(f"\nRun without --quick for full validation.")
            return 0

    # Run full pytest suite
    print_banner("FULL REGRESSION SUITE", YELLOW)

    markers = "regression and critical" if args.critical_only else "regression"
    exit_code, output = run_tests(
        markers=markers,
        verbose=args.verbose,
        stop_on_fail=not args.no_stop
    )

    if args.verbose or exit_code != 0:
        print(output)

    elapsed = time.time() - start_time

    if exit_code == 0:
        print_banner("GATE: PASS", GREEN + BOLD)
        print(f"{GREEN}All regression tests passed.{RESET}")
        print(f"{GREEN}Safe to proceed with deployment/changes.{RESET}")
        print(f"Time: {elapsed:.1f}s")
        return 0
    else:
        print_banner("GATE: FAIL", RED + BOLD)
        print(f"{RED}Regression tests FAILED.{RESET}")
        print(f"{RED}DO NOT PROCEED until issues are resolved.{RESET}")
        print(f"Time: {elapsed:.1f}s")
        return 1


if __name__ == "__main__":
    sys.exit(main())
