#!/usr/bin/env python3
"""
Context Foundry Stress Test Runner

Usage:
    python stress_test/run_stress_test.py --mode quick     # 1 hour, 50 docs, 500 queries
    python stress_test/run_stress_test.py --mode medium    # 4 hours, 400 docs, 4000 queries  
    python stress_test/run_stress_test.py --mode overnight # 8 hours, 1000 docs, 10000 queries
    python stress_test/run_stress_test.py --mode custom --hours 2 --docs 100 --queries 1000
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import logging

from stress_test.config import StressTestConfig, QUICK_CONFIG, MEDIUM_CONFIG, OVERNIGHT_CONFIG
from stress_test.orchestrator import StressTestOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

def main():
    parser = argparse.ArgumentParser(
        description="Context Foundry Stress Test Suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Quick test (1 hour):
    python stress_test/run_stress_test.py --mode quick
    
  Medium test (4 hours):
    python stress_test/run_stress_test.py --mode medium
    
  Overnight test (8 hours):
    python stress_test/run_stress_test.py --mode overnight
    
  Custom test:
    python stress_test/run_stress_test.py --mode custom --hours 2 --docs 100 --queries 1000

Results will be saved to /home/runner/workspace/overnight_results/
        """
    )
    
    parser.add_argument(
        "--mode", 
        choices=["quick", "medium", "overnight", "custom"],
        default="quick",
        help="Test mode: quick (1h), medium (4h), overnight (8h), or custom"
    )
    
    parser.add_argument(
        "--hours",
        type=float,
        default=1.0,
        help="Duration in hours (for custom mode)"
    )
    
    parser.add_argument(
        "--docs",
        type=int,
        default=50,
        help="Target number of documents (for custom mode)"
    )
    
    parser.add_argument(
        "--queries",
        type=int,
        default=500,
        help="Target number of queries (for custom mode)"
    )
    
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:5000",
        help="Base URL of Context Foundry"
    )
    
    args = parser.parse_args()
    
    if args.mode == "quick":
        config = QUICK_CONFIG
    elif args.mode == "medium":
        config = MEDIUM_CONFIG
    elif args.mode == "overnight":
        config = OVERNIGHT_CONFIG
    else:
        config = StressTestConfig()
        config.duration_hours = args.hours
        config.target_documents = args.docs
        config.target_queries = args.queries
        config.docs_per_hour = max(1, int(args.docs / args.hours))
        config.queries_per_hour = max(1, int(args.queries / args.hours))
    
    config.base_url = args.url
    
    print("\n" + "=" * 70)
    print("CONTEXT FOUNDRY STRESS TEST")
    print("=" * 70)
    print(f"Mode: {args.mode}")
    print(f"Duration: {config.duration_hours} hours")
    print(f"Target Documents: {config.target_documents}")
    print(f"Target Queries: {config.target_queries}")
    print(f"Base URL: {config.base_url}")
    print(f"Results: {config.results_dir}")
    print("=" * 70)
    print("\nPress Ctrl+C to stop gracefully and generate reports.\n")
    
    try:
        orchestrator = StressTestOrchestrator(config)
        orchestrator.run()
    except KeyboardInterrupt:
        print("\nTest interrupted. Reports should be generated.")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        raise


if __name__ == "__main__":
    main()
