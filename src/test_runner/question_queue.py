"""
Per-question durable queue for parallel test execution.

This makes Q&A resilient: if a worker dies, stale leased questions are
re-queued and another worker continues.
"""

import json
import os
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker


def get_db_session():
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def ensure_question_queue_schema() -> None:
    """Create queue table/indexes if missing."""
    session = get_db_session()
    try:
        session.execute(text("""
            CREATE TABLE IF NOT EXISTS test_run_questions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                test_run_id UUID NOT NULL REFERENCES test_runs(id) ON DELETE CASCADE,
                question_id VARCHAR(64) NOT NULL,
                question_index INTEGER NOT NULL,
                question_payload JSONB NOT NULL,
                status VARCHAR(16) NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'running', 'done', 'failed')),
                attempt INTEGER NOT NULL DEFAULT 0,
                worker_id VARCHAR(128),
                lease_expires_at TIMESTAMP WITH TIME ZONE,
                started_at TIMESTAMP WITH TIME ZONE,
                completed_at TIMESTAMP WITH TIME ZONE,
                duration_ms INTEGER,
                actual_answer TEXT,
                match_type VARCHAR(64),
                passed BOOLEAN,
                failure_reason TEXT,
                category VARCHAR(100),
                retrieval_metadata JSONB,
                error_message TEXT,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                CONSTRAINT unique_run_question UNIQUE (test_run_id, question_id)
            )
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_trq_run_status
            ON test_run_questions(test_run_id, status, question_index)
        """))
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_trq_lease
            ON test_run_questions(test_run_id, lease_expires_at)
            WHERE status = 'running'
        """))
        session.commit()
    finally:
        session.close()


def seed_questions(test_run_id: str, questions: List[Dict[str, Any]]) -> int:
    """Insert queue rows for all questions (idempotent)."""
    session = get_db_session()
    inserted = 0
    try:
        for i, q in enumerate(questions):
            q_num = i + 1
            qid = str(q.get('id') or q_num)
            result = session.execute(text("""
                INSERT INTO test_run_questions (
                    test_run_id, question_id, question_index, question_payload, status
                ) VALUES (
                    :test_run_id, :question_id, :question_index, CAST(:payload AS JSONB), 'pending'
                )
                ON CONFLICT (test_run_id, question_id) DO NOTHING
                RETURNING id
            """), {
                'test_run_id': test_run_id,
                'question_id': qid,
                'question_index': q_num,
                'payload': json.dumps(q),
            })
            if result.fetchone():
                inserted += 1
        session.commit()
        return inserted
    finally:
        session.close()


def reclaim_stale_questions(test_run_id: str) -> int:
    """Requeue stale leased questions."""
    session = get_db_session()
    try:
        result = session.execute(text("""
            UPDATE test_run_questions
            SET status = 'pending',
                worker_id = NULL,
                lease_expires_at = NULL,
                updated_at = NOW(),
                error_message = COALESCE(error_message, 'Requeued stale lease')
            WHERE test_run_id = :test_run_id
              AND status = 'running'
              AND lease_expires_at IS NOT NULL
              AND lease_expires_at < NOW()
            RETURNING id
        """), {'test_run_id': test_run_id})
        rows = result.fetchall()
        session.commit()
        return len(rows)
    finally:
        session.close()


def lease_next_question(
    test_run_id: str,
    worker_id: str,
    lease_seconds: int = 180,
) -> Optional[Dict[str, Any]]:
    """Lease next pending question using SKIP LOCKED."""
    session = get_db_session()
    try:
        row = session.execute(text("""
            WITH candidate AS (
                SELECT id
                FROM test_run_questions
                WHERE test_run_id = :test_run_id
                  AND status = 'pending'
                ORDER BY question_index ASC
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE test_run_questions q
            SET status = 'running',
                worker_id = :worker_id,
                lease_expires_at = NOW() + CAST((:lease_seconds || ' seconds') AS INTERVAL),
                started_at = COALESCE(started_at, NOW()),
                updated_at = NOW(),
                attempt = attempt + 1
            FROM candidate
            WHERE q.id = candidate.id
            RETURNING q.id, q.question_id, q.question_index, q.question_payload, q.attempt
        """), {
            'test_run_id': test_run_id,
            'worker_id': worker_id,
            'lease_seconds': str(lease_seconds),
        }).fetchone()
        session.commit()
        if not row:
            return None
        payload = row[3] if isinstance(row[3], dict) else json.loads(row[3] or "{}")
        return {
            'row_id': str(row[0]),
            'question_id': row[1],
            'question_index': row[2],
            'question': payload,
            'attempt': row[4],
        }
    finally:
        session.close()


def complete_question(
    row_id: str,
    actual_answer: str,
    match_type: str,
    passed: bool,
    failure_reason: Optional[str],
    category: Optional[str],
    duration_ms: int,
    retrieval_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    session = get_db_session()
    try:
        session.execute(text("""
            UPDATE test_run_questions
            SET status = 'done',
                completed_at = NOW(),
                updated_at = NOW(),
                duration_ms = :duration_ms,
                actual_answer = :actual_answer,
                match_type = :match_type,
                passed = :passed,
                failure_reason = :failure_reason,
                category = :category,
                retrieval_metadata = CAST(:retrieval_metadata AS JSONB),
                error_message = NULL
            WHERE id = :row_id
        """), {
            'row_id': row_id,
            'duration_ms': duration_ms,
            'actual_answer': actual_answer[:2000] if actual_answer else '',
            'match_type': match_type,
            'passed': passed,
            'failure_reason': failure_reason,
            'category': category,
            'retrieval_metadata': json.dumps(retrieval_metadata or {}),
        })
        session.commit()
    finally:
        session.close()


def fail_question(
    row_id: str,
    error_message: str,
    retryable: bool,
    max_attempts: int,
) -> str:
    """
    Mark question failed or requeue it.
    Returns final status: 'pending' or 'failed'.
    """
    session = get_db_session()
    try:
        row = session.execute(text("""
            SELECT attempt FROM test_run_questions WHERE id = :row_id
        """), {'row_id': row_id}).fetchone()
        attempt = (row[0] if row else 1) or 1

        if retryable and attempt < max_attempts:
            status = 'pending'
            session.execute(text("""
                UPDATE test_run_questions
                SET status = 'pending',
                    worker_id = NULL,
                    lease_expires_at = NULL,
                    updated_at = NOW(),
                    error_message = :error_message
                WHERE id = :row_id
            """), {'row_id': row_id, 'error_message': error_message[:500]})
        else:
            status = 'failed'
            session.execute(text("""
                UPDATE test_run_questions
                SET status = 'failed',
                    completed_at = NOW(),
                    updated_at = NOW(),
                    error_message = :error_message
                WHERE id = :row_id
            """), {'row_id': row_id, 'error_message': error_message[:500]})
        session.commit()
        return status
    finally:
        session.close()


def get_queue_progress(test_run_id: str) -> Dict[str, int]:
    session = get_db_session()
    try:
        row = session.execute(text("""
            SELECT
                COUNT(*) AS total,
                COUNT(*) FILTER (WHERE status = 'pending') AS pending,
                COUNT(*) FILTER (WHERE status = 'running') AS running,
                COUNT(*) FILTER (WHERE status = 'done') AS done,
                COUNT(*) FILTER (WHERE status = 'failed') AS failed_terminal,
                COUNT(*) FILTER (WHERE status IN ('done', 'failed')) AS answered_terminal,
                COUNT(*) FILTER (WHERE status = 'done' AND passed = TRUE) AS passed
            FROM test_run_questions
            WHERE test_run_id = :test_run_id
        """), {'test_run_id': test_run_id}).fetchone()
        if not row:
            return {
                'total': 0,
                'pending': 0,
                'running': 0,
                'done': 0,
                'failed_terminal': 0,
                'answered_terminal': 0,
                'passed': 0,
                'failed': 0,
            }
        answered = int(row[5] or 0)
        passed = int(row[6] or 0)
        return {
            'total': int(row[0] or 0),
            'pending': int(row[1] or 0),
            'running': int(row[2] or 0),
            'done': int(row[3] or 0),
            'failed_terminal': int(row[4] or 0),
            'answered_terminal': answered,
            'passed': passed,
            'failed': max(answered - passed, 0),
        }
    finally:
        session.close()


def list_question_results(test_run_id: str) -> List[Dict[str, Any]]:
    """Return per-question result rows ordered by question index."""
    session = get_db_session()
    try:
        rows = session.execute(text("""
            SELECT question_index, question_id, question_payload, status,
                   actual_answer, match_type, passed, failure_reason, category
            FROM test_run_questions
            WHERE test_run_id = :test_run_id
            ORDER BY question_index ASC
        """), {'test_run_id': test_run_id}).fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            q = row[2] if isinstance(row[2], dict) else json.loads(row[2] or "{}")
            query = q.get('question', q.get('query', ''))
            expected = q.get('expected_answer', q.get('answer', q.get('expected', '')))
            status = row[3]
            passed = bool(row[6]) if status == 'done' else False
            match_type = row[5] or ('error' if status == 'failed' else 'pending')
            failure_reason = row[7] if not passed else None
            failure_category = 'ERROR' if status == 'failed' else (None if passed else 'MISMATCH')
            results.append({
                'q': int(row[0]),
                'passed': passed,
                'match_type': match_type,
                'query': (query or '')[:200],
                'expected': (expected or '')[:200],
                'expected_normalized': (expected or '')[:200],
                'actual': (row[4] or '')[:500],
                'actual_normalized': (row[4] or '')[:500],
                'error_type': None if status == 'done' else 'error',
                'failure_reason': failure_reason,
                'failure_category': failure_category,
            })
        return results
    finally:
        session.close()
