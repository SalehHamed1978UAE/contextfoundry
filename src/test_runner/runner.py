#!/usr/bin/env python3
"""
Context Foundry Test Runner
One-command test runner for all corpora.

DEFAULT BEHAVIOR:
- Always runs fresh: deletes cached progress files and runs all questions
- Use --resume only for interrupted tests that need to continue

Usage:
    python -m src.test_runner.runner --list                    # List available corpora
    python -m src.test_runner.runner --corpus "Manus Healthtec"  # Run fresh (default)
    python -m src.test_runner.runner --corpus "X" --resume       # Resume interrupted test
    python -m src.test_runner.runner --all                       # Run all corpora (sequential)
    python -m src.test_runner.runner --corpus "X" --question-set-id <uuid>  # Use question set from DB
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

from .config import TestConfig
from .vault_manager import VaultManager
from .document_uploader import get_files_to_upload
from .test_executor import TestExecutor
from .evaluator import FuzzyEvaluator
from .status import update_status, STATUS_FILE_PATH


def log(msg: str):
    """Print with immediate flush for subprocess visibility."""
    print(msg)


def wait_for_server(api_base_url: str, max_wait: int = 90) -> bool:
    """Poll the platform server until it responds or max_wait seconds elapse.

    Fixes the cold-start race where test workflows launch in parallel with
    `Start All` and try to authenticate before Flask is bound to port 5000.
    """
    base = api_base_url.rstrip("/")
    health_urls = [f"{base}/health", f"{base}/api/health", base]
    deadline = time.time() + max_wait
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        for url in health_urls:
            try:
                resp = requests.get(url, timeout=2)
                if resp.status_code < 500:
                    if attempt > 1:
                        log(f"  Server reachable at {url} after {attempt} attempts")
                    return True
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                continue
            except Exception:
                continue
        if attempt == 1 or attempt % 5 == 0:
            log(f"  Waiting for server at {base}... (attempt {attempt})")
        time.sleep(2)
    return False


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


def run_vault_test(
    vault_id: str,
    question_set_id: str,
    mode: str,
    corpus_folder: str = None,
    config: TestConfig = None,
    test_run_id: str = None,
    expected_tree_based_retrieval: bool | None = None,
    parallel_workers: int = 1,
):
    """
    Run test for a vault with 5-stage status tracking.
    
    Uses the state machine for all state transitions.
    
    Args:
        vault_id: UUID of the vault to test (can be None for fresh mode)
        question_set_id: UUID of the question set
        mode: 'auto' or 'fresh'
        corpus_folder: Path to corpus folder (required for fresh mode)
        config: TestConfig instance
        test_run_id: Database ID for the test run (for persistence)
    """
    from .vault_manager import VaultManager
    from .evaluator import FuzzyEvaluator
    from .test_executor import TestExecutor
    from .state_machine import (
        transition_to, TestRunStatus, refresh_heartbeat, get_test_run
    )
    
    if config is None:
        config = TestConfig('src/test_config.json')
    
    vault_display = vault_id[:8] if vault_id else 'NEW'
    log("\n" + "=" * 70)
    log(f"TEST RUNNER: Vault {vault_display}... ({mode.upper()} mode)")
    if test_run_id:
        log(f"Test Run ID: {test_run_id}")
    effective_tree = os.environ.get("CF_TREE_BASED_RETRIEVAL", "false").lower() == "true"
    log(f"Effective CF_TREE_BASED_RETRIEVAL={effective_tree}")
    log(f"Parallel workers={parallel_workers}")
    if expected_tree_based_retrieval is not None and effective_tree != expected_tree_based_retrieval:
        msg = (
            f"retrieval_flag_mismatch: expected={expected_tree_based_retrieval} "
            f"effective={effective_tree}"
        )
        log(f"ERROR: {msg}")
        update_status('qa', stage_status='failed', overall_status='failed', error=msg)
        return None
    log("=" * 70)
    
    update_status(overall_status='running')
    
    # Track completion status for try/finally
    test_completed = False
    final_status = 'failed'
    error_msg = None
    results = None
    
    vm = VaultManager(config.api_base_url)
    evaluator = FuzzyEvaluator()
    executor = TestExecutor(vm, evaluator)
    
    try:
        log("\n[Auth] Waiting for server cold start...")
        if not wait_for_server(config.api_base_url):
            log(f"ERROR: Server at {config.api_base_url} did not start within 90s")
            update_status('qa', stage_status='failed', overall_status='failed')
            error_msg = "Server unavailable"
            return None
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
            
            if test_run_id:
                transition_to(test_run_id, TestRunStatus.UPLOADING, vault_id=str(vault_id), vault_name=vault_name)
                log(f"  [DB] Updated test_run vault_id to: {vault_id}, transitioned to UPLOADING")
                
                # Update question set to point to new vault (fresh mode creates new vault)
                from .persistence import update_question_set_vault
                update_question_set_vault(question_set_id, str(vault_id))
                log(f"  [DB] Updated question_set vault_id to: {vault_id}")
            
            if not vm.authenticate_dev(tenant_id=vault_id):
                log("WARNING: Failed to set vault context")
            
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
            
            if test_run_id:
                transition_to(test_run_id, TestRunStatus.EXTRACTING)
            update_status('extract', stage_status='running')
            log("\n[Stage: Extract] Waiting for extraction...")
            extraction_config = config.extraction_config
            
            try:
                def on_entity_update(count):
                    update_status('extract', stage_status='running', entities=count)
                
                def heartbeat_refresh():
                    if test_run_id:
                        refresh_heartbeat(test_run_id)
                
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
            update_status('extract', stage_status='running')
            
            if not vm.authenticate_dev(tenant_id=vault_id):
                log("WARNING: Failed to set vault context")
            
            # Verify extraction is complete before starting Q&A (auto mode)
            log("\n[Stage: Extract] Verifying extraction is complete...")
            try:
                vm.verify_extraction_complete(vault_id, timeout_minutes=30)
                stats = vm.get_vault_stats(vault_id)
                update_status('extract', stage_status='complete', entities=stats.get('entity_count', 0))
            except TimeoutError as e:
                log(f"  ERROR: {e}")
                update_status('extract', stage_status='failed', overall_status='failed')
                error_msg = str(e)
                return None
            except ValueError as e:
                log(f"  ERROR: {e}")
                update_status('extract', stage_status='failed', overall_status='failed')
                error_msg = str(e)
                return None
        
        # Read tree_based_retrieval from database (with env var fallback for CLI runs).
        # 2026-05-08: Reverted to False default after -21 regression. Re-enable after _fallback_semantic_search fix.
        import os as _os
        tree_based_retrieval = _os.environ.get("CF_TREE_BASED_RETRIEVAL", "false").lower() == "true"
        log(f"Tree-based retrieval default: {tree_based_retrieval} (env={_os.environ.get('CF_TREE_BASED_RETRIEVAL', '<unset>')})")
        if test_run_id:
            current_run = get_test_run(test_run_id)
            if current_run and current_run['status'] != 'running_qa':
                transition_to(test_run_id, TestRunStatus.RUNNING_QA)
            # Read tree_based_retrieval from test run
            if current_run:
                tree_based_retrieval = current_run.get('tree_based_retrieval', False)
                log(f"Tree-based retrieval from database: {tree_based_retrieval}")

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
            test_run_id=test_run_id,
            tree_based_retrieval=tree_based_retrieval,
            parallel_workers=parallel_workers
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
        if test_run_id:
            if test_completed and results:
                safe_name = f"vault_{vault_id[:8]}"
                progress_file = config.results_dir / f"{safe_name}_{vault_id[:8]}_progress.jsonl"
                transition_to(
                    test_run_id,
                    TestRunStatus.COMPLETE,
                    questions_answered=results['results']['total'],
                    questions_passed=results['results']['passed'],
                    questions_failed=results['results']['failed'],
                    results_file=str(progress_file) if progress_file.exists() else None
                )
            else:
                new_status = TestRunStatus.FAILED if final_status == 'failed' else TestRunStatus.INTERRUPTED
                transition_to(
                    test_run_id,
                    new_status,
                    error_message=error_msg
                )
            log(f"[DB] Test run {test_run_id} marked as {final_status}")
        
        # Clean up ephemeral status file on completion/failure
        if STATUS_FILE_PATH.exists():
            try:
                STATUS_FILE_PATH.unlink()
                log("[Cleanup] Deleted status.json")
            except Exception:
                pass


def run_corpus_test(corpus_name: str, config: TestConfig, questions_only: bool = False, resume: bool = False, question_set_id: str = None):
    """
    Run test for a single corpus (legacy mode).
    
    Default: Always run fresh (delete progress files, run all questions)
    --resume: Continue from previous progress (only for interrupted tests)
    --question-set-id: Use questions from database instead of file
    """
    
    update_status('init', stage_status=None)
    
    # Default: Clear progress files and run fresh
    # Only check for checkpoint if --resume is explicitly passed
    checkpoint = None
    if resume:
        checkpoint = load_checkpoint(config.results_dir, corpus_name)
        if checkpoint and checkpoint.get('extraction_complete'):
            print(f"\n  Found checkpoint from {checkpoint.get('timestamp', 'unknown')}")
    else:
        # Fresh run: delete any existing progress files
        import glob
        safe_name = corpus_name.lower().replace(' ', '_').replace('-', '_')
        patterns = [
            f"test_results/*{safe_name}*progress*.jsonl",
            f"test_results/*{safe_name}*progress*.json",
            f"test_results/vault_*_progress.jsonl",
        ]
        for pattern in patterns:
            for f in glob.glob(pattern):
                try:
                    os.remove(f)
                    print(f"[FRESH] Deleted cache: {f}")
                except Exception:
                    pass
    
    # Determine mode
    will_resume = checkpoint and checkpoint.get('extraction_complete') and resume
    
    mode_str = ""
    if will_resume:
        mode_str = " (RESUMING)"
    elif questions_only:
        mode_str = " (QUESTIONS ONLY)"
    else:
        mode_str = " (FRESH)"
    
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
    
    # Step 0: Wait for server to be reachable (handles cold-start race)
    print("\n[Step 0] Waiting for server cold start...")
    if not wait_for_server(config.api_base_url):
        print(f"ERROR: Server at {config.api_base_url} did not start within 90s")
        return None

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
        
        # Verify extraction is actually complete before Q&A
        try:
            vm.verify_extraction_complete(vault_id, timeout_minutes=30)
        except (TimeoutError, ValueError) as e:
            print(f"ERROR: {e}")
            return None
        
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
        
        # Verify extraction is actually complete before Q&A
        try:
            vm.verify_extraction_complete(vault_id, timeout_minutes=30)
        except (TimeoutError, ValueError) as e:
            print(f"ERROR: {e}")
            return None
        
        files = []
    
    # FRESH PATH: Full run from scratch
    else:
        # If not resuming, delete existing checkpoint first
        if not resume:
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
    
    # Step 5: Run test questions
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
  - Always runs fresh: deletes cached progress files and runs all questions
  - Use --resume only for interrupted tests that need to continue

Examples:
  %(prog)s --corpus "Manus Healthtec"          # Run fresh (default)
  %(prog)s --corpus "Manus Healthtec" --resume # Resume interrupted test
  %(prog)s --vault-id <uuid> --question-set-id <uuid> --mode auto  # Run Q&A on existing vault
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
    parser.add_argument('--resume', action='store_true', help='Resume from previous progress (only use for interrupted tests)')
    parser.add_argument('--config', type=str, default='src/test_config.json', help='Config file path')
    parser.add_argument('--test-run-id', type=str, help='Database test run ID (for persistence)')
    parser.add_argument(
        '--tree-based-retrieval',
        type=str,
        choices=['true', 'false'],
        help='Expected retrieval flag for this run (must match effective env)'
    )
    parser.add_argument(
        '--parallel-workers',
        type=int,
        default=int(os.environ.get('CF_TEST_PARALLEL_WORKERS', '4')),
        help='Number of parallel question workers (1-16)'
    )
    
    args = parser.parse_args()
    
    config = TestConfig(args.config)
    
    if args.list:
        list_corpora(config)
    elif args.question_set_id:
        expected_tree_flag = None
        if args.tree_based_retrieval is not None:
            expected_tree_flag = args.tree_based_retrieval.lower() == 'true'
        run_vault_test(
            vault_id=args.vault_id,
            question_set_id=args.question_set_id,
            mode=args.mode,
            corpus_folder=args.corpus_folder,
            config=config,
            test_run_id=args.test_run_id,
            expected_tree_based_retrieval=expected_tree_flag,
            parallel_workers=max(1, min(args.parallel_workers, 16))
        )
    elif args.corpus:
        run_corpus_test(args.corpus, config, 
                       questions_only=args.questions_only, 
                       resume=args.resume,
                       question_set_id=args.question_set_id)
    elif args.all:
        print("Running all corpora sequentially...")
        for name in config.list_corpora().keys():
            run_corpus_test(name, config, 
                           questions_only=args.questions_only, 
                           resume=args.resume,
                           question_set_id=args.question_set_id)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
