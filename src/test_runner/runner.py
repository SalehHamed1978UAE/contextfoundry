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
from .status import update_status, STATUS_FILE_PATH


def log(msg: str):
    """Print with immediate flush for subprocess visibility."""
    print(msg)
    sys.stdout.flush()


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


def run_vault_test(vault_id: str, question_set_id: str, mode: str, corpus_folder: str = None, config: TestConfig = None, test_run_id: str = None):
    """
    Run test for a vault with 5-stage status tracking.
    
    Args:
        vault_id: UUID of the vault to test
        question_set_id: UUID of the question set
        mode: 'auto' or 'fresh'
        corpus_folder: Path to corpus folder (required for fresh mode)
        config: TestConfig instance
        test_run_id: Database ID for the test run (for persistence)
    """
    from .vault_manager import VaultManager
    from .evaluator import FuzzyEvaluator
    from .test_executor import TestExecutor
    from .persistence import update_test_run_stage, complete_test_run, update_test_run_vault_id
    
    if config is None:
        config = TestConfig('src/test_config.json')
    
    log("\n" + "=" * 70)
    log(f"TEST RUNNER: Vault {vault_id[:8]}... ({mode.upper()} mode)")
    if test_run_id:
        log(f"Test Run ID: {test_run_id}")
    log("=" * 70)
    
    update_status(overall_status='running')
    if test_run_id:
        update_test_run_stage(test_run_id, 'create' if mode == 'fresh' else 'qa')
    
    # Track completion status for try/finally
    test_completed = False
    final_status = 'failed'
    error_msg = None
    results = None
    
    vm = VaultManager(config.api_base_url)
    evaluator = FuzzyEvaluator()
    executor = TestExecutor(vm, evaluator)
    
    try:
        log("\n[Auth] Authenticating...")
        if not vm.authenticate_dev():
            log("ERROR: Failed to authenticate")
            update_status('qa', stage_status='failed', overall_status='failed')
            error_msg = "Failed to authenticate"
            return None
        
        if mode == 'fresh':
            # Get corpus path from config if available, otherwise use default path
            vault_name = corpus_folder  # Use corpus folder name as vault name
            corpus_config = config.get_corpus(corpus_folder)
            if corpus_config and corpus_config.get('root_path'):
                corpus_path = Path(corpus_config['root_path'])
            else:
                # Fallback to default path pattern
                corpus_path = Path('test documents') / corpus_folder
            
            update_status('delete', stage_status='running')
            log(f"\n[Stage: Delete] Deleting vault '{vault_name}'...")
            try:
                # Look up vault by name to get the correct ID for deletion
                existing_id = vm.find_vault_by_name(vault_name)
                if existing_id:
                    log(f"  Found existing vault: {existing_id}")
                    vm.delete_vault(existing_id, vault_name)
                    log(f"  Deleted vault {existing_id}")
                else:
                    log(f"  No existing vault found with name '{vault_name}'")
                update_status('delete', stage_status='complete')
            except Exception as e:
                log(f"  Delete skipped (may not exist): {e}")
                update_status('delete', stage_status='complete')
            
            update_status('create', stage_status='running')
            log(f"\n[Stage: Create] Creating new vault '{vault_name}'...")
            new_vault_id = vm.create_vault(vault_name)
            old_vault_id = vault_id  # Save for logging
            vault_id = new_vault_id
            log(f"  Created vault: {vault_id} (replaced old: {old_vault_id})")
            update_status('create', stage_status='complete', vault_id=str(vault_id))
            
            # CRITICAL: Update the test_run record in DB with the NEW vault ID
            # Without this, all subsequent operations would use the old (deleted) vault ID
            if test_run_id:
                update_test_run_vault_id(test_run_id, str(vault_id), vault_name)
                log(f"  [DB] Updated test_run vault_id to: {vault_id}")
            
            if not vm.authenticate_dev(tenant_id=vault_id):
                log("WARNING: Failed to set vault context")
            
            # Update DB stage to upload
            if test_run_id:
                update_test_run_stage(test_run_id, 'upload')
            update_status('upload', stage_status='running')
            log("\n[Stage: Upload] Uploading documents...")
            from .document_uploader import get_files_to_upload
            files = get_files_to_upload(corpus_path, config.upload_rules)
            log(f"  Corpus path: {corpus_path}")
            log(f"  Found {len(files)} files")
            
            for i, file_path in enumerate(files):
                success = vm.upload_document(vault_id, file_path)
                if (i + 1) % 20 == 0:
                    log(f"  [{i+1}/{len(files)}] uploaded")
            
            update_status('upload', stage_status='complete', file_count=len(files))
            
            # Update DB stage to extract
            if test_run_id:
                update_test_run_stage(test_run_id, 'extract')
            update_status('extract', stage_status='running')
            log("\n[Stage: Extract] Waiting for extraction...")
            extraction_config = config.extraction_config
            
            try:
                def on_entity_update(count):
                    update_status('extract', stage_status='running', entities=count)
                
                # Create heartbeat callback to keep test run alive during long extraction
                def heartbeat_refresh():
                    if test_run_id:
                        update_test_run_stage(test_run_id, 'extract')
                
                vm.wait_for_extraction(
                    vault_id,
                    expected_docs=len(files),
                    timeout_minutes=extraction_config.get('timeout_minutes', 20),
                    poll_interval=extraction_config.get('poll_interval_seconds', 10),
                    heartbeat_callback=heartbeat_refresh
                )
                stats = vm.get_vault_stats(vault_id)
                update_status('extract', stage_status='complete', entities=stats.get('entity_count', 0))
            except TimeoutError as e:
                log(f"  ERROR: {e}")
                update_status('extract', stage_status='failed', overall_status='failed')
                error_msg = str(e)
                return None
        else:
            update_status('delete', stage_status='skipped')
            update_status('create', stage_status='skipped')
            update_status('upload', stage_status='skipped')
            update_status('extract', stage_status='skipped')
            
            if not vm.authenticate_dev(tenant_id=vault_id):
                log("WARNING: Failed to set vault context")
        
        update_status('qa', stage_status='running')
        log("\n[Stage: Q&A] Loading questions...")
        questions_data = load_question_set_from_db(question_set_id)
        if not questions_data:
            log(f"ERROR: Question set not found: {question_set_id}")
            update_status('qa', stage_status='failed', overall_status='failed')
            error_msg = f"Question set not found: {question_set_id}"
            return None
        log(f"  Loaded {len(questions_data)} questions")
        
        log("\n[Stage: Q&A] Running test...")
        extraction_config = config.extraction_config
        results = executor.run_test(
            vault_id=vault_id,
            questions_data=questions_data,
            results_dir=config.results_dir,
            corpus_name=f"vault_{vault_id[:8]}",
            min_chunks=extraction_config.get('min_expected_chunks', 50),
            test_run_id=test_run_id
        )
        
        update_status('qa', stage_status='complete', overall_status='finished', 
                      qa_progress={
                          'total': results['results']['total'],
                          'answered': results['results']['total'],
                          'passed': results['results']['passed'],
                          'failed': results['results']['failed'],
                          'accuracy_percent': results['results']['accuracy_pct']
                      })
        
        test_completed = True
        final_status = 'complete'
        
        log("\n" + "=" * 70)
        log("TEST COMPLETE")
        log(f"Score: {results['results']['passed']}/{results['results']['total']} ({results['results']['accuracy_pct']}%)")
        log("=" * 70 + "\n")
        
        return results
        
    except Exception as e:
        log(f"ERROR: Unexpected exception: {e}")
        error_msg = str(e)
        final_status = 'failed'
        raise
        
    finally:
        # ALWAYS update DB with final status - this is the single source of truth
        if test_run_id:
            if test_completed:
                safe_name = f"vault_{vault_id[:8]}"
                progress_file = config.results_dir / f"{safe_name}_{vault_id[:8]}_progress.jsonl"
                complete_test_run(
                    test_run_id, 
                    status='complete',
                    results_file=str(progress_file) if progress_file.exists() else None
                )
            else:
                # Test didn't complete normally - mark as failed or interrupted
                complete_test_run(test_run_id, status=final_status, error_message=error_msg)
            log(f"[DB] Test run {test_run_id} marked as {final_status}")
        
        # Clean up ephemeral status file on completion/failure
        if STATUS_FILE_PATH.exists():
            try:
                STATUS_FILE_PATH.unlink()
                log("[Cleanup] Deleted status.json")
            except Exception:
                pass


