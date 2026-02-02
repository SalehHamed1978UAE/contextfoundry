"""
Knowledge Graph Ingestor

Phase 4 of the extraction pipeline: Ingests validated consensus outputs
into the knowledge graph database with proper entity resolution.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Tuple, Optional, Any
from datetime import datetime
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..models.schema import Entity, Relationship, LifecycleState, ValidationStatus, EvidenceRecord, FactType
from ..ontology.schema import EntityType, RelationshipType
from ..memory.episodic import openai_embedding
from ..utils.logger import logger
from .entity_resolver import CanonicalEntity, CanonicalRelationship, ConsensusOutput
from .consensus_validator import ValidationReport


@dataclass
class IngestionResult:
    """Result of a KG ingestion operation."""
    entities_created: int
    entities_updated: int
    relationships_created: int
    relationships_updated: int
    errors: List[str]
    warnings: List[str]
    entity_id_map: Dict[str, str]
    ingested_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities_created": self.entities_created,
            "entities_updated": self.entities_updated,
            "relationships_created": self.relationships_created,
            "relationships_updated": self.relationships_updated,
            "errors": self.errors,
            "warnings": self.warnings,
            "entity_id_map": self.entity_id_map,
            "ingested_at": self.ingested_at.isoformat(),
        }


class KGIngestor:
    """Ingests validated consensus outputs into the knowledge graph."""
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def _create_evidence_record(
        self,
        fact_type: FactType,
        fact_id: uuid.UUID,
        evidence_text: str,
        source_document_id: Optional[str] = None
    ) -> Optional[EvidenceRecord]:
        """Create an evidence record linking a fact to its supporting source text."""
        if not evidence_text or not evidence_text.strip():
            return None
        
        try:
            evidence = EvidenceRecord(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(self.tenant_id) if isinstance(self.tenant_id, str) else self.tenant_id,
                fact_type=fact_type,
                fact_id=fact_id,
                evidence_text=evidence_text.strip()[:5000],
                source_document_id=source_document_id
            )
            self.session.add(evidence)
            return evidence
        except Exception as e:
            logger.debug(f"[KGIngestor] Failed to create evidence record: {e}")
            return None
    
    def ingest(
        self,
        consensus: ConsensusOutput,
        validation_report: Optional[ValidationReport] = None,
        lifecycle_state: LifecycleState = LifecycleState.STAGING,
        source_document_id: Optional[str] = None,
    ) -> IngestionResult:
        """
        Ingest a validated consensus output into the KG.
        
        Args:
            consensus: The consensus output to ingest
            validation_report: Optional validation report for metadata
            lifecycle_state: Initial lifecycle state for new entities
            source_document_id: Document ID for source tracking
        
        Returns:
            IngestionResult with counts and entity ID mapping
        """
        result = IngestionResult(
            entities_created=0,
            entities_updated=0,
            relationships_created=0,
            relationships_updated=0,
            errors=[],
            warnings=[],
            entity_id_map={},
        )
        
        for entity in consensus.entities:
            try:
                entity_id = self._upsert_entity(
                    entity,
                    lifecycle_state,
                    source_document_id,
                    result,
                )
                result.entity_id_map[entity.canonical_name] = str(entity_id)
            except Exception as e:
                result.errors.append(f"Failed to ingest entity '{entity.canonical_name}': {e}")
        
        for rel in consensus.relationships:
            try:
                self._upsert_relationship(
                    rel,
                    result.entity_id_map,
                    lifecycle_state,
                    source_document_id,
                    result,
                )
            except Exception as e:
                result.errors.append(
                    f"Failed to ingest relationship '{rel.source_entity}' -> '{rel.target_entity}': {e}"
                )
        
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            result.errors.append(f"Failed to commit transaction: {e}")
        
        return result
    
    def _upsert_entity(
        self,
        entity: CanonicalEntity,
        lifecycle_state: LifecycleState,
        source_document_id: Optional[str],
        result: IngestionResult,
    ) -> uuid.UUID:
        """Upsert an entity (update existing or create new)."""
        existing = self.session.query(Entity).filter(
            and_(
                Entity.tenant_id == self.tenant_id,
                Entity.name == entity.canonical_name,
                Entity.entity_type == entity.entity_type.value,
            )
        ).first()
        
        if existing:
            self._update_entity(existing, entity, source_document_id)
            result.entities_updated += 1
            return existing.id
        else:
            new_entity = self._create_entity(
                entity, lifecycle_state, source_document_id
            )
            self.session.add(new_entity)
            self.session.flush()
            
            evidence_parts = [f"Entity: {entity.canonical_name}", f"Type: {entity.entity_type.value}"]
            if entity.name_variants:
                evidence_parts.append(f"Variants: {', '.join(entity.name_variants[:5])}")
            if entity.properties:
                prop_strs = [f"{k}={v}" for k, v in list(entity.properties.items())[:5] if v]
                if prop_strs:
                    evidence_parts.append(f"Properties: {'; '.join(prop_strs)}")
            evidence_text = " | ".join(evidence_parts)
            
            if entity.source_documents:
                for source_doc in entity.source_documents:
                    self._create_evidence_record(
                        fact_type=FactType.ENTITY,
                        fact_id=new_entity.id,
                        evidence_text=evidence_text,
                        source_document_id=source_doc
                    )
            else:
                logger.debug(f"[KGIngestor] No source documents for entity '{entity.canonical_name}', creating single evidence record")
                self._create_evidence_record(
                    fact_type=FactType.ENTITY,
                    fact_id=new_entity.id,
                    evidence_text=evidence_text,
                    source_document_id=source_document_id
                )
            
            result.entities_created += 1
            return new_entity.id
    
    def _create_entity(
        self,
        entity: CanonicalEntity,
        lifecycle_state: LifecycleState,
        source_document_id: Optional[str],
    ) -> Entity:
        """Create a new Entity from a CanonicalEntity."""
        properties = dict(entity.properties)
        properties["_source_models"] = entity.source_models
        properties["_name_variants"] = entity.name_variants
        properties["_consensus_metadata"] = entity.consensus_metadata
        
        name_embedding = None
        try:
            name_embedding = openai_embedding(entity.canonical_name)
        except Exception as e:
            logger.warning(f"Failed to compute embedding for entity '{entity.canonical_name}': {e}")
        
        return Entity(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            name=entity.canonical_name,
            entity_type=entity.entity_type.value,
            lifecycle_state=lifecycle_state,
            validation_status=ValidationStatus.VALID,
            properties=properties,
            confidence=entity.confidence,
            source_document_id=source_document_id or (
                entity.source_documents[0] if entity.source_documents else None
            ),
            extraction_method="multi_model_consensus",
            extracted_at=datetime.utcnow(),
            name_embedding=name_embedding,
        )
    
    def _update_entity(
        self,
        existing: Entity,
        entity: CanonicalEntity,
        source_document_id: Optional[str],
    ) -> None:
        """Update an existing Entity with new data from CanonicalEntity."""
        existing_props = existing.properties or {}
        new_props = dict(entity.properties)
        
        for key, value in new_props.items():
            if value is not None:
                existing_props[key] = value
        
        existing_props["_source_models"] = list(set(
            existing_props.get("_source_models", []) + entity.source_models
        ))
        existing_props["_name_variants"] = list(set(
            existing_props.get("_name_variants", []) + entity.name_variants
        ))
        existing_props["_consensus_metadata"] = entity.consensus_metadata
        existing_props["_last_extraction"] = datetime.utcnow().isoformat()
        
        existing.properties = existing_props
        existing.confidence = max(existing.confidence or 0, entity.confidence)
        existing.updated_at = datetime.utcnow()
    
    def _upsert_relationship(
        self,
        rel: CanonicalRelationship,
        entity_id_map: Dict[str, str],
        lifecycle_state: LifecycleState,
        source_document_id: Optional[str],
        result: IngestionResult,
    ) -> Optional[uuid.UUID]:
        """Upsert a relationship (update existing or create new)."""
        source_id = entity_id_map.get(rel.source_entity)
        target_id = entity_id_map.get(rel.target_entity)
        
        if not source_id:
            source_entity = self._find_entity_by_name(rel.source_entity)
            if source_entity:
                source_id = str(source_entity.id)
                entity_id_map[rel.source_entity] = source_id
            else:
                result.warnings.append(
                    f"Source entity '{rel.source_entity}' not found for relationship"
                )
                return None
        
        if not target_id:
            target_entity = self._find_entity_by_name(rel.target_entity)
            if target_entity:
                target_id = str(target_entity.id)
                entity_id_map[rel.target_entity] = target_id
            else:
                result.warnings.append(
                    f"Target entity '{rel.target_entity}' not found for relationship"
                )
                return None
        
        existing = self.session.query(Relationship).filter(
            and_(
                Relationship.tenant_id == self.tenant_id,
                Relationship.source_id == source_id,
                Relationship.target_id == target_id,
                Relationship.relationship_type == rel.relationship_type.value,
            )
        ).first()
        
        if existing:
            self._update_relationship(existing, rel, source_document_id)
            result.relationships_updated += 1
            return existing.id
        else:
            new_rel = self._create_relationship(
                rel, source_id, target_id, lifecycle_state, source_document_id
            )
            self.session.add(new_rel)
            self.session.flush()
            
            if rel.evidence:
                for evidence_text in rel.evidence:
                    self._create_evidence_record(
                        fact_type=FactType.RELATIONSHIP,
                        fact_id=new_rel.id,
                        evidence_text=evidence_text,
                        source_document_id=source_document_id
                    )
            else:
                fallback_evidence = f"Relationship: {rel.source_entity} --[{rel.relationship_type.value}]--> {rel.target_entity}"
                logger.debug(f"[KGIngestor] No evidence for relationship, using fallback: {fallback_evidence[:100]}")
                self._create_evidence_record(
                    fact_type=FactType.RELATIONSHIP,
                    fact_id=new_rel.id,
                    evidence_text=fallback_evidence,
                    source_document_id=source_document_id
                )
            
            result.relationships_created += 1
            return new_rel.id
    
    def _create_relationship(
        self,
        rel: CanonicalRelationship,
        source_id: str,
        target_id: str,
        lifecycle_state: LifecycleState,
        source_document_id: Optional[str],
    ) -> Relationship:
        """Create a new Relationship from a CanonicalRelationship."""
        properties = dict(rel.properties)
        properties["_source_models"] = rel.source_models
        properties["_consensus_metadata"] = rel.consensus_metadata
        
        evidence_text = "\n".join(rel.evidence) if rel.evidence else None
        
        return Relationship(
            id=uuid.uuid4(),
            tenant_id=self.tenant_id,
            source_id=source_id,
            target_id=target_id,
            relationship_type=rel.relationship_type.value,
            lifecycle_state=lifecycle_state,
            validation_status=ValidationStatus.VALID,
            properties=properties,
            confidence=rel.confidence,
            source_document_id=source_document_id,
            source_sentence=evidence_text,
            extracted_at=datetime.utcnow(),
        )
    
    def _update_relationship(
        self,
        existing: Relationship,
        rel: CanonicalRelationship,
        source_document_id: Optional[str],
    ) -> None:
        """Update an existing Relationship with new data."""
        existing_props = existing.properties or {}
        new_props = dict(rel.properties)
        
        for key, value in new_props.items():
            if value is not None:
                existing_props[key] = value
        
        existing_props["_source_models"] = list(set(
            existing_props.get("_source_models", []) + rel.source_models
        ))
        existing_props["_consensus_metadata"] = rel.consensus_metadata
        existing_props["_last_extraction"] = datetime.utcnow().isoformat()
        
        existing.properties = existing_props
        existing.confidence = max(existing.confidence or 0, rel.confidence)
        existing.updated_at = datetime.utcnow()
        
        if rel.evidence:
            existing_evidence = existing.source_sentence or ""
            new_evidence = "\n".join(rel.evidence)
            if new_evidence not in existing_evidence:
                existing.source_sentence = (
                    existing_evidence + "\n" + new_evidence
                ).strip()
    
    def _find_entity_by_name(self, name: str) -> Optional[Entity]:
        """Find an entity by name in the current tenant."""
        return self.session.query(Entity).filter(
            and_(
                Entity.tenant_id == self.tenant_id,
                Entity.name == name,
            )
        ).first()


def run_full_pipeline(
    session: Session,
    tenant_id: str,
    extractions: Dict[str, Any],
    document_path: str = "",
    source_document_id: Optional[str] = None,
) -> Tuple[ConsensusOutput, ValidationReport, IngestionResult]:
    """
    Run the full extraction-to-ingestion pipeline.
    
    Args:
        session: Database session
        tenant_id: Tenant ID for the KG
        extractions: Dict mapping model_name -> ExtractionOutput
        document_path: Path to the source document
        source_document_id: Document ID for source tracking
    
    Returns:
        Tuple of (ConsensusOutput, ValidationReport, IngestionResult)
    """
    from .entity_resolver import run_consensus
    from .consensus_validator import validate_consensus, resolve_conflicts
    
    consensus = run_consensus(extractions, document_path)
    
    report = validate_consensus(consensus)
    
    if report.conflicts:
        consensus = resolve_conflicts(consensus, report)
        report = validate_consensus(consensus)
    
    ingestor = KGIngestor(session, tenant_id)
    result = ingestor.ingest(
        consensus,
        validation_report=report,
        lifecycle_state=LifecycleState.STAGING,
        source_document_id=source_document_id,
    )
    
    return consensus, report, result
