"""
Test Runner State Machine

Defines the formal state machine for test runs with:
- TestRunState enum for overall test status
- TestRunStage enum for pipeline stages
- Valid transitions with validation
- Atomic transition_to() function
"""

from enum import Enum
from typing import Optional, Set, Dict
from datetime import datetime, timezone
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import os

logger = logging.getLogger(__name__)


class TestRunState(Enum):
    """Overall status of a test run."""
    PENDING = 'pending'
    RUNNING = 'running'
    COMPLETE = 'complete'
    FAILED = 'failed'
    INTERRUPTED = 'interrupted'


class TestRunStage(Enum):
    """Pipeline stages for a test run (Fresh mode uses all, Auto mode skips to QA)."""
    INIT = 'init'
    DELETE = 'delete'
    CREATE = 'create'
    UPLOAD = 'upload'
    EXTRACT = 'extract'
    QA = 'qa'
    COMPLETE = 'complete'


VALID_STATE_TRANSITIONS: Dict[TestRunState, Set[TestRunState]] = {
    TestRunState.PENDING: {TestRunState.RUNNING, TestRunState.FAILED},
    TestRunState.RUNNING: {TestRunState.COMPLETE, TestRunState.FAILED, TestRunState.INTERRUPTED},
    TestRunState.COMPLETE: set(),
    TestRunState.FAILED: {TestRunState.RUNNING},
    TestRunState.INTERRUPTED: {TestRunState.RUNNING, TestRunState.FAILED},
}

STAGE_ORDER = [
    TestRunStage.INIT,
    TestRunStage.DELETE,
    TestRunStage.CREATE,
    TestRunStage.UPLOAD,
    TestRunStage.EXTRACT,
    TestRunStage.QA,
    TestRunStage.COMPLETE,
]


