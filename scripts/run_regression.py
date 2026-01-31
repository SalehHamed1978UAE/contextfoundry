#!/usr/bin/env python3
"""
Context Foundry Regression Test Runner

A convenience script for running regression tests during development.
Use this to quickly validate that changes haven't broken existing functionality.

Usage:
    python scripts/run_regression.py          # Run fast regression (default)
    python scripts/run_regression.py --smoke  # Run smoke tests only (fastest)
    python scripts/run_regression.py --full   # Run all tests including integration
    python scripts/run_regression.py --quick  # Alias for --smoke

Examples:
    # Before making changes, run fast regression
    python scripts/run_regression.py
    
    # Quick sanity check
    python scripts/run_regression.py --smoke
    
    # Full validation (nightly)
    python scripts/run_regression.py --full
"""

import subprocess
import sys
import argparse
import time
from datetime import datetime


def run_tests(markers: str, verbose: bool = True) -> int:
    """Run pytest with specified markers."""
    cmd = [
        "python", "-m", "pytest",
        "tests/test_regression_suite.py",
        "-m", markers,
    ]
    
    if verbose:
        cmd.append("-v")
    
    cmd.extend([
        "--tb=short",
        "-x",  # Stop on first failure for faster feedback
    ])
    
    print(f"\n{'='*60}")
    print(f"Running: {' '.join(cmd)}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    start = time.time()
    result = subprocess.run(cmd)
    elapsed = time.time() - start
    
    print(f"\n{'='*60}")
    print(f"Completed in {elapsed:.1f} seconds")
    print(f"Exit code: {result.returncode}")
    print(f"{'='*60}\n")
    
    return result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Context Foundry Regression Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Test Levels:
  --smoke       Smoke tests only (<30 seconds)
                - Import verification
                - Database connectivity
                - Core class instantiation
                
  --fast        Fast regression (default, <3 minutes)
                - All smoke tests
                - Query classification
                - Entity resolution
                - Confidence quadrants
                - DTL/precedent tests
                
  --full        Full suite including integration (5+ minutes)
                - All fast regression tests
                - Component tests
                - Full E2E pipeline tests
"""
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--smoke", "--quick", "-s",
        action="store_true",
        help="Run smoke tests only (fastest)"
    )
    group.add_argument(
        "--fast", "-f",
        action="store_true",
        default=True,
        help="Run fast regression tests (default)"
    )
    group.add_argument(
        "--full", "-a",
        action="store_true",
        help="Run all tests including integration"
    )
    group.add_argument(
        "--component", "-c",
        action="store_true",
        help="Run component tests only"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Less verbose output"
    )
    
    args = parser.parse_args()
    
    if args.smoke:
        markers = "smoke"
        print("Running SMOKE tests (fastest)...")
    elif args.full:
        markers = "smoke or fast_regression or component or integration"
        print("Running FULL regression suite...")
    elif args.component:
        markers = "component"
        print("Running COMPONENT tests...")
    else:
        markers = "smoke or fast_regression"
        print("Running FAST regression tests...")
    
    return run_tests(markers, verbose=not args.quiet)


if __name__ == "__main__":
    sys.exit(main())
