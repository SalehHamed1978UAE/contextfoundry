from __future__ import annotations

from typing import Dict, List

METRIC_HIERARCHY: Dict[str, Dict[str, object]] = {
    "REVENUE": {
        "children": ["REVENUE.COMMERCIAL", "REVENUE.DEFENSE", "REVENUE.SERVICES"],
        "aggregation": "SUM",
        "description": "Total revenue is the sum of segment revenues",
    },
    "CAPEX": {
        "children": ["CAPEX.FACILITY", "CAPEX.EQUIPMENT", "CAPEX.IT"],
        "aggregation": "SUM",
        "description": "Total capex is the sum of category-level capex",
    },
    "HEADCOUNT": {
        "children": ["HEADCOUNT.ENGINEERING", "HEADCOUNT.SALES", "HEADCOUNT.OPERATIONS"],
        "aggregation": "SUM",
        "description": "Total headcount is the sum of departmental headcounts",
    },
}

METRIC_RELATIONSHIPS = {
    ("CONTRACT_VALUE", "REVENUE"): {
        "type": "RELATED_NOT_EQUIVALENT",
        "note": "Contract value is total deal size; revenue is periodic recognition. Never treat as conflict.",
    },
    ("RELATIONSHIP_VALUE", "REVENUE"): {
        "type": "RELATED_NOT_EQUIVALENT",
        "note": "Relationship value is valuation; revenue is periodic recognition. Never treat as conflict.",
    },
}


def is_child_metric(parent: str, child: str) -> bool:
    children: List[str] = METRIC_HIERARCHY.get(parent, {}).get("children", [])
    return child in children
