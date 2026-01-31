"""
Failure analysis infrastructure for Context Foundry.

This package provides tools for:
- Analyzing test failures through all pipeline layers
- Targeted extraction for specific failure patterns
- Applying fixes to the knowledge graph
- Running improvement loops to reach accuracy targets
"""

from .failure_analyzer import FailureAnalyzer, FailureReport, FailureLayer, FailurePattern
from .targeted_extractor import TargetedExtractor, TARGETED_PROMPTS
from .fix_applier import FixApplier
from .improvement_loop import ImprovementLoop

__all__ = [
    "FailureAnalyzer",
    "FailureReport",
    "FailureLayer",
    "FailurePattern",
    "TargetedExtractor",
    "TARGETED_PROMPTS",
    "FixApplier",
    "ImprovementLoop",
]
