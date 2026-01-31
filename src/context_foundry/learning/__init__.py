"""
Learning Flow Module

Adaptive learning system that learns from user interactions to improve extraction quality.
Detects query gaps, queues learning tasks, and performs targeted re-extraction.
"""

from .gap_detector import GapDetector, get_gap_detector, GapType, QueryType
from .queue_manager import LearningQueueManager, get_queue_manager
from .targeted_extractor import TargetedExtractor, get_targeted_extractor
from .orchestrator import LearningFlowOrchestrator, get_orchestrator

__all__ = [
    'GapDetector',
    'get_gap_detector',
    'GapType',
    'QueryType',
    'LearningQueueManager',
    'get_queue_manager',
    'TargetedExtractor',
    'get_targeted_extractor',
    'LearningFlowOrchestrator',
    'get_orchestrator',
]
