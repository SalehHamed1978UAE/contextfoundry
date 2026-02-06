from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, List


@dataclass
class FactEvidence:
    source_document_id: Optional[str] = None
    source_type: Optional[str] = None
    source_text: Optional[str] = None
    source_excerpt: Optional[str] = None
    source_date: Optional[str] = None
    reporting_period: Optional[str] = None


@dataclass
class Fact:
    subject: str
    predicate: str
    obj: str
    value: Optional[float] = None
    unit: Optional[str] = None
    canonical_metric: Optional[str] = None
    period: Optional[str] = None
    confidence: float = 0.5
    lifecycle_weight: float = 0.5
    recency_weight: float = 0.5
    evidence_count: int = 1
    evidence: FactEvidence = field(default_factory=FactEvidence)
    qualifiers: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConflictGroup:
    key: str
    facts: List[Fact]
    variance_detected: bool = False
