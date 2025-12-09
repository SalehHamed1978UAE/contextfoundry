"""
Pipeline module for long-running document ingestion.

Implements Anthropic's "long-running agent harness" pattern:
- Incremental progress tracking
- Checkpoint/resume capability
- Pre-TRUSTED verification
"""

from .progress import ProgressTracker, DocumentProgress, IngestionStep

__all__ = ["ProgressTracker", "DocumentProgress", "IngestionStep"]
