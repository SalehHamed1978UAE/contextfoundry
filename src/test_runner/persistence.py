"""
Database persistence for test runs.
Ensures test state survives server restarts.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

HEARTBEAT_TIMEOUT_SECONDS = 300  # 5 minutes - long enough for slow LLM calls


def get_db_session():
    """Get database session."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def create_test_run(
    vault_id: str,
    vault_name: str,
    question_set_id: str,
    question_set_name: str,
    mode: str,
    corpus_folder: str = None,
    questions_total: int = 0
) -> str:
    """Create a new test run in the database immediately.
    Returns the test_run_id.
    """
    session = get_db_session()
    try:
        result = session.execute(text("""
            INSERT INTO test_runs (
                vault_id, vault_name, question_set_id, question_set_name,
                mode, corpus_folder, status, stage, questions_total, heartbeat_at
            ) VALUES (
                :vault_id, :vault_name, :question_set_id, :question_set_name,
                :mode, :corpus_folder, 'running', 'create', :questions_total, NOW()
            )
            RETURNING id
        """), {
            'vault_id': vault_id,
            'vault_name': vault_name,
            'question_set_id': question_set_id,
            'question_set_name': question_set_name,
            'mode': mode,
            'corpus_folder': corpus_folder,
            'questions_total': questions_total
        })
        session.commit()
        row = result.fetchone()
        return str(row[0])
    finally:
        session.close()


def update_test_run_stage(test_run_id: str, stage: str, **kwargs):
    """Update the current stage of a test run and refresh heartbeat."""
    session = get_db_session()
    try:
        updates = ["stage = :stage", "heartbeat_at = NOW()"]
        params = {'test_run_id': test_run_id, 'stage': stage}
        
        if 'questions_total' in kwargs:
            updates.append("questions_total = :questions_total")
            params['questions_total'] = kwargs['questions_total']
        
        session.execute(text(f"""
            UPDATE test_runs 
            SET {', '.join(updates)}
            WHERE id = :test_run_id
        """), params)
        session.commit()
    finally:
        session.close()


def update_test_run_progress(
    test_run_id: str,
    questions_answered: int,
    questions_passed: int,
    questions_failed: int,
    current_question: Dict = None
):
    """Update Q&A progress and refresh heartbeat."""
    session = get_db_session()
    try:
        checkpoint = None
        if current_question:
            checkpoint = json.dumps({
                'last_question_id': current_question.get('id'),
                'last_question_text': current_question.get('text', '')[:100]
            })
        
        session.execute(text("""
            UPDATE test_runs 
            SET questions_answered = :answered,
                questions_passed = :passed,
                questions_failed = :failed,
                checkpoint = :checkpoint,
                heartbeat_at = NOW()
            WHERE id = :test_run_id
        """), {
            'test_run_id': test_run_id,
            'answered': questions_answered,
            'passed': questions_passed,
            'failed': questions_failed,
            'checkpoint': checkpoint
        })
        session.commit()
    finally:
        session.close()


def save_test_result(
    test_run_id: str,
    question_id: str,
    question_text: str,
    expected_answer: str,
    actual_answer: str,
    passed: bool,
    failure_reason: str = None,
    category: str = None,
    duration_ms: int = None
):
    """Save an individual test result to the database."""
    session = get_db_session()
    try:
        session.execute(text("""
            INSERT INTO test_results (
                test_run_id, question_id, question_text, expected_answer,
                actual_answer, category, passed, failure_reason, duration_ms
            ) VALUES (
                :test_run_id, :question_id, :question_text, :expected_answer,
                :actual_answer, :category, :passed, :failure_reason, :duration_ms
            )
            ON CONFLICT (test_run_id, question_id) 
            DO UPDATE SET
                actual_answer = EXCLUDED.actual_answer,
                passed = EXCLUDED.passed,
                failure_reason = EXCLUDED.failure_reason,
                duration_ms = EXCLUDED.duration_ms,
                answered_at = NOW()
        """), {
            'test_run_id': test_run_id,
            'question_id': str(question_id),
            'question_text': question_text[:2000] if question_text else '',
            'expected_answer': expected_answer[:2000] if expected_answer else '',
            'actual_answer': actual_answer[:2000] if actual_answer else '',
            'category': category,
            'passed': passed,
            'failure_reason': failure_reason,
            'duration_ms': duration_ms
        })
        session.commit()
    finally:
        session.close()


