from .models import Fact, FactEvidence, ConflictGroup
from .detector import detect_conflicts
from .resolver import resolve_conflicts, resolve_conflict, score_fact
from .registry import (
    RELATION_CARDINALITY,
    DOCUMENT_AUTHORITY_TIERS,
    DEFAULT_SOURCE_TRUST,
    source_trust_for,
)

__all__ = [
    "Fact",
    "FactEvidence",
    "ConflictGroup",
    "detect_conflicts",
    "resolve_conflicts",
    "resolve_conflict",
    "score_fact",
    "RELATION_CARDINALITY",
    "DOCUMENT_AUTHORITY_TIERS",
    "DEFAULT_SOURCE_TRUST",
    "source_trust_for",
]
