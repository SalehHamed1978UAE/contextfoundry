from __future__ import annotations

from typing import List, Tuple, Optional

from .models import Fact, ConflictGroup
from .registry import source_trust_for, DEFAULT_SOURCE_TRUST


class ResolutionResult:
    def __init__(self, selected: Optional[Fact], contested: bool, candidates: List[Fact]):
        self.selected = selected
        self.contested = contested
        self.candidates = candidates


def score_fact(fact: Fact) -> float:
    source_trust = source_trust_for(fact.evidence.source_type)
    score = (
        0.30 * source_trust
        + 0.25 * fact.confidence
        + 0.20 * fact.recency_weight
        + 0.15 * fact.lifecycle_weight
        + 0.10 * min(fact.evidence_count, 5) / 5.0
    )
    return max(0.0, min(1.0, score))


def resolve_conflict(group: ConflictGroup) -> ResolutionResult:
    scored: List[Tuple[Fact, float]] = [(f, score_fact(f)) for f in group.facts]
    scored.sort(key=lambda x: x[1], reverse=True)

    if not scored:
        return ResolutionResult(None, True, [])

    top_fact, top_score = scored[0]
    runner_up_score = scored[1][1] if len(scored) > 1 else 0.0

    if top_score < 0.50:
        return ResolutionResult(None, True, [f for f, _ in scored])

    ratio = (top_score / runner_up_score) if runner_up_score > 0 else 10.0

    if ratio > 1.25:
        return ResolutionResult(top_fact, False, [f for f, _ in scored])

    if ratio > 1.10:
        return ResolutionResult(top_fact, True, [f for f, _ in scored])

    return ResolutionResult(None, True, [f for f, _ in scored])


def resolve_conflicts(conflicts: List[ConflictGroup]) -> List[ResolutionResult]:
    return [resolve_conflict(c) for c in conflicts]
