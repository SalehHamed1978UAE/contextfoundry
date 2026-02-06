from __future__ import annotations

from typing import Dict, Optional

METRIC_CANONICAL_MAP: Dict[str, str] = {
    # Revenue family
    "revenue": "REVENUE",
    "net revenue": "REVENUE",
    "net sales": "REVENUE",
    "sales": "REVENUE",
    "top-line": "REVENUE",
    "total revenue": "REVENUE",
    "annual revenue": "REVENUE",

    # Revenue — contract/relationship
    "contract value": "CONTRACT_VALUE",
    "relationship value": "RELATIONSHIP_VALUE",
    "total contract value": "CONTRACT_VALUE",

    # Revenue subtypes
    "commercial revenue": "REVENUE.COMMERCIAL",
    "defense revenue": "REVENUE.DEFENSE",
    "services revenue": "REVENUE.SERVICES",

    # Capex family
    "capex": "CAPEX",
    "capital expenditure": "CAPEX",
    "capital spending": "CAPEX",

    # Other
    "backlog": "BACKLOG",
    "unfilled orders": "BACKLOG",
    "order backlog": "BACKLOG",
    "headcount": "HEADCOUNT",
    "employee count": "HEADCOUNT",
    "fte": "HEADCOUNT",
    "full-time equivalents": "HEADCOUNT",
}


def canonicalize_metric_name(raw_name: str) -> Optional[str]:
    if not raw_name:
        return None
    key = raw_name.strip().lower()
    return METRIC_CANONICAL_MAP.get(key)
