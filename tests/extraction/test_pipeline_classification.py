"""
Piece 2 Stage 1 — OntologyCentricPipeline classification-decision tests.

Verifies that the pipeline's _classify_for_scoped helper makes the right
branch decisions and that scoped vs legacy vs skip_failed paths work as
designed. These tests are unit-level: they call helper methods directly
without invoking the full LLM extraction loop.

Brief acceptance:
  - Low-confidence metadata creates audit_records row and does not change scope.
  - Missing/failed classification does not fall back to full union.
  - MultiModelExtractor.EXTRACTION_SYSTEM_PROMPT SHA unchanged (covered in
    test_multi_extractor_prompt_sha.py).
"""
import os
import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text as sql_text
from sqlalchemy.orm import sessionmaker

from src.context_foundry.extraction.ontology_centric_pipeline import (
    OntologyCentricPipeline,
)


@pytest.fixture(scope="module")
def db_session():
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL not set; pipeline tests require live DB")
    engine = create_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def pipeline_strict(db_session):
    """Pipeline with enforce_scoped_prompts=True (Stage 1 enforcement on)."""
    return OntologyCentricPipeline(
        session=db_session,
        tenant_id="00000000-0000-0000-0000-000000000000",
        enable_canonicalization=False,
        auto_stage=False,
        enable_job_tracking=False,
        enforce_scoped_prompts=True,
    )


@pytest.fixture
def pipeline_legacy(db_session):
    """Pipeline with enforce_scoped_prompts=False (default, backward compat)."""
    return OntologyCentricPipeline(
        session=db_session,
        tenant_id="00000000-0000-0000-0000-000000000000",
        enable_canonicalization=False,
        auto_stage=False,
        enable_job_tracking=False,
        enforce_scoped_prompts=False,
    )


@pytest.fixture
def cleanup_audit_rows(db_session):
    """Track audit row ids inserted by the pipeline + clean up."""
    seen_before = set(
        r[0] for r in db_session.execute(
            sql_text("SELECT id::text FROM platform.audit_records")
        )
    )
    yield seen_before
    after = set(
        r[0] for r in db_session.execute(
            sql_text("SELECT id::text FROM platform.audit_records")
        )
    )
    new_ids = after - seen_before
    if new_ids:
        db_session.execute(
            sql_text(
                "DELETE FROM platform.audit_records "
                "WHERE id::text = ANY(:ids)"
            ),
            {"ids": list(new_ids)},
        )
        db_session.commit()


# =============================================================================
# _classify_for_scoped decision logic
# =============================================================================

def test_classify_returns_scoped_when_status_ok_and_primary_domain(pipeline_strict):
    decision = pipeline_strict._classify_for_scoped({
        "classification_status": "ok",
        "primary_domain": "finance",
        "classification_confidence": 0.92,
    })
    assert decision == "scoped"


def test_classify_returns_skip_failed_when_status_failed_and_strict(pipeline_strict):
    decision = pipeline_strict._classify_for_scoped({
        "classification_status": "failed",
        "primary_domain": None,
    })
    assert decision == "skip_failed"


def test_classify_returns_skip_failed_when_metadata_none_and_strict(pipeline_strict):
    decision = pipeline_strict._classify_for_scoped(None)
    assert decision == "skip_failed"


def test_classify_returns_skip_failed_when_primary_domain_missing_and_strict(pipeline_strict):
    decision = pipeline_strict._classify_for_scoped({
        "classification_status": "ok",
        "primary_domain": None,
    })
    assert decision == "skip_failed"


def test_classify_returns_skip_failed_when_unclassified_and_strict(pipeline_strict):
    decision = pipeline_strict._classify_for_scoped({
        "classification_status": "unclassified",
        "primary_domain": None,
    })
    assert decision == "skip_failed"


def test_classify_returns_legacy_when_metadata_none_and_not_strict(pipeline_legacy):
    """Backward compat: legacy callers without classification → legacy path."""
    decision = pipeline_legacy._classify_for_scoped(None)
    assert decision == "legacy"


def test_classify_returns_legacy_when_status_failed_and_not_strict(pipeline_legacy):
    decision = pipeline_legacy._classify_for_scoped({
        "classification_status": "failed",
        "primary_domain": None,
    })
    assert decision == "legacy"


