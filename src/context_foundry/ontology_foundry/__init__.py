"""
Ontology Foundry - Schema Governance System

RFC v2 Dual-System Architecture implementation.
Governs what TYPES of things can exist in Context Foundry.
"""

from .rule_executor import RuleExecutor, ValidationResult, RuleResult
from .type_validator import TypeValidator, TypeProposal
from .hierarchy_enforcer import HierarchyEnforcer
from .collision_detector import CollisionDetector
from .approval_manager import (
    ApprovalManager, 
    ApprovalRequest, 
    RequestType, 
    TargetCategory,
    ApprovalLevel,
    RequestStatus,
    Decision
)
from .type_lifecycle_manager import TypeLifecycleManager, LifecycleResult

__all__ = [
    'RuleExecutor',
    'ValidationResult', 
    'RuleResult',
    'TypeValidator',
    'TypeProposal',
    'HierarchyEnforcer',
    'CollisionDetector',
    'ApprovalManager',
    'ApprovalRequest',
    'RequestType',
    'TargetCategory',
    'ApprovalLevel',
    'RequestStatus',
    'Decision',
    'TypeLifecycleManager',
    'LifecycleResult',
]
