"""
Extraction Pipeline for Context Foundry MVP2.
Coordinates entity and relation extraction with staging integration.
"""
from typing import Dict, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.orm import Session

from .entity_extractor import EntityExtractor, ExtractedEntity
from .relation_extractor import RelationExtractor, ExtractedRelation
from .duplicate_detector import DuplicateDetector
from .staging_loader import StagingLoader, StagingResult
from ..ingestion.ingestion_pipeline import IngestedDocument


@dataclass
class ExtractionResult:
    """Result of extraction from a document."""
    document_id: str
    document_title: str
    entities: List[ExtractedEntity]
    relations: List[ExtractedRelation]
    entity_count: int
    relation_count: int
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "document_id": self.document_id,
            "document_title": self.document_title,
            "entities": [e.to_dict() for e in self.entities],
            "relations": [r.to_dict() for r in self.relations],
            "entity_count": self.entity_count,
            "relation_count": self.relation_count,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class ExtractionStats:
    """Statistics for an extraction run."""
    documents_processed: int = 0
    documents_succeeded: int = 0
    documents_failed: int = 0
    total_entities: int = 0
    total_relations: int = 0
    entities_by_type: Dict[str, int] = field(default_factory=dict)
    relations_by_type: Dict[str, int] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "documents_processed": self.documents_processed,
            "documents_succeeded": self.documents_succeeded,
            "documents_failed": self.documents_failed,
            "total_entities": self.total_entities,
            "total_relations": self.total_relations,
            "entities_by_type": self.entities_by_type,
            "relations_by_type": self.relations_by_type,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": (
                (self.completed_at - self.started_at).total_seconds()
                if self.started_at and self.completed_at else None
            ),
        }