def get_db_session():
    """Get database session."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def is_valid_state_transition(from_state: TestRunState, to_state: TestRunState) -> bool:
    """Check if a state transition is valid."""
    if from_state == to_state:
        return True
    return to_state in VALID_STATE_TRANSITIONS.get(from_state, set())


def is_valid_stage_progression(from_stage: TestRunStage, to_stage: TestRunStage, mode: str) -> bool:
    """Check if a stage progression is valid.
    
    In Fresh mode, must progress through all stages in order.
    In Auto mode, can skip directly to QA.
    """
    if from_stage == to_stage:
        return True
    
    from_idx = STAGE_ORDER.index(from_stage)
    to_idx = STAGE_ORDER.index(to_stage)
    
    if mode == 'auto':
        return to_idx > from_idx
    
    return to_idx == from_idx + 1


def create_test_run(
    vault_id: Optional[str],
    vault_name: str,
    question_set_id: str,
    question_set_name: str,
    mode: str,
    corpus_folder: Optional[str] = None,
    questions_total: int = 0
) -> str:
    """Create a new test run in PENDING state.
    
    For Fresh mode, vault_id can be NULL (will be set after vault creation).
    For Auto mode, vault_id must be provided.
    
    Returns the test_run_id.
    """
    session = get_db_session()
    try:
        initial_stage = TestRunStage.INIT.value
        
        result = session.execute(text("""
            INSERT INTO test_runs (
                vault_id, vault_name, question_set_id, question_set_name,
                mode, corpus_folder, status, stage, questions_total, heartbeat_at
            ) VALUES (
                :vault_id, :vault_name, :question_set_id, :question_set_name,
                :mode, :corpus_folder, :status, :stage, :questions_total, NOW()
            )
            RETURNING id
        """), {
            'vault_id': vault_id,
            'vault_name': vault_name,
            'question_set_id': question_set_id,
            'question_set_name': question_set_name,
            'mode': mode,
            'corpus_folder': corpus_folder,
            'status': TestRunState.PENDING.value,
            'stage': initial_stage,
            'questions_total': questions_total
        })
        session.commit()
        row = result.fetchone()
        test_run_id = str(row[0])
        
        logger.info(f"[StateMachine] Created test run {test_run_id}: state=PENDING, stage=INIT, mode={mode}")
        return test_run_id
    finally:
        session.close()


def transition_to(
    test_run_id: str,
    new_state: Optional[TestRunState] = None,
    new_stage: Optional[TestRunStage] = None,
    vault_id: Optional[str] = None,
    error_message: Optional[str] = None,
    questions_total: Optional[int] = None,
    questions_answered: Optional[int] = None,
    questions_passed: Optional[int] = None,
    questions_failed: Optional[int] = None,
    results_file: Optional[str] = None
) -> bool:
    """Transition a test run to a new state and/or stage.
    
    This is the ONLY function that should modify test_run status/stage.
    It validates transitions and atomically updates the DB.
    
    Args:
        test_run_id: The test run to transition
        new_state: New status (if changing)
        new_stage: New stage (if changing)
        vault_id: New vault_id (for Fresh mode after vault creation)
        error_message: Error message (for FAILED state)
        questions_*: Q&A progress counters
        results_file: Path to results file (on completion)
    
    Returns:
        True if transition was successful, False if invalid
    """
    session = get_db_session()
    try:
        result = session.execute(text("""
            SELECT status, stage, mode FROM test_runs WHERE id = :id
        """), {'id': test_run_id})
        row = result.fetchone()
        
        if not row:
            logger.error(f"[StateMachine] Test run {test_run_id} not found")
            return False
        
        current_state = TestRunState(row[0])
        current_stage = TestRunStage(row[1])
        mode = row[2]
        
        if new_state and not is_valid_state_transition(current_state, new_state):
            logger.error(f"[StateMachine] Invalid state transition: {current_state.value} -> {new_state.value}")
            return False
        
        if new_stage and not is_valid_stage_progression(current_stage, new_stage, mode):
            logger.warning(f"[StateMachine] Stage progression {current_stage.value} -> {new_stage.value} (allowing anyway)")
        
        updates = ["heartbeat_at = NOW()"]
        params = {'id': test_run_id}
        
        if new_state:
            updates.append("status = :new_status")
            params['new_status'] = new_state.value
            
            if new_state == TestRunState.COMPLETE:
                updates.append("completed_at = NOW()")
        
        if new_stage:
            updates.append("stage = :new_stage")
            params['new_stage'] = new_stage.value
        
        if vault_id is not None:
            updates.append("vault_id = :vault_id")
            params['vault_id'] = vault_id
        
        if error_message is not None:
            updates.append("error_message = :error_message")
            params['error_message'] = error_message
        
        if questions_total is not None:
            updates.append("questions_total = :questions_total")
            params['questions_total'] = questions_total
        
        if questions_answered is not None:
            updates.append("questions_answered = :questions_answered")
            params['questions_answered'] = questions_answered
        
        if questions_passed is not None:
            updates.append("questions_passed = :questions_passed")
            params['questions_passed'] = questions_passed
        
        if questions_failed is not None:
            updates.append("questions_failed = :questions_failed")
            params['questions_failed'] = questions_failed
        
        if results_file is not None:
            updates.append("results_file = :results_file")
            params['results_file'] = results_file
        
        session.execute(text(f"""
            UPDATE test_runs SET {', '.join(updates)} WHERE id = :id
        """), params)
        session.commit()
        
        state_str = f"state={new_state.value}" if new_state else ""
        stage_str = f"stage={new_stage.value}" if new_stage else ""
        logger.info(f"[StateMachine] Transition {test_run_id}: {state_str} {stage_str}".strip())
        
        return True
    except Exception as e:
        logger.error(f"[StateMachine] Transition failed: {e}")
        session.rollback()
        return False
    finally:
        session.close()


def get_test_run(test_run_id: str) -> Optional[dict]:
    """Get a test run by ID."""
    session = get_db_session()
    try:
        result = session.execute(text("""
            SELECT 
                id, vault_id, vault_name, question_set_id, question_set_name,
                mode, corpus_folder, status, stage, started_at, completed_at,
                questions_total, questions_answered, questions_passed, questions_failed,
                error_message, results_file, heartbeat_at
            FROM test_runs WHERE id = :id
        """), {'id': test_run_id})
        row = result.fetchone()
        
        if not row:
            return None
        
        return {
            'id': str(row[0]),
            'vault_id': str(row[1]) if row[1] else None,
            'vault_name': row[2],
            'question_set_id': str(row[3]) if row[3] else None,
            'question_set_name': row[4],
            'mode': row[5],
            'corpus_folder': row[6],
            'status': row[7],
            'state': TestRunState(row[7]),
            'stage': row[8],
            'stage_enum': TestRunStage(row[8]),
            'started_at': row[9],
            'completed_at': row[10],
            'questions_total': row[11] or 0,
            'questions_answered': row[12] or 0,
            'questions_passed': row[13] or 0,
            'questions_failed': row[14] or 0,
            'error_message': row[15],
            'results_file': row[16],
            'heartbeat_at': row[17]
        }
    finally:
        session.close()


def get_running_test() -> Optional[dict]:
    """Get the currently running test, or None if no test is running.
    
    Uses heartbeat to detect stale tests and mark them as interrupted.
    """
    from .persistence import HEARTBEAT_TIMEOUT_SECONDS
    
    session = get_db_session()
    try:
        result = session.execute(text("""
            SELECT id, heartbeat_at FROM test_runs 
            WHERE status = 'running' 
            ORDER BY started_at DESC LIMIT 1
        """))
        row = result.fetchone()
        
        if not row:
            return None
        
        test_run_id = str(row[0])
        heartbeat_at = row[1]
        now = datetime.now(timezone.utc)
        
        if heartbeat_at:
            if heartbeat_at.tzinfo is None:
                heartbeat_at = heartbeat_at.replace(tzinfo=timezone.utc)
            age_seconds = (now - heartbeat_at).total_seconds()
            is_stale = age_seconds > HEARTBEAT_TIMEOUT_SECONDS
        else:
            is_stale = True
        
        if is_stale:
            transition_to(test_run_id, new_state=TestRunState.INTERRUPTED, 
                         error_message='Stale heartbeat - test interrupted')
            return None
        
        return get_test_run(test_run_id)
    finally:
        session.close()


def cleanup_stale_tests() -> int:
    """Mark tests with stale heartbeats as interrupted.
    
    Called on startup. Only affects tests with heartbeats older than timeout.
    Returns count of tests marked as interrupted.
    """
    from .persistence import HEARTBEAT_TIMEOUT_SECONDS
    
    session = get_db_session()
    try:
        result = session.execute(text(f"""
            UPDATE test_runs 
            SET status = 'interrupted', 
                error_message = 'Server restarted - stale heartbeat'
            WHERE status = 'running'
              AND (heartbeat_at IS NULL OR heartbeat_at < NOW() - INTERVAL '{HEARTBEAT_TIMEOUT_SECONDS} seconds')
            RETURNING id
        """))
        session.commit()
        
        rows = result.fetchall()
        if rows:
            for row in rows:
                logger.info(f"[StateMachine] Marked stale test {row[0]} as interrupted")
        
        return len(rows)
    finally:
        session.close()


def refresh_heartbeat(test_run_id: str) -> bool:
    """Refresh the heartbeat for a running test."""
    session = get_db_session()
    try:
        session.execute(text("""
            UPDATE test_runs SET heartbeat_at = NOW() WHERE id = :id
        """), {'id': test_run_id})
        session.commit()
        return True
    except Exception as e:
        logger.error(f"[StateMachine] Failed to refresh heartbeat: {e}")
        return False
    finally:
        session.close()
