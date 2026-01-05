"""
Graph Builder Agent - Ingests documents, extracts entities/relationships, writes to STAGING.

This is the "perception layer" - how Context Foundry sees new information entering the knowledge graph.

Key principles:
1. Schema-driven extraction - Only looks for defined entity/relationship types from config
2. Everything goes to STAGING first (not TRUSTED)
3. Full provenance tracking (source doc, sentence, character offsets)
4. Confidence scoring on every extraction
5. No inference - only extracts explicitly stated facts
6. Domain-agnostic - works with any schema (IT Ops, Finance, Healthcare, etc.)
"""
import os
import json
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from openai import OpenAI

from ..models.schema import (
    Entity, Relationship, Document,
    LifecycleState,
    get_session
)
from ..config.domain_schema import get_schema_loader, DomainSchemaLoader
from ..utils.logger import logger

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


@dataclass
class Chunk:
    """A chunk of text with provenance."""
    text: str
    start_offset: int
    end_offset: int
    chunk_index: int
    source_document_id: str


@dataclass
class ExtractedEntity:
    """An entity extracted from text."""
    entity_type: str
    canonical_name: str
    properties: Dict = field(default_factory=dict)
    confidence: float = 0.5
    source_sentence: str = ""
    start_offset: int = 0
    end_offset: int = 0


@dataclass
class ExtractedRelationship:
    """A relationship extracted from text."""
    relationship_type: str
    source_name: str
    target_name: str
    properties: Dict = field(default_factory=dict)
    confidence: float = 0.5
    source_sentence: str = ""


@dataclass
class ExtractionResult:
    """Result of document ingestion."""
    document_id: str
    entities_extracted: int
    relationships_extracted: int
    entities_staged: int
    relationships_staged: int
    chunks_processed: int
    errors: List[str] = field(default_factory=list)
    staged: bool = True


ENTITY_EXTRACTION_PROMPT_TEMPLATE = """You are an entity extraction system for {domain} knowledge graphs.

Given this text, extract any entities of these EXACT types:

{entity_types_section}

TYPE PRIORITY - Use SPECIFIC types over GENERIC ones:
- Use SERVICE (not ORGANIZATION or PROCESS) for: software services, APIs, applications, gateways, microservices
  Examples: "Payment Gateway" → SERVICE, "Authentication Service" → SERVICE, "Order Processing API" → SERVICE
- Use DATABASE (not ORGANIZATION or PROCESS) for: databases, data stores, warehouses, caches
  Examples: "User Database" → DATABASE, "Inventory DB" → DATABASE, "Redis Cache" → DATABASE
- Use TEAM (not ORGANIZATION) for: internal teams, squads, departments, engineering groups
  Examples: "Platform Engineering Team" → TEAM, "Security Team" → TEAM, "DevOps Squad" → TEAM
- Use INCIDENT (not EVENT) for: operational incidents, outages, issues with IDs
  Examples: "INC-2026-0105-A" → INCIDENT, "Database Outage" → INCIDENT, "Production Incident" → INCIDENT
- Use ORGANIZATION only for: external companies, agencies, government bodies, corporations
  Examples: "Acme Corporation" → ORGANIZATION, "AWS" → ORGANIZATION, "Federal Reserve" → ORGANIZATION
- Use PROCESS only for: abstract business workflows, procedures, methodologies (NOT software services)
  Examples: "Approval Workflow" → PROCESS, "Onboarding Procedure" → PROCESS
- Use EVENT only for: meetings, conferences, announcements (NOT operational incidents)
  Examples: "Annual Conference" → EVENT, "Q4 Kickoff Meeting" → EVENT

For EACH entity found, return:
- type: One of {entity_type_names}
- canonical_name: The standardized name
- properties: Any additional attributes mentioned (as key-value pairs)
- confidence: 0.0-1.0 how certain you are this is correct
- source_sentence: The EXACT sentence it came from (copy verbatim)

CRITICAL RULES:
1. Only extract what is EXPLICITLY stated in the text
2. Do NOT infer entities that aren't mentioned
3. Use canonical naming (e.g., "Auth Service" not "the auth service")
4. ALWAYS prefer specific types (SERVICE, DATABASE, TEAM, INCIDENT) over generic types (ORGANIZATION, PROCESS, EVENT)
5. Each entity should only appear ONCE with ONE type - no duplicates
6. Confidence should reflect clarity of mention:
   - 0.9-1.0: Clearly named and defined
   - 0.7-0.9: Mentioned by name but minimal context
   - 0.5-0.7: Implied or ambiguous reference
   - Below 0.5: Don't extract, too uncertain

TEXT TO ANALYZE:
{text}

Respond with ONLY a valid JSON array of entities. If no entities found, return [].
Example format:
[
  {{
    "type": "SERVICE",
    "canonical_name": "Payment Gateway",
    "properties": {{"owner": "Platform Team"}},
    "confidence": 0.95,
    "source_sentence": "The Payment Gateway handles all credit card transactions."
  }},
  {{
    "type": "TEAM",
    "canonical_name": "Platform Engineering Team",
    "properties": {{}},
    "confidence": 0.90,
    "source_sentence": "The Platform Engineering Team manages the core infrastructure."
  }}
]"""