class ExtractionPipeline:
    """
    Extraction pipeline that coordinates entity and relation extraction.
    
    Features:
    - LLM-powered entity extraction
    - LLM-powered relation extraction
    - Confidence scoring
    - Provenance tracking
    - Duplicate detection
    """
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,  # Deterministic for consistent extraction
        on_document_processed: Optional[Callable[[ExtractionResult], None]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
    ):
        """
        Initialize the extraction pipeline.
        
        Args:
            model: OpenAI model to use for extraction
            temperature: Temperature for generation (0.0 = deterministic)
            on_document_processed: Callback after each document
            on_progress: Callback with (current, total) for progress
        """
        self.entity_extractor = EntityExtractor(
            model=model,
            temperature=temperature,
        )
        self.relation_extractor = RelationExtractor(
            model=model,
            temperature=temperature,
        )
        self.on_document_processed = on_document_processed
        self.on_progress = on_progress
    
    def extract_from_document(
        self,
        document: IngestedDocument,
    ) -> ExtractionResult:
        """
        Extract entities and relations from an ingested document.
        
        Args:
            document: IngestedDocument with chunks and sentences
            
        Returns:
            ExtractionResult with extracted entities and relations
        """
        try:
            chunks_data = [c.to_dict() for c in document.chunks]
            
            entities = self.entity_extractor.extract_from_chunks(
                chunks=chunks_data,
                document_id=document.document.id,
            )
            
            entities_data = [e.to_dict() for e in entities]
            
            relations = self.relation_extractor.extract_from_chunks(
                chunks=chunks_data,
                entities=entities_data,
                document_id=document.document.id,
            )
            
            return ExtractionResult(
                document_id=document.document.id,
                document_title=document.document.title,
                entities=entities,
                relations=relations,
                entity_count=len(entities),
                relation_count=len(relations),
                success=True,
            )
            
        except Exception as e:
            return ExtractionResult(
                document_id=document.document.id,
                document_title=document.document.title,
                entities=[],
                relations=[],
                entity_count=0,
                relation_count=0,
                success=False,
                error=str(e),
            )
    
    def extract_from_text(
        self,
        text: str,
        document_id: str = "inline",
        document_title: str = "Inline Text",
    ) -> ExtractionResult:
        """
        Extract entities and relations from raw text.
        
        Args:
            text: Text to extract from
            document_id: ID to assign to this document
            document_title: Title for this document
            
        Returns:
            ExtractionResult with extracted entities and relations
        """
        try:
            entities = self.entity_extractor.extract_from_text(
                text=text,
                document_id=document_id,
                chunk_id=f"{document_id}:chunk:0",
                sentence_idx=0,
            )
            
            entities_data = [e.to_dict() for e in entities]
            
            relations = self.relation_extractor.extract_from_text(
                text=text,
                entities=entities_data,
                document_id=document_id,
                chunk_id=f"{document_id}:chunk:0",
            )
            
            return ExtractionResult(
                document_id=document_id,
                document_title=document_title,
                entities=entities,
                relations=relations,
                entity_count=len(entities),
                relation_count=len(relations),
                success=True,
            )
            
        except Exception as e:
            return ExtractionResult(
                document_id=document_id,
                document_title=document_title,
                entities=[],
                relations=[],
                entity_count=0,
                relation_count=0,
                success=False,
                error=str(e),
            )
    
    def extract_with_fallback(
        self,
        text: str,
        document_id: str = "inline",
        document_title: str = "Inline Text",
    ) -> ExtractionResult:
        """
        Extract entities using automatic domain detection with semantic routing.
        
        Uses classifier to detect document domain, combines Core Foundation types
        with domain-specific types for comprehensive extraction.
        
        Args:
            text: Text to extract from
            document_id: ID to assign to this document
            document_title: Title for this document
            
        Returns:
            ExtractionResult with extracted entities and relations
        """
        try:
            from brain.classifier import classify_and_get_types
            
            domain, confidence, entity_types = classify_and_get_types(text)
            
            print(f"[ExtractionPipeline] Domain: {domain} (confidence: {confidence:.3f}), using {len(entity_types)} types")
            
            entities = self.entity_extractor.extract_with_types(
                text=text,
                entity_types=entity_types,
                document_id=document_id,
                chunk_id=f"{document_id}:chunk:0",
                sentence_idx=0,
            )
            
            entities_data = [e.to_dict() for e in entities]
            
            relations = self.relation_extractor.extract_from_text(
                text=text,
                entities=entities_data,
                document_id=document_id,
                chunk_id=f"{document_id}:chunk:0",
            )
            
            return ExtractionResult(
                document_id=document_id,
                document_title=document_title,
                entities=entities,
                relations=relations,
                entity_count=len(entities),
                relation_count=len(relations),
                success=True,
            )
            
        except Exception as e:
            print(f"[ExtractionPipeline] Domain classification failed: {e}, using Core Foundation fallback")
            
            try:
                entities = self.entity_extractor.extract_with_core_foundation(
                    text=text,
                    document_id=document_id,
                    chunk_id=f"{document_id}:chunk:0",
                    sentence_idx=0,
                )
                
                entities_data = [e.to_dict() for e in entities]
                
                relations = self.relation_extractor.extract_from_text(
                    text=text,
                    entities=entities_data,
                    document_id=document_id,
                    chunk_id=f"{document_id}:chunk:0",
                )
                
                return ExtractionResult(
                    document_id=document_id,
                    document_title=document_title,
                    entities=entities,
                    relations=relations,
                    entity_count=len(entities),
                    relation_count=len(relations),
                    success=True,
                )
                
            except Exception as fallback_error:
                return ExtractionResult(
                    document_id=document_id,
                    document_title=document_title,
                    entities=[],
                    relations=[],
                    entity_count=0,
                    relation_count=0,
                    success=False,
                    error=str(fallback_error),
                )
    
    def extract_from_documents(
        self,
        documents: List[IngestedDocument],
    ) -> Tuple[List[ExtractionResult], ExtractionStats]:
        """
        Extract from multiple ingested documents.
        
        Args:
            documents: List of IngestedDocument objects
            
        Returns:
            Tuple of (results, stats)
        """
        stats = ExtractionStats(started_at=datetime.now())
        results = []
        total = len(documents)
        
        for i, document in enumerate(documents):
            stats.documents_processed += 1
            
            result = self.extract_from_document(document)
            results.append(result)
            
            if result.success:
                stats.documents_succeeded += 1
                stats.total_entities += result.entity_count
                stats.total_relations += result.relation_count
                
                for entity in result.entities:
                    entity_type = entity.entity_type
                    stats.entities_by_type[entity_type] = (
                        stats.entities_by_type.get(entity_type, 0) + 1
                    )
                
                for relation in result.relations:
                    relation_type = relation.relation_type
                    stats.relations_by_type[relation_type] = (
                        stats.relations_by_type.get(relation_type, 0) + 1
                    )
            else:
                stats.documents_failed += 1
                stats.errors.append(result.error or "Unknown error")
            
            if self.on_document_processed:
                self.on_document_processed(result)
            
            if self.on_progress:
                self.on_progress(i + 1, total)
        
        stats.completed_at = datetime.now()
        return results, stats
    
    def merge_results(
        self,
        results: List[ExtractionResult],
        session: Optional[Session] = None,
    ) -> Tuple[List[ExtractedEntity], List[ExtractedRelation]]:
        """
        Merge extraction results from multiple documents.
        
        Uses DuplicateDetector for smart deduplication with fuzzy matching.
        
        Args:
            results: List of ExtractionResult objects
            session: Optional database session for dedup against existing entities
            
        Returns:
            Tuple of (deduplicated_entities, deduplicated_relations)
        """
        all_entities = []
        all_relations = []
        
        for result in results:
            if result.success:
                all_entities.extend(result.entities)
                all_relations.extend(result.relations)
        
        if session:
            detector = DuplicateDetector(session, similarity_threshold=0.8)
            deduplicated_entities = detector.deduplicate_entities(
                all_entities, 
                merge_strategy="highest_confidence"
            )
        else:
            entity_map = {}
            for entity in all_entities:
                key = (entity.entity_type, entity.canonical_name.lower())
                if key not in entity_map:
                    entity_map[key] = entity
                elif entity.confidence > entity_map[key].confidence:
                    entity_map[key] = entity
            deduplicated_entities = list(entity_map.values())
        
        relation_map = {}
        for relation in all_relations:
            key = (
                relation.relation_type,
                relation.source_name.lower(),
                relation.target_name.lower(),
            )
            if key not in relation_map:
                relation_map[key] = relation
            elif relation.confidence > relation_map[key].confidence:
                relation_map[key] = relation
        
        return deduplicated_entities, list(relation_map.values())
    
    def run(
        self,
        documents: List[IngestedDocument],
        session: Session,
        enable_deduplication: bool = True,
        commit: bool = True,
    ) -> Tuple[ExtractionStats, StagingResult]:
        """
        Run the full extraction pipeline with staging integration.
        
        This is the main entry point for the extraction pipeline that:
        1. Extracts entities and relations from documents
        2. Deduplicates extracted data
        3. Loads into STAGING layer with provenance
        
        Args:
            documents: List of IngestedDocument objects to process
            session: Database session for staging
            enable_deduplication: Whether to deduplicate entities
            commit: Whether to commit the transaction
            
        Returns:
            Tuple of (ExtractionStats, StagingResult)
        """
        results, stats = self.extract_from_documents(documents)
        
        merged_entities, merged_relations = self.merge_results(
            results, 
            session if enable_deduplication else None
        )
        
        loader = StagingLoader(
            session, 
            enable_deduplication=enable_deduplication,
            similarity_threshold=0.8
        )
        staging_result = loader.load_all(
            entities=merged_entities,
            relations=merged_relations,
            commit=commit,
        )
        
        return stats, staging_result
    
    def run_from_text(
        self,
        text: str,
        session: Session,
        document_id: str = "inline",
        document_title: str = "Inline Text",
        enable_deduplication: bool = True,
        commit: bool = True,
    ) -> Tuple[ExtractionResult, StagingResult]:
        """
        Extract from text and load into STAGING layer.
        
        Args:
            text: Text to extract from
            session: Database session for staging
            document_id: ID to assign to this document
            document_title: Title for this document
            enable_deduplication: Whether to deduplicate entities
            commit: Whether to commit the transaction
            
        Returns:
            Tuple of (ExtractionResult, StagingResult)
        """
        result = self.extract_from_text(
            text=text,
            document_id=document_id,
            document_title=document_title,
        )
        
        loader = StagingLoader(
            session,
            enable_deduplication=enable_deduplication,
            similarity_threshold=0.8
        )
        staging_result = loader.load_all(
            entities=result.entities,
            relations=result.relations,
            commit=commit,
        )
        
        return result, staging_result