def run_corpus_test(corpus_name: str, config: TestConfig, questions_only: bool = False, fresh: bool = False, question_set_id: str = None):
    """
    Run test for a single corpus (legacy mode).
    
    Default: Auto-resume if checkpoint exists (extraction complete)
    --fresh: Force full run from scratch (delete vault, upload, extract, Q&A)
    --question-set-id: Use questions from database instead of file
    """
    
    update_status('init', stage_status=None)
    
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
            update_status('qa', stage_status='failed', overall_status='failed')
            return None
        print(f"  Loaded {len(questions_data)} questions from database")
    else:
        questions_file = config.questions_dir / corpus['questions_file']
        if not questions_file.exists():
            print(f"ERROR: Questions file not found: {questions_file}")
            update_status('qa', stage_status='failed', overall_status='failed')
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
        update_status('qa', stage_status='failed', overall_status='failed')
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
    
    update_status('qa', stage_status='complete', overall_status='finished',
                  qa_progress={
                      'total': results['results']['total'],
                      'answered': results['results']['total'],
                      'passed': results['results']['passed'],
                      'failed': results['results']['failed'],
                      'accuracy_percent': results['results']['accuracy_pct']
                  })
    
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
  %(prog)s --vault-id <uuid> --question-set-id <uuid> --mode auto  # Run Q&A on existing vault
  %(prog)s --vault-id <uuid> --question-set-id <uuid> --mode fresh --corpus-folder "test documents/Manus Healthtec"
  %(prog)s --corpus "Manus Healthtec"          # Legacy: Auto-resume if checkpoint exists
  %(prog)s --list                              # Show checkpoint status for all corpora
