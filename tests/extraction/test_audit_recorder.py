"""
Piece 2 Stage 1 — AuditRecorder unit tests.

Verifies write path to platform.audit_records (created 2026-05-10 by the
Step C migration). Tests run against the live DB and clean up rows by id.
"""
import os
import json
import pytest
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker

from src.context_foundry.extraction.audit_recorder import AuditRecorder


@pytest.fixture(scope="module")
def db_session():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set; AuditRecorder tests require live DB")
    engine = create_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def cleanup_ids(db_session):
    """Track inserted record ids and delete on teardown."""
    ids = []
    yield ids
    if ids:
        db_session.execute(
            sql_text(
                "DELETE FROM platform.audit_records "
                "WHERE id::text = ANY(:ids)"
            ),
            {"ids": [str(i) for i in ids]},
        )
        db_session.commit()


def _fetch(db_session, record_id):
    row = db_session.execute(
        sql_text(
            "SELECT id::text, document_id::text, signal_type, severity, "
            "payload, created_at FROM platform.audit_records WHERE id = :id"
        ),
        {"id": record_id},
    ).fetchone()
    return row


def test_emit_low_confidence_inserts_row(db_session, cleanup_ids):
    recorder = AuditRecorder(db_session)
    rec_id = recorder.emit_low_confidence(
        confidence=0.18,
        primary_domain="finance",
        classifier_version="v1.2.3",
        classification_evidence={"keywords": ["10-K", "balance sheet"]},
        document_id=None,
    )
    db_session.commit()
    cleanup_ids.append(rec_id)

    row = _fetch(db_session, rec_id)
    assert row is not None
    assert row.signal_type == "low_confidence"
    assert row.severity == "warn"
    assert row.document_id is None
    payload = row.payload if isinstance(row.payload, dict) else json.loads(row.payload)
    assert payload["confidence"] == 0.18
    assert payload["primary_domain"] == "finance"
    assert payload["classifier_version"] == "v1.2.3"
    assert payload["classification_evidence"] == {
        "keywords": ["10-K", "balance sheet"]
    }


def test_emit_classification_failed_inserts_row(db_session, cleanup_ids):
    recorder = AuditRecorder(db_session)
    rec_id = recorder.emit_classification_failed(
        reason="primary_domain absent",
        classification_status="ok",
        primary_domain=None,
        classifier_version="v1.2.3",
        classification_metadata={"classification_status": "ok"},
        document_id=None,
    )
    db_session.commit()
    cleanup_ids.append(rec_id)

    row = _fetch(db_session, rec_id)
    assert row is not None
    assert row.signal_type == "classification_failed"
    assert row.severity == "error"
    payload = row.payload if isinstance(row.payload, dict) else json.loads(row.payload)
    assert payload["reason"] == "primary_domain absent"
    assert payload["primary_domain"] is None


def test_emit_classification_missing_inserts_row(db_session, cleanup_ids):
    recorder = AuditRecorder(db_session)
    rec_id = recorder.emit_classification_missing(document_id=None)
    db_session.commit()
    cleanup_ids.append(rec_id)

    row = _fetch(db_session, rec_id)
    assert row is not None
    assert row.signal_type == "classification_missing"
    assert row.severity == "error"


def test_payload_is_jsonb_queryable(db_session, cleanup_ids):
    """Payload must be jsonb (not text) so downstream consumers can query it."""
    recorder = AuditRecorder(db_session)
    rec_id = recorder.emit_low_confidence(
        confidence=0.05,
        primary_domain="aviation",
        classifier_version="v0",
        classification_evidence=None,
        document_id=None,
    )
    db_session.commit()
    cleanup_ids.append(rec_id)

    # JSONB → operator works only on jsonb columns; will error if column is text.
    row = db_session.execute(
        sql_text(
            "SELECT payload->>'primary_domain' AS pd "
            "FROM platform.audit_records WHERE id = :id"
        ),
        {"id": rec_id},
    ).fetchone()
    assert row.pd == "aviation"


def test_audit_failure_does_not_rollback_prior_pipeline_writes(db_session):
    """ARCHITECT FIX (HIGH #2): audit emit failure must NOT roll back
    prior uncommitted extraction work in the same session.

    Repro: insert a sentinel row into a temp table (representing prior
    pipeline work), then invoke an audit emit that is forced to fail
    (e.g. invalid signal_type that violates varchar(16) on severity, or
    a NOT NULL violation). Assert the sentinel row survives the
    savepoint rollback and is still visible in the session before any
    explicit commit.
    """
    # Set up a temp sentinel table within the session's transaction.
    db_session.execute(sql_text(
        "CREATE TEMP TABLE IF NOT EXISTS pipeline_sentinel "
        "(id serial primary key, marker text)"
    ))
    db_session.execute(sql_text(
        "INSERT INTO pipeline_sentinel (marker) VALUES ('pre-audit')"
    ))
    sentinel_count_before = db_session.execute(sql_text(
        "SELECT count(*) FROM pipeline_sentinel WHERE marker='pre-audit'"
    )).scalar()
    assert sentinel_count_before == 1

    recorder = AuditRecorder(db_session)
    # Force a failure by passing an oversize severity (varchar(16))
    # which will trigger a Postgres error inside the SAVEPOINT.
    forced_failure = False
    try:
        recorder.emit(
            signal_type="forced_failure_test",
            severity="x" * 17,  # exceeds varchar(16)
            payload={},
            document_id=None,
        )
    except Exception:
        forced_failure = True
    assert forced_failure, "audit emit should have raised on oversize severity"

    # Sentinel row from BEFORE the audit must still be visible.
    sentinel_count_after = db_session.execute(sql_text(
        "SELECT count(*) FROM pipeline_sentinel WHERE marker='pre-audit'"
    )).scalar()
    assert sentinel_count_after == 1, (
        "audit emit failure incorrectly rolled back prior pipeline writes; "
        "savepoint isolation broken"
    )

    # And subsequent inserts should still work (session is not poisoned).
    db_session.execute(sql_text(
        "INSERT INTO pipeline_sentinel (marker) VALUES ('post-audit')"
    ))
    post_count = db_session.execute(sql_text(
        "SELECT count(*) FROM pipeline_sentinel WHERE marker='post-audit'"
    )).scalar()
    assert post_count == 1
    db_session.rollback()  # clean up — temp table scoped to session anyway


def test_signal_type_index_exists(db_session):
    """Sanity — verify the migration's signal_type index is in place."""
    rows = db_session.execute(sql_text(
        "SELECT indexname FROM pg_indexes "
        "WHERE schemaname='platform' AND tablename='audit_records' "
        "ORDER BY indexname"
    )).fetchall()
    indexnames = [r.indexname for r in rows]
    assert "audit_records_pkey" in indexnames
    assert "audit_records_document_id_idx" in indexnames
    assert "audit_records_signal_type_idx" in indexnames
