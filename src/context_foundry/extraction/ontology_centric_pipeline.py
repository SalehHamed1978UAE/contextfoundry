"""
Ontology-Centric Extraction Pipeline for Context Foundry.

Implements the document-aware, ontology-centric pipeline:
1. Store document chunks for RAG retrieval
2. Classify document type
3. Load/generate per-document-type ontology
4. Extract with ontology guidance (open extraction)
5. Define predicates with semantic definitions
6. Canonicalize using embedding similarity
7. Update reference ontology with new types
"""
import uuid
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text

from .document_classifier import classify_with_fallback
from .ontology_manager import OntologyManager, EntityTypeSchema, RelationshipTypeSchema
from .canonicalizer import Canonicalizer, RawTriplet, CanonicalTriplet, convert_to_raw_triplets
from .entity_extractor import EntityExtractor, ExtractedEntity
from .relation_extractor import RelationExtractor, ExtractedRelation
from .staging_loader import StagingLoader, StagingResult
from .post_processor import get_post_processor
from .job_tracker import ExtractionJobTracker, get_job_tracker

from ..utils.logger import logger
from ..utils.text_sanitizer import sanitize_text
from ..models.schema import DocumentChunk
from ..memory.episodic import openai_embedding


@dataclass
class OntologyCentricResult:
    """Result of ontology-centric extraction."""
    document_id: str
    document_type: str
    entities: List[ExtractedEntity]
    relations: List[ExtractedRelation]
    canonical_triplets: List[CanonicalTriplet]
    new_entity_types: List[str]
    new_relationship_types: List[str]
    staging_result: Optional[StagingResult] = None
    chunks_stored: int = 0
    success: bool = True
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "document_id": self.document_id,
            "document_type": self.document_type,
            "entity_count": len(self.entities),
            "relation_count": len(self.relations),
            "canonical_triplet_count": len(self.canonical_triplets),
            "new_entity_types": self.new_entity_types,
            "new_relationship_types": self.new_relationship_types,
            "staging_result": self.staging_result.to_dict() if self.staging_result else None,
            "chunks_stored": self.chunks_stored,
            "success": self.success,
            "error": self.error,
        }


