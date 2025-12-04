"""
Graph Builder Agent - Ingests documents, extracts entities/relationships, writes to STAGING.

This is the "perception layer" - how Context Foundry sees new information entering the knowledge graph.

Key principles:
1. Schema-driven extraction - Only looks for defined entity/relationship types
2. Everything goes to STAGING first (not TRUSTED)
3. Full provenance tracking (source doc, sentence, character offsets)
4. Confidence scoring on every extraction
5. No inference - only extracts explicitly stated facts
"""
import os
import json
import re
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from openai import OpenAI

from ..models.schema import (
    Entity, Relationship, Document,
    LifecycleState, EntityType, RelationshipType,
    get_session
)
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


ENTITY_EXTRACTION_PROMPT = """You are an entity extraction system for IT operations knowledge graphs.

Given this text, extract any entities of these EXACT types:

ENTITY TYPES:
- SERVICE: A software service or application (e.g., "Auth Service", "Payment Gateway")
  Required: canonical_name
  Optional: tier, owner_team, description

- COMPONENT: Part of a service (API, queue, cache, module)
  Required: canonical_name, component_type
  Optional: parent_service

- TEAM: An organizational team (e.g., "Platform Team", "Payments Team")
  Required: name
  Optional: department, manager

- PERSON: An individual (e.g., "John Smith", "Sarah Chen")
  Required: canonical_name
  Optional: email, role, team

- DATABASE: A database instance (e.g., "Users DB", "Payments Database")
  Required: canonical_name
  Optional: db_type (postgres, mysql, redis, etc.)

- INCIDENT: An incident or outage reference (e.g., "INC-2024-001")
  Required: external_id, title
  Optional: severity, status

For EACH entity found, return:
- type: One of SERVICE, COMPONENT, TEAM, PERSON, DATABASE, INCIDENT
- canonical_name: The standardized name
- properties: Any additional attributes mentioned (as key-value pairs)
- confidence: 0.0-1.0 how certain you are this is correct
- source_sentence: The EXACT sentence it came from (copy verbatim)

CRITICAL RULES:
1. Only extract what is EXPLICITLY stated in the text
2. Do NOT infer entities that aren't mentioned
3. Use canonical naming (e.g., "Auth Service" not "the auth service")
4. Confidence should reflect clarity of mention:
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
    "canonical_name": "Auth Service",
    "properties": {{"tier": "critical", "owner": "Platform Team"}},
    "confidence": 0.95,
    "source_sentence": "The Auth Service handles all authentication requests."
  }}
]"""

RELATIONSHIP_EXTRACTION_PROMPT = """You are a relationship extraction system for IT operations knowledge graphs.

Given this text and the entities already identified, extract relationships between them.

RELATIONSHIP TYPES (with valid source → target):
- DEPENDS_ON: Service/Component → Service/Component/Database
  (e.g., "Payment Service depends on Auth Service")

- OWNS: Team → Service/Component/Database
  (e.g., "Platform Team owns the Auth Service")

- SUPPORTS: Team → Service/Component
  (e.g., "DevOps Team supports the Kubernetes cluster")

- MEMBER_OF: Person → Team
  (e.g., "John Smith is on the Platform Team")

- MANAGES: Person → Team
  (e.g., "Sarah leads the Payments Team")

- AFFECTS: Incident → Service/Component/Database
  (e.g., "INC-001 affected the Payment Service")

- CAUSED_BY: Incident → Incident/Change
  (e.g., "The outage was caused by a config change")

ENTITIES FOUND IN THIS TEXT:
{entities}

TEXT TO ANALYZE:
{text}

For EACH relationship found, return:
- type: One of DEPENDS_ON, OWNS, SUPPORTS, MEMBER_OF, MANAGES, AFFECTS, CAUSED_BY
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
    "type": "OWNS",
    "source_name": "Platform Team",
    "target_name": "Auth Service",
    "properties": {{}},
    "confidence": 0.92,
    "source_sentence": "The Platform Team owns and maintains the Auth Service."
  }}
]"""


