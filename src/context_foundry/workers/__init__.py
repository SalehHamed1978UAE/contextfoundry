"""
Brain Workers - Queue Consumers for Platform Foundation

These workers process ExtractionRequests from Platform Foundation
and return ExtractionResults.
"""

from .extraction_worker import ExtractionWorker

__all__ = ["ExtractionWorker"]
