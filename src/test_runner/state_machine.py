"""
Test Runner State Machine - Single Source of Truth

Implements the specification exactly:
- TestRunStatus enum with 7 states
- Valid transitions table
- transition_to() as the ONLY way to change status
- Heartbeat stale detection for INTERRUPTED
"""

from enum import Enum
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Set
import os
import logging
import json

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)

HEARTBEAT_TIMEOUT_MINUTES = 5


class TestRunStatus(Enum):
    CREATING_VAULT = 'creating_vault'
    UPLOADING = 'uploading'
    EXTRACTING = 'extracting'
    RUNNING_QA = 'running_qa'
    COMPLETE = 'complete'
    FAILED = 'failed'
    INTERRUPTED = 'interrupted'


ACTIVE_STATUSES = [
    TestRunStatus.CREATING_VAULT.value,
    TestRunStatus.UPLOADING.value,
    TestRunStatus.EXTRACTING.value,
    TestRunStatus.RUNNING_QA.value,
]

VALID_TRANSITIONS: Dict[Optional[TestRunStatus], Set[TestRunStatus]] = {
    None: {TestRunStatus.CREATING_VAULT, TestRunStatus.RUNNING_QA},
    TestRunStatus.CREATING_VAULT: {TestRunStatus.UPLOADING, TestRunStatus.FAILED, TestRunStatus.INTERRUPTED},
    TestRunStatus.UPLOADING: {TestRunStatus.EXTRACTING, TestRunStatus.FAILED, TestRunStatus.INTERRUPTED},
    TestRunStatus.EXTRACTING: {TestRunStatus.RUNNING_QA, TestRunStatus.FAILED, TestRunStatus.INTERRUPTED},
    TestRunStatus.RUNNING_QA: {TestRunStatus.COMPLETE, TestRunStatus.FAILED, TestRunStatus.INTERRUPTED},
    TestRunStatus.INTERRUPTED: {TestRunStatus.RUNNING_QA},
    TestRunStatus.COMPLETE: set(),
    TestRunStatus.FAILED: set(),
}


class InvalidStateTransition(Exception):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, from_status: Optional[str], to_status: str):
        self.from_status = from_status
        self.to_status = to_status
        super().__init__(f"Invalid transition from '{from_status}' to '{to_status}'")


def is_valid_transition(from_status: Optional[TestRunStatus], to_status: TestRunStatus) -> bool:
    """Check if a transition is valid according to the state machine."""
    valid_targets = VALID_TRANSITIONS.get(from_status, set())
    return to_status in valid_targets