def test_classify_returns_legacy_in_non_strict_mode_even_when_metadata_valid(pipeline_legacy):
    """ARCHITECT FIX (HIGH #1): scoped path is gated behind
    enforce_scoped_prompts=True, NOT just by metadata presence.

    This preserves backward compat for scripts/run_vault_extraction.py
    which already passes classification_metadata at line 781. Without
    this gate, that caller would silently switch to scoped mode in
    Stage 1.

    Stage 2 will flip enforce_scoped_prompts default to True after
    callers are audited and migrated.
    """
    decision = pipeline_legacy._classify_for_scoped({
        "classification_status": "ok",
        "primary_domain": "healthcare",
    })
    assert decision == "legacy", (
        "non-strict mode must return 'legacy' even when metadata is valid; "
        "scoped path requires enforce_scoped_prompts=True"
    )


def test_classify_returns_scoped_only_when_strict_and_metadata_valid(pipeline_strict):
    """Sanity — strict mode with valid metadata → scoped (the only path that returns 'scoped')."""
    decision = pipeline_strict._classify_for_scoped({
        "classification_status": "ok",
        "primary_domain": "healthcare",
    })
    assert decision == "scoped"


# =============================================================================
# Low-confidence audit emission (scope MUST stay scoped, not widen)
# =============================================================================

def test_low_confidence_audit_is_emitted(pipeline_strict, db_session, cleanup_audit_rows):
    metadata = {
        "classification_status": "ok",
        "primary_domain": "finance",
        "classification_confidence": 0.18,  # below 0.30 threshold
        "classifier_version": "v1.0",
        "classification_evidence": {"top_keywords": ["10-K"]},
    }
    pipeline_strict._maybe_emit_low_confidence_audit(metadata, document_id=None)
    db_session.commit()

    row = db_session.execute(sql_text(
        "SELECT signal_type, severity, payload "
        "FROM platform.audit_records "
        "WHERE signal_type='low_confidence' "
        "ORDER BY created_at DESC LIMIT 1"
    )).fetchone()
    assert row is not None
    assert row.signal_type == "low_confidence"
    assert row.severity == "warn"
    payload = row.payload if isinstance(row.payload, dict) else json.loads(row.payload)
    assert payload["confidence"] == 0.18
    assert payload["primary_domain"] == "finance"


def test_high_confidence_does_not_emit_audit(pipeline_strict, db_session, cleanup_audit_rows):
    metadata = {
        "classification_status": "ok",
        "primary_domain": "finance",
        "classification_confidence": 0.92,
        "classifier_version": "v1.0",
        "classification_evidence": None,
    }
    before = db_session.execute(sql_text(
        "SELECT count(*) FROM platform.audit_records "
        "WHERE signal_type='low_confidence'"
    )).scalar()
    pipeline_strict._maybe_emit_low_confidence_audit(metadata, document_id=None)
    db_session.commit()
    after = db_session.execute(sql_text(
        "SELECT count(*) FROM platform.audit_records "
        "WHERE signal_type='low_confidence'"
    )).scalar()
    assert after == before, "high-confidence classification must NOT emit low_confidence audit"


def test_low_confidence_does_not_change_scope_decision(pipeline_strict):
    """Brief lines 205, 287: low confidence must NOT change prompt scope."""
    metadata_low = {
        "classification_status": "ok",
        "primary_domain": "finance",
        "classification_confidence": 0.05,
    }
    metadata_high = {
        "classification_status": "ok",
        "primary_domain": "finance",
        "classification_confidence": 0.99,
    }
    assert pipeline_strict._classify_for_scoped(metadata_low) == "scoped"
    assert pipeline_strict._classify_for_scoped(metadata_high) == "scoped"


# =============================================================================
# Scoped extraction lists are non-empty and dedupe core
# =============================================================================

def test_load_scoped_extraction_lists_finance(pipeline_strict):
    entity_type_names, relation_type_defs = (
        pipeline_strict._load_scoped_extraction_lists("finance")
    )
    assert len(entity_type_names) > 0
    assert len(relation_type_defs) > 0
    rel_names = {d["name"] for d in relation_type_defs}
    # Core (HOLDS_POSITION via Piece 0.6) + finance (HAS_COMPENSATION) both present.
    assert "HOLDS_POSITION" in rel_names
    assert "HAS_COMPENSATION" in rel_names


def test_load_scoped_extraction_lists_rejects_none(pipeline_strict):
    with pytest.raises(ValueError):
        pipeline_strict._load_scoped_extraction_lists(None)
