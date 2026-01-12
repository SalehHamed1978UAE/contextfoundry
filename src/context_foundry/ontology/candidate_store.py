"""
Candidate Store

Handles storage and retrieval of ontology candidates and pending extractions.
"""

import json
from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime, timedelta
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.context_foundry.ontology.normalizer import CandidateNormalizer
from src.context_foundry.utils.logger import logger


class CandidateStore:
    """Store for ontology candidates and pending extractions."""
    
    CANDIDATE_EXPIRY_DAYS = 90
    
    def __init__(self, session: Session, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
        self.normalizer = CandidateNormalizer()
    
    def add_relationship_candidate(
        self,
        proposed_name: str,
        normalized_name: str,
        source_entity_type: str,
        target_entity_type: str,
        source_entity_name: str,
        target_entity_name: str,
        properties: Optional[Dict] = None,
        original_text: Optional[str] = None,
        document_id: Optional[str] = None,
        chunk_id: Optional[str] = None
    ) -> UUID:
        """
        Add a relationship candidate or update existing one.
        
        If a candidate with the same normalized_name exists:
        - Increment document_count and mention_count
        - Add to example_mentions
        - Recalculate confidence
        
        Always creates a pending_extraction record.
        
        Returns the candidate_id.
        """
        properties = properties or {}
        
        existing = self._get_existing_candidate(normalized_name, "RELATIONSHIP")
        
        if existing:
            candidate_id = existing['id']
            logger.debug(f"[OntologyFoundry] Updating existing candidate: {normalized_name}")
            self._update_candidate_evidence(
                candidate_id=candidate_id,
                example_text=original_text,
                document_id=document_id,
                properties=properties
            )
        else:
            logger.info(f"[OntologyFoundry] New candidate created: {normalized_name}")
            candidate_id = self._create_candidate(
                candidate_type="RELATIONSHIP",
                proposed_name=proposed_name,
                normalized_name=normalized_name,
                source_entity_type=source_entity_type,
                target_entity_type=target_entity_type,
                example_text=original_text,
                document_id=document_id,
                properties=properties
            )
        
        self._create_pending_extraction(
            candidate_id=candidate_id,
            source_entity_name=source_entity_name,
            source_entity_type=source_entity_type,
            target_entity_name=target_entity_name,
            target_entity_type=target_entity_type,
            relationship_type=normalized_name,
            properties=properties,
            document_id=document_id,
            chunk_id=chunk_id,
            chunk_text=original_text
        )
        
        return candidate_id
    
    def add_entity_candidate(
        self,
        proposed_name: str,
        normalized_name: str,
        entity_name: str,
        properties: Optional[Dict] = None,
        original_text: Optional[str] = None,
        document_id: Optional[str] = None
    ) -> UUID:
        """Add an entity type candidate."""
        properties = properties or {}
        
        existing = self._get_existing_candidate(normalized_name, "ENTITY")
        
        if existing:
            candidate_id = existing['id']
            logger.debug(f"[OntologyFoundry] Updating existing entity candidate: {normalized_name}")
            self._update_candidate_evidence(
                candidate_id=candidate_id,
                example_text=original_text,
                document_id=document_id,
                properties=properties
            )
        else:
            logger.info(f"[OntologyFoundry] New entity candidate created: {normalized_name}")
            candidate_id = self._create_candidate(
                candidate_type="ENTITY",
                proposed_name=proposed_name,
                normalized_name=normalized_name,
                example_text=original_text,
                document_id=document_id,
                properties=properties
            )
        
        return candidate_id
    
    def get_pending_candidates(
        self,
        candidate_type: Optional[str] = None,
        min_confidence: float = 0.0
    ) -> List[Dict]:
        """Get pending candidates, sorted by confidence descending."""
        
        query = """
            SELECT 
                id, candidate_type, proposed_name, normalized_name,
                source_entity_type, target_entity_type,
                detected_properties, example_mentions,
                document_count, mention_count, confidence_score,
                status, created_at, expires_at
            FROM ontology_candidates
            WHERE tenant_id = :tenant_id
              AND status = 'PENDING'
              AND confidence_score >= :min_confidence
        """
        
        params = {
            'tenant_id': str(self.tenant_id),
            'min_confidence': min_confidence
        }
        
        if candidate_type:
            query += " AND candidate_type = :candidate_type"
            params['candidate_type'] = candidate_type
        
        query += " ORDER BY confidence_score DESC"
        
        result = self.session.execute(text(query), params)
        
        candidates = []
        for row in result:
            candidate = dict(row._mapping)
            candidate['id'] = str(candidate['id'])
            if isinstance(candidate.get('detected_properties'), str):
                candidate['detected_properties'] = json.loads(candidate['detected_properties'])
            if isinstance(candidate.get('example_mentions'), str):
                candidate['example_mentions'] = json.loads(candidate['example_mentions'])
            candidates.append(candidate)
        
        return candidates
    
    def get_candidate_by_id(self, candidate_id: UUID) -> Optional[Dict]:
        """Get a single candidate by ID."""
        query = """
            SELECT *
            FROM ontology_candidates
            WHERE id = :candidate_id AND tenant_id = :tenant_id
        """
        
        result = self.session.execute(text(query), {
            'candidate_id': str(candidate_id),
            'tenant_id': str(self.tenant_id)
        }).fetchone()
        
        if not result:
            return None
        
        candidate = dict(result._mapping)
        candidate['id'] = str(candidate['id'])
        if isinstance(candidate.get('detected_properties'), str):
            candidate['detected_properties'] = json.loads(candidate['detected_properties'])
        if isinstance(candidate.get('example_mentions'), str):
            candidate['example_mentions'] = json.loads(candidate['example_mentions'])
        
        return candidate
    
    def get_pending_extractions(self, candidate_id: UUID) -> List[Dict]:
        """Get all pending extractions for a candidate."""
        query = """
            SELECT *
            FROM pending_extractions
            WHERE candidate_id = :candidate_id
              AND tenant_id = :tenant_id
              AND status = 'PENDING'
            ORDER BY created_at
        """
        
        result = self.session.execute(text(query), {
            'candidate_id': str(candidate_id),
            'tenant_id': str(self.tenant_id)
        })
        
        extractions = []
        for row in result:
            extraction = dict(row._mapping)
            extraction['id'] = str(extraction['id'])
            extraction['candidate_id'] = str(extraction['candidate_id'])
            if isinstance(extraction.get('properties'), str):
                extraction['properties'] = json.loads(extraction['properties'])
            extractions.append(extraction)
        
        return extractions
    
    def get_stats(self) -> Dict[str, Dict[str, int]]:
        """Get counts by candidate type and status."""
        query = """
            SELECT candidate_type, status, COUNT(*) as count
            FROM ontology_candidates
            WHERE tenant_id = :tenant_id
            GROUP BY candidate_type, status
        """
        
        result = self.session.execute(text(query), {
            'tenant_id': str(self.tenant_id)
        })
        
        stats = {
            "RELATIONSHIP": {"PENDING": 0, "APPROVED": 0, "REJECTED": 0},
            "ENTITY": {"PENDING": 0, "APPROVED": 0, "REJECTED": 0},
            "ATTRIBUTE": {"PENDING": 0, "APPROVED": 0, "REJECTED": 0}
        }
        
        for row in result:
            if row.candidate_type in stats and row.status in stats[row.candidate_type]:
                stats[row.candidate_type][row.status] = row.count
        
        return stats
    
    def _get_existing_candidate(
        self, 
        normalized_name: str, 
        candidate_type: str
    ) -> Optional[Dict]:
        """Find existing candidate by normalized name."""
        query = """
            SELECT id, document_count, mention_count, example_mentions
            FROM ontology_candidates
            WHERE tenant_id = :tenant_id
              AND normalized_name = :normalized_name
              AND candidate_type = :candidate_type
              AND status = 'PENDING'
        """
        
        result = self.session.execute(text(query), {
            'tenant_id': str(self.tenant_id),
            'normalized_name': normalized_name,
            'candidate_type': candidate_type
        }).fetchone()
        
        if not result:
            return None
        
        return dict(result._mapping)
    
    def _create_candidate(
        self,
        candidate_type: str,
        proposed_name: str,
        normalized_name: str,
        source_entity_type: Optional[str] = None,
        target_entity_type: Optional[str] = None,
        example_text: Optional[str] = None,
        document_id: Optional[str] = None,
        properties: Optional[Dict] = None
    ) -> UUID:
        """Create a new candidate."""
        example_mentions = []
        if example_text:
            example_mentions.append({
                'text': example_text[:500],
                'document_id': document_id
            })
        
        expires_at = datetime.utcnow() + timedelta(days=self.CANDIDATE_EXPIRY_DAYS)
        confidence = self._calculate_confidence(1, 1)
        
        query = """
            INSERT INTO ontology_candidates (
                tenant_id, candidate_type, proposed_name, normalized_name,
                source_entity_type, target_entity_type,
                detected_properties, example_mentions,
                document_count, mention_count, confidence_score,
                expires_at
            ) VALUES (
                :tenant_id, :candidate_type, :proposed_name, :normalized_name,
                :source_entity_type, :target_entity_type,
                :detected_properties, :example_mentions,
                1, 1, :confidence_score,
                :expires_at
            )
            RETURNING id
        """
        
        result = self.session.execute(text(query), {
            'tenant_id': str(self.tenant_id),
            'candidate_type': candidate_type,
            'proposed_name': proposed_name,
            'normalized_name': normalized_name,
            'source_entity_type': source_entity_type,
            'target_entity_type': target_entity_type,
            'detected_properties': json.dumps(properties or {}),
            'example_mentions': json.dumps(example_mentions),
            'confidence_score': confidence,
            'expires_at': expires_at
        })
        
        self.session.commit()
        
        row = result.fetchone()
        return UUID(str(row.id)) if row else None
    
    def _update_candidate_evidence(
        self,
        candidate_id: UUID,
        example_text: Optional[str],
        document_id: Optional[str],
        properties: Optional[Dict]
    ):
        """Update an existing candidate with new evidence."""
        current = self.get_candidate_by_id(candidate_id)
        if not current:
            return
        
        example_mentions = current.get('example_mentions', [])
        if isinstance(example_mentions, str):
            example_mentions = json.loads(example_mentions)
        
        existing_doc_ids = {m.get('document_id') for m in example_mentions}
        is_new_document = document_id not in existing_doc_ids
        
        if example_text and len(example_mentions) < 10:
            example_mentions.append({
                'text': example_text[:500],
                'document_id': document_id
            })
        
        new_doc_count = current['document_count'] + (1 if is_new_document else 0)
        new_mention_count = current['mention_count'] + 1
        new_confidence = self._calculate_confidence(new_doc_count, new_mention_count)
        
        query = """
            UPDATE ontology_candidates
            SET document_count = :doc_count,
                mention_count = :mention_count,
                example_mentions = :example_mentions,
                confidence_score = :confidence_score,
                updated_at = NOW()
            WHERE id = :candidate_id
        """
        
        self.session.execute(text(query), {
            'candidate_id': str(candidate_id),
            'doc_count': new_doc_count,
            'mention_count': new_mention_count,
            'example_mentions': json.dumps(example_mentions),
            'confidence_score': new_confidence
        })
        
        self.session.commit()
        
        logger.debug(f"[OntologyFoundry] Updated candidate {candidate_id}: "
                    f"docs={new_doc_count}, mentions={new_mention_count}, confidence={new_confidence}")
    
    def _create_pending_extraction(
        self,
        candidate_id: UUID,
        source_entity_name: str,
        source_entity_type: str,
        target_entity_name: str,
        target_entity_type: str,
        relationship_type: str,
        properties: Optional[Dict],
        document_id: Optional[str],
        chunk_id: Optional[str],
        chunk_text: Optional[str]
    ):
        """Create a pending extraction record."""
        query = """
            INSERT INTO pending_extractions (
                tenant_id, candidate_id,
                source_entity_name, source_entity_type,
                target_entity_name, target_entity_type,
                relationship_type, properties,
                document_id, chunk_id, chunk_text
            ) VALUES (
                :tenant_id, :candidate_id,
                :source_entity_name, :source_entity_type,
                :target_entity_name, :target_entity_type,
                :relationship_type, :properties,
                :document_id, :chunk_id, :chunk_text
            )
        """
        
        self.session.execute(text(query), {
            'tenant_id': str(self.tenant_id),
            'candidate_id': str(candidate_id),
            'source_entity_name': source_entity_name,
            'source_entity_type': source_entity_type,
            'target_entity_name': target_entity_name,
            'target_entity_type': target_entity_type,
            'relationship_type': relationship_type,
            'properties': json.dumps(properties or {}),
            'document_id': document_id,
            'chunk_id': chunk_id,
            'chunk_text': chunk_text[:1000] if chunk_text else None
        })
        
        self.session.commit()
    
    def _calculate_confidence(self, document_count: int, mention_count: int) -> float:
        """
        Calculate confidence score based on evidence.
        
        Formula:
        - 40% from document diversity (full score at 3+ docs)
        - 30% from mention frequency (full score at 5+ mentions)
        - 30% base score
        """
        doc_score = min(document_count / 3.0, 1.0) * 0.40
        mention_score = min(mention_count / 5.0, 1.0) * 0.30
        base_score = 0.30
        
        return round(doc_score + mention_score + base_score, 2)
