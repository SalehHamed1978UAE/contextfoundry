from __future__ import annotations

from enum import Enum
from typing import Optional

from ..metrics.temporal import temporal_relationship, NormalizedPeriod
from ..metrics.hierarchy import METRIC_HIERARCHY, METRIC_RELATIONSHIPS


class FactRelation(Enum):
    CONFLICT = "CONFLICT"
    COMPLEMENT_CROSS_ENTITY = "COMPLEMENT_CROSS_ENTITY"
    COMPLEMENT_TEMPORAL = "COMPLEMENT_TEMPORAL"
    COMPLEMENT_DIMENSIONAL = "COMPLEMENT_DIMENSIONAL"
    SUBSUMPTION = "SUBSUMPTION"
    HIERARCHICAL = "HIERARCHICAL"
    RELATED_NOT_EQUIVALENT = "RELATED_NOT_EQUIVALENT"
    UNRELATED = "UNRELATED"
    UNCERTAIN = "UNCERTAIN"


def classify_fact_pair(
    entity_a: str,
    entity_b: str,
    metric_a: str,
    metric_b: str,
    period_a: Optional[NormalizedPeriod],
    period_b: Optional[NormalizedPeriod],
    scope_a: Optional[str],
    scope_b: Optional[str],
) -> FactRelation:
    if metric_a == metric_b and entity_a == entity_b and period_a and period_b:
        rel = temporal_relationship(period_a, period_b)
        if rel == "IDENTICAL":
            return FactRelation.CONFLICT
        if rel in ("CONTAINED_IN", "CONTAINS"):
            return FactRelation.SUBSUMPTION
        if rel in ("ADJACENT", "DISJOINT"):
            return FactRelation.COMPLEMENT_TEMPORAL

    if metric_a == metric_b and entity_a != entity_b and period_a == period_b:
        return FactRelation.COMPLEMENT_CROSS_ENTITY

    if scope_a and scope_b and scope_a != scope_b and metric_a == metric_b:
        return FactRelation.COMPLEMENT_DIMENSIONAL

    if metric_a != metric_b:
        if metric_a in METRIC_HIERARCHY and metric_b in METRIC_HIERARCHY.get(metric_a, {}).get("children", []):
            return FactRelation.HIERARCHICAL
        if metric_b in METRIC_HIERARCHY and metric_a in METRIC_HIERARCHY.get(metric_b, {}).get("children", []):
            return FactRelation.HIERARCHICAL

        if (metric_a, metric_b) in METRIC_RELATIONSHIPS or (metric_b, metric_a) in METRIC_RELATIONSHIPS:
            return FactRelation.RELATED_NOT_EQUIVALENT

    return FactRelation.UNCERTAIN
