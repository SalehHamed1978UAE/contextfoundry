"""
Document Classification Wrapper — Piece 1.

Combines the two canonical classifiers (locked decision per docs/decisions.md
ADR-002 and the Piece 1 brief: two classifiers, two roles, must not be
confused):

  - brain/classifier.py
        → primary_domain (one of the 8 canonical domain IDs from
          ontology.domains: core, it_infrastructure, healthcare, finance,
          aviation, supply_chain, manufacturing, construction)
        → classification_confidence (cosine similarity of document
          embedding against domain-description embedding)

  - src/context_foundry/extraction/document_classifier.py
        → document_type (free-text label normalized against the
          DOCUMENT_TYPES taxonomy: resume, financial_report, meeting_notes,
          policy_document, technical_spec, etc.; falls through to a
          descriptive lowercase_underscored label when none of the canonical
          types match)

These two axes are independent and must remain so. domain controls ontology
scope (Piece 2); document_type controls extraction hints and source
authority (later Pieces).

Failure behavior:
    Either underlying classifier may raise (network error, API quota,
    embedding failure, etc.). The wrapper catches all exceptions and
    returns a structured result with classification_status='failed',
    primary_domain=None, document_type=None, classification_error set to
    the exception class+message. The wrapper NEVER raises. Production
    extraction MUST continue using its existing behavior when classification
    fails — see scripts/run_vault_extraction.py for the call site (Piece 1
    section F).

This Piece (Piece 1) wires classification metadata into the production
extraction path. It does NOT change extraction prompt content. Prompt
generation that uses domain scope is Piece 2.
"""
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from brain.classifier import score_domains
from src.context_foundry.extraction.document_classifier import (
    classify_with_fallback as classify_doc_type,
)


CLASSIFIER_VERSION = "v1.0.0-2026-05"


@dataclass
class ClassificationResult:
    """Structured classification result returned by classify().

    Shape matches the Piece 1 brief exactly. All fields except
    secondary_domains, classifier_version, and classification_status may be
    None when classification fails or partially succeeds.
    """
    primary_domain: Optional[str]
    secondary_domains: List[str]
    document_type: Optional[str]
    classification_confidence: Optional[float]
    classifier_version: str
    classification_evidence: Optional[str]
    classification_status: str         # "ok" | "failed"
    classification_error: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def classify(text: str, filename: Optional[str] = None) -> ClassificationResult:
    """Classify a document along two independent axes (domain, document_type).

    Args:
        text: Full document text content.
        filename: Original filename, if available. Used by the document_type
            classifier's filename-hint short-circuit before the LLM call.

    Returns:
        ClassificationResult with classification_status='ok' on success or
        'failed' on any underlying classifier exception. Per Piece 1 design,
        secondary_domains is always [] in this iteration (multi-domain
        detection is future work).

    Failure behavior:
        Catches every exception from the underlying classifiers. On failure,
        returns a result with classification_status='failed',
        primary_domain=None, document_type=None, classification_error set,
        and classification_confidence=None. The caller (production extraction
        runner) MUST continue with its existing extraction behavior in the
        failure case — Piece 1 is a metadata flow only and must not block
        extraction on classification errors.
    """
    try:
        # Domain axis — embedding-based, 8 canonical IDs from ontology.domains.
        # score_domains is an additive helper; it does not change
        # classify_document()'s contract.
        domain, confidence, scores = score_domains(text)

        # document_type axis — filename hint first, then LLM fallback.
        # classify_with_fallback already swallows LLM errors and returns
        # 'unknown'; we further normalize 'unknown' to None below so the
        # downstream column reflects a true absence rather than a string.
        doc_type = classify_doc_type(text, filename=filename)

        # classification_evidence is built from available scoring data.
        # Per-domain scores give an auditable explanation of why this
        # primary_domain won; classifier_version makes the result
        # reproducible if descriptions/embeddings are later regenerated.
        if scores:
            sorted_scores = sorted(scores.items(), key=lambda kv: -kv[1])
            scores_str = ", ".join(f"{d}:{s:.3f}" for d, s in sorted_scores)
        else:
            scores_str = "<embedding API failed>"
        evidence = (
            f"domain_scores=[{scores_str}] "
            f"primary={domain}@{confidence:.3f} "
            f"document_type={doc_type} "
            f"version={CLASSIFIER_VERSION}"
        )

        # 'unknown' is the in-band sentinel both underlying classifiers use
        # when they cannot produce a real answer. We surface it as None at
        # the wrapper boundary so the documents column reflects absence
        # rather than a magic string.
        normalized_domain = domain if domain and domain != "unknown" else None
        normalized_doc_type = doc_type if doc_type and doc_type != "unknown" else None

        # If the embedding API failed entirely, score_domains returns
        # ('unknown', 0.0, {}) — that is a partial-failure state. We still
        # report 'ok' if document_type succeeded, but record the absence
        # honestly via primary_domain=None and confidence=None.
        confidence_value = float(confidence) if scores else None

        return ClassificationResult(
            primary_domain=normalized_domain,
            secondary_domains=[],
            document_type=normalized_doc_type,
            classification_confidence=confidence_value,
            classifier_version=CLASSIFIER_VERSION,
            classification_evidence=evidence,
            classification_status="ok",
            classification_error=None,
        )

    except Exception as e:
        return ClassificationResult(
            primary_domain=None,
            secondary_domains=[],
            document_type=None,
            classification_confidence=None,
            classifier_version=CLASSIFIER_VERSION,
            classification_evidence=None,
            classification_status="failed",
            classification_error=f"{type(e).__name__}: {e}",
        )
