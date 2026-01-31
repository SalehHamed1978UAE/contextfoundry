"""
ConstrainedExtractor - Ontology-constrained extraction pipeline.

Uses SchemaPromptGenerator to build dynamic prompts and validates all extractions
against the database-backed ontology before writing to entities_v2.
"""

import json
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from uuid import UUID
import psycopg2
from psycopg2.extras import RealDictCursor

from openai import OpenAI

try:
    from replit.ai.config import AI_INTEGRATIONS_OPENAI_API_KEY, AI_INTEGRATIONS_OPENAI_BASE_URL
except ImportError:
    AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
    AI_INTEGRATIONS_OPENAI_BASE_URL = None

from .prompt_generator import SchemaPromptGenerator
from .repository import OntologyRepository, get_ontology_repository
from .models import (
    EntityExtraction,
    RelationshipExtraction,
    ExtractionResult,
    OntologySnapshot
)
from ..config.feature_flags import (
    get_extraction_mode,
    ExtractionMode,
    should_write_shadow
)
from ..monitoring.shadow_metrics import ShadowMetrics
from ..utils.logger import logger


class ConstrainedExtractor:
    """
    Ontology-constrained entity and relationship extractor.
    
    This is the Session 2 implementation that:
    1. Queries ontology_types at extraction time (no hardcoded types)
    2. Validates all extractions against the ontology before accepting
    3. Rejects entities with invalid types (like CREATURE)
    4. Writes validated entities to entities_v2 shadow table
    5. Logs extraction events for audit trail
    """
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,
        max_retries: int = 3,
        repository: Optional[OntologyRepository] = None,
        prompt_generator: Optional[SchemaPromptGenerator] = None,
        database_url: Optional[str] = None
    ):
        """
        Initialize the constrained extractor.
        
        Args:
            model: OpenAI model to use
            temperature: Temperature for generation (0.0 = deterministic)
            max_retries: Maximum retries on API errors
            repository: OntologyRepository instance
            prompt_generator: SchemaPromptGenerator instance
            database_url: Database URL for writing results
        """
        self.client = OpenAI(
            api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
            base_url=AI_INTEGRATIONS_OPENAI_BASE_URL,
        )
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self._repository = repository
        self._prompt_generator = prompt_generator
        self.database_url = database_url or os.environ.get("DATABASE_URL")
    
    @property
    def repository(self) -> OntologyRepository:
        """Get ontology repository (lazy initialization)."""
        if self._repository is None:
            self._repository = get_ontology_repository()
        return self._repository
    
    @property
    def prompt_generator(self) -> SchemaPromptGenerator:
        """Get prompt generator (lazy initialization)."""
        if self._prompt_generator is None:
            self._prompt_generator = SchemaPromptGenerator(repository=self.repository)
        return self._prompt_generator
    
    def extract_entities(
        self,
        text: str,
        document_id: Optional[UUID] = None
    ) -> ExtractionResult:
        """
        Extract entities from text with ontology validation.
        
        Args:
            text: Text to extract entities from
            document_id: Optional source document ID for provenance
        
        Returns:
            ExtractionResult with validated entities and rejected items
        """
        result = ExtractionResult(
            extraction_started_at=datetime.utcnow(),
            model_used=self.model
        )
        
        try:
            snapshot = self.repository.get_snapshot()
            valid_types = snapshot.get_valid_type_names()
            
            prompt = self.prompt_generator.build_entity_extraction_prompt(text)
            system_prompt = self.prompt_generator.build_system_prompt()
            
            logger.info(f"Extracting entities with {len(valid_types)} valid types from ontology")
            
            raw_extractions = self._call_llm(system_prompt, prompt)
            
            for raw in raw_extractions:
                raw_entity_type = raw.get("entity_type", "").strip()
                
                normalized_type = snapshot.normalize_type_name(raw_entity_type)
                
                if not normalized_type:
                    result.rejected_entities.append({
                        "raw": raw,
                        "reason": f"Invalid entity_type '{raw_entity_type}' not in ontology",
                        "valid_types": list(valid_types)
                    })
                    result.validation_errors.append(
                        f"Rejected entity '{raw.get('canonical_name', 'unknown')}' - "
                        f"type '{raw_entity_type}' is not defined in the ontology"
                    )
                    continue
                
                try:
                    type_obj = snapshot.get_type_by_name(normalized_type)
                    entity = EntityExtraction(
                        entity_type=normalized_type,
                        canonical_name=raw.get("canonical_name", ""),
                        properties=raw.get("properties", {}),
                        source_span=raw.get("source_span", ""),
                        confidence=float(raw.get("confidence", 0.8)),
                        entity_type_id=type_obj.id if type_obj else None
                    )
                    result.entities.append(entity)
                    
                except Exception as e:
                    result.rejected_entities.append({
                        "raw": raw,
                        "reason": f"Validation error: {str(e)}"
                    })
                    result.validation_errors.append(str(e))
            
            result.extraction_completed_at = datetime.utcnow()
            
            logger.info(
                f"Entity extraction complete: "
                f"{len(result.entities)} validated, "
                f"{len(result.rejected_entities)} rejected"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            result.validation_errors.append(f"Extraction failed: {str(e)}")
            result.extraction_completed_at = datetime.utcnow()
            return result
    
    def extract_relationships(
        self,
        text: str,
        entities: List[EntityExtraction],
        document_id: Optional[UUID] = None
    ) -> ExtractionResult:
        """
        Extract relationships from text with ontology validation.
        
        Args:
            text: Text to extract relationships from
            entities: List of already-extracted entities
            document_id: Optional source document ID for provenance
        
        Returns:
            ExtractionResult with validated relationships and rejected items
        """
        result = ExtractionResult(
            extraction_started_at=datetime.utcnow(),
            model_used=self.model
        )
        
        if not entities:
            logger.warning("No entities provided for relationship extraction")
            result.extraction_completed_at = datetime.utcnow()
            return result
        
        try:
            snapshot = self.repository.get_snapshot()
            
            entities_str = "\n".join([
                f"- {e.canonical_name} ({e.entity_type})"
                for e in entities
            ])
            entity_lookup = {e.canonical_name: e for e in entities}
            
            prompt = self.prompt_generator.build_relationship_extraction_prompt(
                text, entities_str
            )
            system_prompt = self.prompt_generator.build_system_prompt()
            
            valid_relation_names = set(r.relation_type for r in snapshot.relations)
            logger.info(f"Extracting relationships with {len(valid_relation_names)} valid relation types")
            
            raw_extractions = self._call_llm(system_prompt, prompt)
            
            for raw in raw_extractions:
                relation_type = raw.get("relation_type", "").strip()
                source_name = raw.get("source_name", "").strip()
                target_name = raw.get("target_name", "").strip()
                
                if relation_type not in valid_relation_names:
                    result.rejected_relationships.append({
                        "raw": raw,
                        "reason": f"Invalid relation_type '{relation_type}' not in ontology"
                    })
                    result.validation_errors.append(
                        f"Rejected relationship - type '{relation_type}' is not defined in the ontology"
                    )
                    continue
                
                if source_name not in entity_lookup:
                    result.rejected_relationships.append({
                        "raw": raw,
                        "reason": f"Source entity '{source_name}' not found in known entities"
                    })
                    continue
                
                if target_name not in entity_lookup:
                    result.rejected_relationships.append({
                        "raw": raw,
                        "reason": f"Target entity '{target_name}' not found in known entities"
                    })
                    continue
                
                source_entity = entity_lookup[source_name]
                target_entity = entity_lookup[target_name]
                
                valid_relations = snapshot.get_relations_for_types(
                    source_entity.entity_type,
                    target_entity.entity_type
                )
                matching_relation = next(
                    (r for r in valid_relations if r.relation_type == relation_type),
                    None
                )
                
                if not matching_relation:
                    result.rejected_relationships.append({
                        "raw": raw,
                        "reason": (
                            f"Relation '{relation_type}' not allowed between "
                            f"{source_entity.entity_type} and {target_entity.entity_type}"
                        )
                    })
                    result.validation_errors.append(
                        f"Rejected relationship '{relation_type}' - "
                        f"not valid between {source_entity.entity_type} → {target_entity.entity_type}"
                    )
                    continue
                
                try:
                    relationship = RelationshipExtraction(
                        relation_type=relation_type,
                        source_name=source_name,
                        target_name=target_name,
                        source_span=raw.get("source_span", ""),
                        confidence=float(raw.get("confidence", 0.8)),
                        relation_type_id=matching_relation.id if matching_relation else None
                    )
                    result.relationships.append(relationship)
                    
                except Exception as e:
                    result.rejected_relationships.append({
                        "raw": raw,
                        "reason": f"Validation error: {str(e)}"
                    })
                    result.validation_errors.append(str(e))
            
            result.extraction_completed_at = datetime.utcnow()
            
            logger.info(
                f"Relationship extraction complete: "
                f"{len(result.relationships)} validated, "
                f"{len(result.rejected_relationships)} rejected"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Relationship extraction failed: {e}")
            result.validation_errors.append(f"Extraction failed: {str(e)}")
            result.extraction_completed_at = datetime.utcnow()
            return result
    
    def extract_all(
        self,
        text: str,
        document_id: Optional[UUID] = None,
        write_to_shadow: bool = True
    ) -> Tuple[ExtractionResult, ExtractionResult]:
        """
        Extract both entities and relationships from text.
        
        Args:
            text: Text to extract from
            document_id: Optional source document ID
            write_to_shadow: If True and shadow mode enabled, write to entities_v2
        
        Returns:
            Tuple of (entity_result, relationship_result)
        """
        logger.info(f"Starting constrained extraction (mode: {get_extraction_mode().value})")
        
        entity_result = self.extract_entities(text, document_id)
        relationship_result = self.extract_relationships(
            text, entity_result.entities, document_id
        )
        
        if write_to_shadow and should_write_shadow():
            self._write_to_shadow_table(
                entity_result, relationship_result, text, document_id
            )
        
        self._log_extraction_event(
            entity_result, relationship_result, text, document_id
        )
        
        return entity_result, relationship_result
    
    def _call_llm(self, system_prompt: str, user_prompt: str) -> List[Dict[str, Any]]:
        """Call LLM and parse JSON response."""
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=self.temperature
                )
                
                content = response.choices[0].message.content
                if content:
                    content = content.strip()
                    if content.startswith("```"):
                        lines = content.split("\n")
                        content = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
                    
                    return json.loads(content)
                return []
                
            except json.JSONDecodeError as e:
                logger.warning(f"JSON parse error on attempt {attempt + 1}: {e}")
                if attempt == self.max_retries - 1:
                    raise
            except Exception as e:
                logger.warning(f"LLM call failed on attempt {attempt + 1}: {e}")
                if attempt == self.max_retries - 1:
                    raise
        
        return []
    
    def _write_to_shadow_table(
        self,
        entity_result: ExtractionResult,
        relationship_result: ExtractionResult,
        text: str,
        document_id: Optional[UUID]
    ):
        """Write validated entities to entities_v2 shadow table."""
        if not self.database_url:
            logger.warning("No database URL configured for shadow writes")
            return
        
        conn = None
        try:
            conn = psycopg2.connect(self.database_url)
            with conn.cursor() as cur:
                for entity in entity_result.entities:
                    cur.execute("""
                        INSERT INTO entities_v2 (
                            name, entity_type, entity_type_id, 
                            properties, confidence, lifecycle,
                            provenance, corroboration_count
                        ) VALUES (
                            %s, %s, %s, %s, %s, 'STAGING',
                            %s, 1
                        )
                        ON CONFLICT (name, entity_type) DO UPDATE
                        SET corroboration_count = entities_v2.corroboration_count + 1,
                            confidence = GREATEST(entities_v2.confidence, EXCLUDED.confidence)
                    """, (
                        entity.canonical_name,
                        entity.entity_type,
                        str(entity.entity_type_id) if entity.entity_type_id else None,
                        json.dumps(entity.properties),
                        entity.confidence,
                        json.dumps({
                            "source_document_id": str(document_id) if document_id else None,
                            "source_span": entity.source_span,
                            "extraction_mode": "constrained",
                            "extracted_at": datetime.utcnow().isoformat()
                        })
                    ))
                
                conn.commit()
                logger.info(f"Wrote {len(entity_result.entities)} entities to entities_v2")
                
        except Exception as e:
            logger.error(f"Failed to write to shadow table: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()
    
    def _log_extraction_event(
        self,
        entity_result: ExtractionResult,
        relationship_result: ExtractionResult,
        text: str,
        document_id: Optional[UUID]
    ):
        """Log extraction event to extraction_events table."""
        if not self.database_url:
            return
        
        conn = None
        try:
            conn = psycopg2.connect(self.database_url)
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO extraction_events (
                        source_document_id, source_text, model_used,
                        extraction_mode,
                        validated_entities, rejected_entities, rejection_reasons,
                        entities_extracted, entities_validated, entities_rejected,
                        validation_errors,
                        extraction_started_at, extraction_completed_at
                    ) VALUES (
                        %s, %s, %s, 'constrained', %s, %s, %s,
                        %s, %s, %s, %s, %s, %s
                    )
                """, (
                    str(document_id) if document_id else None,
                    text[:5000],
                    self.model,
                    json.dumps([e.model_dump() for e in entity_result.entities], default=str),
                    json.dumps(entity_result.rejected_entities),
                    json.dumps([r.get("reason") for r in entity_result.rejected_entities]),
                    len(entity_result.entities) + len(entity_result.rejected_entities),
                    len(entity_result.entities),
                    len(entity_result.rejected_entities),
                    json.dumps(entity_result.validation_errors),
                    entity_result.extraction_started_at,
                    entity_result.extraction_completed_at
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to log extraction event: {e}")
        finally:
            if conn:
                conn.close()
