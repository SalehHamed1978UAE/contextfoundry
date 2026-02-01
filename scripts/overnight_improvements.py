#!/usr/bin/env python3
"""
Overnight Improvement Script for Context Foundry
================================================

This script runs three major improvement tasks:
1. Verify and fix Inference Validation Layer
2. Investigate extraction regression (73% relationship loss)
3. Prepare PageIndex integration analysis

Run this script and check results in the morning.

Usage:
    python scripts/overnight_improvements.py --vault-id "1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91"
"""

import os
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'overnight_run_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

VAULT_ID = os.environ.get('VAULT_ID', '1f3320cd-82f3-4e16-91f0-5fe7ff8f8a91')
RESULTS_DIR = Path('overnight_results')
RESULTS_DIR.mkdir(exist_ok=True)


def task1_verify_inference_validation():
    """
    TASK 1: Verify Inference Validation Layer is Running

    The inference validation layer was built but never verified to be working.
    This task checks if it's running and if it's correcting answers.
    """
    logger.info("=" * 60)
    logger.info("TASK 1: Verifying Inference Validation Layer")
    logger.info("=" * 60)

    results = {
        'task': 'inference_validation',
        'status': 'unknown',
        'findings': []
    }

    try:
        # Check if the module exists and can be imported
        from context_foundry.validation.inference_validator import (
            InferenceValidator, ValidationResult
        )
        logger.info("✓ InferenceValidator module imported successfully")
        results['findings'].append("Module imports correctly")

        # Check if it's integrated in core.py
        from context_foundry.core import ContextFoundry
        logger.info("✓ ContextFoundry imported successfully")

        # Initialize and run a test query
        logger.info(f"Initializing ContextFoundry with vault {VAULT_ID[:8]}...")
        cf = ContextFoundry(tenant_id=VAULT_ID)

        # Test query that previously had issues (Toyota vs NextGen)
        test_query = "Who does Nexus Industries partner with for solid-state battery development?"
        logger.info(f"Running test query: {test_query}")

        result = cf.query(test_query, display_output=False, save_to_log=False)

        # Check for inference validation fields
        inference_validated = result.get('inference_validated')
        inference_correction = result.get('inference_correction_reason')
        inference_confidence = result.get('inference_confidence')

        logger.info(f"Answer: {result.get('answer', 'N/A')[:100]}...")
        logger.info(f"inference_validated: {inference_validated}")
        logger.info(f"inference_correction_reason: {inference_correction}")
        logger.info(f"inference_confidence: {inference_confidence}")

        if inference_validated is not None:
            results['status'] = 'running'
            results['findings'].append(f"Inference validation IS running")
            results['findings'].append(f"Validated: {inference_validated}")
            if inference_correction:
                results['findings'].append(f"Correction applied: {inference_correction}")
        else:
            results['status'] = 'not_running'
            results['findings'].append("Inference validation NOT running - field is None")
            results['findings'].append("Check core.py integration")

        results['test_answer'] = result.get('answer', '')[:200]

    except Exception as e:
        logger.error(f"Task 1 failed: {e}")
        results['status'] = 'error'
        results['error'] = str(e)

    # Save results
    with open(RESULTS_DIR / 'task1_inference_validation.json', 'w') as f:
        json.dump(results, f, indent=2)

    logger.info(f"Task 1 complete. Status: {results['status']}")
    return results


