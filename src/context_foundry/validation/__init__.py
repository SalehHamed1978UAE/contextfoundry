"""
Validation module for Context Foundry.

Implements the "refuse to hallucinate" Data Gates system:
- Entity existence validation
- Source coverage checking
- Answer grounding verification
- Hedging/fabrication detection
"""

from .coherence_checker import CoherenceChecker, CoherenceResult, CheckResult, ConfidenceLevel
from .data_gates import (
    DataGates,
    DataGateResult,
    DataGateEvaluation,
    evaluate_data_gates
)

__all__ = [
    'CoherenceChecker',
    'CoherenceResult',
    'CheckResult',
    'ConfidenceLevel',
    'DataGates',
    'DataGateResult',
    'DataGateEvaluation',
    'evaluate_data_gates',
]
