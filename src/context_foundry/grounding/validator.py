from __future__ import annotations

from typing import List, Dict


def validate_path_contains_anchor(
    relationships: List[Dict],
    anchor_name: str,
) -> List[Dict]:
    """Filter relationships to those that mention the anchor name.

    Lightweight grounding validator: ensure anchor entity appears on path.
    """
    if not anchor_name:
        return relationships

    anchor_lower = anchor_name.lower()
    filtered = []
    for rel in relationships:
        source = str(rel.get("source_name", "")).lower()
        target = str(rel.get("target_name", "")).lower()
        if anchor_lower in source or anchor_lower in target:
            filtered.append(rel)
    return filtered