def complete_test_run(test_run_id: str, status: str = 'complete', error_message: str = None, results_file: str = None):
    """Mark a test run as complete, failed, or interrupted."""
    session = get_db_session()
    try:
        session.execute(text("""
            UPDATE test_runs 
            SET status = :status,
                stage = 'complete',
                completed_at = NOW(),
                error_message = :error_message,
                results_file = :results_file,
                heartbeat_at = NOW()
            WHERE id = :test_run_id
        """), {
            'test_run_id': test_run_id,
            'status': status,
            'error_message': error_message,
            'results_file': results_file
        })
        session.commit()
    finally:
        session.close()


def get_running_test() -> Optional[Dict]:
    """Get the currently running test, or None if no test is running.
    
    A test is considered "running" if:
    - status = 'running' AND heartbeat_at is within HEARTBEAT_TIMEOUT_SECONDS
    
    A test is considered "interrupted" if:
    - status = 'running' AND heartbeat_at is older than HEARTBEAT_TIMEOUT_SECONDS
    
    If a stale heartbeat is detected, the test is marked as interrupted in the DB.
    """
    session = get_db_session()
    try:
        result = session.execute(text("""
            SELECT 
                id, vault_id, vault_name, question_set_id, question_set_name,
                mode, corpus_folder, status, stage, started_at, 
                questions_total, questions_answered, questions_passed, questions_failed,
                checkpoint, heartbeat_at
            FROM test_runs
            WHERE status = 'running'
            ORDER BY started_at DESC
            LIMIT 1
        """))
        
        row = result.fetchone()
        if not row:
            return None
        
        test_id = str(row[0])
        heartbeat_at = row[15]
        now = datetime.now(timezone.utc)
        age_seconds = None
        
        if heartbeat_at:
            if heartbeat_at.tzinfo is None:
                heartbeat_at = heartbeat_at.replace(tzinfo=timezone.utc)
            
            age_seconds = (now - heartbeat_at).total_seconds()
            is_stale = age_seconds > HEARTBEAT_TIMEOUT_SECONDS
        else:
            is_stale = True
            age_seconds = 999
        
        if is_stale:
            session.execute(text("""
                UPDATE test_runs SET status = 'interrupted' WHERE id = :id
            """), {'id': test_id})
            session.commit()
            actual_status = 'interrupted'
        else:
            actual_status = 'running'
        
        return {
            'id': test_id,
            'vault_id': str(row[1]) if row[1] else None,
            'vault_name': row[2],
            'question_set_id': str(row[3]) if row[3] else None,
            'question_set_name': row[4],
            'mode': row[5],
            'corpus_folder': row[6],
            'status': actual_status,
            'db_status': row[7],
            'stage': row[8],
            'started_at': row[9].isoformat() if row[9] else None,
            'questions_total': row[10] or 0,
            'questions_answered': row[11] or 0,
            'questions_passed': row[12] or 0,
            'questions_failed': row[13] or 0,
            'checkpoint': row[14] if isinstance(row[14], dict) else (json.loads(row[14]) if row[14] else None),
            'heartbeat_at': heartbeat_at.isoformat() if heartbeat_at else None,
            'heartbeat_age_seconds': age_seconds
        }
    finally:
        session.close()


def mark_stale_tests_interrupted():
    """Mark any running tests with stale heartbeats as interrupted."""
    session = get_db_session()
    try:
        result = session.execute(text("""
            UPDATE test_runs
            SET status = 'interrupted'
            WHERE status = 'running'
            AND heartbeat_at < NOW() - INTERVAL ':timeout seconds'
            RETURNING id
        """.replace(':timeout', str(HEARTBEAT_TIMEOUT_SECONDS))))
        session.commit()
        
        rows = result.fetchall()
        return len(rows)
    finally:
        session.close()


def get_last_answered_question_id(test_run_id: str) -> Optional[str]:
    """Get the ID of the last answered question for a test run."""
    session = get_db_session()
    try:
        result = session.execute(text("""
            SELECT question_id 
            FROM test_results 
            WHERE test_run_id = :test_run_id
            ORDER BY answered_at DESC
            LIMIT 1
        """), {'test_run_id': test_run_id})
        
        row = result.fetchone()
        return row[0] if row else None
    finally:
        session.close()


