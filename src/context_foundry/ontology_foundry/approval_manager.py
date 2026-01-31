"""
ApprovalManager - Human-in-the-loop governance for RFC v2 §10

Implements the decision matrix for type/relation promotions:
- Routes requests to appropriate approval level based on confidence
- Manages SLA deadlines and escalation
- Records all decisions in audit log
"""

import os
import json
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import UUID
import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class RequestType(Enum):
    TYPE_PROMOTION = "TYPE_PROMOTION"
    TYPE_DEPRECATION = "TYPE_DEPRECATION"
    RELATION_PROMOTION = "RELATION_PROMOTION"
    RELATION_DEPRECATION = "RELATION_DEPRECATION"


class TargetCategory(Enum):
    CONCRETE_TYPE = "CONCRETE_TYPE"
    ABSTRACT_TYPE = "ABSTRACT_TYPE"
    RELATION = "RELATION"


class ApprovalLevel(Enum):
    AUTO_APPROVE = 0
    DOMAIN_LEAD = 1
    ARCHITECTURE_TEAM = 2
    HEAD_OF_QDATA = 3


class RequestStatus(Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"
    EXPIRED = "EXPIRED"


class Decision(Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ESCALATED = "ESCALATED"


@dataclass
class ApprovalRequest:
    id: UUID
    request_type: RequestType
    target_category: TargetCategory
    target_id: UUID
    target_snapshot: Dict[str, Any]
    assigned_level: ApprovalLevel
    assigned_to_user_id: Optional[UUID]
    assigned_to_role: Optional[str]
    confidence_score: float
    evidence_summary: Optional[str]
    validation_results: Optional[Dict[str, Any]]
    llm_recommendation: Optional[str]
    llm_reasoning: Optional[str]
    status: RequestStatus
    created_at: datetime
    sla_deadline: datetime
    decision: Optional[Decision]
    decision_at: Optional[datetime]
    decision_by_user_id: Optional[UUID]
    decision_notes: Optional[str]


SLA_DEADLINES = {
    ApprovalLevel.AUTO_APPROVE: timedelta(seconds=0),
    ApprovalLevel.DOMAIN_LEAD: timedelta(days=3),
    ApprovalLevel.ARCHITECTURE_TEAM: timedelta(days=5),
    ApprovalLevel.HEAD_OF_QDATA: timedelta(days=7),
}

ROLE_FOR_LEVEL = {
    ApprovalLevel.DOMAIN_LEAD: "DOMAIN_LEAD",
    ApprovalLevel.ARCHITECTURE_TEAM: "ARCHITECTURE_TEAM",
    ApprovalLevel.HEAD_OF_QDATA: "HEAD_OF_QDATA",
}


class ApprovalManager:
    """Manages the approval workflow per RFC v2 §10."""
    
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or os.environ.get("DATABASE_URL")
        
    def _get_connection(self):
        return psycopg2.connect(self.db_url)
    
    def determine_level(
        self,
        target_category: TargetCategory,
        request_type: RequestType,
        confidence_score: float
    ) -> Optional[ApprovalLevel]:
        """
        RFC v2 §10.1 Decision Matrix:
        
        | Request Type        | Confidence ≥ 0.98    | 0.90-0.98            | < 0.90  |
        |---------------------|----------------------|----------------------|---------|
        | New concrete type   | Auto-approve (L0)    | Domain Lead (L1)     | Reject  |
        | New abstract type   | Domain Lead (L1)     | Architecture (L2)    | Reject  |
        | Type deprecation    | Architecture (L2)    | Architecture (L2)    | N/A     |
        """
        is_deprecation = request_type in (
            RequestType.TYPE_DEPRECATION, 
            RequestType.RELATION_DEPRECATION
        )
        
        if is_deprecation:
            return ApprovalLevel.ARCHITECTURE_TEAM
        
        if target_category == TargetCategory.CONCRETE_TYPE:
            if confidence_score >= 0.98:
                return ApprovalLevel.AUTO_APPROVE
            elif confidence_score >= 0.90:
                return ApprovalLevel.DOMAIN_LEAD
            else:
                return None
                
        elif target_category == TargetCategory.ABSTRACT_TYPE:
            if confidence_score >= 0.98:
                return ApprovalLevel.DOMAIN_LEAD
            elif confidence_score >= 0.90:
                return ApprovalLevel.ARCHITECTURE_TEAM
            else:
                return None
                
        elif target_category == TargetCategory.RELATION:
            if confidence_score >= 0.98:
                return ApprovalLevel.AUTO_APPROVE
            elif confidence_score >= 0.90:
                return ApprovalLevel.DOMAIN_LEAD
            else:
                return None
        
        return None
    
    def create_request(
        self,
        request_type: RequestType,
        target_category: TargetCategory,
        target_id: UUID,
        target_snapshot: Dict[str, Any],
        confidence_score: float,
        evidence_summary: Optional[str] = None,
        validation_results: Optional[Dict[str, Any]] = None,
        llm_recommendation: Optional[str] = None,
        llm_reasoning: Optional[str] = None,
        domain_id: Optional[str] = None
    ) -> Optional[ApprovalRequest]:
        """
        Create an approval request and route to appropriate level.
        
        Returns None if confidence is too low (auto-reject).
        Returns ApprovalRequest with status=APPROVED if auto-approved.
        """
        level = self.determine_level(target_category, request_type, confidence_score)
        
        if level is None:
            logger.warning(
                f"Auto-reject: {request_type.value} for {target_id} "
                f"with confidence {confidence_score} < 0.90"
            )
            return None
        
        now = datetime.utcnow()
        sla_deadline = now + SLA_DEADLINES[level]
        
        assigned_to_role = ROLE_FOR_LEVEL.get(level)
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if level == ApprovalLevel.AUTO_APPROVE:
                    cur.execute("""
                        INSERT INTO ontology.approval_requests (
                            request_type, target_category, target_id, target_snapshot,
                            assigned_level, assigned_to_role,
                            confidence_score, evidence_summary, validation_results,
                            llm_recommendation, llm_reasoning,
                            status, sla_deadline,
                            decision, decision_at, decision_notes
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            'APPROVED', %s,
                            'APPROVED', NOW(), 'Auto-approved: confidence >= 0.98'
                        ) RETURNING *
                    """, (
                        request_type.value, target_category.value, str(target_id), 
                        json.dumps(target_snapshot),
                        level.value, assigned_to_role,
                        confidence_score, evidence_summary, 
                        json.dumps(validation_results) if validation_results else None,
                        llm_recommendation, llm_reasoning,
                        sla_deadline
                    ))
                    
                    row = cur.fetchone()
                    
                    self._log_audit(
                        cur, 'ontology.approval_requests', target_id,
                        'APPROVE', None, target_snapshot,
                        'Auto-approved by system (confidence >= 0.98)'
                    )
                    
                    conn.commit()
                    if row is None:
                        raise ValueError("Failed to create approval request")
                    return self._row_to_request(row)
                else:
                    assigned_user_id = self._find_assignee(
                        cur, level, domain_id
                    )
                    
                    cur.execute("""
                        INSERT INTO ontology.approval_requests (
                            request_type, target_category, target_id, target_snapshot,
                            assigned_level, assigned_to_user_id, assigned_to_role,
                            confidence_score, evidence_summary, validation_results,
                            llm_recommendation, llm_reasoning,
                            status, sla_deadline
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            'PENDING', %s
                        ) RETURNING *
                    """, (
                        request_type.value, target_category.value, str(target_id),
                        json.dumps(target_snapshot),
                        level.value, str(assigned_user_id) if assigned_user_id else None,
                        assigned_to_role,
                        confidence_score, evidence_summary,
                        json.dumps(validation_results) if validation_results else None,
                        llm_recommendation, llm_reasoning,
                        sla_deadline
                    ))
                    
                    row = cur.fetchone()
                    
                    self._log_audit(
                        cur, 'ontology.approval_requests', target_id,
                        'CREATE', None, target_snapshot,
                        f'Routed to {assigned_to_role} (Level {level.value})'
                    )
                    
                    conn.commit()
                    if row is None:
                        raise ValueError("Failed to create approval request")
                    return self._row_to_request(row)
    
    def _find_assignee(
        self, 
        cur, 
        level: ApprovalLevel, 
        domain_id: Optional[str]
    ) -> Optional[UUID]:
        """Find an active user at the specified level."""
        role = ROLE_FOR_LEVEL.get(level)
        if not role:
            return None
        
        if role == "DOMAIN_LEAD" and domain_id:
            cur.execute("""
                SELECT id FROM shared.users 
                WHERE role = %s AND domain_id = %s AND is_active = TRUE
                LIMIT 1
            """, (role, domain_id))
        else:
            cur.execute("""
                SELECT id FROM shared.users 
                WHERE role = %s AND is_active = TRUE
                LIMIT 1
            """, (role,))
        
        row = cur.fetchone()
        return UUID(row['id']) if row else None
    
    def approve(
        self,
        request_id: UUID,
        user_id: UUID,
        notes: Optional[str] = None
    ) -> ApprovalRequest:
        """Approve a pending request."""
        return self._decide(request_id, user_id, Decision.APPROVED, notes)
    
    def reject(
        self,
        request_id: UUID,
        user_id: UUID,
        notes: str
    ) -> ApprovalRequest:
        """Reject a pending request. Notes are required."""
        if not notes:
            raise ValueError("Rejection notes are required")
        return self._decide(request_id, user_id, Decision.REJECTED, notes)
    
    def escalate(
        self,
        request_id: UUID,
        user_id: UUID,
        notes: Optional[str] = None
    ) -> ApprovalRequest:
        """Escalate to next approval level."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM ontology.approval_requests WHERE id = %s
                """, (str(request_id),))
                row = cur.fetchone()
                
                if not row:
                    raise ValueError(f"Request {request_id} not found")
                if row['status'] != 'PENDING':
                    raise ValueError(f"Request is not pending: {row['status']}")
                
                current_level = ApprovalLevel(row['assigned_level'])
                
                if current_level == ApprovalLevel.HEAD_OF_QDATA:
                    raise ValueError("Cannot escalate beyond HEAD_OF_QDATA")
                
                new_level = ApprovalLevel(current_level.value + 1)
                new_role = ROLE_FOR_LEVEL.get(new_level)
                new_deadline = datetime.utcnow() + SLA_DEADLINES[new_level]
                new_assignee = self._find_assignee(cur, new_level, row.get('domain_id'))
                
                cur.execute("""
                    UPDATE ontology.approval_requests
                    SET assigned_level = %s,
                        assigned_to_user_id = %s,
                        assigned_to_role = %s,
                        sla_deadline = %s,
                        status = 'ESCALATED'
                    WHERE id = %s
                    RETURNING *
                """, (
                    new_level.value,
                    str(new_assignee) if new_assignee else None,
                    new_role,
                    new_deadline,
                    str(request_id)
                ))
                
                cur.execute("""
                    UPDATE ontology.approval_requests
                    SET status = 'PENDING'
                    WHERE id = %s
                """, (str(request_id),))
                
                self._log_audit(
                    cur, 'ontology.approval_requests', UUID(row['target_id']),
                    'ESCALATE', {'level': current_level.value}, {'level': new_level.value},
                    notes or f'Escalated from Level {current_level.value} to Level {new_level.value}',
                    user_id, request_id
                )
                
                cur.execute("""
                    SELECT * FROM ontology.approval_requests WHERE id = %s
                """, (str(request_id),))
                row = cur.fetchone()
                conn.commit()
                
                if row is None:
                    raise ValueError(f"Request {request_id} not found after escalation")
                return self._row_to_request(row)
    
    def _decide(
        self,
        request_id: UUID,
        user_id: UUID,
        decision: Decision,
        notes: Optional[str]
    ) -> ApprovalRequest:
        """Record a decision on a request."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM ontology.approval_requests WHERE id = %s
                """, (str(request_id),))
                row = cur.fetchone()
                
                if not row:
                    raise ValueError(f"Request {request_id} not found")
                if row['status'] != 'PENDING':
                    raise ValueError(f"Request is not pending: {row['status']}")
                
                cur.execute("""
                    UPDATE ontology.approval_requests
                    SET status = %s,
                        decision = %s,
                        decision_at = NOW(),
                        decision_by_user_id = %s,
                        decision_notes = %s
                    WHERE id = %s
                    RETURNING *
                """, (
                    decision.value,
                    decision.value,
                    str(user_id),
                    notes,
                    str(request_id)
                ))
                
                self._log_audit(
                    cur, 'ontology.approval_requests', UUID(row['target_id']),
                    decision.value, row['target_snapshot'], row['target_snapshot'],
                    notes or f'{decision.value} by user',
                    user_id, request_id
                )
                
                row = cur.fetchone()
                conn.commit()
                
                if row is None:
                    raise ValueError(f"Request {request_id} not found after decision")
                return self._row_to_request(row)
    
    def check_expired_requests(self) -> List[ApprovalRequest]:
        """Find and escalate expired pending requests."""
        expired = []
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM ontology.approval_requests
                    WHERE status = 'PENDING' AND sla_deadline < NOW()
                """)
                rows = cur.fetchall()
                
                for row in rows:
                    request = self._row_to_request(row)
                    
                    if request.assigned_level == ApprovalLevel.HEAD_OF_QDATA:
                        cur.execute("""
                            UPDATE ontology.approval_requests
                            SET status = 'EXPIRED'
                            WHERE id = %s
                        """, (str(request.id),))
                        
                        self._log_audit(
                            cur, 'ontology.approval_requests', request.target_id,
                            'UPDATE', {'status': 'PENDING'}, {'status': 'EXPIRED'},
                            'SLA expired at highest level'
                        )
                        request.status = RequestStatus.EXPIRED
                    else:
                        new_level = ApprovalLevel(request.assigned_level.value + 1)
                        new_role = ROLE_FOR_LEVEL.get(new_level)
                        new_deadline = datetime.utcnow() + SLA_DEADLINES[new_level]
                        new_assignee = self._find_assignee(cur, new_level, None)
                        
                        cur.execute("""
                            UPDATE ontology.approval_requests
                            SET assigned_level = %s,
                                assigned_to_user_id = %s,
                                assigned_to_role = %s,
                                sla_deadline = %s
                            WHERE id = %s
                        """, (
                            new_level.value,
                            str(new_assignee) if new_assignee else None,
                            new_role,
                            new_deadline,
                            str(request.id)
                        ))
                        
                        self._log_audit(
                            cur, 'ontology.approval_requests', request.target_id,
                            'ESCALATE', 
                            {'level': request.assigned_level.value, 'assigned_to': str(request.assigned_to_user_id) if request.assigned_to_user_id else None},
                            {'level': new_level.value, 'assigned_to': str(new_assignee) if new_assignee else None},
                            f'Auto-escalated due to SLA expiry'
                        )
                        
                        request.assigned_level = new_level
                        request.assigned_to_user_id = new_assignee
                        request.sla_deadline = new_deadline
                    
                    expired.append(request)
                
                conn.commit()
        
        return expired
    
    def get_pending_for_user(self, user_id: UUID) -> List[ApprovalRequest]:
        """Get all pending requests assigned to a user."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM ontology.approval_requests
                    WHERE assigned_to_user_id = %s AND status = 'PENDING'
                    ORDER BY sla_deadline ASC
                """, (str(user_id),))
                
                return [self._row_to_request(row) for row in cur.fetchall()]
    
    def get_pending_for_role(self, role: str) -> List[ApprovalRequest]:
        """Get all pending requests assigned to a role (unassigned to specific user)."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM ontology.approval_requests
                    WHERE assigned_to_role = %s 
                      AND assigned_to_user_id IS NULL 
                      AND status = 'PENDING'
                    ORDER BY sla_deadline ASC
                """, (role,))
                
                return [self._row_to_request(row) for row in cur.fetchall()]
    
    def _log_audit(
        self,
        cur,
        table_name: str,
        record_id: UUID,
        action: str,
        old_state: Optional[Dict],
        new_state: Optional[Dict],
        change_reason: str,
        user_id: Optional[UUID] = None,
        request_id: Optional[UUID] = None
    ):
        """Record an audit log entry."""
        cur.execute("""
            INSERT INTO shared.audit_log (
                table_name, record_id, action,
                old_state, new_state, change_reason,
                performed_by_user_id, request_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            table_name, str(record_id), action,
            json.dumps(old_state) if old_state else None,
            json.dumps(new_state) if new_state else None,
            change_reason,
            str(user_id) if user_id else None,
            str(request_id) if request_id else None
        ))
    
    def _row_to_request(self, row: Dict) -> ApprovalRequest:
        """Convert a database row to an ApprovalRequest."""
        return ApprovalRequest(
            id=UUID(row['id']),
            request_type=RequestType(row['request_type']),
            target_category=TargetCategory(row['target_category']),
            target_id=UUID(row['target_id']),
            target_snapshot=row['target_snapshot'] if isinstance(row['target_snapshot'], dict) else json.loads(row['target_snapshot']),
            assigned_level=ApprovalLevel(row['assigned_level']),
            assigned_to_user_id=UUID(row['assigned_to_user_id']) if row['assigned_to_user_id'] else None,
            assigned_to_role=row['assigned_to_role'],
            confidence_score=float(row['confidence_score']) if row['confidence_score'] else 0.0,
            evidence_summary=row['evidence_summary'],
            validation_results=row['validation_results'],
            llm_recommendation=row['llm_recommendation'],
            llm_reasoning=row['llm_reasoning'],
            status=RequestStatus(row['status']),
            created_at=row['created_at'],
            sla_deadline=row['sla_deadline'],
            decision=Decision(row['decision']) if row['decision'] else None,
            decision_at=row['decision_at'],
            decision_by_user_id=UUID(row['decision_by_user_id']) if row['decision_by_user_id'] else None,
            decision_notes=row['decision_notes']
        )
