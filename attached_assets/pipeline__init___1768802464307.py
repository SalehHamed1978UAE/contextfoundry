"""
Pipeline module for long-running document ingestion and query precedence.

Implements Anthropic's "long-running agent harness" pattern:
- Incremental progress tracking
- Checkpoint/resume capability
- Pre-TRUSTED verification

Also implements tri-memory precedence pipeline:
- Symbolic > Semantic > Episodic flow
- Data Gates validation
- Symbolic override evaluation
"""

from .progress import ProgressTracker, DocumentProgress, IngestionStep
from .precedence_pipeline import (
    PrecedencePipeline,
    PrecedenceResult,
    AnswerSource,
    apply_precedence
)

__all__ = [
    # Ingestion progress
    "ProgressTracker",
    "DocumentProgress",
    "IngestionStep",
    # Precedence pipeline
    "PrecedencePipeline",
    "PrecedenceResult",
    "AnswerSource",
    "apply_precedence",
]