def task2_investigate_extraction_regression():
    """
    TASK 2: Investigate Extraction Regression

    We found that:
    - Old vault (Jan 28): 7,323 entities, 2,836 relationships
    - New vault (Feb 1): 5,349 entities, 777 relationships

    This is a 73% drop in relationships. Find out why.
    """
    logger.info("=" * 60)
    logger.info("TASK 2: Investigating Extraction Regression")
    logger.info("=" * 60)

    results = {
        'task': 'extraction_regression',
        'status': 'unknown',
        'findings': [],
        'old_vault': {'entities': 7323, 'relationships': 2836},
        'new_vault': {'entities': 5349, 'relationships': 777}
    }

    try:
        from sqlalchemy import text
        from context_foundry.models.schema import get_session

        session = get_session()

        # Query relationship types distribution
        logger.info("Analyzing relationship type distribution...")

        rel_query = text("""
            SELECT relationship_type, COUNT(*) as count
            FROM relationships
            WHERE tenant_id = :tenant_id
            GROUP BY relationship_type
            ORDER BY count DESC
            LIMIT 20
        """)

        rel_results = session.execute(rel_query, {'tenant_id': VAULT_ID}).fetchall()

        rel_distribution = {row[0]: row[1] for row in rel_results}
        results['relationship_distribution'] = rel_distribution
        logger.info(f"Relationship types found: {len(rel_distribution)}")
        for rel_type, count in list(rel_distribution.items())[:10]:
            logger.info(f"  {rel_type}: {count}")

        # Check for SUPPLIES_TO relationships
        supplies_count = rel_distribution.get('SUPPLIES_TO', 0)
        supplies_count += rel_distribution.get('SUPPLIED_BY', 0)
        logger.info(f"Supplier relationships: {supplies_count}")
        results['findings'].append(f"Supplier relationships: {supplies_count}")

        # Check for CUSTOMER_OF relationships with values
        customer_query = text("""
            SELECT COUNT(*)
            FROM relationships
            WHERE tenant_id = :tenant_id
            AND relationship_type = 'CUSTOMER_OF'
            AND properties->>'relationship_value' IS NOT NULL
        """)
        try:
            customers_with_values = session.execute(customer_query, {'tenant_id': VAULT_ID}).scalar()
            logger.info(f"Customer relationships with values: {customers_with_values}")
            results['findings'].append(f"Customers with values: {customers_with_values}")
        except Exception as e:
            logger.warning(f"Could not query customer values: {e}")

        # Check for SPECIFICATION entities
        spec_query = text("""
            SELECT COUNT(*)
            FROM entities
            WHERE tenant_id = :tenant_id
            AND entity_type = 'SPECIFICATION'
        """)
        try:
            spec_count = session.execute(spec_query, {'tenant_id': VAULT_ID}).scalar()
            logger.info(f"SPECIFICATION entities: {spec_count}")
            results['findings'].append(f"Specification entities: {spec_count}")
        except Exception as e:
            logger.warning(f"Could not query specifications: {e}")

        # Check extraction request status
        extraction_query = text("""
            SELECT status, COUNT(*)
            FROM platform.extraction_requests
            WHERE tenant_id = :tenant_id
            GROUP BY status
        """)
        try:
            extraction_status = session.execute(extraction_query, {'tenant_id': VAULT_ID}).fetchall()
            results['extraction_status'] = {row[0]: row[1] for row in extraction_status}
            logger.info(f"Extraction status: {results['extraction_status']}")
        except Exception as e:
            logger.warning(f"Could not query extraction status: {e}")

        results['status'] = 'complete'

    except Exception as e:
        logger.error(f"Task 2 failed: {e}")
        results['status'] = 'error'
        results['error'] = str(e)

    # Save results
    with open(RESULTS_DIR / 'task2_extraction_regression.json', 'w') as f:
        json.dump(results, f, indent=2)

    logger.info(f"Task 2 complete. Status: {results['status']}")
    return results


def task3_pageindex_analysis():
    """
    TASK 3: PageIndex Integration Analysis

    Analyze the codebase to identify where PageIndex-style
    tree retrieval could be integrated.
    """
    logger.info("=" * 60)
    logger.info("TASK 3: PageIndex Integration Analysis")
    logger.info("=" * 60)

    results = {
        'task': 'pageindex_analysis',
        'status': 'unknown',
        'findings': [],
        'integration_points': []
    }

    try:
        # Check current retrieval architecture
        src_path = Path(__file__).parent.parent / 'src' / 'context_foundry'

        # Files to analyze
        key_files = [
            'agents/retrieval_router.py',
            'agents/retrieval.py',
            'search/document_searcher.py',
            'agents/directed_retriever.py',
        ]

        for file_path in key_files:
            full_path = src_path / file_path
            if full_path.exists():
                logger.info(f"✓ Found: {file_path}")
                results['integration_points'].append({
                    'file': file_path,
                    'exists': True,
                    'recommendation': f"Review for PageIndex integration"
                })
            else:
                logger.warning(f"✗ Not found: {file_path}")

        # PageIndex key concepts to integrate
        pageindex_concepts = [
            {
                'concept': 'Hierarchical Tree Index',
                'description': 'Build tree structure from document sections/headings',
                'integration_point': 'document_searcher.py - add tree building during indexing'
            },
            {
                'concept': 'Reasoning-Based Retrieval',
                'description': 'Use LLM to decide which tree branch to explore',
                'integration_point': 'retrieval_router.py - add tree navigation logic'
            },
            {
                'concept': 'Section-Level Relevance',
                'description': 'Score relevance at section level, not just chunk level',
                'integration_point': 'directed_retriever.py - add section scoring'
            },
            {
                'concept': 'Multi-Step Navigation',
                'description': 'Iteratively narrow down to relevant sections',
                'integration_point': 'retrieval.py - add iterative refinement'
            }
        ]

        results['pageindex_concepts'] = pageindex_concepts

        for concept in pageindex_concepts:
            logger.info(f"PageIndex concept: {concept['concept']}")
            logger.info(f"  Integration: {concept['integration_point']}")

        results['findings'].append("Current retrieval uses flat chunk similarity")
        results['findings'].append("PageIndex would add hierarchical navigation")
        results['findings'].append("Key benefit: Better for structured documents")

        results['status'] = 'complete'
        results['recommendation'] = """
        To integrate PageIndex:
        1. During indexing: Build section tree from document headings
        2. During retrieval: Navigate tree using LLM reasoning
        3. Return section-level context, not just chunks

        Start with document_searcher.py to add tree building.
        """

    except Exception as e:
        logger.error(f"Task 3 failed: {e}")
        results['status'] = 'error'
        results['error'] = str(e)

    # Save results
    with open(RESULTS_DIR / 'task3_pageindex_analysis.json', 'w') as f:
        json.dump(results, f, indent=2)

    logger.info(f"Task 3 complete. Status: {results['status']}")
    return results


