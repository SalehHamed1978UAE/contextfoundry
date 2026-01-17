"""
Gap Detector

Identifies when the system can't answer a query well and records the gap
for future learning.
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4
from enum import Enum

from sqlalchemy import text

logger = logging.getLogger(__name__)


class GapType(str, Enum):
    MISSING_ENTITY = "missing_entity"
    MISSING_RELATIONSHIP = "missing_relationship"
    WRONG_ANSWER = "wrong_answer"
    LOW_CONFIDENCE = "low_confidence"
    NO_ANSWER = "no_answer"


class QueryType(str, Enum):
    ENTITY = "entity"
    RELATIONSHIP = "relationship"
    ATTRIBUTE = "attribute"
    GENERAL = "general"


class GapDetector:
    """Detects and records query gaps for learning"""
    
    LOW_CONFIDENCE_THRESHOLD = 0.70
    NO_ANSWER_PATTERNS = [
        "i don't have",
        "no information",
        "not found",
        "cannot find",
        "don't see",
        "not mentioned",
        "no data",
        "unable to find",
        "not in the knowledge graph",
        "i couldn't find",
        "no results",
        "not available",
        "does not specify",
        "not provided",
        "could not find",
        "information is not included",
        "not included in the retrieved",
        "unable to determine",
        "i do not have",
        "don't have enough",
        "insufficient information",
        "no specific",
        "not explicitly",
        "cannot determine"
    ]
    
    def __init__(self, db_session):
        self.db = db_session
    
    def analyze_response(
        self,
        tenant_id: UUID,
        query_text: str,
        response_text: str,
        confidence: float,
        entities_used: List[str] = None,
        relationships_used: List[str] = None,
        user_id: str = None,
        session_id: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a query response to detect gaps.
        
        Returns gap info if a gap is detected, None otherwise.
        """
        
        gap_type = None
        
        if self._is_no_answer(response_text):
            gap_type = GapType.NO_ANSWER
        elif confidence < self.LOW_CONFIDENCE_THRESHOLD:
            gap_type = GapType.LOW_CONFIDENCE
        
        if not gap_type:
            return None
        
        query_type = self._classify_query(query_text)
        expected = self._extract_expected(query_text, query_type)
        
        gap_id = self._record_gap(
            tenant_id=tenant_id,
            query_text=query_text,
            query_type=query_type,
            gap_type=gap_type,
            response_text=response_text,
            confidence=confidence,
            expected=expected,
            user_id=user_id,
            session_id=session_id
        )
        
        logger.info(f"Gap detected: {gap_type.value} for query '{query_text[:50]}...'")
        
        return {
            "gap_id": str(gap_id),
            "gap_type": gap_type.value,
            "query_type": query_type.value,
            "expected": expected
        }
    
    def record_user_correction(
        self,
        tenant_id: UUID,
        original_value: str,
        corrected_value: str,
        correction_field: str,
        query_gap_id: Optional[UUID] = None,
        feedback_text: Optional[str] = None,
        entity_id: Optional[UUID] = None,
        relationship_id: Optional[UUID] = None,
        user_id: str = None
    ) -> UUID:
        """Record explicit user feedback/correction"""
        
        feedback_id = uuid4()
        
        self.db.execute(text("""
            INSERT INTO user_feedback (
                id, tenant_id, query_gap_id, entity_id, relationship_id,
                feedback_type, original_value, corrected_value, 
                correction_field, feedback_text, user_id
            ) VALUES (
                :id, :tenant_id, :gap_id, :entity_id, :rel_id,
                'correction', :original, :corrected, :field, :text, :user_id
            )
        """), {
            "id": feedback_id,
            "tenant_id": tenant_id,
            "gap_id": query_gap_id,
            "entity_id": entity_id,
            "rel_id": relationship_id,
            "original": original_value,
            "corrected": corrected_value,
            "field": correction_field,
            "text": feedback_text,
            "user_id": user_id
        })
        self.db.commit()
        
        logger.info(f"User correction recorded: {correction_field} '{original_value}' -> '{corrected_value}'")
        
        return feedback_id
    
    def _is_no_answer(self, response_text: str) -> bool:
        """Check if response indicates no answer was found"""
        response_lower = response_text.lower()
        return any(pattern in response_lower for pattern in self.NO_ANSWER_PATTERNS)
    
    def _classify_query(self, query_text: str) -> QueryType:
        """Classify the type of query"""
        query_lower = query_text.lower()
        
        if any(p in query_lower for p in ["who is", "what is", "tell me about"]):
            if "who" in query_lower:
                return QueryType.ENTITY
            return QueryType.GENERAL
        
        if any(p in query_lower for p in ["reports to", "works for", "manages", "leads", "who reports"]):
            return QueryType.RELATIONSHIP
        
        if any(p in query_lower for p in ["salary", "compensation", "how much", "what is the"]):
            return QueryType.ATTRIBUTE
        
        return QueryType.GENERAL
    
    def _extract_expected(self, query_text: str, query_type: QueryType) -> Dict[str, Any]:
        """Extract what the user was likely looking for"""
        expected = {}
        query_lower = query_text.lower()
        
        roles = ["ceo", "cto", "cfo", "coo", "cmo", "cio", "president", "director", 
                 "manager", "partner", "vp", "chief"]
        for role in roles:
            if role in query_lower:
                expected["entity_type"] = "PERSON"
                expected["role"] = role.upper()
                break
        
        capitalized = re.findall(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b', query_text)
        common_words = {"Who", "What", "Tell", "About", "The", "Is", "Are", "Does", "How", "When", "Where"}
        names = [w for w in capitalized if w not in common_words]
        if names:
            expected["entity_name"] = names[0]
        
        return expected
    
    def _record_gap(
        self,
        tenant_id: UUID,
        query_text: str,
        query_type: QueryType,
        gap_type: GapType,
        response_text: str,
        confidence: float,
        expected: Dict[str, Any],
        user_id: str = None,
        session_id: str = None
    ) -> UUID:
        """Record a gap in the database"""
        
        gap_id = uuid4()
        
        self.db.execute(text("""
            INSERT INTO query_gaps (
                id, tenant_id, query_text, query_type, gap_type,
                system_response, confidence_score,
                expected_entity_type, expected_entity_name,
                user_id, session_id
            ) VALUES (
                :id, :tenant_id, :query, :query_type, :gap_type,
                :response, :confidence,
                :entity_type, :entity_name,
                :user_id, :session_id
            )
        """), {
            "id": gap_id,
            "tenant_id": tenant_id,
            "query": query_text,
            "query_type": query_type.value,
            "gap_type": gap_type.value,
            "response": response_text[:2000],
            "confidence": confidence,
            "entity_type": expected.get("entity_type"),
            "entity_name": expected.get("entity_name"),
            "user_id": user_id,
            "session_id": session_id
        })
        self.db.commit()
        
        return gap_id
    
    def get_open_gaps(self, tenant_id: UUID, limit: int = 20) -> List[Dict[str, Any]]:
        """Get open gaps for a tenant"""
        
        result = self.db.execute(text("""
            SELECT id, tenant_id, query_text, query_type, gap_type,
                   expected_entity_type, expected_entity_name,
                   confidence_score, status, created_at
            FROM query_gaps
            WHERE tenant_id = :tenant_id AND status = 'OPEN'
            ORDER BY created_at DESC
            LIMIT :limit
        """), {"tenant_id": tenant_id, "limit": limit})
        
        return [dict(r._mapping) for r in result.fetchall()]
    
    def get_gap_by_id(self, gap_id: UUID) -> Optional[Dict[str, Any]]:
        """Get a specific gap by ID"""
        
        result = self.db.execute(text("""
            SELECT * FROM query_gaps WHERE id = :gap_id
        """), {"gap_id": gap_id}).fetchone()
        
        return dict(result._mapping) if result else None


def get_gap_detector(db_session) -> GapDetector:
    """Get gap detector with provided session"""
    return GapDetector(db_session)
