"""
Document Classification Wrapper — Piece 1.

Combines the two canonical classifiers (locked decision per
docs/decisions.md ADR-002 and the Piece 1 brief: two classifiers, two
roles, must not be confused):

  - brain/classifier.py
        → primary_domain (one of the 8 canonical domain IDs from
          ontology.domains: core, it_infrastructure, healthcare, finance,
          aviation, supply_chain, manufacturing, construction)
        → classification_confidence (cosine similarity of document
          embedding against domain-description embedding)

  - src/context_foundry/extraction/document_classifier.py
        → document_type (free-text label normalized against the
          DOCUMENT_TYPES taxonomy: resume, financial_report, meeting_notes,
          policy_document, technical_spec, etc.)

Semantic contract for classification_status (sign-off 2026-05, Decision 3):

    ok           = BOTH primary_domain (canonical ontology.domains ID) AND
                   document_type are populated
    failed       = classification was attempted but produced an unusable
                   result; classification_error explains why
    unclassified = never attempted (default for pre-existing rows)

Empty-text guard (sign-off 2026-05, Decision 2):
    Inputs with fewer than 50 non-whitespace characters short-circuit to
    classification_status='failed' with classification_error=
    'insufficient_text_for_classification'. This prevents the upstream
    extraction/document_classifier.py LLM from returning a literal
    request-for-input string ("please_provide_the_document...") and
    polluting the document_type column.

Failure behavior:
    Any exception from the underlying classifiers is caught and surfaced
    as classification_status='failed' with a structured
    classification_error. The wrapper NEVER raises. Production extraction
    MUST continue with its existing behavior on failure — Piece 1 is a
    metadata flow only and must not block extraction on classification
    errors.
"""
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from brain.classifier import score_domains
from src.context_foundry.extraction.document_classifier import (
    classify_with_fallback as classify_doc_type,
)


CLASSIFIER_VERSION = "v1.0.0-2026-05"
MIN_TEXT_CHARS = 50  # Decision 2: empty-text guard threshold


@dataclass
class ClassificationResult:
    """Structured classification result returned by classify().

    Shape matches the Piece 1 brief exactly. All fields except
    secondary_domains, classifier_version, and classification_status may
    be None when classification fails.
    """
    primary_domain: Optional[str]
    secondary_domains: List[str]
    document_type: Optional[str]
    classification_confidence: Optional[float]
    classifier_version: str
    classification_evidence: Optional[str]
    classification_status: str         # "ok" | "failed" | "unclassified"
    classification_error: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _failed(reason: str) -> ClassificationResult:
    """Build a uniform 'failed' result. Per Decision 3, when domain
    classification fails we also null out document_type so the row is
    not partially populated."""
    return ClassificationResult(
        primary_domain=None,
        secondary_domains=[],
        document_type=None,
        classification_confidence=None,
        classifier_version=CLASSIFIER_VERSION,
        classification_evidence=None,
        classification_status="failed",
        classification_error=reason,
    )


def classify(text: str, filename: Optional[str] = None) -> ClassificationResult:
    """Classify a document along two independent axes (domain, document_type).

    Args:
        text: Full document text content.
        filename: Original filename, if available. Used by the
            document_type classifier's filename-hint short-circuit before
            the LLM call.

    Returns:
        ClassificationResult. classification_status is:
            'ok'     — primary_domain and document_type both populated
            'failed' — classification attempted but unusable
        Per Decision 3, partial success (e.g. document_type ok but
        domain unknown) is reported as 'failed', not 'ok'. The
        'unclassified' status is never returned by this function — it is
        reserved for the column default on pre-existing rows.
    """
    # Decision 2: empty-text guard. Must run BEFORE either classifier so
    # the LLM never sees an empty prompt that would cause it to ask for
    # input as a literal string.
    if text is None or len(text.strip()) < MIN_TEXT_CHARS:
        return _failed("insufficient_text_for_classification")

    # Domain axis — embedding-based, 8 canonical IDs from ontology.domains.
    try:
        domain, confidence, scores = score_domains(text)
    except Exception as e:
        return _failed(f"domain_classifier_error: {type(e).__name__}: {e}")

    # Decision 3: if domain is unusable, escalate the whole record to
    # 'failed' even if document_type would have succeeded. Domain is the
    # load-bearing output for Piece 1.
    if not scores or not domain or domain == "unknown":
        return _failed(
            "domain_classifier_returned_unknown" if not scores
            else f"domain_classifier_returned_unusable: {domain!r}"
        )

    # document_type axis — filename hint first, then LLM fallback.
    try:
        doc_type = classify_doc_type(text, filename=filename)
    except Exception as e:
        return _failed(f"document_type_classifier_error: {type(e).__name__}: {e}")

    if not doc_type or doc_type == "unknown":
        return _failed("document_type_classifier_returned_unknown")

    # Build auditable evidence: full per-domain score breakdown + winner +
    # document_type + classifier version. Sorted descending.
    sorted_scores = sorted(scores.items(), key=lambda kv: -kv[1])
    scores_str = ", ".join(f"{d}:{s:.3f}" for d, s in sorted_scores)
    evidence = (
        f"domain_scores=[{scores_str}] "
        f"primary={domain}@{confidence:.3f} "
        f"document_type={doc_type} "
        f"version={CLASSIFIER_VERSION}"
    )

    return ClassificationResult(
        primary_domain=domain,
        secondary_domains=[],
        document_type=doc_type,
        classification_confidence=float(confidence),
        classifier_version=CLASSIFIER_VERSION,
        classification_evidence=evidence,
        classification_status="ok",
        classification_error=None,
    )
