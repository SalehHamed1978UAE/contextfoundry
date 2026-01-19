#!/usr/bin/env python3
"""
Context Foundry Test Runner
One-command test runner for all corpora.

Usage:
    python -m src.test_runner.runner --list                    # List available corpora
    python -m src.test_runner.runner --corpus "Manus Healthtec"  # Run specific corpus
    python -m src.test_runner.runner --all                      # Run all corpora (sequential)
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .config import TestConfig
from .vault_manager import VaultManager
from .document_uploader import get_files_to_upload
from .test_executor import TestExecutor
from .evaluator import FuzzyEvaluator


def list_corpora(config: TestConfig):
    """List all available corpora with status."""
    print("\n" + "=" * 60)
    print("AVAILABLE TEST CORPORA")
    print("=" * 60)
    
    for name, info in config.list_corpora().items():
        print(f"\n{name}")
        print(f"  Path: {info.get('root_path')}")
        print(f"  Questions: {info.get('questions_file')}")
        print(f"  Current Vault: {info.get('current_vault_id', 'None')}")
        print(f"  Last Run: {info.get('last_run', 'Never')}")
        print(f"  Last Accuracy: {info.get('last_accuracy', 'N/A')}")
    
    print("\n" + "=" * 60)


def run_corpus_test(corpus_name: str, config: TestConfig, questions_only: bool = False):
    """Run test for a single corpus."""
    
    print("\n" + "=" * 70)
    print(f"TEST RUNNER: {corpus_name}" + (" (QUESTIONS ONLY)" if questions_only else ""))
    print("=" * 70)
    
    corpus = config.get_corpus(corpus_name)
    if not corpus:
        print(f"ERROR: Corpus '{corpus_name}' not found in config")
        return None
    
    root_path = Path(corpus['root_path'])
    questions_file = config.questions_dir / corpus['questions_file']
    if not questions_file.exists():
        print(f"ERROR: Questions file not found: {questions_file}")
        return None
    
    vm = VaultManager(config.api_base_url)
    evaluator = FuzzyEvaluator()
    executor = TestExecutor(vm, evaluator)
    
    # Step 1: Initial auth (no tenant context yet)
    print("\n[Step 1] Authenticating...")
    if not vm.authenticate_dev():
        print("ERROR: Failed to authenticate")
        return None
    print("  Authenticated")
    
    if questions_only:
        # Use existing vault from config
        vault_id = corpus.get('current_vault_id')
        if not vault_id:
            print(f"ERROR: No vault ID configured for '{corpus_name}'. Run without --questions-only first.")
            return None
        print(f"\n[Step 2-4] SKIPPED (using existing vault: {vault_id})")
        # Re-authenticate with vault context
        if not vm.authenticate_dev(tenant_id=vault_id):
            print("WARNING: Failed to set vault context, continuing...")
        files = []  # No files uploaded
    else:
        if not root_path.exists():
            print(f"ERROR: Corpus path does not exist: {root_path}")
            return None
        
        # Step 2: Create clean vault
        print(f"\n[Step 2] Creating clean vault...")
        vault_id = vm.ensure_clean_vault(corpus_name)
        
        # Step 2b: Re-authenticate with vault context
        print(f"  Setting vault context...")
        if not vm.authenticate_dev(tenant_id=vault_id):
            print("WARNING: Failed to set vault context, continuing...")
        
        # Update config with new vault ID
        config.update_corpus(corpus_name, current_vault_id=vault_id)
        
        # Step 3: Upload documents
        print(f"\n[Step 3] Uploading documents...")
        files = get_files_to_upload(root_path, config.upload_rules)
        print(f"  Found {len(files)} files to upload")
        
        if len(files) == 0:
            print("  WARNING: No files found to upload!")
            print(f"  Looking in folders: {config.upload_rules.get('include_folders')}")
            return None
        
        for i, file_path in enumerate(files):
            success = vm.upload_document(vault_id, file_path)
            status = "OK" if success else "FAIL"
            if (i + 1) % 20 == 0 or not success:
                print(f"  [{i+1}/{len(files)}] {file_path.name}: {status}")
        
        print(f"  Uploaded {len(files)} documents")
        
        # Step 4: Wait for extraction
        print(f"\n[Step 4] Waiting for extraction...")
        extraction_config = config.extraction_config
        
        try:
            vm.wait_for_extraction(
                vault_id,
                expected_docs=len(files),
                timeout_minutes=extraction_config.get('timeout_minutes', 20),
                poll_interval=extraction_config.get('poll_interval_seconds', 10)
            )
        except TimeoutError as e:
            print(f"  ERROR: {e}")
            return None
    
    # Step 5: Run test
    print(f"\n[Step 5] Running test questions...")
    extraction_config = config.extraction_config
    try:
        results = executor.run_test(
            vault_id=vault_id,
            questions_file=questions_file,
            results_dir=config.results_dir,
            corpus_name=corpus_name,
            min_chunks=extraction_config.get('min_expected_chunks', 50)
        )
    except ValueError as e:
        print(f"  ERROR: {e}")
        return None
    
    # Update config with results
    config.update_corpus(
        corpus_name,
        last_run=datetime.now().isoformat(),
        last_accuracy=f"{results['results']['accuracy_pct']}%"
    )
    
    # Final summary
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print(f"Corpus:    {corpus_name}")
    print(f"Vault ID:  {vault_id}")
    print(f"Documents: {len(files)}")
    print(f"Chunks:    {results['vault_stats']['chunks']}")
    print(f"Entities:  {results['vault_stats']['entities']}")
    print(f"Relations: {results['vault_stats']['relationships']}")
    print(f"Score:     {results['results']['passed']}/{results['results']['total']} ({results['results']['accuracy_pct']}%)")
    print("=" * 70)
    print("Vault preserved for manual queries in UI")
    print("=" * 70 + "\n")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Context Foundry Test Runner")
    parser.add_argument('--list', action='store_true', help='List available corpora')
    parser.add_argument('--corpus', type=str, help='Run test for specific corpus')
    parser.add_argument('--all', action='store_true', help='Run all corpora (sequential)')
    parser.add_argument('--questions-only', action='store_true', help='Skip upload/extraction, run questions only against existing vault')
    parser.add_argument('--config', type=str, default='src/test_config.json', help='Config file path')
    
    args = parser.parse_args()
    
    config = TestConfig(args.config)
    
    if args.list:
        list_corpora(config)
    elif args.corpus:
        run_corpus_test(args.corpus, config, questions_only=args.questions_only)
    elif args.all:
        print("Running all corpora sequentially...")
        for name in config.list_corpora().keys():
            run_corpus_test(name, config, questions_only=args.questions_only)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