RELATIONSHIP_EXTRACTION_PROMPT_TEMPLATE = """You are a relationship extraction system for {domain} knowledge graphs.

Given this text and the entities already identified, extract relationships between them.

{relationship_types_section}

ENTITIES FOUND IN THIS TEXT:
{entities}

TEXT TO ANALYZE:
{text}

For EACH relationship found, return:
- type: One of {relationship_type_names}
- source_name: The canonical name of the source entity
- target_name: The canonical name of the target entity
- properties: Any additional context (as key-value pairs)
- confidence: 0.0-1.0 how certain you are this relationship exists
- source_sentence: The EXACT sentence that states this relationship

CRITICAL RULES:
1. Only extract relationships EXPLICITLY stated in the text
2. Both source and target must be in the entities list
3. Verify the relationship type matches allowed source→target types
4. Do NOT infer relationships that aren't directly stated
5. Confidence reflects how clearly the relationship is stated

Respond with ONLY a valid JSON array of relationships. If none found, return [].
Example format:
[
  {{
    "type": "RELATIONSHIP_TYPE",
    "source_name": "Source Entity Name",
    "target_name": "Target Entity Name",
    "properties": {{}},
    "confidence": 0.92,
    "source_sentence": "The exact sentence from the text."
  }}
]"""


class GraphBuilderAgent:
    """
    Agent that ingests documents, extracts entities/relationships,
    and writes them to STAGING with confidence and provenance.
    
    This is the perception layer of the cognitive loop.
    Now fully configurable via domain_schema.yaml for any domain.
    """
    
    MAX_CHUNK_TOKENS = 512
    CHARS_PER_TOKEN = 4
    
    def __init__(self, session=None, schema_config_path: str = None):
        self.session = session or get_session()
        
        self.schema_loader = get_schema_loader(
            config_path=schema_config_path, 
            force_reload=schema_config_path is not None
        )
        self.schema = self.schema_loader.schema
        
        logger.info(f"GraphBuilderAgent using domain: {self.schema.domain}")
        logger.info(f"Entity types: {list(self.schema.entity_types.keys())}")
        logger.info(f"Relationship types: {list(self.schema.relationship_types.keys())}")
        
        if AI_INTEGRATIONS_OPENAI_API_KEY and AI_INTEGRATIONS_OPENAI_BASE_URL:
            self.client = OpenAI(
                api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
                base_url=AI_INTEGRATIONS_OPENAI_BASE_URL
            )
        elif OPENAI_API_KEY:
            self.client = OpenAI(api_key=OPENAI_API_KEY)
        else:
            raise ValueError("No OpenAI API key available. Set OPENAI_API_KEY or use Replit AI Integrations.")
        
        self.model = "gpt-4o-mini"
        self._entity_cache = {}
        
        self._valid_entity_types = self.schema_loader.get_valid_entity_types()
        self._valid_relationship_types = self.schema_loader.get_valid_relationship_types()
        
        logger.info("GraphBuilderAgent initialized with configurable schema")
    
    def _build_entity_extraction_prompt(self, text: str) -> str:
        """Build entity extraction prompt dynamically from schema config."""
        entity_types_section = self.schema_loader.build_entity_extraction_prompt()
        entity_type_names = ", ".join(self.schema.get_entity_type_names())
        
        return ENTITY_EXTRACTION_PROMPT_TEMPLATE.format(
            domain=self.schema.domain,
            entity_types_section=entity_types_section,
            entity_type_names=entity_type_names,
            text=text
        )
    
    def _build_relationship_extraction_prompt(self, text: str, entities: List[ExtractedEntity]) -> str:
        """Build relationship extraction prompt dynamically from schema config."""
        relationship_types_section = self.schema_loader.build_relationship_extraction_prompt()
        relationship_type_names = ", ".join(self.schema.get_relationship_type_names())
        
        entities_str = json.dumps([
            {"type": e.entity_type, "name": e.canonical_name}
            for e in entities
        ], indent=2)
        
        return RELATIONSHIP_EXTRACTION_PROMPT_TEMPLATE.format(
            domain=self.schema.domain,
            relationship_types_section=relationship_types_section,
            relationship_type_names=relationship_type_names,
            entities=entities_str,
            text=text
        )
    
    TYPE_MAPPING = {
        "APPLICATION": "SERVICE",
        "API": "SERVICE",
        "PLATFORM": "SERVICE",
        "GATEWAY": "SERVICE",
        "MICROSERVICE": "SERVICE",
        "GROUP": "TEAM",
        "SQUAD": "TEAM",
        "DEPARTMENT": "TEAM",
        "OUTAGE": "INCIDENT",
        "ISSUE": "INCIDENT",
        "FAILURE": "INCIDENT",
        "DATASTORE": "DATABASE",
        "REPOSITORY": "DATABASE",
        "CACHE": "DATABASE",
        "TECHNOLOGY": "SERVICE",
    }
    
    SPECIFIC_TYPE_PATTERNS = {
        "SERVICE": ["service", "gateway", "api", "app", "server", "endpoint", "microservice", "portal"],
        "DATABASE": ["database", "db", "datastore", "store", "warehouse", "cache", "redis", "postgres", "mysql"],
        "TEAM": ["team", "squad", "department", "group", "engineering", "platform team", "security team"],
        "INCIDENT": ["inc-", "incident", "outage", "issue #", "failure", "disruption", "alert"],
    }
    
    def _validate_entity_type(self, entity_type: str) -> bool:
        """Check if entity type is valid according to loaded schema."""
        return entity_type.upper() in self._valid_entity_types
    
    def _validate_relationship(self, rel_type: str, source_type: str, target_type: str) -> Tuple[bool, str]:
        """Validate relationship type and source/target compatibility."""
        return self.schema.validate_relationship(rel_type, source_type, target_type)
    
    def _correct_entity_type(self, extracted_type: str, entity_name: str) -> str:
        """Correct/map generic entity types to specific types.
        
        Uses a priority system:
        1. Direct mapping from TYPE_MAPPING
        2. Pattern matching on entity name
        3. Keep original type if already valid
        
        This helps correct LLM errors like "Payment Gateway" → ORGANIZATION
        to the correct type: SERVICE
        """
        extracted_type = extracted_type.upper()
        
        if extracted_type in self.TYPE_MAPPING:
            mapped = self.TYPE_MAPPING[extracted_type]
            logger.debug(f"Type mapping: {extracted_type} → {mapped} for '{entity_name}'")
            return mapped
        
        name_lower = entity_name.lower()
        
        if extracted_type in ("ORGANIZATION", "PROCESS", "EVENT", "CONCEPT"):
            for specific_type, patterns in self.SPECIFIC_TYPE_PATTERNS.items():
                if any(pattern in name_lower for pattern in patterns):
                    logger.info(f"Type correction: {extracted_type} → {specific_type} for '{entity_name}' (pattern match)")
                    return specific_type
        
        return extracted_type
    
    def _normalize_entity_type(self, entity_type: str) -> str:
        """Normalize entity type string for database storage.
        
        Since entity_type is now VARCHAR, we just normalize to uppercase.
        No enum mapping needed - any type from loaded schema is valid.
        """
        return entity_type.upper()
    
    def _normalize_relationship_type(self, rel_type: str) -> str:
        """Normalize relationship type string for database storage.
        
        Since relationship_type is now VARCHAR, we just normalize to uppercase.
        No enum mapping needed - any type from loaded schema is valid.
        """
        return rel_type.upper()
    
    def ingest_document(self, doc_path: str = None, text: str = None, 
                        doc_type: str = "DOCUMENT", title: str = None,
                        tenant_id: str = None) -> ExtractionResult:
        """
        Main entry point: Ingest a document and extract entities/relationships.
        
        Args:
            doc_path: Path to document file (optional)
            text: Raw text content (optional, use if doc_path not provided)
            doc_type: Type of document (RUNBOOK, MEETING_NOTES, etc.)
            title: Document title (defaults to filename or generated)
            
        Returns:
            ExtractionResult with extraction statistics
        """
        doc_id = str(uuid.uuid4())[:8]
        logger.info(f"[{doc_id}] Starting document ingestion for domain: {self.schema.domain}")
        
        if doc_path:
            try:
                with open(doc_path, 'r', encoding='utf-8') as f:
                    text = f.read()
                title = title or os.path.basename(doc_path)
            except Exception as e:
                logger.error(f"[{doc_id}] Failed to read file: {e}")
                return ExtractionResult(
                    document_id=doc_id,
                    entities_extracted=0,
                    relationships_extracted=0,
                    entities_staged=0,
                    relationships_staged=0,
                    chunks_processed=0,
                    errors=[f"Failed to read file: {str(e)}"],
                    staged=False
                )
        
        if not text:
            return ExtractionResult(
                document_id=doc_id,
                entities_extracted=0,
                relationships_extracted=0,
                entities_staged=0,
                relationships_staged=0,
                chunks_processed=0,
                errors=["No text provided"],
                staged=False
            )
        
        title = title or f"Document_{doc_id}"
        
        chunks = self.chunk_document(text, doc_id)
        logger.info(f"[{doc_id}] Document chunked into {len(chunks)} chunks")
        
        all_entities: List[ExtractedEntity] = []
        all_relationships: List[ExtractedRelationship] = []
        errors: List[str] = []
        
        for chunk in chunks:
            try:
                entities = self.extract_entities(chunk)
                all_entities.extend(entities)
                logger.debug(f"[{doc_id}] Chunk {chunk.chunk_index}: {len(entities)} entities")
                
                relationships = self.extract_relationships(chunk, entities)
                all_relationships.extend(relationships)
                logger.debug(f"[{doc_id}] Chunk {chunk.chunk_index}: {len(relationships)} relationships")
                
            except Exception as e:
                error_msg = f"Chunk {chunk.chunk_index} extraction failed: {str(e)}"
                logger.error(f"[{doc_id}] {error_msg}")
                errors.append(error_msg)
        
        entities_staged, relationships_staged = self.write_to_staging(
            entities=all_entities,
            relationships=all_relationships,
            source_document_id=doc_id,
            document_title=title,
            document_type=doc_type,
            document_text=text,
            tenant_id=tenant_id
        )
        
        result = ExtractionResult(
            document_id=doc_id,
            entities_extracted=len(all_entities),
            relationships_extracted=len(all_relationships),
            entities_staged=entities_staged,
            relationships_staged=relationships_staged,
            chunks_processed=len(chunks),
            errors=errors,
            staged=True
        )
        
        logger.info(f"[{doc_id}] Ingestion complete: {result.entities_extracted} entities, "
                   f"{result.relationships_extracted} relationships extracted")
        
        return result
    
    def chunk_document(self, text: str, doc_id: str = "unknown") -> List[Chunk]:
        """
        Split document into sentence-aware chunks (max 512 tokens).
        
        Uses sentence boundaries to avoid cutting mid-sentence.
        """
        max_chars = self.MAX_CHUNK_TOKENS * self.CHARS_PER_TOKEN
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        current_start = 0
        chunk_index = 0
        char_position = 0
        
        for sentence in sentences:
            sentence_with_space = sentence + " "
            
            if len(current_chunk) + len(sentence_with_space) > max_chars:
                if current_chunk.strip():
                    chunks.append(Chunk(
                        text=current_chunk.strip(),
                        start_offset=current_start,
                        end_offset=char_position,
                        chunk_index=chunk_index,
                        source_document_id=doc_id
                    ))
                    chunk_index += 1
                
                current_chunk = sentence_with_space
                current_start = char_position
            else:
                current_chunk += sentence_with_space
            
            char_position += len(sentence_with_space)
        
        if current_chunk.strip():
            chunks.append(Chunk(
                text=current_chunk.strip(),
                start_offset=current_start,
                end_offset=char_position,
                chunk_index=chunk_index,
                source_document_id=doc_id
            ))
        
        return chunks
    
    def extract_entities(self, chunk: Chunk) -> List[ExtractedEntity]:
        """
        Extract entities from a chunk using schema-driven LLM prompts.
        Prompts are built dynamically from domain_schema.yaml.
        """
        prompt = self._build_entity_extraction_prompt(chunk.text)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an entity extraction system. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # Deterministic extraction
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            if content.startswith("```"):
                content = re.sub(r'^```(?:json)?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            entities_data = json.loads(content)
            
            if not isinstance(entities_data, list):
                entities_data = [entities_data] if entities_data else []
            
            entities = []
            seen_names = set()
            
            for e in entities_data:
                raw_type = e.get("type", "").upper()
                canonical_name = e.get("canonical_name", e.get("name", ""))
                
                name_key = canonical_name.lower().strip()
                if name_key in seen_names:
                    logger.debug(f"Skipping duplicate entity: {canonical_name}")
                    continue
                seen_names.add(name_key)
                
                entity_type = self._correct_entity_type(raw_type, canonical_name)
                
                if not self._validate_entity_type(entity_type):
                    logger.warning(f"Unknown entity type after correction: {entity_type} (original: {raw_type}, valid: {self._valid_entity_types})")
                    continue
                
                confidence = float(e.get("confidence", 0.5))
                if confidence < 0.5:
                    logger.debug(f"Skipping low-confidence entity: {canonical_name} ({confidence})")
                    continue
                
                source_sentence = e.get("source_sentence", "")
                start_offset = chunk.start_offset
                end_offset = chunk.end_offset
                
                if source_sentence:
                    sentence_pos = chunk.text.find(source_sentence)
                    if sentence_pos >= 0:
                        start_offset = chunk.start_offset + sentence_pos
                        end_offset = start_offset + len(source_sentence)
                
                entity = ExtractedEntity(
                    entity_type=entity_type,
                    canonical_name=canonical_name,
                    properties=e.get("properties", {}),
                    confidence=confidence,
                    source_sentence=source_sentence,
                    start_offset=start_offset,
                    end_offset=end_offset
                )
                entities.append(entity)
            
            return entities
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse entity extraction response: {e}")
            return []
        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return []
    
    def extract_relationships(self, chunk: Chunk, entities: List[ExtractedEntity]) -> List[ExtractedRelationship]:
        """
        Extract relationships between entities using schema-driven LLM prompts.
        Validates relationships against config-defined source/target types.
        """
        if len(entities) < 2:
            return []
        
        prompt = self._build_relationship_extraction_prompt(chunk.text, entities)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a relationship extraction system. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # Deterministic extraction
                max_tokens=2000
            )
            
            content = response.choices[0].message.content.strip()
            
            if content.startswith("```"):
                content = re.sub(r'^```(?:json)?\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            
            relationships_data = json.loads(content)
            
            if not isinstance(relationships_data, list):
                relationships_data = [relationships_data] if relationships_data else []
            
            entity_map = {e.canonical_name: e for e in entities}
            
            relationships = []
            for r in relationships_data:
                rel_type = r.get("type", "").upper()
                
                if rel_type not in self._valid_relationship_types:
                    logger.warning(f"Unknown relationship type: {rel_type}")
                    continue
                
                source_name = r.get("source_name")
                target_name = r.get("target_name")
                
                if source_name not in entity_map or target_name not in entity_map:
                    logger.debug(f"Relationship references unknown entity: {source_name} -> {target_name}")
                    continue
                
                source_entity = entity_map[source_name]
                target_entity = entity_map[target_name]
                
                is_valid, error_msg = self._validate_relationship(
                    rel_type, source_entity.entity_type, target_entity.entity_type
                )
                
                if not is_valid:
                    logger.debug(f"Invalid relationship: {error_msg}")
                    continue
                
                confidence = float(r.get("confidence", 0.5))
                if confidence < 0.5:
                    logger.debug(f"Skipping low-confidence relationship: {source_name} -> {target_name} ({confidence})")
                    continue
                
                relationship = ExtractedRelationship(
                    relationship_type=rel_type,
                    source_name=source_name,
                    target_name=target_name,
                    properties=r.get("properties", {}),
                    confidence=confidence,
                    source_sentence=r.get("source_sentence", "")
                )
                relationships.append(relationship)
            
            return relationships
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse relationship extraction response: {e}")
            return []
        except Exception as e:
            logger.error(f"Relationship extraction failed: {e}")
            return []
    
    def write_to_staging(self, entities: List[ExtractedEntity], 
                         relationships: List[ExtractedRelationship],
                         source_document_id: str,
                         document_title: str,
                         document_type: str,
                         document_text: str,
                         tenant_id: str = None) -> Tuple[int, int]:
        """
        Write extracted entities and relationships to STAGING (not TRUSTED).
        
        Maps schema-defined types to database enums for backward compatibility.
        Stores original schema type in properties for future migration.
        
        Returns:
            Tuple of (entities_staged, relationships_staged)
        """
        entities_staged = 0
        relationships_staged = 0
        
        try:
            doc = Document(
                id=uuid.uuid4(),
                tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
                title=document_title,
                doc_type=document_type,
                content=document_text[:5000],
                source_document_id=source_document_id,
                doc_metadata={
                    "ingested_by": "graph_builder",
                    "ingested_at": datetime.utcnow().isoformat(),
                    "domain": self.schema.domain
                }
            )
            self.session.add(doc)
            self.session.flush()
            
        except Exception as e:
            logger.error(f"Failed to create document record: {e}")
            self.session.rollback()
        
        entity_db_map = {}
        
        for entity in entities:
            try:
                db_entity_type = self._normalize_entity_type(entity.entity_type)
                
                existing = self.session.query(Entity).filter(
                    Entity.name == entity.canonical_name,
                    Entity.entity_type == db_entity_type
                ).first()
                
                if existing:
                    entity_db_map[entity.canonical_name] = existing.id
                    logger.debug(f"Entity already exists: {entity.canonical_name}")
                    continue
                
                props_with_provenance = {
                    **entity.properties,
                    "_provenance": {
                        "start_offset": entity.start_offset,
                        "end_offset": entity.end_offset,
                        "extraction_method": "graph_builder_llm"
                    },
                    "_schema_type": entity.entity_type,
                    "_domain": self.schema.domain
                }
                
                db_entity = Entity(
                    id=uuid.uuid4(),
                    tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
                    name=entity.canonical_name,
                    entity_type=db_entity_type,
                    lifecycle_state=LifecycleState.STAGING,
                    properties=props_with_provenance,
                    confidence=entity.confidence,
                    source_document_id=source_document_id,
                    source_sentence=entity.source_sentence[:500] if entity.source_sentence else None,
                    extracted_at=datetime.utcnow(),
                    extraction_method="graph_builder_llm"
                )
                self.session.add(db_entity)
                self.session.flush()
                
                entity_db_map[entity.canonical_name] = db_entity.id
                entities_staged += 1
                
                logger.debug(f"Staged entity: {entity.canonical_name} ({entity.entity_type})")
                
            except Exception as e:
                logger.error(f"Failed to stage entity {entity.canonical_name}: {e}")
                self.session.rollback()
        
        for existing_entity in self.session.query(Entity).all():
            if existing_entity.name not in entity_db_map:
                entity_db_map[existing_entity.name] = existing_entity.id
        
        for rel in relationships:
            try:
                source_id = entity_db_map.get(rel.source_name)
                target_id = entity_db_map.get(rel.target_name)
                
                if not source_id or not target_id:
                    logger.debug(f"Relationship references unmapped entity: {rel.source_name} -> {rel.target_name}")
                    continue
                
                db_rel_type = self._normalize_relationship_type(rel.relationship_type)
                
                existing = self.session.query(Relationship).filter(
                    Relationship.source_id == source_id,
                    Relationship.target_id == target_id,
                    Relationship.relationship_type == db_rel_type
                ).first()
                
                if existing:
                    logger.debug(f"Relationship already exists: {rel.source_name} -> {rel.target_name}")
                    continue
                
                rel_props = {
                    **rel.properties,
                    "_schema_type": rel.relationship_type,
                    "_domain": self.schema.domain
                }
                
                db_rel = Relationship(
                    id=uuid.uuid4(),
                    tenant_id=uuid.UUID(tenant_id) if tenant_id else None,
                    source_id=source_id,
                    target_id=target_id,
                    relationship_type=db_rel_type,
                    lifecycle_state=LifecycleState.STAGING,
                    properties=rel_props,
                    confidence=rel.confidence,
                    source_document_id=source_document_id,
                    source_sentence=rel.source_sentence[:500] if rel.source_sentence else None,
                    extracted_at=datetime.utcnow()
                )
                self.session.add(db_rel)
                relationships_staged += 1
                
                logger.debug(f"Staged relationship: {rel.source_name} -[{rel.relationship_type}]-> {rel.target_name}")
                
            except Exception as e:
                logger.error(f"Failed to stage relationship: {e}")
                self.session.rollback()
        
        try:
            self.session.commit()
            logger.info(f"Committed {entities_staged} entities and {relationships_staged} relationships to STAGING")
        except Exception as e:
            logger.error(f"Failed to commit staging data: {e}")
            self.session.rollback()
            return 0, 0
        
        return entities_staged, relationships_staged
    
    def get_schema_info(self) -> Dict:
        """Return current schema configuration for debugging/API responses."""
        return {
            "domain": self.schema.domain,
            "schema_version": self.schema.schema_version,
            "description": self.schema.description,
            "entity_types": list(self.schema.entity_types.keys()),
            "relationship_types": list(self.schema.relationship_types.keys()),
            "cardinality_constraints": self.schema_loader.get_cardinality_constraints()
        }
    
    def close(self):
        """Close database session."""
        if self.session:
            self.session.close()
