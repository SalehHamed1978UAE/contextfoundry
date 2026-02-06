from __future__ import annotations

from typing import List, Dict

from .models import Fact, ConflictGroup
from .registry import RELATION_CARDINALITY, is_exceptional_cardinality, is_material_difference


def _group_by_key(facts: List[Fact]) -> Dict[str, List[Fact]]:
    groups: Dict[str, List[Fact]] = {}
    for f in facts:
        key = f"{f.subject}::{f.predicate}::{f.period or 'UNKNOWN'}::{f.canonical_metric or ''}"
        groups.setdefault(key, []).append(f)
    return groups


def detect_conflicts(facts: List[Fact]) -> List[ConflictGroup]:
    conflicts: List[ConflictGroup] = []
    groups = _group_by_key(facts)

    for key, group in groups.items():
        if len(group) <= 1:
            continue

        rel_type = group[0].predicate
        cardinality = RELATION_CARDINALITY.get(rel_type, "N-to-N")

        # Cardinality-triggered conflicts
        if cardinality == "1-to-1":
            if any(is_exceptional_cardinality(rel_type, f.evidence.source_text) for f in group):
                continue
            conflicts.append(ConflictGroup(key=key, facts=group))
            continue

        # Metric conflicts by value
        if group[0].value is not None:
            # classify by unit
            kind = "financial"
            if group[0].unit and group[0].unit == "%":
                kind = "percentage"
            if group[0].unit and group[0].unit == "count":
                kind = "count"

            material = False
            variance_detected = False
            base = group[0].value
            for other in group[1:]:
                if other.value is None:
                    continue
                diff_is_material, variance = is_material_difference(base, other.value, kind)
                variance_detected = variance_detected or variance
                if diff_is_material:
                    material = True

            if material:
                conflicts.append(ConflictGroup(key=key, facts=group, variance_detected=variance_detected))
    return conflicts
