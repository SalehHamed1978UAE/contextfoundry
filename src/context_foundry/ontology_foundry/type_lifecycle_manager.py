"""
Type Lifecycle Manager - Orchestrates validation and approval workflow.

This class integrates TypeValidator, HierarchyEnforcer, CollisionDetector
with ApprovalManager to implement RFC v2 §10 type governance workflow.

Workflow:
1. PROPOSED -> validate() -> all checks pass?
2. Yes: Create approval request (auto-approve or route to reviewers)
3. Approval granted: PROPOSED -> APPROVED -> ACTIVE (or VALIDATING -> APPROVED)
4. Approval denied: PROPOSED -> remains PROPOSED with rejection notes
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from uuid import UUID
from sqlalchemy import text
from sqlalchemy.orm import Session

from .type_validator import TypeValidator, TypeProposal
from .hierarchy_enforcer import HierarchyEnforcer
from .collision_detector import CollisionDetector
from .rule_executor import ValidationResult
from .approval_manager import (
    ApprovalManager,
    ApprovalRequest,
    RequestType,
    TargetCategory,
    ApprovalLevel,
    RequestStatus,
    Decision
)

logger = logging.getLogger(__name__)


@dataclass
class LifecycleResult:
    """Result of a lifecycle transition attempt."""
    success: bool
    type_id: str
    type_name: str
    old_status: str
    new_status: Optional[str] = None
    approval_request: Optional[ApprovalRequest] = None
    validation_errors: Optional[List[str]] = None
    validation_warnings: Optional[List[str]] = None
    rejection_reason: Optional[str] = None
    
    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []
        if self.validation_warnings is None:
            self.validation_warnings = []


class TypeLifecycleManager:
    """
    Orchestrates the complete type lifecycle from PROPOSED to ACTIVE.
    
    Responsibilities:
    1. Run all validation agents (TypeValidator, HierarchyEnforcer, CollisionDetector)
    2. Calculate confidence score from validation results
    3. Create approval requests via ApprovalManager
    4. Handle approval callbacks to transition types
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.type_validator = TypeValidator(session)
        self.hierarchy_enforcer = HierarchyEnforcer(session)
        self.collision_detector = CollisionDetector(session)
        self.approval_manager = ApprovalManager()
    
    def validate_and_submit_for_approval(
        self,
        type_id: str,
        llm_recommendation: Optional[str] = None,
        llm_reasoning: Optional[str] = None
    ) -> LifecycleResult:
        """
        Validate a PROPOSED type and submit for approval if valid.
        
        1. Load type from ontology.types
        2. Run TypeValidator, HierarchyEnforcer, CollisionDetector
        3. If all pass, calculate confidence and create approval request
        4. Return lifecycle result with approval request details
        """
        type_data = self._load_type(type_id)
        if not type_data:
            return LifecycleResult(
                success=False,
                type_id=type_id,
                type_name="unknown",
                old_status="unknown",
                rejection_reason=f"Type {type_id} not found"
            )
        
        if type_data['status'] != 'PROPOSED':
            return LifecycleResult(
                success=False,
                type_id=type_id,
                type_name=type_data['type_name'],
                old_status=type_data['status'],
                rejection_reason=f"Type must be in PROPOSED status, currently {type_data['status']}"
            )
        
        proposal = TypeProposal(
            id=type_id,
            type_name=type_data['type_name'],
            layer=type_data['layer'],
            display_name=type_data.get('display_name'),
            description=type_data.get('description'),
            parent_type_id=type_data.get('parent_type_id'),
            properties_schema=type_data.get('properties_schema', {}),
            extraction_hints=type_data.get('extraction_hints'),
            domain_id=type_data.get('domain_id'),
            proposed_by=type_data.get('proposed_by'),
        )
        
        logger.info(f"[LifecycleManager] Validating type: {proposal.type_name}")
        
        type_result = self.type_validator.validate(proposal)
        hierarchy_result = self.hierarchy_enforcer.validate(proposal.to_dict())
        collision_result = self.collision_detector.detect(proposal.to_dict())
        
        all_errors = type_result.errors + hierarchy_result.errors + collision_result.errors
        all_warnings = type_result.warnings + hierarchy_result.warnings + collision_result.warnings
        
        if all_errors:
            error_msgs = [e.message for e in all_errors if e.message]
            warning_msgs = [w.message for w in all_warnings if w.message]
            
            logger.warning(f"[LifecycleManager] Type {proposal.type_name} failed validation: {len(all_errors)} errors")
            
            return LifecycleResult(
                success=False,
                type_id=type_id,
                type_name=proposal.type_name,
                old_status='PROPOSED',
                validation_errors=error_msgs,
                validation_warnings=warning_msgs,
                rejection_reason=f"Validation failed: {len(all_errors)} errors"
            )
        
        confidence_score = self._calculate_confidence(
            type_result, hierarchy_result, collision_result,
            len(all_warnings)
        )
        
        is_abstract = type_data['layer'] <= 1
        target_category = TargetCategory.ABSTRACT_TYPE if is_abstract else TargetCategory.CONCRETE_TYPE
        
        target_snapshot = {
            'type_name': proposal.type_name,
            'layer': proposal.layer,
            'display_name': proposal.display_name,
            'description': proposal.description,
            'parent_type_id': proposal.parent_type_id,
            'domain_id': proposal.domain_id,
            'validation_warnings': [w.message for w in all_warnings if w.message],
        }
        
        evidence_summary = f"Validated with {len(all_warnings)} warnings"
        
        validation_results = {
            'type_validator': {'passed': type_result.passed, 'errors': len(type_result.errors), 'warnings': len(type_result.warnings)},
            'hierarchy_enforcer': {'passed': hierarchy_result.passed, 'errors': len(hierarchy_result.errors), 'warnings': len(hierarchy_result.warnings)},
            'collision_detector': {'passed': collision_result.passed, 'errors': len(collision_result.errors), 'warnings': len(collision_result.warnings)},
        }
        
        approval_request = self.approval_manager.create_request(
            request_type=RequestType.TYPE_PROMOTION,
            target_category=target_category,
            target_id=UUID(type_id),
            target_snapshot=target_snapshot,
            confidence_score=confidence_score,
            evidence_summary=evidence_summary,
            validation_results=validation_results,
            llm_recommendation=llm_recommendation,
            llm_reasoning=llm_reasoning,
            domain_id=proposal.domain_id
        )
        
        if approval_request is None:
            logger.warning(f"[LifecycleManager] Type {proposal.type_name} rejected: confidence {confidence_score:.2f} too low")
            return LifecycleResult(
                success=False,
                type_id=type_id,
                type_name=proposal.type_name,
                old_status='PROPOSED',
                validation_warnings=[w.message for w in all_warnings],
                rejection_reason=f"Confidence score {confidence_score:.2f} below minimum threshold (0.90)"
            )
        
        if approval_request.status == RequestStatus.APPROVED:
            self._transition_type(type_id, 'PROPOSED', 'APPROVED')
            logger.info(f"[LifecycleManager] Type {proposal.type_name} auto-approved with confidence {confidence_score:.2f}")
            
            return LifecycleResult(
                success=True,
                type_id=type_id,
                type_name=proposal.type_name,
                old_status='PROPOSED',
                new_status='APPROVED',
                approval_request=approval_request,
                validation_warnings=[w.message for w in all_warnings if w.message]
            )
        else:
            self._transition_type(type_id, 'PROPOSED', 'VALIDATING')
            logger.info(f"[LifecycleManager] Type {proposal.type_name} submitted for approval (confidence {confidence_score:.2f})")
            
            return LifecycleResult(
                success=True,
                type_id=type_id,
                type_name=proposal.type_name,
                old_status='PROPOSED',
                new_status='VALIDATING',
                approval_request=approval_request,
                validation_warnings=[w.message for w in all_warnings if w.message]
            )
    
    def handle_approval_decision(
        self,
        request_id: UUID,
        decision: Decision,
        user_id: UUID,
        notes: Optional[str] = None
    ) -> LifecycleResult:
        """
        Handle an approval decision and transition the type accordingly.
        
        APPROVED: VALIDATING -> APPROVED
        REJECTED: VALIDATING -> PROPOSED (with rejection notes)
        """
        if decision == Decision.APPROVED:
            request = self.approval_manager.approve(request_id, user_id, notes)
        else:
            request = self.approval_manager.reject(request_id, user_id, notes or "Rejected by reviewer")
        
        type_id = str(request.target_id)
        type_data = self._load_type(type_id)
        
        if not type_data:
            return LifecycleResult(
                success=False,
                type_id=type_id,
                type_name="unknown",
                old_status="unknown",
                rejection_reason=f"Type {type_id} not found"
            )
        
        if decision == Decision.APPROVED:
            self._transition_type(type_id, 'VALIDATING', 'APPROVED')
            logger.info(f"[LifecycleManager] Type {type_data['type_name']} approved by user {user_id}")
            
            return LifecycleResult(
                success=True,
                type_id=type_id,
                type_name=type_data['type_name'],
                old_status='VALIDATING',
                new_status='APPROVED',
                approval_request=request
            )
        else:
            self._transition_type(type_id, 'VALIDATING', 'PROPOSED')
            self._record_rejection(type_id, notes)
            logger.info(f"[LifecycleManager] Type {type_data['type_name']} rejected by user {user_id}")
            
            return LifecycleResult(
                success=True,
                type_id=type_id,
                type_name=type_data['type_name'],
                old_status='VALIDATING',
                new_status='PROPOSED',
                approval_request=request,
                rejection_reason=notes
            )
    
    def activate_approved_type(self, type_id: str) -> LifecycleResult:
        """
        Activate an APPROVED type, making it available for extraction.
        
        APPROVED -> ACTIVE
        """
        type_data = self._load_type(type_id)
        
        if not type_data:
            return LifecycleResult(
                success=False,
                type_id=type_id,
                type_name="unknown",
                old_status="unknown",
                rejection_reason=f"Type {type_id} not found"
            )
        
        if type_data['status'] != 'APPROVED':
            return LifecycleResult(
                success=False,
                type_id=type_id,
                type_name=type_data['type_name'],
                old_status=type_data['status'],
                rejection_reason=f"Type must be APPROVED to activate, currently {type_data['status']}"
            )
        
        self._transition_type(type_id, 'APPROVED', 'ACTIVE')
        logger.info(f"[LifecycleManager] Type {type_data['type_name']} activated")
        
        return LifecycleResult(
            success=True,
            type_id=type_id,
            type_name=type_data['type_name'],
            old_status='APPROVED',
            new_status='ACTIVE'
        )
    
    def _load_type(self, type_id: str) -> Optional[Dict[str, Any]]:
        """Load type data from ontology.types."""
        result = self.session.execute(text("""
            SELECT id, type_name, layer, display_name, description,
                   parent_type_id, properties_schema, extraction_hints,
                   domain_id, status, proposed_by
            FROM ontology.types
            WHERE id = :id
        """), {'id': type_id})
        
        row = result.fetchone()
        if not row:
            return None
        
        return {
            'id': str(row.id),
            'type_name': row.type_name,
            'layer': row.layer,
            'display_name': row.display_name,
            'description': row.description,
            'parent_type_id': str(row.parent_type_id) if row.parent_type_id else None,
            'properties_schema': row.properties_schema or {},
            'extraction_hints': row.extraction_hints,
            'domain_id': str(row.domain_id) if row.domain_id else None,
            'status': row.status,
            'proposed_by': row.proposed_by,
        }
    
    def _calculate_confidence(
        self,
        type_result: ValidationResult,
        hierarchy_result: ValidationResult,
        collision_result: ValidationResult,
        warning_count: int
    ) -> float:
        """
        Calculate confidence score from validation results.
        
        Base confidence: 1.0
        - Each warning: -0.02
        - Failed type validation: -0.10
        - Failed hierarchy: -0.10
        - Failed collision check: -0.10
        - Cap at minimum 0.0
        """
        confidence = 1.0
        
        if not type_result.passed:
            confidence -= 0.10
        if not hierarchy_result.passed:
            confidence -= 0.10
        if not collision_result.passed:
            confidence -= 0.10
        
        confidence -= warning_count * 0.02
        
        return max(0.0, min(1.0, confidence))
    
    def _transition_type(self, type_id: str, from_status: str, to_status: str) -> bool:
        """Update type status in ontology.types."""
        try:
            self.session.execute(text("""
                UPDATE ontology.types
                SET status = :to_status, updated_at = NOW()
                WHERE id = :id AND status = :from_status
            """), {'id': type_id, 'from_status': from_status, 'to_status': to_status})
            self.session.commit()
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"[LifecycleManager] Failed to transition type {type_id}: {e}")
            return False
    
    def _record_rejection(self, type_id: str, notes: Optional[str]) -> None:
        """Record rejection notes on the type."""
        try:
            self.session.execute(text("""
                UPDATE ontology.types
                SET properties_schema = jsonb_set(
                    COALESCE(properties_schema, '{}')::jsonb,
                    '{_rejection_notes}',
                    :notes::jsonb
                ),
                updated_at = NOW()
                WHERE id = :id
            """), {'id': type_id, 'notes': f'"{notes}"' if notes else 'null'})
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"[LifecycleManager] Failed to record rejection: {e}")