def run_baseline_test():
    """Run the 100-question test suite as baseline."""
    logger.info("=" * 60)
    logger.info("Running Baseline Test Suite")
    logger.info("=" * 60)

    try:
        import subprocess
        result = subprocess.run(
            [
                sys.executable, '-m', 'src.test_runner.runner',
                '--vault-id', VAULT_ID,
                '--questions', 'src/test_questions/nexus_100q.json',
                '--output', str(RESULTS_DIR)
            ],
            capture_output=True,
            text=True,
            timeout=1800  # 30 minute timeout
        )

        logger.info(f"Test runner stdout: {result.stdout[-500:]}")
        if result.returncode != 0:
            logger.error(f"Test runner stderr: {result.stderr[-500:]}")

        return result.returncode == 0

    except subprocess.TimeoutExpired:
        logger.error("Test suite timed out after 30 minutes")
        return False
    except Exception as e:
        logger.error(f"Failed to run test suite: {e}")
        return False


def generate_summary():
    """Generate a summary of all overnight results."""
    logger.info("=" * 60)
    logger.info("Generating Summary")
    logger.info("=" * 60)

    summary = {
        'timestamp': datetime.now().isoformat(),
        'vault_id': VAULT_ID,
        'tasks': {}
    }

    # Load all task results
    for task_file in RESULTS_DIR.glob('task*.json'):
        with open(task_file) as f:
            task_data = json.load(f)
            summary['tasks'][task_data['task']] = {
                'status': task_data['status'],
                'key_findings': task_data.get('findings', [])[:5]
            }

    # Load test results if available
    test_files = list(RESULTS_DIR.glob('vault_*.json'))
    if test_files:
        latest_test = max(test_files, key=lambda p: p.stat().st_mtime)
        with open(latest_test) as f:
            test_data = json.load(f)
            summary['test_results'] = {
                'accuracy': test_data.get('results', {}).get('accuracy_pct'),
                'passed': test_data.get('results', {}).get('passed'),
                'failed': test_data.get('results', {}).get('failed')
            }

    # Write summary
    summary_path = RESULTS_DIR / 'OVERNIGHT_SUMMARY.json'
    with open(summary_path, 'w') as f:
        json.dump(summary, f, indent=2)

    # Also write human-readable summary
    readme_path = RESULTS_DIR / 'OVERNIGHT_SUMMARY.md'
    with open(readme_path, 'w') as f:
        f.write("# Overnight Improvement Results\n\n")
        f.write(f"**Run Time:** {summary['timestamp']}\n")
        f.write(f"**Vault:** {VAULT_ID}\n\n")

        f.write("## Task Results\n\n")
        for task_name, task_info in summary['tasks'].items():
            f.write(f"### {task_name}\n")
            f.write(f"**Status:** {task_info['status']}\n\n")
            f.write("**Findings:**\n")
            for finding in task_info['key_findings']:
                f.write(f"- {finding}\n")
            f.write("\n")

        if 'test_results' in summary:
            f.write("## Test Results\n\n")
            f.write(f"- **Accuracy:** {summary['test_results']['accuracy']}%\n")
            f.write(f"- **Passed:** {summary['test_results']['passed']}\n")
            f.write(f"- **Failed:** {summary['test_results']['failed']}\n")

    logger.info(f"Summary written to {summary_path}")
    logger.info(f"Readable summary at {readme_path}")

    return summary


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("CONTEXT FOUNDRY OVERNIGHT IMPROVEMENT SCRIPT")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info(f"Vault: {VAULT_ID}")
    logger.info("=" * 60)

    # Run all tasks
    task1_results = task1_verify_inference_validation()
    task2_results = task2_investigate_extraction_regression()
    task3_results = task3_pageindex_analysis()

    # Run baseline test
    # Uncomment if you want to run the full test suite
    # run_baseline_test()

    # Generate summary
    summary = generate_summary()

    logger.info("=" * 60)
    logger.info("OVERNIGHT RUN COMPLETE")
    logger.info(f"Results in: {RESULTS_DIR.absolute()}")
    logger.info("=" * 60)

    # Print summary for quick review
    print("\n" + "=" * 60)
    print("QUICK SUMMARY")
    print("=" * 60)
    for task_name, task_info in summary['tasks'].items():
        print(f"\n{task_name}: {task_info['status']}")
        for finding in task_info['key_findings'][:3]:
            print(f"  - {finding}")

    return summary


if __name__ == '__main__':
    main()