class OntologyCentricPipeline:
    """
    Document-aware, ontology-centric extraction pipeline.
    
    Key features:
    - Document type classification
    - Per-document-type ontology selection/generation
    - Open extraction with ontology guidance
    - Semantic predicate definitions (embed definition, not label)
    - Embedding-based canonicalization
    - Reference ontology updates
    """
    
    def __init__(
        self,
        session: Session,
        tenant_id: str,
        model: str = "gpt-4o-mini",
        enable_canonicalization: bool = True,
        auto_stage: bool = True,
        enable_job_tracking: bool = True,
    ):
        """
        Initialize the pipeline.
        
        Args:
            session: Database session
            tenant_id: Tenant ID for multi-tenancy
            model: LLM model to use
            enable_canonicalization: Whether to run canonicalization step
            auto_stage: Whether to automatically stage results
            enable_job_tracking: Whether to track extraction jobs for monitoring
        """
        self.session = session
        self.tenant_id = tenant_id
        self.model = model
        self.enable_canonicalization = enable_canonicalization
        self.auto_stage = auto_stage
        self.enable_job_tracking = enable_job_tracking
        
        self.ontology_manager = OntologyManager(session, tenant_id)
        self.canonicalizer = Canonicalizer(session, tenant_id) if enable_canonicalization else None
        self.job_tracker = get_job_tracker(session) if enable_job_tracking else None
        
        self.entity_extractor = EntityExtractor(model=model, temperature=0.0)
        self.relation_extractor = RelationExtractor(model=model, temperature=0.0)

        # Component 2 (TypeDiscoveryAgent) hook — attached via
        # set_type_discovery_agent(). When attached, every staged document is
        # observed; every N docs (default 5) the agent runs discovery and
        # writes APPROVED/PENDING ontology_candidates back to the DB.
        self._type_discovery_agent = None
        self._discovery_interval: int = 5
        self._discovery_auto_approve_confidence: float = 0.85
        self._docs_since_discovery: int = 0
        self._current_document_type: str = "unknown"

    def set_type_discovery_agent(
        self,
        agent,
        interval: int = 5,
        auto_approve_confidence: float = 0.85,
    ) -> None:
        """Attach a TypeDiscoveryAgent to this pipeline.

        Args:
            agent: a TypeDiscoveryAgent instance
            interval: run discover_types() / persist_proposals() every N docs
            auto_approve_confidence: proposals above this confidence are
                written with status='APPROVED' and immediately picked up by
                future extractions; lower-confidence proposals go PENDING for
                human review.
        """
        self._type_discovery_agent = agent
        self._discovery_interval = max(1, int(interval))
        self._discovery_auto_approve_confidence = float(auto_approve_confidence)
        self._docs_since_discovery = 0
    
    def extract(
        self,
        text: str,
        document_id: str,
        filename: Optional[str] = None,
        document_type_override: Optional[str] = None,
        content_hash: Optional[str] = None,
    ) -> OntologyCentricResult:
        """
        Run full ontology-centric extraction pipeline.
        
        Extracts from each chunk individually with provenance tracking.
        
        Args:
            text: Document text content
            document_id: Document ID
            filename: Original filename (for type inference)
            document_type_override: Override automatic classification
            content_hash: Hash of document content for cache optimization
            
        Returns:
            OntologyCentricResult with all extraction data
        """
        chunks_stored = []
        job_id = None
        
        if content_hash is None and self.job_tracker:
            content_hash = ExtractionJobTracker.compute_content_hash(text)
        
        if self.job_tracker and content_hash:
            if self.job_tracker.should_skip_extraction(document_id, content_hash):
                logger.info(f"[OntologyCentricPipeline] Skipping extraction for {document_id}: content unchanged")
                return OntologyCentricResult(
                    document_id=document_id,
                    document_type="cached",
                    entities=[],
                    relations=[],
                    canonical_triplets=[],
                    new_entity_types=[],
                    new_relationship_types=[],
                    chunks_stored=0,
                    success=True,
                )
        
        try:
            chunks_stored = self._store_document_chunks(text, document_id)
            
            if self.job_tracker:
                job_id = self.job_tracker.create_job(
                    tenant_id=uuid.UUID(self.tenant_id),
                    document_id=uuid.UUID(document_id),
                    content_hash=content_hash,
                    chunks_total=len(chunks_stored)
                )
                self.job_tracker.start_job(job_id, chunks_total=len(chunks_stored))
            logger.info(f"[OntologyCentricPipeline] Stored {len(chunks_stored)} chunks for RAG retrieval")
            
            if document_type_override:
                document_type = document_type_override
            else:
                document_type = classify_with_fallback(text, filename)
            
            logger.info(f"[OntologyCentricPipeline] Document type: {document_type}")
            # Propagate the classified document type so the TypeDiscoveryAgent
            # hook tags observations with the correct doc category, instead of
            # the 'unknown' default. This is what makes doc-diversity scoring
            # in the agent meaningful.
            self._current_document_type = document_type or "unknown"
            
            ontology = self.ontology_manager.get_or_create_ontology(document_type, text)
            
            entity_types = self.ontology_manager.get_entity_type_names(document_type)
            
            relationship_type_defs = [rt.to_dict() for rt in ontology.relationship_types]
            
            if not relationship_type_defs:
                relationship_type_defs = [
                    {"name": "RELATED_TO", "definition": "General relationship between entities", "source_types": [], "target_types": []},
                    {"name": "PART_OF", "definition": "Entity is part of or belongs to another", "source_types": [], "target_types": []},
                    {"name": "WORKS_WITH", "definition": "Entity works with or collaborates with another", "source_types": [], "target_types": []},
                    {"name": "HAS_PROPERTY", "definition": "Entity has a property or attribute", "source_types": [], "target_types": []},
                    {"name": "HOLDS_POSITION", "definition": "Person holds a job position", "source_types": ["PERSON"], "target_types": ["ROLE", "JOB_TITLE", "POSITION"]},
                    {"name": "WORKED_AT", "definition": "Person worked at an organization", "source_types": ["PERSON"], "target_types": ["ORGANIZATION"]},
                ]
                logger.warning(f"[OntologyCentricPipeline] No relationship types in ontology for {document_type}, using fallback")
            
            all_entities = []
            all_relations = []
            chunks_processed = 0
            
            for chunk in chunks_stored:
                chunk_id = str(chunk.id)
                chunk_text = chunk.text
                
                if not chunk_text or len(chunk_text.strip()) < 50:
                    chunks_processed += 1
                    continue
                
                chunk_entities = self._extract_entities_with_ontology(
                    chunk_text, document_id, entity_types, document_type, chunk_id=chunk_id
                )
                
                for entity in chunk_entities:
                    entity.source_chunk_id = chunk_id
                
                all_entities.extend(chunk_entities)
                
                if chunk_entities:
                    chunk_relations = self._extract_relations_with_ontology(
                        chunk_text, document_id, chunk_entities, relationship_type_defs, document_type, chunk_id=chunk_id
                    )
                    
                    for rel in chunk_relations:
                        rel.source_chunk_id = chunk_id
                    
                    all_relations.extend(chunk_relations)
                
                chunks_processed += 1
                
                if self.job_tracker and job_id:
                    self.job_tracker.update_progress(
                        job_id, 
                        chunks_processed=chunks_processed,
                        entities_extracted=len(all_entities),
                        relationships_extracted=len(all_relations)
                    )
                
                logger.info(f"[OntologyCentricPipeline] Chunk {chunk.chunk_index}: {len(chunk_entities)} entities, {len(chunk_relations) if chunk_entities else 0} relations")
            
            logger.info(f"[OntologyCentricPipeline] Total extracted: {len(all_entities)} entities, {len(all_relations)} relations from {len(chunks_stored)} chunks")

            # =========================================================================
            # POST-PROCESSOR: Catch relationships the LLM missed using patterns
            # =========================================================================
            post_processor_entities, post_processor_relations = self._run_post_processor(
                text, all_entities, all_relations, document_id
            )
            all_entities.extend(post_processor_entities)

            # _run_post_processor already returns ExtractedRelation objects; just sanity-filter
            filtered_pp_relations = []
            if post_processor_relations:
                filtered_pp_relations = self.relation_extractor._apply_sanity_filter(post_processor_relations)
                logger.info(f"[OntologyCentricPipeline] Post-processor: {len(post_processor_relations)} raw, "
                           f"{len(filtered_pp_relations)} after sanity filter")
                all_relations.extend(filtered_pp_relations)

            if post_processor_entities or filtered_pp_relations:
                logger.info(f"[OntologyCentricPipeline] Post-processor added: {len(post_processor_entities)} entities, "
                           f"{len(filtered_pp_relations)} relations")

            canonical_triplets = []
            if self.enable_canonicalization and self.canonicalizer and all_relations:
                raw_triplets = convert_to_raw_triplets(all_entities, all_relations)
                canonical_triplets = self.canonicalizer.process_triplets(raw_triplets)
                
                for ct in canonical_triplets:
                    for rel in all_relations:
                        if rel.source_name == ct.subject and rel.target_name == ct.object:
                            rel.relation_type = ct.relationship_type
                            break
            
            new_entity_types = self._find_new_entity_types(all_entities, ontology)
            new_relationship_types = self._find_new_relationship_types(all_relations, ontology)
            
            if new_entity_types or new_relationship_types:
                self._update_reference_ontology(
                    document_type, 
                    new_entity_types, 
                    new_relationship_types,
                    all_entities,
                    all_relations
                )
            
            staging_result = None
            if self.auto_stage:
                staging_result = self._stage_results(document_id, all_entities, all_relations)
            
            if self.job_tracker and job_id:
                self.job_tracker.complete_job(
                    job_id,
                    entities_extracted=len(all_entities),
                    relationships_extracted=len(all_relations),
                    partial=False
                )
            
            return OntologyCentricResult(
                document_id=document_id,
                document_type=document_type,
                entities=all_entities,
                relations=all_relations,
                canonical_triplets=canonical_triplets,
                new_entity_types=new_entity_types,
                new_relationship_types=new_relationship_types,
                staging_result=staging_result,
                chunks_stored=len(chunks_stored),
                success=True,
            )
            
        except Exception as e:
            logger.error(f"[OntologyCentricPipeline] Extraction failed: {e}", exc_info=True)
            
            if self.job_tracker and job_id:
                self.job_tracker.fail_job(job_id, str(e))
            
            return OntologyCentricResult(
                document_id=document_id,
                document_type="unknown",
                entities=[],
                relations=[],
                canonical_triplets=[],
                new_entity_types=[],
                new_relationship_types=[],
                chunks_stored=len(chunks_stored) if chunks_stored else 0,
                success=False,
                error=str(e),
            )
    
    def _chunk_text(self, text: str, chunk_size: int = 2000, overlap: int = 400) -> List[Tuple[str, int, int]]:
        """Split text into overlapping chunks with position tracking.
        
        Returns list of (chunk_text, char_start, char_end) tuples.
        """
        if len(text) <= chunk_size:
            return [(text, 0, len(text))]
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            if end < len(text):
                last_period = text.rfind('.', start, end)
                if last_period > start + int(chunk_size * 0.6):
                    end = last_period + 1
            
            chunk_text = text[start:end].strip()
            if chunk_text:
                chunks.append((chunk_text, start, min(end, len(text))))
            
            start = end - overlap
            if start >= len(text):
                break
        
        return chunks
    
    def _store_document_chunks(self, text: str, document_id: str) -> List[DocumentChunk]:
        """Store document chunks for RAG retrieval.
        
        This ensures every document has searchable text chunks regardless
        of entity/relationship extraction success.
        
        Returns list of stored DocumentChunk objects with IDs.
        """
        try:
            existing_chunks = self.session.execute(
                sql_text("SELECT id, chunk_index, text FROM document_chunks WHERE document_id = :doc_id ORDER BY chunk_index"),
                {"doc_id": document_id}
            ).fetchall()
            
            if existing_chunks:
                logger.info(f"[OntologyCentricPipeline] Document {document_id} already has {len(existing_chunks)} chunks, returning existing")
                return [DocumentChunk(id=row[0], chunk_index=row[1], text=row[2], document_id=document_id, tenant_id=self.tenant_id) for row in existing_chunks]
            
            # Sanitize text to remove NUL (0x00) and other problematic control characters
            # PostgreSQL cannot store NUL in text columns - this is the storage boundary
            sanitized_text = sanitize_text(text)
            if len(sanitized_text) != len(text):
                logger.info(f"[OntologyCentricPipeline] Sanitized text: removed {len(text) - len(sanitized_text)} problematic characters")
            
            chunks_data = self._chunk_text(sanitized_text, chunk_size=2000, overlap=400)
            
            stored_chunks = []
            for idx, (chunk_text, char_start, char_end) in enumerate(chunks_data):
                chunk_embedding = None
                try:
                    chunk_embedding = openai_embedding(chunk_text, dim=1536)
                except Exception as embed_e:
                    logger.warning(f"[OntologyCentricPipeline] Failed to generate embedding for chunk {idx}: {embed_e}")
                
                chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=document_id,
                    tenant_id=self.tenant_id,
                    chunk_index=idx,
                    text=chunk_text,
                    char_start=char_start,
                    char_end=char_end,
                    chunk_metadata={"source": "ontology_centric_pipeline"},
                    embedding=chunk_embedding
                )
                self.session.add(chunk)
                stored_chunks.append(chunk)
            
            self.session.flush()
            logger.info(f"[OntologyCentricPipeline] Stored {len(stored_chunks)} chunks with embeddings for document {document_id}")
            return stored_chunks
            
        except Exception as e:
            logger.error(f"[OntologyCentricPipeline] Failed to store chunks: {e}")
            self.session.rollback()
            return []
    
    def _extract_entities_with_ontology(
        self,
        text: str,
        document_id: str,
        entity_types: List[str],
        document_type: str,
        chunk_id: Optional[str] = None,
    ) -> List[ExtractedEntity]:
        """Extract entities using ontology-guided prompt."""
        entities = self.entity_extractor.extract_with_types(
            text=text,
            entity_types=entity_types,
            document_id=document_id,
            chunk_id=chunk_id or f"{document_id}:chunk:0",
            sentence_idx=0,
        )
        
        return entities
    
    def _extract_relations_with_ontology(
        self,
        text: str,
        document_id: str,
        entities: List[ExtractedEntity],
        relationship_type_defs: List[Dict],
        document_type: str,
        chunk_id: Optional[str] = None,
    ) -> List[ExtractedRelation]:
        """Extract relations using ontology-guided prompt."""
        entities_data = [e.to_dict() for e in entities]
        
        relations = self.relation_extractor.extract_with_ontology(
            text=text,
            entities=entities_data,
            document_id=document_id,
            document_type=document_type,
            relationship_types=relationship_type_defs,
            chunk_id=chunk_id or f"{document_id}:chunk:0",
        )
        
        return relations

    def _run_post_processor(
        self,
        text: str,
        entities: List[ExtractedEntity],
        relations: List[ExtractedRelation],
        document_id: str,
    ) -> Tuple[List[ExtractedEntity], List[ExtractedRelation]]:
        """
        Run post-processor to catch relationships the LLM missed.

        This is defense-in-depth: LLM extracts most things, patterns catch the rest.
        Particularly important for INVESTED_IN relationships (portfolio companies).
        """
        try:
            post_processor = get_post_processor()

            # Convert entities to dict format for post-processor
            existing_entities = [e.to_dict() for e in entities]

            # Convert relations to dict format for post-processor
            existing_relationships = []
            for r in relations:
                existing_relationships.append({
                    "source_name": r.source_name,
                    "target_name": r.target_name,
                    "relationship_type": r.relation_type,
                    "relation_type": r.relation_type,
                })

            # Run post-processor
            result = post_processor.process(
                document_text=text,
                existing_entities=existing_entities,
                existing_relationships=existing_relationships
            )

            if not result.new_relationships and not result.new_entities:
                return [], []

            # Convert post-processor entities to ExtractedEntity objects
            new_entities = []
            for entity_dict in result.new_entities:
                import hashlib
                entity_id = hashlib.sha256(f"{entity_dict.get('name', '')}:{entity_dict.get('entity_type', 'UNKNOWN')}:{document_id}".encode()).hexdigest()[:16]
                entity = ExtractedEntity(
                    id=entity_id,
                    canonical_name=entity_dict.get("name", ""),
                    entity_type=entity_dict.get("entity_type", "UNKNOWN"),
                    properties={"extraction_source": "post_processor"},
                    source_span=entity_dict.get("name", ""),
                    source_document_id=document_id,
                    source_chunk_id=document_id,
                    source_sentence_idx=0,
                    confidence=entity_dict.get("confidence", 0.85),
                )
                new_entities.append(entity)

            # Convert post-processor relationships to ExtractedRelation objects
            new_relations = []
            for rel in result.new_relationships:
                import hashlib
                rel_id = hashlib.sha256(f"{rel.source_name}:{rel.relationship_type}:{rel.target_name}:{document_id}".encode()).hexdigest()[:16]
                relation = ExtractedRelation(
                    id=rel_id,
                    source_name=rel.source_name,
                    target_name=rel.target_name,
                    relation_type=rel.relationship_type,
                    confidence=rel.confidence,
                    source_document_id=document_id,
                    source_chunk_id=document_id,
                    source_span=rel.source_text,
                )
                new_relations.append(relation)

            logger.info(f"[PostProcessor] Found {len(new_entities)} new entities, "
                       f"{len(new_relations)} new relationships via pattern matching")

            return new_entities, new_relations

        except Exception as e:
            logger.warning(f"[PostProcessor] Failed to run post-processor: {e}")
            return [], []
    
    def _find_new_entity_types(
        self, 
        entities: List[ExtractedEntity],
        ontology: Any
    ) -> List[str]:
        """Find entity types not in the reference ontology."""
        existing_types = {et.name for et in ontology.entity_types}
        extracted_types = {e.entity_type.upper() for e in entities}
        return list(extracted_types - existing_types)
    
    def _find_new_relationship_types(
        self,
        relations: List[ExtractedRelation],
        ontology: Any
    ) -> List[str]:
        """Find relationship types not in the reference ontology."""
        existing_types = {rt.name for rt in ontology.relationship_types}
        extracted_types = {r.relation_type.upper() for r in relations}
        return list(extracted_types - existing_types)
    
    def _update_reference_ontology(
        self,
        document_type: str,
        new_entity_types: List[str],
        new_relationship_types: List[str],
        entities: List[ExtractedEntity],
        relations: List[ExtractedRelation],
    ) -> None:
        """Update reference ontology with discovered types."""
        entity_type_schemas = []
        for et_name in new_entity_types:
            examples = [e for e in entities if e.entity_type.upper() == et_name]
            definition = f"Entity type '{et_name}' discovered from document"
            if examples:
                definition = f"Entity type representing items like: {', '.join(e.canonical_name for e in examples[:3])}"
            entity_type_schemas.append(EntityTypeSchema(et_name, definition))
        
        rel_type_schemas = []
        for rt_name in new_relationship_types:
            examples = [r for r in relations if r.relation_type.upper() == rt_name]
            definition = f"Relationship type '{rt_name}' discovered from document"
            if examples:
                ex = examples[0]
                definition = f"Relationship between entities like '{ex.source_name}' and '{ex.target_name}'"
            rel_type_schemas.append(RelationshipTypeSchema(rt_name, definition, [], []))
        
        self.ontology_manager.update_ontology(
            document_type,
            entity_type_schemas,
            rel_type_schemas
        )
        
        logger.info(f"[OntologyCentricPipeline] Updated ontology for '{document_type}': "
                   f"+{len(new_entity_types)} entity types, +{len(new_relationship_types)} relationship types")
    
    def _resolve_entities_against_existing(
        self,
        entities: List[ExtractedEntity],
    ) -> Tuple[List[ExtractedEntity], Dict[str, str]]:
        """
        Resolve extracted entities against existing entities in the database.
        
        For each extracted entity, checks if a matching entity already exists
        (in STAGING or TRUSTED state) by NAME. If found, the extracted entity
        is skipped and existing entity ID is returned for relationship linking.
        
        This prevents duplicate entities with the same name regardless of type,
        ensuring entity names are globally unique within a tenant.
        
        Returns:
            Tuple of (deduplicated_entities, name_to_existing_id_map)
        """
        deduplicated = []
        seen_names = set()
        name_to_existing_id = {}
        resolved_count = 0
        
        existing_entities_cache = {}
        try:
            result = self.session.execute(sql_text("""
                SELECT id, LOWER(name) as name_lower 
                FROM entities 
                WHERE tenant_id = :tid 
                AND lifecycle_state IN ('STAGING', 'TRUSTED')
            """), {"tid": self.tenant_id})
            for row in result:
                name_key = row[1]
                if name_key not in existing_entities_cache:
                    existing_entities_cache[name_key] = str(row[0])
            logger.debug(f"[EntityResolution] Cached {len(existing_entities_cache)} existing entity names for dedup")
        except Exception as e:
            logger.warning(f"[EntityResolution] Failed to cache existing entities: {e}")
            try:
                self.session.rollback()
            except:
                pass
        
        for entity in entities:
            if not entity.canonical_name:
                continue
                
            normalized_name = entity.canonical_name.lower().strip()
            
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            
            if normalized_name in existing_entities_cache:
                existing_id = existing_entities_cache[normalized_name]
                name_to_existing_id[entity.canonical_name] = existing_id
                logger.debug(f"[EntityResolution] '{entity.canonical_name}' -> existing entity {existing_id}")
                resolved_count += 1
            else:
                deduplicated.append(entity)
        
        logger.info(f"[OntologyCentricPipeline] Entity resolution: {resolved_count} matched existing, "
                   f"{len(deduplicated)} new entities to stage")
        
        return deduplicated, name_to_existing_id
    
    def _stage_results(
        self,
        document_id: str,
        entities: List[ExtractedEntity],
        relations: List[ExtractedRelation],
    ) -> StagingResult:
        """Stage extracted entities and relations after entity resolution."""
        resolved_entities, name_to_existing_id = self._resolve_entities_against_existing(entities)
        
        for relation in relations:
            if relation.source_name in name_to_existing_id:
                relation.source_id = name_to_existing_id[relation.source_name]
            if relation.target_name in name_to_existing_id:
                relation.target_id = name_to_existing_id[relation.target_name]
        
        loader = StagingLoader(
            session=self.session,
            tenant_id=self.tenant_id,
            enable_deduplication=True,
        )

        # Component 2 hook: attach TypeDiscoveryAgent if the pipeline has one,
        # so it observes raw LLM relations before normalisation.
        agent = getattr(self, "_type_discovery_agent", None)
        if agent is not None:
            doc_type = getattr(self, "_current_document_type", "unknown")
            loader.set_type_discovery_agent(agent, document_type=doc_type)

        result = loader.load_all(resolved_entities, relations, commit=True)

        # After every N documents, run discovery and persist proposals so
        # newly discovered types are picked up by future extractions.
        if agent is not None:
            self._docs_since_discovery = getattr(self, "_docs_since_discovery", 0) + 1
            interval = getattr(self, "_discovery_interval", 5)
            auto_approve = getattr(self, "_discovery_auto_approve_confidence", 0.85)
            if self._docs_since_discovery >= interval:
                try:
                    proposals = agent.discover_types()
                    if proposals and self.tenant_id:
                        approved, pending = agent.persist_proposals(
                            proposals,
                            tenant_id=str(self.tenant_id),
                            auto_approve_confidence=auto_approve,
                        )
                        logger.info(
                            f"[TypeDiscoveryAgent] discovered {len(proposals)} type proposals: "
                            f"{approved} APPROVED, {pending} PENDING"
                        )
                except Exception as e:
                    logger.warning(f"[TypeDiscoveryAgent] discovery failed: {e}")
                self._docs_since_discovery = 0
        
        logger.info(f"[OntologyCentricPipeline] Staged: {result.entities_created} entities, "
                   f"{result.relations_created} relations (resolved {len(name_to_existing_id)} to existing)")
        
        return result


def run_ontology_centric_extraction(
    session: Session,
    tenant_id: str,
    text: str,
    document_id: str,
    filename: Optional[str] = None,
) -> OntologyCentricResult:
    """
    Convenience function to run ontology-centric extraction.
    
    Args:
        session: Database session
        tenant_id: Tenant ID
        text: Document text
        document_id: Document ID
        filename: Original filename
        
    Returns:
        OntologyCentricResult
    """
    pipeline = OntologyCentricPipeline(
        session=session,
        tenant_id=tenant_id,
        enable_canonicalization=True,
        auto_stage=True,
    )
    
    return pipeline.extract(
        text=text,
        document_id=document_id,
        filename=filename,
    )
