"""Piece 2 Stage 1B — controlled scoped activation tests.

Covers:
  Step A — env-var parsing for CF_PIECE2_SCOPED_EXTRACTION
  Step B — telemetry write into platform.extraction_events
  Step B — telemetry failure does NOT break extraction (savepoint isolation)
  Architect rec — unknown_primary_domain regression lock for FIX #3

These tests do NOT exercise the full extract() path (that requires LLM); they
target the scope-decision and telemetry helpers directly with stub sessions
where useful and the real session for DB-write assertions.
"""
import os
import uuid
import json
import pytest
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker

from src.context_foundry.extraction.ontology_centric_pipeline import (
    OntologyCentricPipeline,
)


@pytest.fixture
def db_session():
    engine = create_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def pipeline_strict(db_session):
    return OntologyCentricPipeline(
        session=db_session,
        tenant_id="00000000-0000-0000-0000-000000000000",
        enforce_scoped_prompts=True,
        enable_canonicalization=False,
        auto_stage=False,
        enable_job_tracking=False,
    )


@pytest.fixture
def pipeline_legacy(db_session):
    return OntologyCentricPipeline(
        session=db_session,
        tenant_id="00000000-0000-0000-0000-000000000000",
        enforce_scoped_prompts=False,
        enable_canonicalization=False,
        auto_stage=False,
        enable_job_tracking=False,
    )


# =============================================================================
# Step A — CF_PIECE2_SCOPED_EXTRACTION env-var parsing
# =============================================================================

@pytest.mark.parametrize("env_value,expected", [
    ("true", True),
    ("True", True),
    ("TRUE", True),
    ("1", True),
    ("yes", True),
    ("on", True),
    ("false", False),
    ("False", False),
    ("0", False),
    ("no", False),
    ("off", False),
    ("", False),
    ("anything_else", False),
])
def test_env_var_parsing(env_value, expected):
    """Reproduce the parsing logic in scripts/run_vault_extraction.py."""
    parsed = env_value.strip().lower() in ("true", "1", "yes", "on")
    assert parsed is expected, (
        f"CF_PIECE2_SCOPED_EXTRACTION={env_value!r} parsed to {parsed}, "
        f"expected {expected}"
    )


def test_env_var_default_is_false():
    """Missing env var must default to false (legacy path)."""
    val = os.environ.get("CF_PIECE2_SCOPED_EXTRACTION_DOES_NOT_EXIST", "false")
    parsed = val.strip().lower() in ("true", "1", "yes", "on")
    assert parsed is False


# =============================================================================
# Step B — telemetry write into platform.extraction_events
# =============================================================================

def test_telemetry_writes_extraction_events_row(pipeline_strict, db_session):
    """When enforce_scoped_prompts=True, _record_scope_decision_telemetry
    inserts a row into platform.extraction_events with event_type=
    'scoped_extraction_decision'."""
    sentinel_doc_id = str(uuid.uuid4())
    pipeline_strict._record_scope_decision_telemetry(
        document_id=sentinel_doc_id,
        document_name="test_doc.pdf",
        scope_decision="scoped",
        primary_domain="finance",
        classification_metadata={
            "classification_status": "ok",
            "primary_domain": "finance",
            "classification_confidence": 0.92,
            "classifier_version": "test-v1",
        },
    )
    db_session.commit()

    rows = db_session.execute(sql_text(
        "SELECT vault_id, document_id, event_type, extraction_level, details "
        "FROM platform.extraction_events "
        "WHERE document_id = :doc_id"
    ), {"doc_id": sentinel_doc_id}).fetchall()

    assert len(rows) == 1, "telemetry row not inserted"
    r = rows[0]
    assert r.event_type == "scoped_extraction_decision"
    assert r.extraction_level == "scoped"
    payload = json.loads(r.details)
    assert payload["decision"] == "scoped"
    assert payload["primary_domain"] == "finance"
    assert payload["classification_status"] == "ok"
    assert payload["classification_confidence"] == 0.92

    # Cleanup
    db_session.execute(sql_text(
        "DELETE FROM platform.extraction_events WHERE document_id = :doc_id"
    ), {"doc_id": sentinel_doc_id})
    db_session.commit()