"""
    )
    parser.add_argument('--list', action='store_true', help='List available corpora with checkpoint status')
    parser.add_argument('--corpus', type=str, help='Run test for specific corpus (legacy mode)')
    parser.add_argument('--vault-id', type=str, help='Vault ID to test against')
    parser.add_argument('--question-set-id', type=str, help='Question set ID from database')
    parser.add_argument('--mode', type=str, choices=['auto', 'fresh'], default='auto', help='Test mode: auto (use existing) or fresh (rebuild)')
    parser.add_argument('--corpus-folder', type=str, help='Corpus folder path (required for fresh mode)')
    parser.add_argument('--all', action='store_true', help='Run all corpora (sequential)')
    parser.add_argument('--questions-only', action='store_true', help='Skip upload/extraction, run questions only against existing vault')
    parser.add_argument('--fresh', action='store_true', help='Force fresh start (legacy flag)')
    parser.add_argument('--config', type=str, default='src/test_config.json', help='Config file path')
    parser.add_argument('--test-run-id', type=str, help='Database test run ID (for persistence)')
    
    args = parser.parse_args()
    
    config = TestConfig(args.config)
    
    if args.list:
        list_corpora(config)
    elif args.vault_id and args.question_set_id:
        run_vault_test(
            vault_id=args.vault_id,
            question_set_id=args.question_set_id,
            mode=args.mode,
            corpus_folder=args.corpus_folder,
            config=config,
            test_run_id=getattr(args, 'test_run_id', None)
        )
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
