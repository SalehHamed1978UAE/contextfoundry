#!/usr/bin/env python3
"""
Context Foundry Test Runner
One-command test runner for all corpora.

DEFAULT BEHAVIOR:
- If checkpoint exists (extraction complete), resume Q&A from last answered question
- If no checkpoint, run full test (upload, extract, Q&A)

Usage:
    python -m src.test_runner.runner --list                    # List available corpora
    python -m src.test_runner.runner --corpus "Manus Healthtec"  # Run (auto-resume if checkpoint exists)
    python -m src.test_runner.runner --corpus "X" --fresh        # Force fresh start (delete vault, recreate, full run)
    python -m src.test_runner.runner --all                       # Run all corpora (sequential)
    python -m src.test_runner.runner --corpus "X" --question-set-id <uuid>  # Use question set from DB
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from .config import TestConfig
from .vault_manager import VaultManager
from .document_uploader import get_files_to_upload
from .test_executor import TestExecutor
from .evaluator import FuzzyEvaluator

STATUS_FILE_PATH = Path('data/test-runner/status.json')


def update_status(stage: str, **kwargs):
    """Update the status file with current progress."""
    STATUS_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    status = {}
    if STATUS_FILE_PATH.exists():
        try:
            with open(STATUS_FILE_PATH) as f:
                status = json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    
    status['stage'] = stage
    status['updated_at'] = datetime.now().isoformat()
    status.update(kwargs)
    
    with open(STATUS_FILE_PATH, 'w') as f:
        json.dump(status, f, indent=2, default=str)


def load_question_set_from_db(question_set_id: str) -> list | None:
    """Load questions from database by question_set_id."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        print("ERROR: DATABASE_URL not configured")
        return None
    
    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import sessionmaker
        
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        result = session.execute(text("""
            SELECT questions FROM question_sets WHERE id = :id
        """), {'id': question_set_id})
        
        row = result.fetchone()
        session.close()
        
        if row:
            return row[0]
        return None
    except Exception as e:
        print(f"ERROR: Failed to load question set: {e}")
        return None


def get_checkpoint_file(results_dir: Path, corpus_name: str) -> Path:
    """Get path to checkpoint file for a corpus."""
    safe_name = corpus_name.lower().replace(' ', '_')
    return results_dir / f"{safe_name}_checkpoint.json"


def load_checkpoint(results_dir: Path, corpus_name: str) -> dict | None:
    """Load checkpoint if exists."""
    checkpoint_file = get_checkpoint_file(results_dir, corpus_name)
    if checkpoint_file.exists():
        with open(checkpoint_file) as f:
            return json.load(f)
    return None


def delete_checkpoint(results_dir: Path, corpus_name: str):
    """Delete checkpoint file if exists."""
    checkpoint_file = get_checkpoint_file(results_dir, corpus_name)
    if checkpoint_file.exists():
        checkpoint_file.unlink()
        print(f"  Deleted checkpoint: {checkpoint_file.name}")


def save_checkpoint(results_dir: Path, corpus_name: str, vault_id: str, extraction_complete: bool):
    """Save checkpoint after extraction completes."""
    checkpoint_file = get_checkpoint_file(results_dir, corpus_name)
    results_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = {
        "corpus_name": corpus_name,
        "vault_id": vault_id,
        "extraction_complete": extraction_complete,
        "timestamp": datetime.now().isoformat()
    }
    with open(checkpoint_file, 'w') as f:
        json.dump(checkpoint, f, indent=2)
    print(f"  Checkpoint saved: {checkpoint_file.name}")


def list_corpora(config: TestConfig):
    """List all available corpora with status."""
    print("\n" + "=" * 60)
    print("AVAILABLE TEST CORPORA")
    print("=" * 60)
    
    for name, info in config.list_corpora().items():
        checkpoint = load_checkpoint(config.results_dir, name)
        checkpoint_status = "YES" if checkpoint and checkpoint.get('extraction_complete') else "NO"
        
        print(f"\n{name}")
        print(f"  Path: {info.get('root_path')}")
        print(f"  Questions: {info.get('questions_file')}")
        print(f"  Checkpoint: {checkpoint_status}")
        print(f"  Current Vault: {info.get('current_vault_id', 'None')}")
        print(f"  Last Run: {info.get('last_run', 'Never')}")
        print(f"  Last Accuracy: {info.get('last_accuracy', 'N/A')}")
    
    print("\n" + "=" * 60)