class GraphBuilderAgent:
    """
    Agent that ingests documents, extracts entities/relationships,
    and writes them to STAGING with confidence and provenance.
    
    This is the perception layer of the cognitive loop.
    """
    
    MAX_CHUNK_TOKENS = 512
    CHARS_PER_TOKEN = 4
    
    ENTITY_TYPE_MAP = {
        "SERVICE": EntityType.SERVICE,
        "COMPONENT": EntityType.COMPONENT,
        "TEAM": EntityType.TEAM,
        "PERSON": EntityType.PERSON,
        "DATABASE": EntityType.DATABASE,
        "INCIDENT": EntityType.INCIDENT,
    }
    
    RELATIONSHIP_TYPE_MAP = {
        "DEPENDS_ON": RelationshipType.DEPENDS_ON,
        "OWNS": RelationshipType.OWNS,
        "SUPPORTS": RelationshipType.SUPPORTS,
        "MEMBER_OF": RelationshipType.MEMBER_OF,
        "MANAGES": RelationshipType.MANAGES,
        "AFFECTS": RelationshipType.AFFECTS,
        "CAUSED_BY": RelationshipType.CAUSED_BY,
    }
    
    VALID_RELATIONSHIP_SOURCES = {
        "DEPENDS_ON": {"SERVICE", "COMPONENT"},
        "OWNS": {"TEAM"},
        "SUPPORTS": {"TEAM"},
        "MEMBER_OF": {"PERSON"},
        "MANAGES": {"PERSON"},
        "AFFECTS": {"INCIDENT"},
        "CAUSED_BY": {"INCIDENT"},
    }
    
    VALID_RELATIONSHIP_TARGETS = {
        "DEPENDS_ON": {"SERVICE", "COMPONENT", "DATABASE"},
        "OWNS": {"SERVICE", "COMPONENT", "DATABASE"},
        "SUPPORTS": {"SERVICE", "COMPONENT"},
        "MEMBER_OF": {"TEAM"},
        "MANAGES": {"TEAM"},
        "AFFECTS": {"SERVICE", "COMPONENT", "DATABASE"},
        "CAUSED_BY": {"INCIDENT"},
    }
    
    def __init__(self, session=None):
        self.session = session or get_session()
        
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
        
        logger.info("GraphBuilderAgent initialized")
    
    def ingest_document(self, doc_path: str = None, text: str = None, 
                        doc_type: str = "DOCUMENT", title: str = None) -> ExtractionResult:
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
        logger.info(f"[{doc_id}] Starting document ingestion")
        
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
            document_text=text
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
        """
        prompt = ENTITY_EXTRACTION_PROMPT.format(text=chunk.text)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an entity extraction system. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
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
            for e in entities_data:
                if e.get("type") not in self.ENTITY_TYPE_MAP:
                    logger.warning(f"Unknown entity type: {e.get('type')}")
                    continue
                
                confidence = float(e.get("confidence", 0.5))
                if confidence < 0.5:
                    logger.debug(f"Skipping low-confidence entity: {e.get('canonical_name')} ({confidence})")
                    continue
                
                entity = ExtractedEntity(
                    entity_type=e.get("type"),
                    canonical_name=e.get("canonical_name", e.get("name", "")),
                    properties=e.get("properties", {}),
                    confidence=confidence,
                    source_sentence=e.get("source_sentence", ""),
                    start_offset=chunk.start_offset,
                    end_offset=chunk.end_offset
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
        """
        if len(entities) < 2:
            return []
        
        entities_str = json.dumps([
            {"type": e.entity_type, "name": e.canonical_name}
            for e in entities
        ], indent=2)
        
        prompt = RELATIONSHIP_EXTRACTION_PROMPT.format(
            entities=entities_str,
            text=chunk.text
        )
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a relationship extraction system. Respond only with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
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
                rel_type = r.get("type")
                
                if rel_type not in self.RELATIONSHIP_TYPE_MAP:
                    logger.warning(f"Unknown relationship type: {rel_type}")
                    continue
                
                source_name = r.get("source_name")
                target_name = r.get("target_name")
                
                if source_name not in entity_map or target_name not in entity_map:
                    logger.debug(f"Relationship references unknown entity: {source_name} -> {target_name}")
                    continue
                
                source_entity = entity_map[source_name]
                target_entity = entity_map[target_name]
                
                valid_sources = self.VALID_RELATIONSHIP_SOURCES.get(rel_type, set())
                valid_targets = self.VALID_RELATIONSHIP_TARGETS.get(rel_type, set())
                
                if source_entity.entity_type not in valid_sources:
                    logger.debug(f"Invalid source type for {rel_type}: {source_entity.entity_type}")
                    continue
                
                if target_entity.entity_type not in valid_targets:
                    logger.debug(f"Invalid target type for {rel_type}: {target_entity.entity_type}")
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
                         document_text: str) -> Tuple[int, int]:
        """
        Write extracted entities and relationships to STAGING (not TRUSTED).
        
        Returns:
            Tuple of (entities_staged, relationships_staged)
        """
        entities_staged = 0
        relationships_staged = 0
        
        try:
            doc = Document(
                id=uuid.uuid4(),
                title=document_title,
                doc_type=document_type,
                content=document_text[:5000],
                source_document_id=source_document_id,
                doc_metadata={
                    "ingested_by": "graph_builder",
                    "ingested_at": datetime.utcnow().isoformat()
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
                existing = self.session.query(Entity).filter(
                    Entity.name == entity.canonical_name,
                    Entity.entity_type == self.ENTITY_TYPE_MAP[entity.entity_type]
                ).first()
                
                if existing:
                    entity_db_map[entity.canonical_name] = existing.id
                    logger.debug(f"Entity already exists: {entity.canonical_name}")
                    continue
                
                db_entity = Entity(
                    id=uuid.uuid4(),
                    name=entity.canonical_name,
                    entity_type=self.ENTITY_TYPE_MAP[entity.entity_type],
                    lifecycle_state=LifecycleState.STAGING,
                    properties=entity.properties,
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
                
                existing = self.session.query(Relationship).filter(
                    Relationship.source_id == source_id,
                    Relationship.target_id == target_id,
                    Relationship.relationship_type == self.RELATIONSHIP_TYPE_MAP[rel.relationship_type]
                ).first()
                
                if existing:
                    logger.debug(f"Relationship already exists: {rel.source_name} -> {rel.target_name}")
                    continue
                
                db_rel = Relationship(
                    id=uuid.uuid4(),
                    source_id=source_id,
                    target_id=target_id,
                    relationship_type=self.RELATIONSHIP_TYPE_MAP[rel.relationship_type],
                    lifecycle_state=LifecycleState.STAGING,
                    properties=rel.properties,
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
    
    def close(self):
        """Close database session."""
        if self.session:
            self.session.close()
