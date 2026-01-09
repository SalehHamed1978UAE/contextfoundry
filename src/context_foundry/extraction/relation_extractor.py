"""
Relation Extractor for Context Foundry - Domain-Agnostic Version.
Uses LLM-powered relation extraction with confidence scoring based on active schema.

Uses Replit AI Integrations for OpenAI access (no API key required, billed to credits).
"""
import json
import os
import re
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import hashlib

from openai import OpenAI

from ..config.domain_schema import get_schema_loader, DomainSchemaLoader

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")


@dataclass
class ExtractedRelation:
    """Represents a relationship extracted from text."""
    id: str
    relation_type: str
    source_name: str
    target_name: str
    source_span: str
    source_document_id: str
    source_chunk_id: str
    confidence: float
    properties: Dict = field(default_factory=dict)
    extracted_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "relation_type": self.relation_type,
            "source_name": self.source_name,
            "target_name": self.target_name,
            "source_span": self.source_span,
            "source_document_id": self.source_document_id,
            "source_chunk_id": self.source_chunk_id,
            "confidence": self.confidence,
            "properties": self.properties,
            "extracted_at": self.extracted_at.isoformat(),
        }


class RelationExtractor:
    """
    LLM-powered relation extractor that works with any domain schema.
    
    Loads relationship types dynamically from the active domain schema configuration.
    """
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.0,  # Deterministic for consistent extraction
        max_retries: int = 3,
        schema_loader: Optional[DomainSchemaLoader] = None,
    ):
        """
        Initialize the relation extractor.
        
        Args:
            model: OpenAI model to use
            temperature: Temperature for generation (0.0 = deterministic)
            max_retries: Maximum retries on API errors
            schema_loader: Optional schema loader instance (uses singleton if not provided)
        """
        self.client = OpenAI(
            api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
            base_url=AI_INTEGRATIONS_OPENAI_BASE_URL,
        )
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
        self._schema_loader = schema_loader
    
    @property
    def schema_loader(self) -> DomainSchemaLoader:
        """Get schema loader (lazy initialization)."""
        if self._schema_loader is None:
            self._schema_loader = get_schema_loader()
        return self._schema_loader
    
    def get_valid_relation_types(self) -> Set[str]:
        """Get set of valid relationship type names from schema."""
        return self.schema_loader.get_valid_relationship_types()
    
    def _build_relation_extraction_prompt(self, text: str, entities_str: str) -> str:
        """Build dynamic relation extraction prompt from active schema."""
        schema = self.schema_loader.schema
        domain = schema.domain
        
        rel_descriptions = []
        for name, rel_config in schema.relationship_types.items():
            desc = rel_config.description or f"{name} relationship"
            sources = "/".join(rel_config.source_types) if rel_config.source_types else "any"
            targets = "/".join(rel_config.target_types) if rel_config.target_types else "any"
            cardinality_note = " (one target only)" if rel_config.is_many_to_one() else ""
            
            rel_descriptions.append(f"- {name}: {desc}")
            rel_descriptions.append(f"  Source types: {sources} → Target types: {targets}{cardinality_note}")
        
        rel_list = "\n".join(rel_descriptions)
        rel_type_names = ", ".join(schema.relationship_types.keys())
        
        prompt = f"""You are an expert at extracting relationships between entities from documents.

Given the following text and the list of known entities, extract ALL relationships.

## OPEN CAPTURE MODE

You may use ANY relationship type that accurately describes the connection. Common types include:

PROJECT MEMBERSHIP:
- WORKS_ON: Person works on a project (e.g., "David Kim is on Project Phoenix")
- LEADS: Person leads/directs a project or team
- MANAGES: Person manages a team or project
- MEMBER_OF: Person is a member of a team or organization

EMPLOYMENT:
- WORKS_AT: Person works at an organization
- HAS_ROLE: Person has a job title/role
- REPORTS_TO: Person reports to another person

PROJECT STRUCTURE:
- HAS_MILESTONE: Project has a milestone
- HAS_BUDGET: Project/org has a budget amount
- DELIVERS: Project delivers a deliverable
- DEPENDS_ON: Entity depends on another entity

If you find a relationship that doesn't fit these types, CREATE A NEW TYPE that accurately describes it.

KNOWN ENTITIES:
{entities_str}

## CRITICAL RULES

1. When a PERSON is listed under a PROJECT heading (e.g., "Core Team Members"), extract WORKS_ON relationship to the project
2. When a PERSON has a title like "Project Director", extract both HAS_ROLE and LEADS relationships
3. Extract ALL relationships - every person on a team should have a relationship to the project
4. Both source and target entities must be from KNOWN ENTITIES
5. When multiple people are listed (e.g., "X, Y, and Z"), extract SEPARATE relationships for each

TEXT:
{text}

Respond with ONLY valid JSON array, no markdown code blocks or other text. Format:
[
  {{
    "relation_type": "RELATION_TYPE",
    "source_name": "Source Entity",
    "target_name": "Target Entity",
    "source_span": "exact text showing relationship",
    "confidence": 0.95
  }}
]"""
        return prompt
    
    def _build_system_prompt(self) -> str:
        """Build dynamic system prompt from active schema."""
        schema = self.schema_loader.schema
        return f"You are an expert at extracting relationships between {schema.domain} entities. Respond only with valid JSON."
    
    def _generate_relation_id(
        self, 
        relation_type: str, 
        source_name: str, 
        target_name: str
    ) -> str:
        """Generate deterministic relation ID."""
        combined = f"{relation_type}:{source_name.lower()}:{target_name.lower()}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _format_entities_for_prompt(self, entities: List[Dict]) -> str:
        """Format entity list for the prompt."""
        lines = []
        for entity in entities:
            entity_type = entity.get("entity_type", "UNKNOWN")
            name = entity.get("canonical_name", entity.get("name", "Unknown"))
            lines.append(f"- {entity_type}: {name}")
        return "\n".join(lines)
    
    def _parse_llm_response(self, response_text: str) -> List[Dict]:
        """Parse LLM response into structured relations."""
        text = response_text.strip()
        if text.startswith("```"):
            text = re.sub(r"```json?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        
        try:
            relations = json.loads(text)
            if isinstance(relations, list):
                return relations
            return []
        except json.JSONDecodeError:
            try:
                match = re.search(r'\[.*\]', text, re.DOTALL)
                if match:
                    return json.loads(match.group())
            except:
                pass
            return []
    
    def _strip_type_prefix(self, name: str) -> str:
        """Remove entity type prefix like 'DOCUMENT: ' from a name."""
        prefixes = ['PERSON:', 'ORGANIZATION:', 'DOCUMENT:', 'LOCATION:', 
                    'EVENT:', 'CONCEPT:', 'PROCESS:', 'DATE:',
                    'SERVICE:', 'COMPONENT:', 'TEAM:', 'DATABASE:', 'INCIDENT:']
        name = name.strip()
        for prefix in prefixes:
            if name.upper().startswith(prefix):
                return name[len(prefix):].strip()
        return name
    
    def _fuzzy_match(self, name: str, entity_names_lower: set) -> bool:
        """Check if name matches any entity (exact or as substring)."""
        name_lower = name.lower().strip()
        if name_lower in entity_names_lower:
            return True
        for entity_name in entity_names_lower:
            if name_lower in entity_name or entity_name in name_lower:
                return True
        return False
    
    def _validate_relation(self, relation: Dict, entity_names: set) -> bool:
        """Validate extracted relation has required fields and valid references.
        
        Note: We allow any relationship type (not just schema-defined ones) to support
        domain-agnostic extraction where the LLM creates appropriate types.
        """
        required = ["relation_type", "source_name", "target_name"]
        for fld in required:
            if fld not in relation:
                return False
        
        source_name = self._strip_type_prefix(relation["source_name"])
        target_name = self._strip_type_prefix(relation["target_name"])
        entity_names_lower = {n.lower() for n in entity_names}
        
        source_found = self._fuzzy_match(source_name, entity_names_lower)
        target_found = self._fuzzy_match(target_name, entity_names_lower)
        
        return source_found and target_found
    
    def _normalize_relation(self, relation: Dict) -> Dict:
        """Normalize relation fields."""
        relation["source_name"] = self._strip_type_prefix(relation["source_name"])
        relation["target_name"] = self._strip_type_prefix(relation["target_name"])
        relation["relation_type"] = relation["relation_type"].upper()
        
        if "confidence" not in relation:
            relation["confidence"] = 0.75
        else:
            relation["confidence"] = min(1.0, max(0.0, float(relation["confidence"])))
        
        if "source_span" not in relation:
            relation["source_span"] = f"{relation['source_name']} {relation['relation_type']} {relation['target_name']}"
        
        return relation
    
    def extract_from_text(
        self,
        text: str,
        entities: List[Dict],
        document_id: str,
        chunk_id: str = "",
        document_type: str = None,
    ) -> List[ExtractedRelation]:
        """
        Extract relations from text using LLM.
        
        Args:
            text: Text to extract relations from
            entities: List of known entities (with 'canonical_name' and 'entity_type')
            document_id: ID of the source document
            chunk_id: ID of the source chunk
            document_type: Type of document (resume, incident_report, etc.)
            
        Returns:
            List of ExtractedRelation objects
        """
        if not text.strip() or not entities:
            print(f"[RelationExtractor] Skipping: text={bool(text.strip())}, entities={len(entities) if entities else 0}")
            return []
        
        print(f"[RelationExtractor] Extracting relations from {len(entities)} entities")
        
        entity_names = {
            e.get("canonical_name", e.get("name", "")) 
            for e in entities 
            if e.get("canonical_name") or e.get("name")
        }
        
        entities_str = self._format_entities_for_prompt(entities)
        prompt = self._build_relation_extraction_prompt(text, entities_str)
        system_prompt = self._build_system_prompt()
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=2000,
                )
                
                response_text = response.choices[0].message.content or ""
                raw_relations = self._parse_llm_response(response_text)
                
                print(f"[RelationExtractor] LLM returned {len(raw_relations)} raw relations")
                for raw in raw_relations:
                    print(f"[RelationExtractor] Raw: {raw.get('source_name', '?')} -{raw.get('relation_type', '?')}-> {raw.get('target_name', '?')}")
                
                relations = []
                valid_types = self.get_valid_relation_types()
                for raw in raw_relations:
                    if not self._validate_relation(raw, entity_names):
                        rel_type = raw.get("relation_type", "UNKNOWN").upper()
                        source = raw.get("source_name", "?")
                        target = raw.get("target_name", "?")
                        source_found = source.lower() in {n.lower() for n in entity_names}
                        target_found = target.lower() in {n.lower() for n in entity_names}
                        type_valid = rel_type in valid_types
                        print(f"[RelationExtractor] Skipped: {source} -{rel_type}-> {target} (type_valid={type_valid}, source_found={source_found}, target_found={target_found})")
                        continue
                    
                    normalized = self._normalize_relation(raw)
                    
                    relation = ExtractedRelation(
                        id=self._generate_relation_id(
                            normalized["relation_type"],
                            normalized["source_name"],
                            normalized["target_name"]
                        ),
                        relation_type=normalized["relation_type"],
                        source_name=normalized["source_name"],
                        target_name=normalized["target_name"],
                        source_span=normalized["source_span"],
                        source_document_id=document_id,
                        source_chunk_id=chunk_id,
                        confidence=normalized["confidence"],
                    )
                    relations.append(relation)
                
                return relations
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    print(f"Relation extraction failed after {self.max_retries} attempts: {e}")
                    return []
        
        return []
    
    def extract_from_chunks(
        self,
        chunks: List[Dict],
        entities: List[Dict],
        document_id: str,
    ) -> List[ExtractedRelation]:
        """
        Extract relations from multiple chunks.
        
        Args:
            chunks: List of chunk dictionaries with 'content' and 'chunk_id'
            entities: List of known entities
            document_id: ID of the source document
            
        Returns:
            List of ExtractedRelation objects
        """
        all_relations = []
        
        for chunk in chunks:
            content = chunk.get("content", "")
            chunk_id = chunk.get("chunk_id", "")
            
            relations = self.extract_from_text(
                text=content,
                entities=entities,
                document_id=document_id,
                chunk_id=chunk_id,
            )
            all_relations.extend(relations)
        
        return self._deduplicate_relations(all_relations)
    
    def _deduplicate_relations(
        self,
        relations: List[ExtractedRelation]
    ) -> List[ExtractedRelation]:
        """Deduplicate relations, keeping highest confidence."""
        relation_map = {}
        
        for relation in relations:
            key = (
                relation.relation_type,
                relation.source_name.lower(),
                relation.target_name.lower()
            )
            
            if key not in relation_map:
                relation_map[key] = relation
            elif relation.confidence > relation_map[key].confidence:
                relation_map[key] = relation
        
        return list(relation_map.values())
    
    def extract_with_ontology(
        self,
        text: str,
        entities: List[Dict],
        document_id: str,
        document_type: str,
        relationship_types: List[Dict],
        chunk_id: str = "",
    ) -> List[ExtractedRelation]:
        """
        Extract relations using ontology-guided prompt.
        
        Args:
            text: Text to extract relations from
            entities: List of known entities
            document_id: Document ID
            document_type: Type of document (resume, incident_report, etc.)
            relationship_types: List of relationship type definitions with name/definition
            chunk_id: Chunk ID
            
        Returns:
            List of ExtractedRelation objects
        """
        if not text.strip() or not entities:
            return []
        
        entity_names = {
            e.get("canonical_name", e.get("name", ""))
            for e in entities
            if e.get("canonical_name") or e.get("name")
        }
        
        entities_str = self._format_entities_for_prompt(entities)
        
        rel_descriptions = []
        for rt in relationship_types:
            name = rt.get("name", "UNKNOWN")
            definition = rt.get("definition", f"{name} relationship")
            source_types = rt.get("source_types", [])
            target_types = rt.get("target_types", [])
            
            sources = ", ".join(source_types) if source_types else "any"
            targets = ", ".join(target_types) if target_types else "any"
            rel_descriptions.append(f"- {name}: {definition} (from {sources} to {targets})")
        
        rel_list = "\n".join(rel_descriptions) if rel_descriptions else "No predefined types - extract what you find"
        
        prompt = f"""You are an expert at extracting relationships between entities from {document_type} documents.

Given the following text and the list of known entities, extract all relationships.

RECOMMENDED RELATIONSHIP TYPES for {document_type.upper()} documents:
{rel_list}

Use these types when they fit. If you find a relationship not covered by these types, 
create a descriptive relationship type in UPPERCASE_UNDERSCORE format.

KNOWN ENTITIES:
{entities_str}

For each relationship, provide:
1. relation_type: A relationship type (preferably from the recommended list)
2. source_name: The name of the source entity (must be from KNOWN ENTITIES)
3. target_name: The name of the target entity (must be from KNOWN ENTITIES)
4. source_span: The exact text that indicates this relationship
5. confidence: Your confidence in this extraction (0.0 to 1.0)

IMPORTANT RULES:
- Extract ALL relationships mentioned in the text
- Both source and target entities must be from the KNOWN ENTITIES list
- Use recommended relationship types when they fit the document type
- Assign lower confidence (0.5-0.7) if the relationship is implied
- Assign higher confidence (0.8-1.0) if the relationship is explicitly stated

TEXT:
{text}

Respond with ONLY valid JSON array:
[
  {{
    "relation_type": "RELATION_TYPE",
    "source_name": "Source Entity",
    "target_name": "Target Entity",
    "source_span": "exact text",
    "confidence": 0.95
  }}
]"""

        system_prompt = f"You are an expert at extracting relationships from {document_type} documents. Respond only with valid JSON."
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=8000,
                )
                
                response_text = response.choices[0].message.content or ""
                raw_relations = self._parse_llm_response(response_text)
                
                print(f"[RelationExtractor] Ontology-guided: {len(raw_relations)} raw relations for {document_type}")
                
                relations = []
                for raw in raw_relations:
                    if not self._validate_relation(raw, entity_names):
                        continue
                    
                    normalized = self._normalize_relation(raw)
                    
                    relation = ExtractedRelation(
                        id=self._generate_relation_id(
                            normalized["relation_type"],
                            normalized["source_name"],
                            normalized["target_name"]
                        ),
                        relation_type=normalized["relation_type"],
                        source_name=normalized["source_name"],
                        target_name=normalized["target_name"],
                        source_span=normalized["source_span"],
                        source_document_id=document_id,
                        source_chunk_id=chunk_id,
                        confidence=normalized["confidence"],
                    )
                    relations.append(relation)
                
                return relations
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    print(f"Ontology-guided relation extraction failed: {e}")
                    return []
        
        return []
