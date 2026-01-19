"""
Validation module for Context Foundry.

Implements the "refuse to hallucinate" Data Gates system:
- Entity existence validation
- Source coverage checking
- Answer grounding verification
- Hedging/fabrication detection
"""

from .data_gates import (
    DataGates,
    DataGateResult,
    DataGateEvaluation,
    evaluate_data_gates
)

__all__ = [
    "DataGates",
    "DataGateResult",
    "DataGateEvaluation",
    "evaluate_data_gates",
]
