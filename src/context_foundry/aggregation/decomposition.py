from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class DecompositionResult:
    is_aggregation: bool
    top_n: Optional[int]
    metric_hint: Optional[str]
    entity_terms: List[str]


def decompose_aggregation_query(query: str) -> DecompositionResult:
    q = query.lower()
    top_n = None
    m = re.search(r"top\s+(\d+)", q)
    if m:
        top_n = int(m.group(1))

    metric_hint = None
    for key in ["revenue", "value", "backlog", "capex", "budget", "headcount", "customer"]:
        if key in q:
            metric_hint = key
            break

    entity_terms = []
    # very light heuristic: phrases after 'for'
    for_match = re.search(r"for\s+(.+)$", q)
    if for_match:
        entity_terms = [t.strip() for t in re.split(r",|and", for_match.group(1)) if t.strip()]

    is_agg = bool(top_n) or any(word in q for word in ["total", "sum", "aggregate"])

    return DecompositionResult(
        is_aggregation=is_agg,
        top_n=top_n,
        metric_hint=metric_hint,
        entity_terms=entity_terms,
    )
