from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


RELATION_CARDINALITY: Dict[str, str] = {
    "PRESIDENT_OF": "1-to-1",
    "CEO_OF": "1-to-1",
    "CFO_OF": "1-to-1",
    "CTO_OF": "1-to-1",
    "APPOINTED_ON": "1-to-1",
    "HAS_ENERGY_DENSITY": "1-to-1",
    "HAS_ASSET_COUNT": "1-to-1",
    "HAS_MEMBER": "N-to-N",
    "HAS_CUSTOMER": "1-to-N",
}

CARDINALITY_EXCEPTIONS = {
    "CEO_OF": ["co-", "interim", "acting"],
    "PRESIDENT_OF": ["co-", "interim", "acting"],
}

DOCUMENT_AUTHORITY_TIERS: Dict[str, float] = {
    # Tier 1: Structural / Official
    "organizational_chart": 0.95,
    "annual_report": 0.95,
    "financial_statement": 0.95,
    "strategic_plan": 0.90,

    # Tier 2: Procedural / Operational
    "project_charter": 0.70,
    "meeting_notes": 0.60,

    # Tier 3: Communication
    "email": 0.40,
    "slack_message": 0.40,

    # Tier 4: Personal / Draft
    "draft": 0.15,
    "personal_notes": 0.15,
}

DEFAULT_SOURCE_TRUST = 0.50


@dataclass(frozen=True)
class MaterialityThresholds:
    financial_pct: float = 0.02
    percentage_points: float = 0.005


THRESHOLDS = MaterialityThresholds()


def source_trust_for(document_type: Optional[str]) -> float:
    if not document_type:
        return DEFAULT_SOURCE_TRUST
    return DOCUMENT_AUTHORITY_TIERS.get(document_type.lower(), DEFAULT_SOURCE_TRUST)


def is_exceptional_cardinality(rel_type: str, context_text: Optional[str]) -> bool:
    if not context_text:
        return False
    for term in CARDINALITY_EXCEPTIONS.get(rel_type, []):
        if term in context_text.lower():
            return True
    return False


def is_material_difference(a: float, b: float, kind: str) -> Tuple[bool, bool]:
    """Return (is_material, variance_detected) for a metric difference.

    kind: financial | percentage | count
    """
    if a == b:
        return False, False

    if kind == "financial":
        diff = abs(a - b)
        base = max(abs(a), abs(b))
        pct = diff / base if base else 0.0
        return pct > THRESHOLDS.financial_pct, True

    if kind == "percentage":
        diff = abs(a - b)
        return diff > THRESHOLDS.percentage_points, True

    # counts: any difference is material
    return True, True
