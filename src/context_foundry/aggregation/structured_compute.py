from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ComponentValue:
    entity: str
    value: float
    metric: str


@dataclass
class ComputeResult:
    total: Optional[float]
    coverage_percent: float
    components_used: List[ComponentValue]
    discrepancy_flag: bool = False
    preferred_reported_total: Optional[float] = None


def compute_top_n(components: List[ComponentValue], n: int) -> List[ComponentValue]:
    ordered = sorted(components, key=lambda c: c.value, reverse=True)
    return ordered[:n]


def structured_sum(
    components: List[ComponentValue],
    expected_count: Optional[int] = None,
    reported_total: Optional[float] = None,
) -> ComputeResult:
    if not components:
        return ComputeResult(total=None, coverage_percent=0.0, components_used=[])

    values_sum = sum(c.value for c in components)
    discrepancy_flag = False

    if reported_total is not None:
        denom = reported_total if reported_total != 0 else 1.0
        if abs(values_sum - reported_total) / denom < 0.05:
            return ComputeResult(
                total=values_sum,
                coverage_percent=1.0,
                components_used=components,
                discrepancy_flag=False,
                preferred_reported_total=None,
            )
        discrepancy_flag = True

    if expected_count:
        coverage = min(1.0, len(components) / expected_count)
    else:
        coverage = 1.0

    return ComputeResult(
        total=values_sum,
        coverage_percent=coverage,
        components_used=components,
        discrepancy_flag=discrepancy_flag,
        preferred_reported_total=reported_total if discrepancy_flag else None,
    )
