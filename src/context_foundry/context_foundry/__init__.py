"""
Context Foundry - Instance Governance System

RFC v2 Dual-System Architecture implementation.
Governs what SPECIFIC things we know (entities, relationships).
"""

from .orphan_detector import OrphanDetector, OrphanPattern, OrphanScanResult

__all__ = [
    'OrphanDetector',
    'OrphanPattern',
    'OrphanScanResult',
]
