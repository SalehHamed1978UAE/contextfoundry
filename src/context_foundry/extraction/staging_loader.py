"""
Staging Loader for Context Foundry MVP2.
Loads extracted entities and relations into the STAGING layer with provenance.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..models.schema import (
    Entity, Relationship, LifecycleState
)
from .entity_extractor import ExtractedEntity
from .relation_extractor import ExtractedRelation
from .duplicate_detector import DuplicateDetector, DuplicateDetectionResult


@dataclass
class StagingResult:
    """Result of staging extracted data."""
    entities_created: int = 0
    entities_updated: int = 0
    entities_skipped: int = 0
    entities_deduplicated: int = 0
    duplicate_candidates_found: int = 0
    relations_created: int = 0
    relations_updated: int = 0
    relations_skipped: int = 0
    errors: List[str] = field(default_factory=list)
    duplicate_detection: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        return {
            "entities_created": self.entities_created,
            "entities_updated": self.entities_updated,
            "entities_skipped": self.entities_skipped,
            "entities_deduplicated": self.entities_deduplicated,
            "duplicate_candidates_found": self.duplicate_candidates_found,
            "relations_created": self.relations_created,
            "relations_updated": self.relations_updated,
            "relations_skipped": self.relations_skipped,
            "errors": self.errors,
            "duplicate_detection": self.duplicate_detection,
        }


class StagingLoader:
    """
    Loads extracted entities and relations into the STAGING layer.
    
    Features:
    - Upsert logic (skip if exists with higher confidence)
    - Provenance tracking (source document, sentence)
    - Duplicate detection
    - Error handling with rollback
    - Tenant isolation via tenant_id
    """
    
    def __init__(
        self, 
        session: Session,
        enable_deduplication: bool = True,
        similarity_threshold: float = 0.8,
        tenant_id: Optional[str] = None
    ):
        """
        Initialize the staging loader.
        
        Args:
            session: SQLAlchemy session for database operations
            enable_deduplication: Whether to deduplicate entities before loading
            similarity_threshold: Minimum similarity for fuzzy duplicate detection
            tenant_id: Tenant ID for multi-tenancy isolation
        """
        self.session = session
        self._entity_cache = {}
        self.enable_deduplication = enable_deduplication
        self.duplicate_detector = DuplicateDetector(session, similarity_threshold)
        self.tenant_id = tenant_id
    
    def _normalize_entity_type(self, entity_type: str) -> str:
        """Normalize entity type string for database storage.
        
        Since entity_type is now VARCHAR, we just normalize to uppercase.
        Any type from the loaded schema config is valid.
        """
        return entity_type.upper()
    
    def _normalize_relation_type(self, relation_type: str) -> str:
        """Normalize relationship type string for database storage.
        
        Since relationship_type is now VARCHAR, we just normalize to uppercase.
        Any type from the loaded schema config is valid.
        """
        return relation_type.upper()
    
    def _find_entity_by_name(
        self, 
        name: str, 
        entity_type: Optional[str] = None
    ) -> Optional[Entity]:
        """Find an entity by name within the current tenant, optionally filtered by type."""
        cache_key = (name.lower(), entity_type if entity_type else None, self.tenant_id)
        
        if cache_key in self._entity_cache:
            return self._entity_cache[cache_key]
        
        query = self.session.query(Entity).filter(
            Entity.name.ilike(name)
        )
        if self.tenant_id:
            query = query.filter(Entity.tenant_id == uuid.UUID(self.tenant_id))
        if entity_type:
            query = query.filter(Entity.entity_type == entity_type)
        
        entity = query.first()
        if entity:
            self._entity_cache[cache_key] = entity
        
        return entity
    
    def _find_entity_by_name_any_type(self, name: str) -> Optional[Entity]:
        """Find an entity by name within the current tenant, regardless of type."""
        cache_key = (name.lower(), None, self.tenant_id)
        
        if cache_key in self._entity_cache:
            return self._entity_cache[cache_key]
        
        query = self.session.query(Entity).filter(
            Entity.name.ilike(name)
        )
        if self.tenant_id:
            query = query.filter(Entity.tenant_id == uuid.UUID(self.tenant_id))
        
        entity = query.first()
        
        if entity:
            self._entity_cache[cache_key] = entity
            specific_key = (name.lower(), entity.entity_type, self.tenant_id)
            self._entity_cache[specific_key] = entity
        
        return entity
    
    def load_entity(
        self,
        extracted: ExtractedEntity,
        update_if_higher_confidence: bool = True,
    ) -> Tuple[Optional[Entity], str]:
        """
        Load an extracted entity into STAGING.
        
        Args:
            extracted: ExtractedEntity to load
            update_if_higher_confidence: Update existing if new has higher confidence
            
        Returns:
            Tuple of (entity, action) where action is 'created', 'updated', or 'skipped'
        """
        entity_type = self._normalize_entity_type(extracted.entity_type)
        
        existing = self._find_entity_by_name(extracted.canonical_name, entity_type)
        
        if existing:
            if update_if_higher_confidence and extracted.confidence > existing.confidence:
                existing.confidence = extracted.confidence
                existing.properties = {
                    **existing.properties,
                    **extracted.properties
                }
                existing.source_document_id = extracted.source_document_id
                existing.source_sentence = extracted.source_span
                existing.extraction_method = "llm_extraction"
                existing.updated_at = datetime.utcnow()
                
                return existing, "updated"
            
            return existing, "skipped"
        
        entity = Entity(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(self.tenant_id) if self.tenant_id else None,
            name=extracted.canonical_name,
            entity_type=entity_type,
            lifecycle_state=LifecycleState.STAGING,
            properties=extracted.properties,
            confidence=extracted.confidence,
            source_document_id=extracted.source_document_id,
            source_sentence=extracted.source_span,
            extraction_method="llm_extraction",
            extracted_at=datetime.utcnow(),
        )
        
        self.session.add(entity)
        
        cache_key = (extracted.canonical_name.lower(), entity_type, self.tenant_id)
        self._entity_cache[cache_key] = entity
        
        return entity, "created"
    
    def load_relation(
        self,
        extracted: ExtractedRelation,
        update_if_higher_confidence: bool = True,
    ) -> Tuple[Optional[Relationship], str]:
        """
        Load an extracted relation into STAGING.
        
        Args:
            extracted: ExtractedRelation to load
            update_if_higher_confidence: Update existing if new has higher confidence
            
        Returns:
            Tuple of (relationship, action) where action is 'created', 'updated', 'skipped', or 'error'
        """
        relation_type = self._normalize_relation_type(extracted.relation_type)
        
        source_entity = self._find_entity_by_name_any_type(extracted.source_name)
        target_entity = self._find_entity_by_name_any_type(extracted.target_name)
        
        if not source_entity or not target_entity:
            return None, "error"
        
        filters = [
            Relationship.source_id == source_entity.id,
            Relationship.target_id == target_entity.id,
            Relationship.relationship_type == relation_type,
        ]
        if self.tenant_id:
            filters.append(Relationship.tenant_id == uuid.UUID(self.tenant_id))
        
        existing = self.session.query(Relationship).filter(
            and_(*filters)
        ).first()
        
        if existing:
            if update_if_higher_confidence and extracted.confidence > existing.confidence:
                existing.confidence = extracted.confidence
                existing.source_document_id = extracted.source_document_id
                existing.source_sentence = extracted.source_span
                existing.updated_at = datetime.utcnow()
                
                return existing, "updated"
            
            return existing, "skipped"
        
        relationship = Relationship(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(self.tenant_id) if self.tenant_id else None,
            source_id=source_entity.id,
            target_id=target_entity.id,
            relationship_type=relation_type,
            lifecycle_state=LifecycleState.STAGING,
            confidence=extracted.confidence,
            source_document_id=extracted.source_document_id,
            source_sentence=extracted.source_span,
            extracted_at=datetime.utcnow(),
        )
        
        self.session.add(relationship)
        
        return relationship, "created"
    
    def load_entities(
        self,
        entities: List[ExtractedEntity],
    ) -> StagingResult:
        """
        Load multiple extracted entities into STAGING.
        
        Args:
            entities: List of ExtractedEntity to load
            
        Returns:
            StagingResult with counts
        """
        result = StagingResult()
        
        for extracted in entities:
            try:
                entity, action = self.load_entity(extracted)
                
                if action == "created":
                    result.entities_created += 1
                elif action == "updated":
                    result.entities_updated += 1
                elif action == "skipped":
                    result.entities_skipped += 1
                else:
                    result.errors.append(f"Failed to load entity: {extracted.canonical_name}")
                    
            except Exception as e:
                result.errors.append(f"Error loading entity {extracted.canonical_name}: {str(e)}")
        
        return result
    
    def load_relations(
        self,
        relations: List[ExtractedRelation],
    ) -> StagingResult:
        """
        Load multiple extracted relations into STAGING.
        
        Args:
            relations: List of ExtractedRelation to load
            
        Returns:
            StagingResult with counts
        """
        result = StagingResult()
        
        for extracted in relations:
            try:
                relationship, action = self.load_relation(extracted)
                
                if action == "created":
                    result.relations_created += 1
                elif action == "updated":
                    result.relations_updated += 1
                elif action == "skipped":
                    result.relations_skipped += 1
                else:
                    result.errors.append(
                        f"Failed to load relation: {extracted.source_name} -> {extracted.target_name}"
                    )
                    
            except Exception as e:
                result.errors.append(
                    f"Error loading relation {extracted.source_name} -> {extracted.target_name}: {str(e)}"
                )
        
        return result
    
    def load_all(
        self,
        entities: List[ExtractedEntity],
        relations: List[ExtractedRelation],
        commit: bool = True,
    ) -> StagingResult:
        """
        Load all extracted entities and relations into STAGING.
        
        Args:
            entities: List of ExtractedEntity to load
            relations: List of ExtractedRelation to load
            commit: Whether to commit the transaction
            
        Returns:
            Combined StagingResult
        """
        self._entity_cache = {}
        self.duplicate_detector.clear_cache()
        
        result = StagingResult()
        
        entities_to_load = entities
        if self.enable_deduplication and entities:
            original_count = len(entities)
            entities_to_load = self.duplicate_detector.deduplicate_entities(
                entities, 
                merge_strategy="highest_confidence"
            )
            result.entities_deduplicated = original_count - len(entities_to_load)
            
            dup_detection = self.duplicate_detector.detect_duplicates(entities_to_load)
            result.duplicate_candidates_found = len(dup_detection.candidates)
            result.duplicate_detection = dup_detection.to_dict()
        
        entity_result = self.load_entities(entities_to_load)
        result.entities_created = entity_result.entities_created
        result.entities_updated = entity_result.entities_updated
        result.entities_skipped = entity_result.entities_skipped
        result.errors.extend(entity_result.errors)
        
        try:
            self.session.flush()
        except Exception as e:
            result.errors.append(f"Failed to flush entities: {str(e)}")
            self.session.rollback()
            return result
        
        relation_result = self.load_relations(relations)
        result.relations_created = relation_result.relations_created
        result.relations_updated = relation_result.relations_updated
        result.relations_skipped = relation_result.relations_skipped
        result.errors.extend(relation_result.errors)
        
        if commit:
            try:
                self.session.commit()
            except Exception as e:
                result.errors.append(f"Failed to commit transaction: {str(e)}")
                self.session.rollback()
        
        return result
    
    def clear_cache(self):
        """Clear the entity cache."""
        self._entity_cache = {}
