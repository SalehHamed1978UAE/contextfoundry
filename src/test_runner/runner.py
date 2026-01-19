"""
Main entry point for the test runner.

Usage:
    python -m test_runner.runner --corpus medsync_health
    python -m test_runner.runner --list
    python -m test_runner.runner --corpus medsync_health --skip-upload
"""

import argparse
import sys
from pathlib import Path
from datetime import datetime

from .config import load_config, save_config, update_corpus_state
from .document_uploader import get_files_to_upload, summarize_upload_plan
from .vault_manager import VaultManager
from .test_executor import TestExecutor, load_questions
from .evaluator import FuzzyEvaluator


def list_corpora():
    """List all configured corpora and their status."""
    config = load_config()
    
    print("\n" + "="*60)
    print("  CONFIGURED TEST CORPORA")
    print("="*60)
    
    for name, corpus in config.corpora.items():
        print(f"\n  {name}")
        print(f"    Root:       {corpus.root_path}")
        print(f"    Questions:  {corpus.questions_file}")
        print(f"    Vault ID:   {corpus.current_vault_id or 'None'}")
        print(f"    Last Run:   {corpus.last_run or 'Never'}")
        print(f"    Accuracy:   {corpus.last_accuracy or 'N/A'}%")
    
    print("\n" + "="*60)


def run_test(corpus_name: str, skip_upload: bool = False, skip_extraction_wait: bool = False):
    """Run test for a specific corpus."""
    config = load_config()
    
    if corpus_name not in config.corpora:
        print(f"ERROR: Unknown corpus '{corpus_name}'")
        print(f"Available: {list(config.corpora.keys())}")
        sys.exit(1)
    
    corpus = config.corpora[corpus_name]
    
    # Validate auth token
    if not config.auth_token:
        print("ERROR: No auth token configured.")
        print("Set CF_API_TOKEN environment variable or add auth_token to test_config.json")
        sys.exit(1)
    
    print("\n" + "="*60)
    print(f"  RUNNING TEST: {corpus_name}")
    print("="*60)
    
    # Validate paths
    corpus_root = Path(corpus.root_path)
    if not corpus_root.exists():
        print(f"ERROR: Corpus root does not exist: {corpus_root}")
        sys.exit(1)
    
    # Find questions file
    questions_file = corpus_root / corpus.questions_file
    if not questions_file.exists():
        # Try in test_questions directory
        questions_file = Path(config.questions_dir) / corpus.questions_file
        if not questions_file.exists():
            print(f"ERROR: Questions file not found: {corpus.questions_file}")
            print(f"Checked: {corpus_root / corpus.questions_file}")
            print(f"Checked: {Path(config.questions_dir) / corpus.questions_file}")
            sys.exit(1)
    
    print(f"  Corpus root:     {corpus_root}")
    print(f"  Questions file:  {questions_file}")
    
    # Initialize vault manager
    vault_manager = VaultManager(config.api_base_url, config.auth_token)
    
    if not skip_upload:
        # Get files to upload
        print("\n  Scanning for documents...")
        files = get_files_to_upload(corpus_root)
        
        if not files:
            print("  ERROR: No files to upload")
            sys.exit(1)
        
        print(f"  Found {len(files)} files to upload")
        
        # Create/clean vault
        print("\n  Setting up vault...")
        vault_id = vault_manager.ensure_clean_vault(corpus_name)
        
        # Upload documents
        print("\n  Uploading documents...")
        upload_result = vault_manager.upload_documents(vault_id, files)
        print(f"  Uploaded: {upload_result['uploaded']}, Failed: {upload_result['failed']}")
        
        if not skip_extraction_wait:
            # Wait for extraction
            print("\n  Waiting for extraction...")
            try:
                vault_manager.wait_for_extraction(
                    vault_id,
                    expected_docs=upload_result['uploaded'],
                    timeout_minutes=config.extraction.timeout_minutes,
                    poll_interval=config.extraction.poll_interval_seconds
                )
            except TimeoutError as e:
                print(f"  ERROR: {e}")
                print("  Continuing with test anyway...")
    else:
        # Use existing vault
        vault_id = corpus.current_vault_id
        if not vault_id:
            vault_id = vault_manager.find_vault_by_name(corpus_name)
        
        if not vault_id:
            print(f"  ERROR: No existing vault found for {corpus_name}")
            print("  Run without --skip-upload to create one")
            sys.exit(1)
        
        print(f"  Using existing vault: {vault_id}")
    
    # Run tests
    print("\n  Running test questions...")
    executor = TestExecutor(vault_manager, FuzzyEvaluator())
    
    summary = executor.run_test(
        vault_id=vault_id,
        questions_file=questions_file,
        results_dir=Path(config.results_dir),
        corpus_name=corpus_name,
        min_chunks=config.extraction.min_expected_chunks
    )
    
    # Print summary
    executor.print_summary(summary)
    
    # Update config with results
    update_corpus_state(
        corpus_name,
        vault_id=vault_id,
        accuracy=summary['summary']['accuracy_pct']
    )
    
    print(f"\n  Vault preserved: {vault_id}")
    print(f"  You can query it manually in the UI")
    
    return summary


def main():
    parser = argparse.ArgumentParser(
        description="Context Foundry Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m test_runner.runner --list
  python -m test_runner.runner --corpus medsync_health
  python -m test_runner.runner --corpus medsync_health --skip-upload
        """
    )
    
    parser.add_argument(
        '--corpus', '-c',
        help='Name of corpus to test (e.g., medsync_health)'
    )
    parser.add_argument(
        '--list', '-l',
        action='store_true',
        help='List all configured corpora'
    )
    parser.add_argument(
        '--skip-upload',
        action='store_true',
        help='Skip upload, use existing vault'
    )
    parser.add_argument(
        '--skip-extraction-wait',
        action='store_true',
        help='Skip waiting for extraction (useful if already complete)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be uploaded without actually uploading'
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_corpora()
        return
    
    if args.dry_run and args.corpus:
        config = load_config()
        if args.corpus not in config.corpora:
            print(f"ERROR: Unknown corpus '{args.corpus}'")
            sys.exit(1)
        
        corpus = config.corpora[args.corpus]
        summary = summarize_upload_plan(Path(corpus.root_path))
        
        print(f"\nDry run for: {args.corpus}")
        print(f"Total files: {summary['total_files']}")
        print(f"By folder: {summary['by_folder']}")
        print(f"By extension: {summary['by_extension']}")
        print(f"\nFiles:")
        for f in summary['files'][:20]:
            print(f"  {f}")
        if len(summary['files']) > 20:
            print(f"  ... and {len(summary['files']) - 20} more")
        return
    
    if not args.corpus:
        parser.print_help()
        print("\nERROR: --corpus or --list required")
        sys.exit(1)
    
    run_test(args.corpus, args.skip_upload, args.skip_extraction_wait)


if __name__ == '__main__':
    main()
