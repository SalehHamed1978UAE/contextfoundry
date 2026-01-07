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

from ..utils.logger import logger
from ..models.schema import DocumentChunk


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
    ):
        """
        Initialize the pipeline.
        
        Args:
            session: Database session
            tenant_id: Tenant ID for multi-tenancy
            model: LLM model to use
            enable_canonicalization: Whether to run canonicalization step
            auto_stage: Whether to automatically stage results
        """
        self.session = session
        self.tenant_id = tenant_id
        self.model = model
        self.enable_canonicalization = enable_canonicalization
        self.auto_stage = auto_stage
        
        self.ontology_manager = OntologyManager(session, tenant_id)
        self.canonicalizer = Canonicalizer(session, tenant_id) if enable_canonicalization else None
        
        self.entity_extractor = EntityExtractor(model=model, temperature=0.0)
        self.relation_extractor = RelationExtractor(model=model, temperature=0.0)
    
    def extract(
        self,
        text: str,
        document_id: str,
        filename: Optional[str] = None,
        document_type_override: Optional[str] = None,
    ) -> OntologyCentricResult:
        """
        Run full ontology-centric extraction pipeline.
        
        Args:
            text: Document text content
            document_id: Document ID
            filename: Original filename (for type inference)
            document_type_override: Override automatic classification
            
        Returns:
            OntologyCentricResult with all extraction data
        """
        chunks_stored = 0
        try:
            chunks_stored = self._store_document_chunks(text, document_id)
            logger.info(f"[OntologyCentricPipeline] Stored {chunks_stored} chunks for RAG retrieval")
            
            if document_type_override:
                document_type = document_type_override
            else:
                document_type = classify_with_fallback(text, filename)
            
            logger.info(f"[OntologyCentricPipeline] Document type: {document_type}")
            
            ontology = self.ontology_manager.get_or_create_ontology(document_type, text)
            
            entity_types = self.ontology_manager.get_entity_type_names(document_type)
            relationship_types = self.ontology_manager.get_relationship_type_names(document_type)
            
            entities = self._extract_entities_with_ontology(
                text, document_id, entity_types, document_type
            )
            
            relationship_type_defs = [rt.to_dict() for rt in ontology.relationship_types]
            
            if not relationship_type_defs:
                relationship_type_defs = [
                    {"name": "RELATED_TO", "definition": "General relationship between entities", "source_types": [], "target_types": []},
                    {"name": "PART_OF", "definition": "Entity is part of or belongs to another", "source_types": [], "target_types": []},
                    {"name": "WORKS_WITH", "definition": "Entity works with or collaborates with another", "source_types": [], "target_types": []},
                ]
                logger.warning(f"[OntologyCentricPipeline] No relationship types in ontology for {document_type}, using fallback")
            
            relations = self._extract_relations_with_ontology(
                text, document_id, entities, relationship_type_defs, document_type
            )
            
            canonical_triplets = []
            if self.enable_canonicalization and self.canonicalizer and relations:
                raw_triplets = convert_to_raw_triplets(entities, relations)
                canonical_triplets = self.canonicalizer.process_triplets(raw_triplets)
                
                for ct in canonical_triplets:
                    for rel in relations:
                        if rel.source_name == ct.subject and rel.target_name == ct.object:
                            rel.relation_type = ct.relationship_type
                            break
            
            new_entity_types = self._find_new_entity_types(entities, ontology)
            new_relationship_types = self._find_new_relationship_types(relations, ontology)
            
            if new_entity_types or new_relationship_types:
                self._update_reference_ontology(
                    document_type, 
                    new_entity_types, 
                    new_relationship_types,
                    entities,
                    relations
                )
            
            staging_result = None
            if self.auto_stage:
                staging_result = self._stage_results(document_id, entities, relations)
            
            return OntologyCentricResult(
                document_id=document_id,
                document_type=document_type,
                entities=entities,
                relations=relations,
                canonical_triplets=canonical_triplets,
                new_entity_types=new_entity_types,
                new_relationship_types=new_relationship_types,
                staging_result=staging_result,
                chunks_stored=chunks_stored,
                success=True,
            )
            
        except Exception as e:
            logger.error(f"[OntologyCentricPipeline] Extraction failed: {e}", exc_info=True)
            return OntologyCentricResult(
                document_id=document_id,
                document_type="unknown",
                entities=[],
                relations=[],
                canonical_triplets=[],
                new_entity_types=[],
                new_relationship_types=[],
                chunks_stored=chunks_stored,
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
    
    def _store_document_chunks(self, text: str, document_id: str) -> int:
        """Store document chunks for RAG retrieval.
        
        This ensures every document has searchable text chunks regardless
        of entity/relationship extraction success.
        
        Returns number of chunks stored.
        """
        try:
            existing_check = self.session.execute(
                sql_text("SELECT COUNT(*) FROM document_chunks WHERE document_id = :doc_id"),
                {"doc_id": document_id}
            ).scalar()
            
            if existing_check and existing_check > 0:
                logger.info(f"[OntologyCentricPipeline] Document {document_id} already has {existing_check} chunks, skipping")
                return existing_check
            
            chunks = self._chunk_text(text, chunk_size=2000, overlap=400)
            
            stored_count = 0
            for idx, (chunk_text, char_start, char_end) in enumerate(chunks):
                chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=document_id,
                    tenant_id=self.tenant_id,
                    chunk_index=idx,
                    text=chunk_text,
                    char_start=char_start,
                    char_end=char_end,
                    chunk_metadata={"source": "ontology_centric_pipeline"}
                )
                self.session.add(chunk)
                stored_count += 1
            
            self.session.flush()
            return stored_count
            
        except Exception as e:
            logger.error(f"[OntologyCentricPipeline] Failed to store chunks: {e}")
            self.session.rollback()
            return 0
    
    def _extract_entities_with_ontology(
        self,
        text: str,
        document_id: str,
        entity_types: List[str],
        document_type: str,
    ) -> List[ExtractedEntity]:
        """Extract entities using ontology-guided prompt."""
        entities = self.entity_extractor.extract_with_types(
            text=text,
            entity_types=entity_types,
            document_id=document_id,
            chunk_id=f"{document_id}:chunk:0",
            sentence_idx=0,
        )
        
        logger.info(f"[OntologyCentricPipeline] Extracted {len(entities)} entities "
                   f"using {len(entity_types)} ontology types for {document_type}")
        
        return entities
    
    def _extract_relations_with_ontology(
        self,
        text: str,
        document_id: str,
        entities: List[ExtractedEntity],
        relationship_type_defs: List[Dict],
        document_type: str,
    ) -> List[ExtractedRelation]:
        """Extract relations using ontology-guided prompt."""
        entities_data = [e.to_dict() for e in entities]
        
        relations = self.relation_extractor.extract_with_ontology(
            text=text,
            entities=entities_data,
            document_id=document_id,
            document_type=document_type,
            relationship_types=relationship_type_defs,
            chunk_id=f"{document_id}:chunk:0",
        )
        
        logger.info(f"[OntologyCentricPipeline] Extracted {len(relations)} relations "
                   f"using {len(relationship_type_defs)} ontology types for {document_type}")
        
        return relations
    
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
    
    def _stage_results(
        self,
        document_id: str,
        entities: List[ExtractedEntity],
        relations: List[ExtractedRelation],
    ) -> StagingResult:
        """Stage extracted entities and relations."""
        loader = StagingLoader(
            session=self.session,
            tenant_id=self.tenant_id,
            enable_deduplication=True,
        )
        
        result = loader.load_all(entities, relations, commit=True)
        
        logger.info(f"[OntologyCentricPipeline] Staged: {result.entities_created} entities, "
                   f"{result.relations_created} relations")
        
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