def run_corpus_test(corpus_name: str, config: TestConfig, questions_only: bool = False, fresh: bool = False, question_set_id: str = None):
    """
    Run test for a single corpus.
    
    Default: Auto-resume if checkpoint exists (extraction complete)
    --fresh: Force full run from scratch (delete vault, upload, extract, Q&A)
    --question-set-id: Use questions from database instead of file
    """
    
    update_status('init', corpus=corpus_name, status='running')
    
    # Check for checkpoint first (unless --fresh is specified)
    checkpoint = None
    if not fresh:
        checkpoint = load_checkpoint(config.results_dir, corpus_name)
        if checkpoint and checkpoint.get('extraction_complete'):
            print(f"\n  Found checkpoint from {checkpoint.get('timestamp', 'unknown')}")
    
    # Determine mode
    will_resume = checkpoint and checkpoint.get('extraction_complete') and not fresh
    
    mode_str = ""
    if fresh:
        mode_str = " (FRESH START)"
    elif will_resume:
        mode_str = " (RESUMING)"
    elif questions_only:
        mode_str = " (QUESTIONS ONLY)"
    
    print("\n" + "=" * 70)
    print(f"TEST RUNNER: {corpus_name}{mode_str}")
    print("=" * 70)
    
    corpus = config.get_corpus(corpus_name)
    if not corpus:
        print(f"ERROR: Corpus '{corpus_name}' not found in config")
        return None
    
    root_path = Path(corpus['root_path'])
    
    questions_data = None
    questions_file = None
    
    if question_set_id:
        print(f"\n  Loading questions from database (ID: {question_set_id})")
        questions_data = load_question_set_from_db(question_set_id)
        if not questions_data:
            print(f"ERROR: Question set not found in database: {question_set_id}")
            update_status('failed', status='failed', error='Question set not found')
            return None
        print(f"  Loaded {len(questions_data)} questions from database")
    else:
        questions_file = config.questions_dir / corpus['questions_file']
        if not questions_file.exists():
            print(f"ERROR: Questions file not found: {questions_file}")
            update_status('failed', status='failed', error='Questions file not found')
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
    
    # Initialize variables
    vault_id = None
    files = []
    
    # RESUME PATH: Checkpoint exists and extraction is complete
    if will_resume and checkpoint:
        vault_id = checkpoint['vault_id']
        print(f"\n[Step 2-4] SKIPPED (checkpoint: extraction complete)")
        print(f"  Vault ID: {vault_id}")
        print(f"  Checkpoint from: {checkpoint.get('timestamp', 'unknown')}")
        
        # Re-authenticate with vault context
        if not vm.authenticate_dev(tenant_id=vault_id):
            print("WARNING: Failed to set vault context, continuing...")
        files = []  # No files to track since we're resuming
    
    # QUESTIONS-ONLY PATH: Use existing vault without extraction
    elif questions_only:
        vault_id = corpus.get('current_vault_id')
        if not vault_id:
            print(f"ERROR: No vault ID configured for '{corpus_name}'. Run without --questions-only first.")
            return None
        print(f"\n[Step 2-4] SKIPPED (using existing vault: {vault_id})")
        if not vm.authenticate_dev(tenant_id=vault_id):
            print("WARNING: Failed to set vault context, continuing...")
        files = []
    
    # FRESH PATH: Full run from scratch
    else:
        # If --fresh, delete existing checkpoint first
        if fresh:
            delete_checkpoint(config.results_dir, corpus_name)
        
        if not root_path.exists():
            print(f"ERROR: Corpus path does not exist: {root_path}")
            return None
        
        # Step 2: Create clean vault
        print(f"\n[Step 2] Creating clean vault...")
        update_status('create', vault_name=corpus_name)
        vault_id = vm.ensure_clean_vault(corpus_name)
        
        # Step 2b: Re-authenticate with vault context
        print(f"  Setting vault context...")
        if not vm.authenticate_dev(tenant_id=vault_id):
            print("WARNING: Failed to set vault context, continuing...")
        
        # Update config with new vault ID
        config.update_corpus(corpus_name, current_vault_id=vault_id)
        
        # Step 3: Upload documents
        print(f"\n[Step 3] Uploading documents...")
        update_status('upload', vault_id=str(vault_id))
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
        update_status('extract', documents_uploaded=len(files))
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
        
        # Save checkpoint after extraction completes successfully
        save_checkpoint(config.results_dir, corpus_name, vault_id, extraction_complete=True)
    
    # Step 5: Run test (with auto-resume from progress file)
    if not vault_id:
        print("ERROR: No vault ID available")
        return None
    
    print(f"\n[Step 5] Running test questions...")
    update_status('qa', vault_id=str(vault_id))
    extraction_config = config.extraction_config
    try:
        results = executor.run_test(
            vault_id=vault_id,
            questions_file=questions_file,
            questions_data=questions_data,
            results_dir=config.results_dir,
            corpus_name=corpus_name,
            min_chunks=extraction_config.get('min_expected_chunks', 50)
        )
    except ValueError as e:
        print(f"  ERROR: {e}")
        update_status('failed', status='failed', error=str(e))
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
    
    update_status('complete', 
                  status='finished',
                  progress={
                      'total': results['results']['total'],
                      'completed': results['results']['total'],
                      'passed': results['results']['passed'],
                      'failed': results['results']['failed']
                  },
                  accuracy=results['results']['accuracy_pct'])
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Context Foundry Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Default behavior:
  - If checkpoint exists (extraction complete), resume Q&A from last answered question
  - If no checkpoint, run full test (upload, extract, Q&A)

Examples:
  %(prog)s --corpus "Manus Healthtec"          # Auto-resume if checkpoint exists
  %(prog)s --corpus "Manus Healthtec" --fresh  # Force fresh start from scratch
  %(prog)s --list                              # Show checkpoint status for all corpora
"""
    )
    parser.add_argument('--list', action='store_true', help='List available corpora with checkpoint status')
    parser.add_argument('--corpus', type=str, help='Run test for specific corpus')
    parser.add_argument('--all', action='store_true', help='Run all corpora (sequential)')
    parser.add_argument('--questions-only', action='store_true', help='Skip upload/extraction, run questions only against existing vault')
    parser.add_argument('--fresh', action='store_true', help='Force fresh start: delete vault, recreate, upload, extract, run Q&A (ignores checkpoint)')
    parser.add_argument('--question-set-id', type=str, help='Use questions from database by question set ID')
    parser.add_argument('--config', type=str, default='src/test_config.json', help='Config file path')
    
    args = parser.parse_args()
    
    config = TestConfig(args.config)
    
    if args.list:
        list_corpora(config)
    elif args.corpus:
        run_corpus_test(args.corpus, config, 
                       questions_only=args.questions_only, 
                       fresh=args.fresh,
                       question_set_id=args.question_set_id)
    elif args.all:
        print("Running all corpora sequentially...")
        for name in config.list_corpora().keys():
            run_corpus_test(name, config, 
                           questions_only=args.questions_only, 
                           fresh=args.fresh,
                           question_set_id=args.question_set_id)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