def get_answered_question_ids(test_run_id: str) -> set:
    """Get all answered question IDs for a test run."""
    session = get_db_session()
    try:
        result = session.execute(text("""
            SELECT question_id 
            FROM test_results 
            WHERE test_run_id = :test_run_id
        """), {'test_run_id': test_run_id})
        
        return {row[0] for row in result}
    finally:
        session.close()


def get_test_run_progress(test_run_id: str) -> dict:
    """Get the current progress counts for a test run."""
    session = get_db_session()
    try:
        result = session.execute(text("""
            SELECT questions_total, questions_answered, questions_passed, questions_failed
            FROM test_runs
            WHERE id = :test_run_id
        """), {'test_run_id': test_run_id})
        
        row = result.fetchone()
        if row:
            return {
                'total': row[0] or 0,
                'answered': row[1] or 0,
                'passed': row[2] or 0,
                'failed': row[3] or 0
            }
        return {'total': 0, 'answered': 0, 'passed': 0, 'failed': 0}
    finally:
        session.close()


def reset_test_run_for_resume(test_run_id: str):
    """Reset a test run's status to running for resume."""
    session = get_db_session()
    try:
        session.execute(text("""
            UPDATE test_runs
            SET status = 'running',
                stage = 'qa',
                heartbeat_at = NOW(),
                completed_at = NULL,
                error_message = NULL
            WHERE id = :test_run_id
        """), {'test_run_id': test_run_id})
        session.commit()
    finally:
        session.close()


def recover_file_test_to_db(file_status: dict) -> Optional[str]:
    """Create a DB record from a file-only interrupted test.
    
    This handles backward compatibility for tests run before DB persistence was added.
    Returns the new test_run_id if successful, None otherwise.
    """
    vault_id = file_status.get('vault_id')
    question_set_id = file_status.get('question_set_id')
    
    if not vault_id or not question_set_id:
        return None
    
    qa_progress = file_status.get('qa_progress', {})
    current_question = file_status.get('current_question', {})
    
    session = get_db_session()
    try:
        existing = session.execute(text("""
            SELECT id FROM test_runs 
            WHERE vault_id = :vault_id AND question_set_id = :question_set_id 
            AND status IN ('running', 'interrupted')
            LIMIT 1
        """), {'vault_id': vault_id, 'question_set_id': question_set_id})
        if existing.fetchone():
            return None
        
        vault_result = session.execute(text("""
            SELECT name FROM platform.tenants WHERE id = :vault_id
        """), {'vault_id': vault_id})
        vault_row = vault_result.fetchone()
        vault_name = vault_row[0] if vault_row else 'Unknown'
        
        qs_result = session.execute(text("""
            SELECT name FROM question_sets WHERE id = :qs_id
        """), {'qs_id': question_set_id})
        qs_row = qs_result.fetchone()
        qs_name = qs_row[0] if qs_row else 'Unknown'
        
        result = session.execute(text("""
            INSERT INTO test_runs (
                vault_id, vault_name, question_set_id, question_set_name,
                mode, corpus_folder, status, stage, 
                questions_total, questions_answered, questions_passed, questions_failed,
                started_at, heartbeat_at, error_message
            ) VALUES (
                :vault_id, :vault_name, :question_set_id, :question_set_name,
                :mode, :corpus_folder, 'interrupted', 'qa',
                :questions_total, :questions_answered, :questions_passed, :questions_failed,
                :started_at, NOW(), 'Recovered from status file (pre-persistence test)'
            )
            RETURNING id
        """), {
            'vault_id': vault_id,
            'vault_name': vault_name,
            'question_set_id': question_set_id,
            'question_set_name': qs_name,
            'mode': file_status.get('mode', 'auto'),
            'corpus_folder': file_status.get('corpus_folder'),
            'questions_total': qa_progress.get('total', 0),
            'questions_answered': qa_progress.get('answered', 0),
            'questions_passed': qa_progress.get('passed', 0),
            'questions_failed': qa_progress.get('failed', 0),
            'started_at': file_status.get('started_at', datetime.now(timezone.utc).isoformat())
        })
        session.commit()
        row = result.fetchone()
        return str(row[0]) if row else None
    except Exception as e:
        session.rollback()
        print(f"[Persistence] Failed to recover file test to DB: {e}")
        return None
    finally:
        session.close()
