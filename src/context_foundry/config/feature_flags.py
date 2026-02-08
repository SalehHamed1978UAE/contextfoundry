"""
Feature flags for Context Foundry extraction modes and retrieval strategies.

Part of Week 0: Shadow Mode Setup per ontology architecture spec.
"""

import os
from enum import Enum


class ExtractionMode(str, Enum):
    """Extraction pipeline mode for migration"""
    LEGACY = "legacy"           # Old unconstrained extraction
    SHADOW = "shadow"           # Both paths, compare results
    CONSTRAINED = "constrained" # New ontology-constrained path only


EXTRACTION_MODE = os.getenv("CF_EXTRACTION_MODE", ExtractionMode.LEGACY.value)
SHADOW_WRITE_ENABLED = os.getenv("CF_SHADOW_WRITE", "false").lower() == "true"

# Tree-Based Retrieval Feature Flag
TREE_BASED_RETRIEVAL_ENABLED = os.getenv("CF_TREE_BASED_RETRIEVAL", "false").lower() == "true"


def get_extraction_mode() -> ExtractionMode:
    """Get the current extraction mode"""
    mode_str = os.getenv("CF_EXTRACTION_MODE", ExtractionMode.LEGACY.value)
    try:
        return ExtractionMode(mode_str)
    except ValueError:
        return ExtractionMode.LEGACY


def is_shadow_mode() -> bool:
    """Check if running in shadow mode (dual-path extraction)"""
    return get_extraction_mode() == ExtractionMode.SHADOW


def is_constrained_mode() -> bool:
    """Check if running in constrained-only mode"""
    return get_extraction_mode() == ExtractionMode.CONSTRAINED


def should_write_shadow() -> bool:
    """Check if shadow writes are enabled"""
    return SHADOW_WRITE_ENABLED or is_shadow_mode()


def is_tree_based_retrieval_enabled(override: bool = None) -> bool:
    """
    Check if tree-based retrieval is enabled.

    Tree-based retrieval prioritizes graph proximity over semantic similarity.
    Enable with environment variable: CF_TREE_BASED_RETRIEVAL=true

    Args:
        override: Optional request-scoped override. If provided, takes precedence over env var.

    Returns:
        True if tree-based retrieval should be used, False otherwise.
    """
    if override is not None:
        return override
    return TREE_BASED_RETRIEVAL_ENABLED