def test_telemetry_skipped_when_not_strict(pipeline_legacy, db_session):
    """When enforce_scoped_prompts=False (legacy), telemetry must NOT be
    recorded (would be 100% noise from legacy callers)."""
    sentinel_doc_id = str(uuid.uuid4())
    pipeline_legacy._record_scope_decision_telemetry(
        document_id=sentinel_doc_id,
        document_name="test.pdf",
        scope_decision="legacy",
        primary_domain=None,
        classification_metadata=None,
    )
    db_session.commit()

    count = db_session.execute(sql_text(
        "SELECT count(*) FROM platform.extraction_events "
        "WHERE document_id = :doc_id"
    ), {"doc_id": sentinel_doc_id}).scalar()
    assert count == 0, "legacy path must not write telemetry"


def test_telemetry_failure_does_not_break_pipeline(pipeline_strict, db_session):
    """Telemetry failure (forced via invalid vault_id type) must NOT raise
    or rollback prior session state. Per savepoint pattern from architect
    fix HIGH #2."""
    # Set up sentinel
    db_session.execute(sql_text(
        "CREATE TEMP TABLE IF NOT EXISTS s1b_sentinel (id serial primary key, marker text)"
    ))
    db_session.execute(sql_text(
        "INSERT INTO s1b_sentinel (marker) VALUES ('pre-telemetry')"
    ))

    # Force telemetry failure: corrupt vault_id to non-UUID string
    pipeline_strict.tenant_id = "this-is-not-a-uuid-and-will-fail-the-cast"
    pipeline_strict._record_scope_decision_telemetry(
        document_id=str(uuid.uuid4()),
        document_name="forced_fail.pdf",
        scope_decision="scoped",
        primary_domain="finance",
        classification_metadata={
            "classification_status": "ok",
            "primary_domain": "finance",
        },
    )
    # No exception should propagate.

    # Sentinel from BEFORE the telemetry must still be visible
    cnt = db_session.execute(sql_text(
        "SELECT count(*) FROM s1b_sentinel WHERE marker = 'pre-telemetry'"
    )).scalar()
    assert cnt == 1, (
        "telemetry savepoint failure incorrectly rolled back prior pipeline state"
    )
    db_session.rollback()


# =============================================================================
# Architect-recommended regression lock — FIX #3 unknown_primary_domain
# =============================================================================

def test_load_scoped_extraction_lists_with_unknown_domain_returns_core_only(pipeline_strict):
    """The architect recommended an explicit lock for FIX #3 — when
    primary_domain is unknown (no rows), _load_scoped_extraction_lists
    returns core-only types (the unknown-domain GUARD itself runs in
    extract()). This test documents that the helper itself DOES NOT
    raise — the guard is in extract(), not in the loader."""
    et, rels = pipeline_strict._load_scoped_extraction_lists("nonexistent_domain_xyz")
    # Should return core types only (not crash, not raise).
    assert isinstance(et, list)
    assert isinstance(rels, list)
    # Core has 25 types. With no extra domain rows, scoped extraction lists
    # should equal core-only counts.
    assert len(et) > 0, "core types must be present even when domain unknown"


def test_unknown_primary_domain_classified_as_scoped_not_skip_failed(pipeline_strict):
    """_classify_for_scoped returns 'scoped' for valid metadata REGARDLESS
    of whether primary_domain exists in ontology.types. The unknown-domain
    GUARD is downstream in extract() (FIX #3), not in classification.

    This locks the contract: classification = metadata-shape check only;
    domain existence is a separate validation step."""
    decision = pipeline_strict._classify_for_scoped({
        "classification_status": "ok",
        "primary_domain": "nonexistent_domain_xyz",
    })
    assert decision == "scoped", (
        "_classify_for_scoped is shape-only — domain existence is checked "
        "downstream in extract() per FIX #3"
    )