def get_db_session():
    """Get a database session."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL not set")
    
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def create_test_run(
    mode: str,
    vault_id: Optional[str],
    vault_name: Optional[str],
    question_set_id: str,
    question_set_name: str,
    questions_total: int
) -> str:
    """
    Create a new test run with appropriate initial status.
    
    Fresh mode: status=CREATING_VAULT, vault_id=NULL
    Auto mode: status=RUNNING_QA, vault_id from payload
    
    Returns the new test run ID.
    """
    session = get_db_session()
    try:
        if mode == 'fresh':
            initial_status = TestRunStatus.CREATING_VAULT.value
            actual_vault_id = None
        else:
            initial_status = TestRunStatus.RUNNING_QA.value
            actual_vault_id = vault_id
        
        now = datetime.utcnow()
        
        result = session.execute(
            text("""
                INSERT INTO test_runs (
                    status, mode, vault_id, vault_name, question_set_id, question_set_name,
                    questions_total, questions_answered, questions_passed, questions_failed,
                    created_at, heartbeat_at, started_at
                ) VALUES (
                    :status, :mode, :vault_id, :vault_name, :question_set_id, :question_set_name,
                    :questions_total, 0, 0, 0,
                    :created_at, :heartbeat_at, :started_at
                ) RETURNING id
            """),
            {
                'status': initial_status,
                'mode': mode,
                'vault_id': actual_vault_id,
                'vault_name': vault_name,
                'question_set_id': question_set_id,
                'question_set_name': question_set_name,
                'questions_total': questions_total,
                'created_at': now,
                'heartbeat_at': now,
                'started_at': now if mode == 'auto' else None,
            }
        )
        row = result.fetchone()
        if not row:
            raise RuntimeError("Failed to insert test run - no ID returned")
        run_id = row[0]
        session.commit()
        logger.info(f"[StateMachine] Created test run {run_id}: status={initial_status}, mode={mode}")
        return str(run_id)
    finally:
        session.close()


def transition_to(
    run_id: str,
    new_status: TestRunStatus,
    vault_id: Optional[str] = None,
    vault_name: Optional[str] = None,
    questions_answered: Optional[int] = None,
    questions_passed: Optional[int] = None,
    questions_failed: Optional[int] = None,
    current_question: Optional[Dict[str, Any]] = None,
    error_message: Optional[str] = None,
    results_file: Optional[str] = None
) -> None:
    """
    Transition a test run to a new status.
    
    This is the ONLY function that should modify test_run status.
    Validates the transition before applying it.
    
    Raises InvalidStateTransition if the transition is not allowed.
    """
    session = get_db_session()
    try:
        result = session.execute(
            text("SELECT status FROM test_runs WHERE id = :id"),
            {'id': run_id}
        )
        row = result.fetchone()
        if not row:
            raise ValueError(f"Test run {run_id} not found")
        
        old_status_str = row[0]
        old_status = TestRunStatus(old_status_str) if old_status_str else None
        
        if not is_valid_transition(old_status, new_status):
            raise InvalidStateTransition(old_status_str, new_status.value)
        
        now = datetime.utcnow()
        
        updates = ["status = :new_status", "heartbeat_at = :now"]
        params = {
            'new_status': new_status.value,
            'now': now,
        }
        
        if vault_id is not None:
            updates.append("vault_id = :vault_id")
            params['vault_id'] = vault_id
        
        if vault_name is not None:
            updates.append("vault_name = :vault_name")
            params['vault_name'] = vault_name
        
        if questions_answered is not None:
            updates.append("questions_answered = :questions_answered")
            params['questions_answered'] = questions_answered
        
        if questions_passed is not None:
            updates.append("questions_passed = :questions_passed")
            params['questions_passed'] = questions_passed
        
        if questions_failed is not None:
            updates.append("questions_failed = :questions_failed")
            params['questions_failed'] = questions_failed
        
        if current_question is not None:
            updates.append("current_question = :current_question")
            params['current_question'] = json.dumps(current_question)
        
        if error_message is not None:
            updates.append("error_message = :error_message")
            params['error_message'] = error_message
        
        if results_file is not None:
            updates.append("results_file = :results_file")
            params['results_file'] = results_file
        
        if new_status == TestRunStatus.RUNNING_QA:
            updates.append("started_at = COALESCE(started_at, :started_at)")
            params['started_at'] = now
        
        if new_status in (TestRunStatus.COMPLETE, TestRunStatus.FAILED, TestRunStatus.INTERRUPTED):
            updates.append("completed_at = :completed_at")
            params['completed_at'] = now
        
        params['id'] = run_id
        sql = f"UPDATE test_runs SET {', '.join(updates)} WHERE id = :id"
        session.execute(text(sql), params)
        session.commit()
        
        logger.info(f"[StateMachine] Transition {run_id}: {old_status_str} -> {new_status.value}")
        
    finally:
        session.close()


def refresh_heartbeat(
    run_id: str,
    questions_answered: Optional[int] = None,
    questions_passed: Optional[int] = None,
    questions_failed: Optional[int] = None,
    current_question: Optional[Dict[str, Any]] = None
) -> None:
    """
    Update heartbeat and optionally progress counters.
    
    Called after each question and after each major stage during Fresh mode.
    Does NOT change status - use transition_to() for that.
    """
    session = get_db_session()
    try:
        now = datetime.utcnow()
        
        updates = ["heartbeat_at = :now"]
        params = {'id': run_id, 'now': now}
        
        if questions_answered is not None:
            updates.append("questions_answered = :questions_answered")
            params['questions_answered'] = questions_answered
        
        if questions_passed is not None:
            updates.append("questions_passed = :questions_passed")
            params['questions_passed'] = questions_passed
        
        if questions_failed is not None:
            updates.append("questions_failed = :questions_failed")
            params['questions_failed'] = questions_failed
        
        if current_question is not None:
            updates.append("current_question = :current_question")
            params['current_question'] = json.dumps(current_question)
        
        sql = f"UPDATE test_runs SET {', '.join(updates)} WHERE id = :id"
        session.execute(text(sql), params)
        session.commit()
        
    finally:
        session.close()


def get_running_test() -> Optional[Dict[str, Any]]:
    """
    Get the currently running test (if any).
    
    Returns the test run with an active status, or None if no test is running.
    """
    session = get_db_session()
    try:
        result = session.execute(
            text("""
                SELECT id, status, mode, vault_id, vault_name, question_set_id, question_set_name,
                       questions_total, questions_answered, questions_passed, questions_failed,
                       current_question, created_at, started_at, completed_at, heartbeat_at,
                       error_message, results_file
                FROM test_runs
                WHERE status IN ('creating_vault', 'uploading', 'extracting', 'running_qa')
                ORDER BY created_at DESC
                LIMIT 1
            """)
        )
        row = result.fetchone()
        if not row:
            return None
        
        status = row[1]
        # Map state machine status to stage name
        stage_map = {
            'creating_vault': 'create',
            'uploading': 'upload',
            'extracting': 'extract',
            'running_qa': 'qa'
        }
        stage = stage_map.get(status, 'qa')
        
        return {
            'id': str(row[0]),
            'status': status,
            'mode': row[2],
            'vault_id': row[3],
            'vault_name': row[4],
            'question_set_id': row[5],
            'question_set_name': row[6],
            'questions_total': row[7],
            'questions_answered': row[8],
            'questions_passed': row[9],
            'questions_failed': row[10],
            'current_question': row[11],
            'created_at': row[12],
            'started_at': row[13],
            'completed_at': row[14],
            'heartbeat_at': row[15],
            'error_message': row[16],
            'results_file': row[17],
            'stage': stage,
            'checkpoint': row[8],  # questions_answered is the checkpoint
        }
    finally:
        session.close()


def cleanup_stale_tests() -> int:
    """
    Detect and interrupt stale runs (heartbeat older than HEARTBEAT_TIMEOUT_MINUTES).
    
    Called on API startup and can be called via cron.
    Returns the number of tests interrupted.
    """
    session = get_db_session()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=HEARTBEAT_TIMEOUT_MINUTES)
        
        result = session.execute(
            text("""
                UPDATE test_runs
                SET status = 'interrupted',
                    error_message = 'Interrupted: heartbeat stale',
                    completed_at = :now,
                    heartbeat_at = :now
                WHERE status IN ('creating_vault', 'uploading', 'extracting', 'running_qa')
                AND heartbeat_at < :cutoff
                RETURNING id
            """),
            {'cutoff': cutoff, 'now': datetime.utcnow()}
        )
        rows = result.fetchall()
        session.commit()
        
        for row in rows:
            logger.info(f"[StateMachine] Marked stale test {row[0]} as interrupted")
        
        return len(rows)
        
    finally:
        session.close()


def get_test_run(run_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific test run by ID."""
    session = get_db_session()
    try:
        result = session.execute(
            text("""
                SELECT id, status, mode, vault_id, vault_name, question_set_id,
                       questions_total, questions_answered, questions_passed, questions_failed,
                       current_question, created_at, started_at, completed_at, heartbeat_at,
                       error_message, results_file
                FROM test_runs
                WHERE id = :id
            """),
            {'id': run_id}
        )
        row = result.fetchone()
        if not row:
            return None
        
        return {
            'id': str(row[0]),
            'status': row[1],
            'mode': row[2],
            'vault_id': row[3],
            'vault_name': row[4],
            'question_set_id': row[5],
            'questions_total': row[6],
            'questions_answered': row[7],
            'questions_passed': row[8],
            'questions_failed': row[9],
            'current_question': row[10],
            'created_at': row[11],
            'started_at': row[12],
            'completed_at': row[13],
            'heartbeat_at': row[14],
            'error_message': row[15],
            'results_file': row[16],
        }
    finally:
        session.close()


def can_resume(run_id: str) -> bool:
    """
    Check if a test run can be resumed.
    
    Resume only allowed when status is INTERRUPTED.
    """
    run = get_test_run(run_id)
    if not run:
        return False
    return run['status'] == TestRunStatus.INTERRUPTED.value
