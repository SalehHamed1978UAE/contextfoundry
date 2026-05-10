"""
AuditRecorder — Piece 2 Stage 1 governance signal write path.

Persists classification-related governance signals from the ontology-centric
extraction pipeline to platform.audit_records. Stage 1 is WRITE-ONLY:
no consumer, UI, review queue, routing, or notifications. See
docs/inbox/piece_2_stage1_implementation_2026-05-10.md and
docs/inbox/piece_2_stage1_step_b_signoff_2026-05-10.md.
"""
import json
import uuid
from typing import Any, Dict, Optional

from sqlalchemy import text as sql_text
from sqlalchemy.orm import Session

from ..utils.logger import logger


class AuditRecorder:
    """Write-only persistence for governance audit signals.

    All inserts go to platform.audit_records. The table is created by the
    Piece 2 Stage 1 migration (committed 2026-05-10). FK to
    platform.documents(id); document_id is nullable so non-document-bound
    signals (e.g. classifier-version drift) can be recorded in future stages.
    """

    SIGNAL_LOW_CONFIDENCE = "low_confidence"
    SIGNAL_NARROW_MARGIN = "narrow_margin"
    SIGNAL_CLASSIFICATION_FAILED = "classification_failed"
    SIGNAL_CLASSIFICATION_MISSING = "classification_missing"

    SEVERITY_INFO = "info"
    SEVERITY_WARN = "warn"
    SEVERITY_ERROR = "error"

    def __init__(self, session: Session):
        self.session = session

    def emit(
        self,
        signal_type: str,
        severity: str,
        payload: Dict[str, Any],
        document_id: Optional[str] = None,
    ) -> str:
        """Insert one audit_records row and return its id.

        Wraps the INSERT in a SAVEPOINT (`session.begin_nested()`) so that
        an audit failure rolls back ONLY the audit insert, preserving any
        prior uncommitted pipeline state in the same session (e.g. chunks
        inserted by `_store_document_chunks`, extraction-job rows). This
        is required by the brief's rule that audit failures must not break
        extraction. The pipeline catches the re-raised exception and
        continues.

        Args:
            signal_type: Short signal name (varchar(64)).
            severity: 'info' | 'warn' | 'error' (varchar(16)).
            payload: JSON-serializable dict; stored as jsonb.
            document_id: Optional UUID string of related platform.documents row.
        """
        record_id = uuid.uuid4()
        savepoint = self.session.begin_nested()
        try:
            self.session.execute(
                sql_text(
                    "INSERT INTO platform.audit_records "
                    "(id, document_id, signal_type, severity, payload, created_at) "
                    "VALUES (:id, :document_id, :signal_type, :severity, "
                    "CAST(:payload AS jsonb), now())"
                ),
                {
                    "id": str(record_id),
                    "document_id": str(document_id) if document_id else None,
                    "signal_type": signal_type,
                    "severity": severity,
                    "payload": json.dumps(payload, default=str),
                },
            )
            savepoint.commit()
            logger.info(
                f"[AuditRecorder] emitted signal_type={signal_type} "
                f"severity={severity} document_id={document_id} id={record_id}"
            )
            return str(record_id)
        except Exception as e:
            logger.error(
                f"[AuditRecorder] failed to emit signal_type={signal_type}: {e}"
            )
            try:
                savepoint.rollback()
            except Exception:
                # Savepoint may already be released by the failure;
                # in that case the failed INSERT had no effect anyway.
                pass
            raise

    def emit_low_confidence(
        self,
        confidence: float,
        primary_domain: Optional[str],
        classifier_version: Optional[str],
        classification_evidence: Optional[Any],
        document_id: Optional[str] = None,
    ) -> str:
        """Emit a low_confidence signal (classification_confidence < 0.30).

        Per brief lines 174-187. Does NOT change prompt scope.
        """
        payload = {
            "confidence": confidence,
            "primary_domain": primary_domain,
            "classifier_version": classifier_version,
            "classification_evidence": classification_evidence,
        }
        return self.emit(
            self.SIGNAL_LOW_CONFIDENCE,
            self.SEVERITY_WARN,
            payload,
            document_id=document_id,
        )

    def emit_narrow_margin(
        self,
        top_two_margin: float,
        top_domain: Optional[str],
        runner_up_domain: Optional[str],
        classifier_version: Optional[str],
        classification_evidence: Optional[Any],
        document_id: Optional[str] = None,
    ) -> str:
        """Emit a narrow_margin signal (top_two_margin < 0.05).

        Per brief lines 188-202. NOT wired in Stage 1 because top-two margin
        cannot be parsed reliably from current classification_evidence shape
        (brief line 113 limitation). Reserved for Stage 1.5 / Stage 2.
        """
        payload = {
            "top_two_margin": top_two_margin,
            "top_domain": top_domain,
            "runner_up_domain": runner_up_domain,
            "classifier_version": classifier_version,
            "classification_evidence": classification_evidence,
        }
        return self.emit(
            self.SIGNAL_NARROW_MARGIN,
            self.SEVERITY_WARN,
            payload,
            document_id=document_id,
        )

    def emit_classification_failed(
        self,
        reason: str,
        classification_status: Optional[str],
        primary_domain: Optional[str],
        classifier_version: Optional[str],
        classification_metadata: Optional[Dict] = None,
        document_id: Optional[str] = None,
    ) -> str:
        """Emit a classification_failed signal (status != 'ok' or primary_domain absent).

        Used when OntologyCentricPipeline runs with enforce_scoped_prompts=True
        and the classification metadata is invalid; pipeline returns a failed
        result rather than silently falling back to full-union prompts.
        """
        payload = {
            "reason": reason,
            "classification_status": classification_status,
            "primary_domain": primary_domain,
            "classifier_version": classifier_version,
            "classification_metadata": classification_metadata,
        }
        return self.emit(
            self.SIGNAL_CLASSIFICATION_FAILED,
            self.SEVERITY_ERROR,
            payload,
            document_id=document_id,
        )

    def emit_classification_missing(
        self,
        document_id: Optional[str] = None,
    ) -> str:
        """Emit a classification_missing signal (no classification_metadata provided).

        Used when OntologyCentricPipeline runs with enforce_scoped_prompts=True
        and no classification_metadata is supplied at all.
        """
        payload = {
            "reason": (
                "classification_metadata not provided to "
                "OntologyCentricPipeline.extract() while "
                "enforce_scoped_prompts=True"
            ),
        }
        return self.emit(
            self.SIGNAL_CLASSIFICATION_MISSING,
            self.SEVERITY_ERROR,
            payload,
            document_id=document_id,
        )
