#!/usr/bin/env python3
"""
Run Context Foundry regression tests.

Usage:
    python run_regression_tests.py           # Run all tests
    python run_regression_tests.py --quick   # Run quick subset
    python run_regression_tests.py --smoke   # Run smoke tests only
"""

import sys
import subprocess
import argparse

def main():
    parser = argparse.ArgumentParser(description='Run Context Foundry regression tests')
    parser.add_argument('--quick', action='store_true', help='Run quick subset of tests')
    parser.add_argument('--smoke', action='store_true', help='Run smoke tests only')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    args = parser.parse_args()
    
    pytest_args = ['python', '-m', 'pytest', 'tests/test_regression.py']
    
    if args.verbose:
        pytest_args.append('-v')
    
    pytest_args.extend(['--tb=short'])
    
    if args.quick:
        pytest_args.extend([
            '-k', 
            'test_person_concerns_mia_white or test_cloud_migration_decisions or '
            'test_auth_service_failure_impact or test_unknown_project or '
            'test_vendor_switch_cloudshift_to_migratex'
        ])
    elif args.smoke:
        pytest_args.extend([
            '-k',
            'test_person_concerns_mia_white or test_unknown_project'
        ])
    
    print(f"Running: {' '.join(pytest_args)}")
    print("-" * 60)
    
    result = subprocess.run(pytest_args)
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
