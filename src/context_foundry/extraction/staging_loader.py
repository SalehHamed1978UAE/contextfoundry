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
    Entity, Relationship, LifecycleState, EntityMention, Document, ValidationStatus,
    EvidenceRecord, FactType
)
from .entity_extractor import ExtractedEntity

from ..utils.logger import logger
from ..ontology.candidate_store import CandidateStore
from ..ontology.normalizer import CandidateNormalizer


from .relation_extractor import ExtractedRelation
from .duplicate_detector import DuplicateDetector, DuplicateDetectionResult
from .entity_hygiene import is_valid_entity_name, clean_entity_name


def _safe_uuid(value) -> Optional[uuid.UUID]:
    """Safely convert a value to UUID, returning None if invalid.
    
    Handles chunk_id values that have _c0, _c1 etc suffixes from sub-chunking.
    """
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    try:
        str_val = str(value)
        if '_c' in str_val:
            str_val = str_val.rsplit('_c', 1)[0]
        return uuid.UUID(str_val)
    except (ValueError, AttributeError):
        return None


_document_existence_cache: Dict[str, bool] = {}


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
    relations_as_candidates: int = 0
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
            "relations_as_candidates": self.relations_as_candidates,
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
        self._document_exists_cache: Dict[str, bool] = {}
        self.enable_deduplication = enable_deduplication
        self.tenant_id = tenant_id
        self.duplicate_detector = DuplicateDetector(session, similarity_threshold, tenant_id=tenant_id)
        self._candidate_normalizer = CandidateNormalizer()
        self._known_relationship_types_cache: Optional[set] = None

        # Validate ontology map on initialization
        if tenant_id:
            self._validate_ontology_map()

    def _validate_ontology_map(self):
        """Validate that all LLM_TO_ONTOLOGY_TYPE_MAP targets are valid ontology types."""
        try:
            known_types = self._get_known_relationship_types()
            invalid_targets = []

            for llm_type, ontology_type in self.LLM_TO_ONTOLOGY_TYPE_MAP.items():
                if ontology_type not in known_types:
                    invalid_targets.append(f"{llm_type} → {ontology_type}")

            if invalid_targets:
                logger.warning(
                    f"[OntologyFoundry] LLM_TO_ONTOLOGY_TYPE_MAP contains {len(invalid_targets)} "
                    f"invalid target types:\n  " + "\n  ".join(invalid_targets)
                )
        except Exception as e:
            logger.debug(f"Could not validate ontology map: {e}")

    def _create_evidence_record(
        self,
        fact_type: FactType,
        fact_id: uuid.UUID,
        evidence_text: str,
        source_document_id: Optional[str] = None,
        chunk_id: Optional[uuid.UUID] = None
    ) -> Optional[EvidenceRecord]:
        """Create an evidence record linking a fact to its supporting source text.
        
        Args:
            fact_type: ENTITY or RELATIONSHIP
            fact_id: UUID of the entity or relationship
            evidence_text: The source text supporting this fact
            source_document_id: Document ID where evidence was found
            chunk_id: Chunk ID where evidence was found
            
        Returns:
            Created EvidenceRecord or None if evidence_text is empty
        """
        if not evidence_text or not evidence_text.strip():
            return None
        
        if not self.tenant_id:
            return None
        
        try:
            evidence = EvidenceRecord(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(self.tenant_id),
                fact_type=fact_type,
                fact_id=fact_id,
                evidence_text=evidence_text.strip()[:5000],
                source_document_id=source_document_id,
                chunk_id=chunk_id
            )
            self.session.add(evidence)
            return evidence
        except Exception as e:
            logger.debug(f"[StagingLoader] Failed to create evidence record: {e}")
            return None
    
    def _document_exists_in_public(self, doc_id: uuid.UUID) -> bool:
        """Check if a document exists in public.documents (for FK constraint).
        
        EntityMention has a FK to public.documents, but extraction documents
        may only exist in platform.documents. This check prevents FK violations.
        """
        cache_key = str(doc_id)
        if cache_key in self._document_exists_cache:
            return self._document_exists_cache[cache_key]
        
        try:
            exists = self.session.query(Document).filter(Document.id == doc_id).first() is not None
            self._document_exists_cache[cache_key] = exists
            return exists
        except Exception:
            self._document_exists_cache[cache_key] = False
            return False
    
    def _normalize_entity_type(self, entity_type: str) -> str:
        """Normalize entity type string for database storage.
        
        Since entity_type is now VARCHAR, we just normalize to uppercase.
        Any type from the loaded schema config is valid.
        """
        return entity_type.upper()
    
    def _ensure_entity_type_exists(self, entity_type: str) -> None:
        """Ensure entity type exists in ontology.types (required by database trigger).
        
        The entities table has a trigger that validates entity_type against
        ontology.types. This method creates the type if it doesn't exist.
        
        Uses a separate connection to avoid SQLAlchemy autoflush issues.
        """
        import os
        import psycopg2
        
        normalized_type = entity_type.upper()
        
        try:
            database_url = os.environ.get("DATABASE_URL")
            with psycopg2.connect(database_url) as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT 1 FROM ontology.types 
                        WHERE LOWER(type_name) = LOWER(%s) AND status = 'ACTIVE'
                    """, (normalized_type,))
                    result = cur.fetchone()
                    
                    if not result:
                        cur.execute("""
                            INSERT INTO ontology.types (
                                id, type_name, layer, display_name, description, 
                                status, confidence, created_at, updated_at
                            ) VALUES (
                                gen_random_uuid(), %s, 2, %s, %s,
                                'ACTIVE', 0.8, NOW(), NOW()
                            )
                            ON CONFLICT DO NOTHING
                        """, (
                            normalized_type,
                            entity_type.replace("_", " ").title(),
                            f"Dynamically created entity type: {entity_type}"
                        ))
                        conn.commit()
        except Exception as e:
            pass
    
    LLM_TO_ONTOLOGY_TYPE_MAP = {
        # FIXED: Changed from OWNS to RELATED_TO to prevent meaningless ownership edges
        # Context: "HAS_CONTRACT" should not map to OWNS (e.g., "Boeing HAS_CONTRACT $730M" → "Boeing OWNS $730M" is wrong)
        'HAS_CONTRACT': 'RELATED_TO',
        'HAS_DIVISION': 'PART_OF',
        'GENERATES_REVENUE': 'EARNS',
        'INVOLVED_IN': 'MEMBER_OF',
        'BELONGS_TO': 'MEMBER_OF',
        'PARTICIPATES_IN': 'MEMBER_OF',
        'ATTENDED_BY': 'MEMBER_OF',
        'WORKS_FOR': 'WORKS_AT',
        'EMPLOYED_BY': 'WORKS_AT',
        'EMPLOYED_AT': 'WORKS_AT',
        # FIXED: Changed from OWNS to RELATED_TO
        'CONTRACTED_BY': 'RELATED_TO',
        'HAS_ROLE': 'HOLDS_POSITION',
        'HAS_POSITION': 'HOLDS_POSITION',
        'PROVIDES': 'SUPPLIES',
        'PROVIDES_TO': 'SUPPLIES',
        'DELIVERS_TO': 'SUPPLIES',
        'VENDOR_FOR': 'SUPPLIES',
        'SUPPLIER_OF': 'SUPPLIES',
        'SUPPLIER_FOR': 'SUPPLIES',
        'SUPPLIES_TO': 'SUPPLIES',
        'CONTRACTED_TO_SUPPLY': 'SUPPLIES',
        'PURCHASED_BY': 'SUPPLIES',
        'PURCHASED_FROM': 'SUPPLIES',
        'OFFERS_PRODUCT': 'SUPPLIES',
        'LOCATED_AT': 'LOCATED_IN',
        'BASED_IN': 'LOCATED_IN',
        'HEADQUARTERED_AT': 'LOCATED_IN',
        'SUPERVISES': 'MANAGES',
        'DIRECTS': 'LEADS',
        'CHAIRS': 'LEADS',
        'HEAD_OF': 'LEADS',
        'HAS_SPEC': 'DESCRIBES',
        'HAS_SPECIFICATION': 'DESCRIBES',
        'SPECIFIES': 'DESCRIBES',
        'PRESENTED_BY': 'AUTHORED_BY',
        'HAS_KEY_CONTACT': 'AFFILIATED_WITH',
        'HAS_FINANCIAL_METRIC': 'EARNS',
        'HAS_METRIC': 'EARNS',
        # FIXED: Changed from OWNS to HAS_METRIC (budget is a metric, not ownership)
        'HAS_BUDGET': 'HAS_METRIC',
        'HAS_STATUS': 'RELATED_TO',
        'ATTENDS': 'MEMBER_OF',
        'HAS_RATING': 'RELATED_TO',
        'HAS_ISSUE': 'AFFECTS',
        'HAS_RESOLUTION': 'RELATED_TO',
        'OCCURS_ON': 'OCCURRED_ON',
        'EVALUATES': 'MANAGES',
        'PART_OF_PROJECT': 'PART_OF',
    }

    def _normalize_relation_type(self, relation_type: str) -> str:
        """Normalize relationship type string for database storage.
        
        Maps common LLM-generated types to known ontology types, then normalizes to uppercase.
        """
        upper = relation_type.upper()
        mapped = self.LLM_TO_ONTOLOGY_TYPE_MAP.get(upper, upper)
        return mapped
    
    def _get_known_relationship_types(self) -> set:
        """Get all known relationship types from schema + approved candidates.

        Ontology Foundry Phase 1: Types not in this set will be stored as candidates.
        For ontology extraction, preserve raw schema types without synonym normalization.
        """
        if self._known_relationship_types_cache is not None:
            return self._known_relationship_types_cache

        base_types = set()
        try:
            from ..config.domain_schema import get_schema_loader
            loader = get_schema_loader()
            schema_types = loader.schema.get_relationship_type_names()
            # FIXED: Use raw uppercase ontology types, no synonym collapse
            base_types = {t.upper() for t in schema_types}
        except Exception as e:
            logger.debug(f"Could not load schema types: {e}")
        
        if self.tenant_id:
            try:
                from sqlalchemy import text
                query = """
                    SELECT DISTINCT normalized_name 
                    FROM ontology_candidates 
                    WHERE tenant_id = :tenant_id 
                      AND candidate_type = 'RELATIONSHIP' 
                      AND status = 'APPROVED'
                """
                result = self.session.execute(text(query), {'tenant_id': self.tenant_id})
                approved = {row.normalized_name for row in result}
                base_types = base_types | approved
            except Exception as e:
                logger.debug(f"Could not load approved candidates: {e}")
        
        self._known_relationship_types_cache = base_types
        return base_types
    
    def _is_known_relationship_type(self, rel_type: str) -> bool:
        """Check if a relationship type is known (in schema or approved).
        
        First maps through LLM_TO_ONTOLOGY_TYPE_MAP, then checks against known types.
        """
        mapped = self._normalize_relation_type(rel_type)
        normalized = self._candidate_normalizer.normalize_relationship(mapped)
        known_types = self._get_known_relationship_types()
        if normalized in known_types:
            return True
        raw_normalized = self._candidate_normalizer.normalize_relationship(rel_type.upper())
        return raw_normalized in known_types
    
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
        cleaned_name = clean_entity_name(extracted.canonical_name)
        if not cleaned_name:
            logger.debug(f"[StagingLoader] Skipping invalid entity name: '{extracted.canonical_name}'")
            return None, "skipped"
        
        if cleaned_name != extracted.canonical_name:
            extracted.canonical_name = cleaned_name
        
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
                
                if hasattr(extracted, 'source_chunk_id') and extracted.source_chunk_id:
                    chunk_uuid = _safe_uuid(extracted.source_chunk_id)
                    doc_uuid = _safe_uuid(extracted.source_document_id)
                    tenant_uuid = _safe_uuid(self.tenant_id)
                    
                    if chunk_uuid and tenant_uuid and doc_uuid and self._document_exists_in_public(doc_uuid):
                        existing_mention = self.session.query(EntityMention).filter_by(
                            entity_id=existing.id,
                            chunk_id=chunk_uuid
                        ).first()
                        
                        if not existing_mention:
                            mention = EntityMention(
                                id=uuid.uuid4(),
                                entity_id=existing.id,
                                document_id=doc_uuid,
                                chunk_id=chunk_uuid,
                                tenant_id=tenant_uuid,
                                mention_text=extracted.source_span or extracted.canonical_name,
                                confidence=extracted.confidence,
                            )
                            self.session.add(mention)
                
                return existing, "updated"
            
            return existing, "skipped"
        
        self._ensure_entity_type_exists(entity_type)
        
        logger.debug(f"[StagingLoader] Creating entity: {extracted.canonical_name} ({entity_type})")
        
        chunk_uuid = None
        if hasattr(extracted, 'source_chunk_id') and extracted.source_chunk_id:
            chunk_uuid = _safe_uuid(extracted.source_chunk_id)
        
        entity = Entity(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(self.tenant_id) if self.tenant_id else None,
            name=extracted.canonical_name,
            entity_type=entity_type,
            lifecycle_state=LifecycleState.STAGING,
            validation_status=ValidationStatus.VALID,
            properties=extracted.properties,
            confidence=extracted.confidence,
            source_document_id=extracted.source_document_id,
            source_chunk_id=chunk_uuid,
            source_sentence=extracted.source_span,
            extraction_method="llm_extraction",
            extracted_at=datetime.utcnow(),
        )
        
        self.session.add(entity)
        
        if extracted.source_span:
            self._create_evidence_record(
                fact_type=FactType.ENTITY,
                fact_id=entity.id,
                evidence_text=extracted.source_span,
                source_document_id=extracted.source_document_id,
                chunk_id=chunk_uuid
            )
        else:
            fallback_evidence = f"Entity: {extracted.canonical_name} | Type: {extracted.entity_type}"
            logger.debug(f"[StagingLoader] No source_span for entity '{extracted.canonical_name}', using fallback evidence")
            self._create_evidence_record(
                fact_type=FactType.ENTITY,
                fact_id=entity.id,
                evidence_text=fallback_evidence,
                source_document_id=extracted.source_document_id,
                chunk_id=chunk_uuid
            )
        
        if hasattr(extracted, 'source_chunk_id') and extracted.source_chunk_id:
            doc_uuid = _safe_uuid(extracted.source_document_id)
            chunk_uuid = _safe_uuid(extracted.source_chunk_id)
            tenant_uuid = _safe_uuid(self.tenant_id)
            
            if chunk_uuid and tenant_uuid and doc_uuid and self._document_exists_in_public(doc_uuid):
                mention = EntityMention(
                    id=uuid.uuid4(),
                    entity_id=entity.id,
                    document_id=doc_uuid,
                    chunk_id=chunk_uuid,
                    tenant_id=tenant_uuid,
                    mention_text=extracted.source_span or extracted.canonical_name,
                    confidence=extracted.confidence,
                )
                self.session.add(mention)
        
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
        
        Ontology Foundry Phase 1: Unknown relationship types are stored as candidates
        instead of being written directly to the knowledge graph.
        
        Args:
            extracted: ExtractedRelation to load
            update_if_higher_confidence: Update existing if new has higher confidence
            
        Returns:
            Tuple of (relationship, action) where action is 'created', 'updated', 'skipped', 'candidate', or 'error'
        """
        # Map LLM type to ontology type
        mapped_type = self._normalize_relation_type(extracted.relation_type)

        # Preserve mapped ontology type as-is if it's a known type
        known_types = self._get_known_relationship_types()
        if mapped_type in known_types:
            canonical_type = mapped_type  # Use mapped type directly, no synonym normalization
        else:
            # Only normalize through synonyms if type is truly unknown
            canonical_type = self._candidate_normalizer.normalize_relationship(mapped_type)

        if not self._is_known_relationship_type(canonical_type):
            normalized_type = canonical_type
            if self.tenant_id:
                try:
                    candidate_store = CandidateStore(self.session, uuid.UUID(self.tenant_id))
                    doc_id = str(extracted.source_document_id) if extracted.source_document_id else None
                    
                    candidate_store.add_relationship_candidate(
                        proposed_name=extracted.relation_type,
                        normalized_name=normalized_type,
                        source_entity_type=getattr(extracted, 'source_type', 'UNKNOWN'),
                        target_entity_type=getattr(extracted, 'target_type', 'UNKNOWN'),
                        source_entity_name=extracted.source_name,
                        target_entity_name=extracted.target_name,
                        properties={},
                        original_text=extracted.source_span or "",
                        document_id=doc_id,
                        chunk_id=getattr(extracted, 'source_chunk_id', None)
                    )
                    logger.info(
                        f"[OntologyFoundry] Unknown relationship type "
                        f"original='{extracted.relation_type}', mapped='{mapped_type}', canonical='{canonical_type}' "
                        f"→ candidate as '{normalized_type}'"
                    )
                    return None, "candidate"
                except Exception as e:
                    logger.error(f"[OntologyFoundry] Failed to store candidate '{extracted.relation_type}': {e}")
                    raise RuntimeError(f"Candidate storage failed for unknown type '{extracted.relation_type}': {e}")
            else:
                logger.warning(f"[OntologyFoundry] Skipping unknown type '{extracted.relation_type}': no tenant_id for candidate storage")
                return None, "skipped"
        
        source_entity = self._find_entity_by_name_any_type(extracted.source_name)
        target_entity = self._find_entity_by_name_any_type(extracted.target_name)
        
        if not source_entity or not target_entity:
            return None, "error"
        
        filters = [
            Relationship.source_id == source_entity.id,
            Relationship.target_id == target_entity.id,
            Relationship.relationship_type == canonical_type,
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
        
        chunk_uuid = None
        if hasattr(extracted, 'source_chunk_id') and extracted.source_chunk_id:
            chunk_uuid = _safe_uuid(extracted.source_chunk_id)
        
        relationship = Relationship(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(self.tenant_id) if self.tenant_id else None,
            source_id=source_entity.id,
            target_id=target_entity.id,
            relationship_type=canonical_type,
            raw_relationship_type=extracted.relation_type,  # Preserve original LLM output
            lifecycle_state=LifecycleState.STAGING,
            validation_status=ValidationStatus.VALID,
            confidence=extracted.confidence,
            source_document_id=extracted.source_document_id,
            source_chunk_id=chunk_uuid,
            source_sentence=extracted.source_span,
            extracted_at=datetime.utcnow(),
        )
        
        self.session.add(relationship)
        
        if extracted.source_span:
            self._create_evidence_record(
                fact_type=FactType.RELATIONSHIP,
                fact_id=relationship.id,
                evidence_text=extracted.source_span,
                source_document_id=extracted.source_document_id,
                chunk_id=chunk_uuid
            )
        else:
            fallback_evidence = f"Relationship: {extracted.source_name} --[{extracted.relation_type}]--> {extracted.target_name}"
            logger.debug(f"[StagingLoader] No source_span for relationship, using fallback evidence")
            self._create_evidence_record(
                fact_type=FactType.RELATIONSHIP,
                fact_id=relationship.id,
                evidence_text=fallback_evidence,
                source_document_id=extracted.source_document_id,
                chunk_id=chunk_uuid
            )
        
        return relationship, "created"
    
    def load_entities(
        self,
        entities: List[ExtractedEntity],
    ) -> Tuple[StagingResult, List[Tuple['Entity', ExtractedEntity]]]:
        """
        Load multiple extracted entities into STAGING.
        
        Args:
            entities: List of ExtractedEntity to load
            
        Returns:
            Tuple of (StagingResult with counts, List of (persisted Entity, original ExtractedEntity) pairs)
        """
        result = StagingResult()
        persisted_entities = []  # Track (Entity, ExtractedEntity) pairs for aggregation hooks
        
        for extracted in entities:
            try:
                entity, action = self.load_entity(extracted)
                
                if action == "created":
                    result.entities_created += 1
                    if entity:
                        persisted_entities.append((entity, extracted))
                elif action == "updated":
                    result.entities_updated += 1
                    if entity:
                        persisted_entities.append((entity, extracted))
                elif action == "skipped":
                    result.entities_skipped += 1
                else:
                    result.errors.append(f"Failed to load entity: {extracted.canonical_name}")
                    
            except Exception as e:
                result.errors.append(f"Error loading entity {extracted.canonical_name}: {str(e)}")
        
        return result, persisted_entities
    
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
                elif action == "candidate":
                    result.relations_as_candidates += 1
                else:
                    result.errors.append(
                        f"Failed to load relation: {extracted.source_name} -> {extracted.target_name}"
                    )
                    
            except RuntimeError:
                raise
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
        
        entity_result, persisted_entities = self.load_entities(entities_to_load)
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
        result.relations_as_candidates = relation_result.relations_as_candidates
        result.errors.extend(relation_result.errors)
        
        if commit:
            try:
                self.session.commit()
                logger.info(f"[StagingLoader] Committed {result.entities_created} entities, {result.relations_created} relations")
                
                # Wire aggregation framework: Index entity mentions for document
                # Use persisted_entities which have actual DB IDs
                if self.tenant_id and persisted_entities:
                    try:
                        from ..aggregation.hooks import on_document_processed
                        # Group entities by document for indexing using actual persisted Entity IDs
                        doc_entities = {}
                        for db_entity, extracted_entity in persisted_entities:
                            doc_id = getattr(extracted_entity, 'source_document_id', None)
                            if doc_id and db_entity and db_entity.id:
                                if doc_id not in doc_entities:
                                    doc_entities[doc_id] = []
                                doc_entities[doc_id].append({
                                    'entity_id': db_entity.id,  # Use actual DB entity ID
                                    'mention_count': 1
                                })
                        
                        # Index each document's entity mentions
                        for doc_id, doc_entity_list in doc_entities.items():
                            if doc_id and doc_entity_list:
                                try:
                                    doc_uuid = _safe_uuid(doc_id)
                                    tenant_uuid = uuid.UUID(self.tenant_id)
                                    if doc_uuid:
                                        on_document_processed(
                                            self.session, 
                                            tenant_uuid, 
                                            doc_uuid, 
                                            [e for e in doc_entity_list if e.get('entity_id')]
                                        )
                                        self.session.commit()  # Commit aggregation data
                                except Exception as hook_err:
                                    logger.debug(f"[StagingLoader] Aggregation hook skipped: {hook_err}")
                    except ImportError:
                        pass  # Aggregation module not available
                    except Exception as agg_err:
                        logger.debug(f"[StagingLoader] Aggregation indexing skipped: {agg_err}")
                        
            except Exception as e:
                logger.error(f"[StagingLoader] Failed to commit: {str(e)}")
                result.errors.append(f"Failed to commit transaction: {str(e)}")
                self.session.rollback()
        
        if result.errors:
            logger.warning(f"[StagingLoader] Errors: {result.errors}")
        
        return result
    
    def clear_cache(self):
        """Clear the entity cache."""
        self._entity_cache = {}
