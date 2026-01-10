"""
Extraction Validator

Gap detection for ALL known relationship types.
Detects when documents have content suggesting relationships exist but no relationships were extracted.
Config-driven — extend without code changes.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.context_foundry.utils.logger import logger


class GapSeverity(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class ExtractionGap:
    gap_type: str
    severity: GapSeverity
    message: str
    details: Dict

    def to_dict(self) -> Dict:
        return {
            'gap_type': self.gap_type,
            'severity': self.severity.value,
            'message': self.message,
            'details': self.details
        }


class GapValidator:
    """
    Gap detection for ALL known relationship types.
    Detects missing relationships based on document keywords.
    Config-driven — extend without code changes.
    
    Note: Renamed from ExtractionValidator to avoid conflict with 
    existing extraction/validation.py ExtractionValidator.
    """
    
    RELATIONSHIP_INDICATORS = {
        'HOLD_POSITION': {
            'keywords': ['ceo', 'cfo', 'cto', 'cio', 'coo', 'chief', 'officer', 
                        'director', 'manager', 'partner', 'chair', 'head of',
                        'chief executive', 'chief financial', 'chief technology',
                        'chief operating', 'chief information', 'managing partner'],
            'entity_type': 'PERSON',
        },
        'REPORTS_TO': {
            'keywords': ['reports to', 'reporting to', 'managed by', 
                        'org chart', 'organizational structure', 'hierarchy',
                        'direct report'],
            'entity_type': None,
        },
        'INVESTED_IN': {
            'keywords': ['invested', 'investment', 'stake', 'ownership', 
                        'portfolio', 'funding', 'series a', 'series b', 'seed',
                        'equity', 'venture capital', 'vc'],
            'entity_type': 'ORGANIZATION',
        },
        'WORKS_AT': {
            'keywords': ['works at', 'employed', 'employee', 'joined', 
                        'staff', 'team member', 'hired'],
            'entity_type': 'PERSON',
        },
        'HAS_SALARY': {
            'keywords': ['salary', 'compensation', 'base pay', 'annual salary',
                        'base draw', 'hourly rate'],
            'entity_type': 'PERSON',
        },
        'HAS_BONUS': {
            'keywords': ['bonus', 'performance bonus', 'signing bonus', 'incentive'],
            'entity_type': 'PERSON',
        },
    }
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def validate(self, document_id: str) -> List[ExtractionGap]:
        """Validate extraction for all known relationship types."""
        gaps = []
        doc_text = self._get_document_text(document_id)
        
        if not doc_text:
            logger.warning(f"[VALIDATOR] No document text found for {document_id}")
            return gaps
        
        doc_text_lower = doc_text.lower()
        
        for rel_type, config in self.RELATIONSHIP_INDICATORS.items():
            keywords_found = [kw for kw in config['keywords'] if kw in doc_text_lower]
            has_keywords = len(keywords_found) > 0
            
            if has_keywords:
                rel_count = self._count_relationships(document_id, rel_type)
                
                if rel_count == 0:
                    severity = GapSeverity.HIGH if len(keywords_found) >= 3 else GapSeverity.MEDIUM
                    gaps.append(ExtractionGap(
                        gap_type=f'MISSING_{rel_type}',
                        severity=severity,
                        message=f"Document has {rel_type} keywords but no {rel_type} relationships",
                        details={
                            'keywords_found': keywords_found[:5],
                            'relationship_count': 0
                        }
                    ))
                    logger.warning(f"[VALIDATOR] {severity.value}: Missing {rel_type} relationships (keywords: {keywords_found[:3]})")
        
        person_count = self._count_entities(document_id, 'PERSON')
        role_count = self._count_relationships(document_id, 'HOLD_POSITION')
        
        if person_count > 0 and role_count == 0:
            has_role_keywords = any(kw in doc_text_lower for kw in 
                                   ['ceo', 'cfo', 'cto', 'cio', 'coo', 'chief', 'director', 'manager'])
            if has_role_keywords:
                gaps.append(ExtractionGap(
                    gap_type='PEOPLE_WITHOUT_ROLES',
                    severity=GapSeverity.HIGH,
                    message=f"Found {person_count} people but no role relationships despite role keywords",
                    details={'person_count': person_count, 'role_count': role_count}
                ))
                logger.warning(f"[VALIDATOR] HIGH: {person_count} people with no role relationships")
        
        return gaps
    
    def validate_tenant(self) -> Dict:
        """Validate all documents in the tenant."""
        query = text("""
            SELECT DISTINCT source_document_id 
            FROM entities 
            WHERE tenant_id = :tenant_id 
            AND source_document_id IS NOT NULL
        """)
        
        try:
            results = self.session.execute(query, {"tenant_id": self.tenant_id}).fetchall()
            
            all_gaps = []
            for row in results:
                doc_id = row.source_document_id
                gaps = self.validate(doc_id)
                if gaps:
                    all_gaps.extend(gaps)
            
            return {
                'documents_checked': len(results),
                'gaps_found': len(all_gaps),
                'gaps': [g.to_dict() for g in all_gaps],
                'high_severity': len([g for g in all_gaps if g.severity == GapSeverity.HIGH]),
                'medium_severity': len([g for g in all_gaps if g.severity == GapSeverity.MEDIUM]),
                'low_severity': len([g for g in all_gaps if g.severity == GapSeverity.LOW]),
            }
        except Exception as e:
            logger.error(f"[VALIDATOR] Tenant validation failed: {e}")
            return {'error': str(e)}
    
    def _get_document_text(self, document_id: str) -> str:
        """Get combined text from all chunks of a document."""
        query = text("""
            SELECT text FROM document_chunks 
            WHERE tenant_id = :tenant_id 
            AND document_id = :document_id
            ORDER BY chunk_index
        """)
        
        try:
            results = self.session.execute(query, {
                "tenant_id": self.tenant_id,
                "document_id": document_id
            }).fetchall()
            return '\n'.join([row.text for row in results])
        except Exception as e:
            logger.debug(f"[VALIDATOR] Failed to get document text: {e}")
            return ""
    
    def _count_relationships(self, document_id: str, rel_type: str) -> int:
        """Count relationships of a specific type for a document."""
        query = text("""
            SELECT COUNT(*) as cnt FROM relationships r
            JOIN entities e ON r.source_id = e.id
            WHERE r.tenant_id = :tenant_id 
            AND e.source_document_id = :document_id
            AND r.relationship_type = :rel_type
        """)
        
        try:
            result = self.session.execute(query, {
                "tenant_id": self.tenant_id,
                "document_id": document_id,
                "rel_type": rel_type
            }).fetchone()
            return result.cnt if result else 0
        except Exception as e:
            logger.debug(f"[VALIDATOR] Failed to count relationships: {e}")
            return 0
    
    def _count_entities(self, document_id: str, entity_type: str) -> int:
        """Count entities of a specific type for a document."""
        query = text("""
            SELECT COUNT(*) as cnt FROM entities
            WHERE tenant_id = :tenant_id 
            AND source_document_id = :document_id
            AND entity_type = :entity_type
        """)
        
        try:
            result = self.session.execute(query, {
                "tenant_id": self.tenant_id,
                "document_id": document_id,
                "entity_type": entity_type
            }).fetchone()
            return result.cnt if result else 0
        except Exception as e:
            logger.debug(f"[VALIDATOR] Failed to count entities: {e}")
            return 0
