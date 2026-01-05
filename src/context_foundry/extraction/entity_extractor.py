"""
Entity Extractor for Context Foundry - Domain-Agnostic Version.
Uses LLM-powered NER to extract entities based on active schema configuration.

Uses Replit AI Integrations for OpenAI access (no API key required, billed to credits).
"""
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field
from datetime import datetime
import hashlib

from openai import OpenAI

from ..config.domain_schema import get_schema_loader, DomainSchemaLoader


def load_few_shot_examples(domain: str = "core") -> list:
    """Load few-shot examples for the specified domain."""
    examples_dir = Path(__file__).parent.parent.parent.parent / "brain" / "examples"
    
    domain_file = examples_dir / f"{domain}_examples.json"
    core_file = examples_dir / "core_examples.json"
    
    file_to_load = domain_file if domain_file.exists() else core_file
    
    if not file_to_load.exists():
        return []
    
    try:
        with open(file_to_load, 'r') as f:
            data = json.load(f)
            return data.get('examples', [])
    except Exception:
        return []


def format_few_shot_examples(examples: list) -> str:
    """Format few-shot examples for inclusion in prompt."""
    if not examples:
        return "No examples available."
    
    formatted = []
    for i, ex in enumerate(examples, 1):
        input_text = ex.get('input', '')
        output = ex.get('output', [])
        
        output_str = "\n".join([
            f"  - \"{e['name']}\" -> {e['type']} ({e.get('reasoning', '')})"
            for e in output
        ])
        
        formatted.append(f"Example {i}:\nInput: \"{input_text}\"\nOutput:\n{output_str}")
    
    return "\n\n".join(formatted)

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")

CORE_FOUNDATION_TYPES = {
    "PERSON": {
        "description": "A human individual - any named person, role, or position",
        "required_fields": ["canonical_name"],
        "optional_fields": ["role", "title", "organization", "email"]
    },
    "ORGANIZATION": {
        "description": "A company, team, department, institution, or any organized group",
        "required_fields": ["canonical_name"],
        "optional_fields": ["org_type", "industry", "location", "parent_org"]
    },
    "DOCUMENT": {
        "description": "A document, report, file, policy, or written artifact",
        "required_fields": ["canonical_name"],
        "optional_fields": ["document_type", "author", "date", "version"]
    },
    "LOCATION": {
        "description": "A physical or logical place - city, region, address, or venue",
        "required_fields": ["canonical_name"],
        "optional_fields": ["location_type", "address", "parent_location"]
    },
    "EVENT": {
        "description": "An occurrence, meeting, incident, milestone, or happening",
        "required_fields": ["canonical_name"],
        "optional_fields": ["event_type", "date", "duration", "participants"]
    },
    "CONCEPT": {
        "description": "An abstract idea, topic, theme, principle, or methodology",
        "required_fields": ["canonical_name"],
        "optional_fields": ["category", "related_concepts", "definition"]
    },
    "PROCESS": {
        "description": "A workflow, procedure, method, or sequence of steps",
        "required_fields": ["canonical_name"],
        "optional_fields": ["process_type", "steps", "owner", "status"]
    },
    "DATE": {
        "description": "A specific date, time period, deadline, or temporal reference",
        "required_fields": ["canonical_name"],
        "optional_fields": ["date_value", "date_type", "timezone"]
    }
}


@dataclass
class ExtractedEntity:
    """Represents an entity extracted from text."""
    id: str
    entity_type: str
    canonical_name: str
    properties: Dict
    source_span: str
    source_document_id: str
    source_chunk_id: str
    source_sentence_idx: int
    confidence: float
    tenant_id: Optional[str] = None
    extracted_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "canonical_name": self.canonical_name,
            "properties": self.properties,
            "source_span": self.source_span,
            "source_document_id": self.source_document_id,
            "source_chunk_id": self.source_chunk_id,
            "source_sentence_idx": self.source_sentence_idx,
            "confidence": self.confidence,
            "tenant_id": self.tenant_id,
            "extracted_at": self.extracted_at.isoformat(),
        }


class EntityExtractor:
    """
    LLM-powered entity extractor that works with any domain schema.
    
    Loads entity types dynamically from the active domain schema configuration.
    """
    
    def __init__(
        self,
        model: str = "gpt-4o",  # Using GPT-4o for better entity extraction (4o-mini has ~21% omission rate)
        temperature: float = 0.0,  # Deterministic for consistent extraction
        max_retries: int = 3,
        schema_loader: Optional[DomainSchemaLoader] = None,
    ):
        """
        Initialize the entity extractor.
        
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
    
    def get_valid_entity_types(self) -> Set[str]:
        """Get set of valid entity type names from schema."""
        return self.schema_loader.get_valid_entity_types()
    
    def _build_entity_extraction_prompt(self, text: str) -> str:
        """Build simplified entity extraction prompt optimized for completeness."""
        schema = self.schema_loader.schema
        entity_type_names = ", ".join(schema.entity_types.keys())
        
        prompt = f"""Extract ALL entities from this text. Be EXHAUSTIVE - a short list is a FAILED extraction.

Valid types: {entity_type_names}

## ENTITY TYPE DEFINITIONS

CONCEPT: Named frameworks, methodologies, models, systems, approaches, architectures
PERSON: Named individuals AND job roles/titles (Data Steward, CEO, CFO)
ORGANIZATION: Companies, agencies, departments, ministries, groups that ACT
LOCATION: PHYSICAL places ONLY (cities, countries, buildings)
PROCESS: Workflows, procedures, phases, stages
EVENT: Meetings, milestones, occurrences
DATE: Time references (December 2025, Q4, Months 1-6)
DOCUMENT: Referenced reports, policies, forms

## EXTRACTION RULES

1. Extract ALL capitalized multi-word terms and named concepts
2. Extract document titles, section headers, and acronyms  
3. Extract job titles and roles as PERSON
4. Be EXHAUSTIVE - do not stop until every entity is captured
5. When uncertain, INCLUDE with confidence 0.7-0.8

## OUTPUT FORMAT

Return valid JSON array only (no markdown):
[{{"entity_type": "TYPE", "canonical_name": "exact text", "confidence": 0.9}}]

## TEXT TO EXTRACT

{text}"""
        return prompt
    
    def _chunk_text(self, text: str, chunk_size: int = 2000, overlap: int = 400) -> List[str]:
        """Split text into overlapping chunks to avoid output saturation."""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = chunk.rfind('. ')
                if last_period > chunk_size * 0.6:
                    end = start + last_period + 2
                    chunk = text[start:end]
            
            chunks.append(chunk)
            start = end - overlap
            if start >= len(text):
                break
        
        return chunks
    
    def _build_system_prompt(self) -> str:
        """Build dynamic system prompt from active schema."""
        schema = self.schema_loader.schema
        return f"You are an expert entity extractor. Your goal is COMPLETENESS - extract ALL entities from {schema.domain} documents. Respond only with valid JSON."
    
    def _generate_entity_id(self, entity_type: str, canonical_name: str) -> str:
        """Generate deterministic entity ID."""
        combined = f"{entity_type}:{canonical_name.lower()}"
        return hashlib.md5(combined.encode()).hexdigest()
    
    def _parse_llm_response(self, response_text: str) -> List[Dict]:
        """Parse LLM response into structured entities."""
        text = response_text.strip()
        if text.startswith("```"):
            text = re.sub(r"```json?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        
        try:
            entities = json.loads(text)
            if isinstance(entities, list):
                return entities
            return []
        except json.JSONDecodeError:
            try:
                match = re.search(r'\[.*\]', text, re.DOTALL)
                if match:
                    return json.loads(match.group())
            except:
                pass
            return []
    
    def _validate_entity(self, entity: Dict) -> bool:
        """Validate extracted entity has required fields and valid type."""
        if "entity_type" not in entity:
            return False
        if "canonical_name" not in entity and "name" not in entity:
            return False
        if entity["entity_type"].upper() not in self.get_valid_entity_types():
            return False
        return True
    
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
    
    SPECIFIC_TYPE_PATTERNS = [
        ("TEAM", ["team", "squad"]),
        ("INCIDENT", ["inc-", "incident", "outage", "sev1", "sev2"]),
        ("SERVICE", ["service", "gateway", "api", "app", "server", "endpoint", "microservice", "portal"]),
        ("DATABASE", ["database", "db", "datastore", "store", "warehouse", "cache", "redis", "postgres", "mysql", "inventory"]),
    ]
    
    def _correct_entity_type(self, entity: Dict) -> Dict:
        """Correct common entity type misclassifications.
        
        Uses a priority system:
        1. Direct mapping from TYPE_MAPPING (e.g., GATEWAY → SERVICE)
        2. Pattern matching on entity name (e.g., "Payment Gateway" → SERVICE)
        3. LOCATION → ORGANIZATION ACT test
        """
        entity_type = entity.get("entity_type", "").upper()
        name = entity.get("canonical_name", entity.get("name", ""))
        name_lower = name.lower()
        
        if entity_type in self.TYPE_MAPPING:
            new_type = self.TYPE_MAPPING[entity_type]
            logger.info(f"[TypeCorrection] Mapping: {entity_type} → {new_type} for '{name}'")
            entity["entity_type"] = new_type
            return entity
        
        if entity_type in ("ORGANIZATION", "PROCESS", "EVENT", "CONCEPT"):
            for specific_type, patterns in self.SPECIFIC_TYPE_PATTERNS:
                if any(pattern in name_lower for pattern in patterns):
                    logger.info(f"[TypeCorrection] Pattern match: {entity_type} → {specific_type} for '{name}'")
                    entity["entity_type"] = specific_type
                    return entity
        
        if entity_type == "LOCATION":
            org_patterns = [
                "government", "ministry", "department", "agency", "committee",
                "corporation", "company", "holding", "subsidiary", "division",
                "board", "council", "authority", "office", "bureau", "institute",
                "foundation", "association", "federation", "organization", "team",
                "group", "unit", "branch", "sector", "regime", "administration"
            ]
            for pattern in org_patterns:
                if pattern in name_lower:
                    entity["entity_type"] = "ORGANIZATION"
                    break
        
        return entity
    
    def _normalize_entity(self, entity: Dict) -> Dict:
        """Normalize entity fields."""
        if "name" in entity and "canonical_name" not in entity:
            entity["canonical_name"] = entity.pop("name")
        
        entity["canonical_name"] = entity["canonical_name"].strip()
        entity["entity_type"] = entity["entity_type"].upper()
        
        entity = self._correct_entity_type(entity)
        
        if "properties" not in entity:
            entity["properties"] = {}
        
        if "confidence" not in entity:
            entity["confidence"] = 0.75
        else:
            entity["confidence"] = min(1.0, max(0.0, float(entity["confidence"])))
        
        if "source_span" not in entity:
            entity["source_span"] = entity["canonical_name"]
        
        return entity
    
    def _build_concept_gap_check_prompt(self, text: str, already_extracted: List[str]) -> str:
        """Build prompt for second-pass concept extraction."""
        already_list = ", ".join(already_extracted[:30]) if already_extracted else "none"
        
        return f"""You already extracted these entities: {already_list}

Now find ADDITIONAL entities we MISSED. Focus on:

1. CONCEPT: Named frameworks, methodologies, standards, approaches, models, systems, architectures
   - Look for capitalized multi-word terms: "Federated Data Catalog", "Hub-and-Spoke Model"
   - Look for acronyms and their full names: "KPI", "ROI", "GDPR", "API"
   - Section titles and document headers are often CONCEPT entities

2. PERSON: Job titles and named roles: "Data Steward", "Chief Data Officer", "Executive Sponsor"

3. DOCUMENT: Referenced documents, reports, policies, guidelines

4. DATE: All time references: "Q1 2025", "Phase 1", "Year 1", "Months 1-6"

5. PROCESS: Named processes, workflows, phases, stages, approaches

Return ONLY entities NOT in the already-extracted list above.

Return valid JSON array:
[{{"entity_type": "TYPE", "canonical_name": "name", "properties": {{}}, "source_span": "context", "confidence": 0.85}}]

TEXT:
{text}"""

    def _run_extraction_pass(
        self,
        prompt: str,
        system_prompt: str,
        document_id: str,
        chunk_id: str,
        sentence_idx: int,
    ) -> List[ExtractedEntity]:
        """Run a single extraction pass and return entities."""
        for attempt in range(self.max_retries):
            try:
                print(f"[EntityExtractor] Using model: {self.model}")
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=4000,
                )
                
                response_text = response.choices[0].message.content or ""
                raw_entities = self._parse_llm_response(response_text)
                
                entities = []
                for raw in raw_entities:
                    if not self._validate_entity(raw):
                        continue
                    
                    normalized = self._normalize_entity(raw)
                    
                    entity = ExtractedEntity(
                        id=self._generate_entity_id(
                            normalized["entity_type"],
                            normalized["canonical_name"]
                        ),
                        entity_type=normalized["entity_type"],
                        canonical_name=normalized["canonical_name"],
                        properties=normalized["properties"],
                        source_span=normalized["source_span"],
                        source_document_id=document_id,
                        source_chunk_id=chunk_id,
                        source_sentence_idx=sentence_idx,
                        confidence=normalized["confidence"],
                    )
                    entities.append(entity)
                
                return entities
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    print(f"Extraction pass failed after {self.max_retries} attempts: {e}")
                    return []
        
        return []

    def _extract_from_single_chunk(
        self,
        text: str,
        document_id: str,
        chunk_id: str,
        sentence_idx: int,
    ) -> List[ExtractedEntity]:
        """Extract entities from a single text chunk."""
        prompt = self._build_entity_extraction_prompt(text)
        system_prompt = self._build_system_prompt()
        
        return self._run_extraction_pass(
            prompt, system_prompt, document_id, chunk_id, sentence_idx
        )

    def extract_from_text(
        self,
        text: str,
        document_id: str,
        chunk_id: str = "",
        sentence_idx: int = 0,
    ) -> List[ExtractedEntity]:
        """
        Extract entities from text using chunked extraction to avoid output saturation.
        
        Long documents are split into ~2000 char chunks with overlap to ensure
        the LLM doesn't hit the "lazy list" effect (RLHF-induced output saturation).
        
        Args:
            text: Text to extract entities from
            document_id: ID of the source document
            chunk_id: ID of the source chunk
            sentence_idx: Index of the source sentence
            
        Returns:
            List of ExtractedEntity objects
        """
        if not text.strip():
            return []
        
        # Split into chunks to avoid output saturation
        chunks = self._chunk_text(text, chunk_size=2000, overlap=400)
        print(f"[EntityExtractor] Processing {len(chunks)} chunks from {len(text)} chars")
        
        all_entities = []
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            
            chunk_entities = self._extract_from_single_chunk(
                chunk, document_id, f"{chunk_id}_c{i}", sentence_idx
            )
            print(f"[EntityExtractor] Chunk {i+1}/{len(chunks)}: {len(chunk_entities)} entities")
            all_entities.extend(chunk_entities)
        
        # Deduplicate across all chunks
        deduped = self._deduplicate_entities(all_entities)
        print(f"[EntityExtractor] Total: {len(all_entities)} raw, {len(deduped)} after dedup")
        return deduped
    
    def extract_from_chunks(
        self,
        chunks: List[Dict],
        document_id: str,
        batch_size: int = 5,
    ) -> List[ExtractedEntity]:
        """
        Extract entities from multiple chunks.
        
        Args:
            chunks: List of chunk dictionaries with 'content' and 'chunk_id'
            document_id: ID of the source document
            batch_size: Number of chunks to process at once
            
        Returns:
            List of ExtractedEntity objects
        """
        all_entities = []
        
        for chunk in chunks:
            content = chunk.get("content", "")
            chunk_id = chunk.get("chunk_id", "")
            start_sentence = chunk.get("start_sentence", 0)
            
            entities = self.extract_from_text(
                text=content,
                document_id=document_id,
                chunk_id=chunk_id,
                sentence_idx=start_sentence,
            )
            all_entities.extend(entities)
        
        return self._deduplicate_entities(all_entities)
    
    def _deduplicate_entities(
        self,
        entities: List[ExtractedEntity]
    ) -> List[ExtractedEntity]:
        """Deduplicate entities by canonical name, keeping highest confidence."""
        entity_map = {}
        
        for entity in entities:
            key = (entity.entity_type, entity.canonical_name.lower())
            
            if key not in entity_map:
                entity_map[key] = entity
            elif entity.confidence > entity_map[key].confidence:
                entity_map[key] = entity
        
        return list(entity_map.values())
    
    def _build_dynamic_prompt(self, text: str, entity_types: List[str]) -> str:
        """Build extraction prompt using a dynamic list of entity types."""
        entity_descriptions = []
        
        for type_name in entity_types:
            upper_name = type_name.upper()
            if upper_name in CORE_FOUNDATION_TYPES:
                config = CORE_FOUNDATION_TYPES[upper_name]
                desc = config["description"]
                entity_descriptions.append(f"- {upper_name}: {desc}")
            else:
                entity_descriptions.append(f"- {type_name}: Entity of type {type_name}")
        
        entity_list = "\n".join(entity_descriptions)
        entity_type_names = ", ".join(entity_types)
        
        prompt = f"""You are an expert at extracting entities from documents.

Given the following text, extract all entities of these types:
{entity_list}

For each entity, provide:
1. entity_type: One of {entity_type_names}
2. canonical_name: The standardized name of the entity
3. properties: Additional properties relevant to the entity type
4. source_span: The exact text span where this entity appears
5. confidence: Your confidence in this extraction (0.0 to 1.0)

IMPORTANT RULES:
- Extract ALL meaningful entities from the text
- Use the MOST SPECIFIC type that applies (prefer domain types over general types)
- Include people, organizations, concepts, processes, dates mentioned
- Use the exact text span where the entity appears
- Assign confidence based on how clearly the entity type is indicated

Return the result as a JSON array of objects.

TEXT:
{text}

Respond with ONLY valid JSON, no markdown code blocks or other text. Format:
[
  {{
    "entity_type": "ENTITY_TYPE",
    "canonical_name": "Entity Name",
    "properties": {{}},
    "source_span": "exact text",
    "confidence": 0.95
  }}
]"""
        return prompt

    def _extract_single_chunk_with_types(
        self,
        text: str,
        entity_types: List[str],
        document_id: str,
        chunk_id: str,
        sentence_idx: int,
    ) -> List[ExtractedEntity]:
        """Extract entities from a single chunk using custom types."""
        prompt = self._build_dynamic_prompt(text, entity_types)
        system_prompt = "You are an expert at extracting entities. Be EXHAUSTIVE. Respond only with valid JSON."
        
        valid_types = set(t.upper() for t in entity_types)
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=4000,
                )
                
                response_text = response.choices[0].message.content or ""
                raw_entities = self._parse_llm_response(response_text)
                
                entities = []
                
                for raw in raw_entities:
                    if "entity_type" not in raw:
                        continue
                    if "canonical_name" not in raw and "name" not in raw:
                        continue
                    
                    raw_type = raw["entity_type"].upper()
                    if raw_type not in valid_types:
                        for valid_type in valid_types:
                            if valid_type.upper() == raw_type:
                                raw["entity_type"] = valid_type
                                break
                        else:
                            continue
                    
                    normalized = self._normalize_entity(raw)
                    
                    entity = ExtractedEntity(
                        id=self._generate_entity_id(
                            normalized["entity_type"],
                            normalized["canonical_name"]
                        ),
                        entity_type=normalized["entity_type"],
                        canonical_name=normalized["canonical_name"],
                        properties=normalized["properties"],
                        source_span=normalized["source_span"],
                        source_document_id=document_id,
                        source_chunk_id=chunk_id,
                        source_sentence_idx=sentence_idx,
                        confidence=normalized["confidence"],
                    )
                    entities.append(entity)
                
                return entities
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    print(f"Entity extraction failed after {self.max_retries} attempts: {e}")
                    return []
        
        return []

    def extract_with_types(
        self,
        text: str,
        entity_types: List[str],
        document_id: str,
        chunk_id: str = "",
        sentence_idx: int = 0,
    ) -> List[ExtractedEntity]:
        """
        Extract entities using custom types with chunking to avoid output saturation.
        
        Long documents are split into ~2000 char chunks to prevent the LLM from
        hitting the "lazy list" effect (RLHF-induced output saturation).
        """
        if not text.strip():
            return []
        
        # Split into chunks to avoid output saturation
        chunks = self._chunk_text(text, chunk_size=2000, overlap=400)
        print(f"[EntityExtractor] Processing {len(chunks)} chunks from {len(text)} chars")
        
        all_entities = []
        for i, chunk in enumerate(chunks):
            if not chunk.strip():
                continue
            
            chunk_entities = self._extract_single_chunk_with_types(
                chunk, entity_types, document_id, f"{chunk_id}_c{i}", sentence_idx
            )
            print(f"[EntityExtractor] Chunk {i+1}/{len(chunks)}: {len(chunk_entities)} entities")
            all_entities.extend(chunk_entities)
        
        # Deduplicate across all chunks
        deduped = self._deduplicate_entities(all_entities)
        print(f"[EntityExtractor] Total: {len(all_entities)} raw, {len(deduped)} after dedup")
        return deduped

    def _build_core_foundation_prompt(self, text: str) -> str:
        """Build extraction prompt using Core Foundation types (fallback)."""
        entity_descriptions = []
        for name, config in CORE_FOUNDATION_TYPES.items():
            desc = config["description"]
            entity_descriptions.append(f"- {name}: {desc}")
            if config.get("required_fields"):
                entity_descriptions.append(f"  Required: {', '.join(config['required_fields'])}")
            if config.get("optional_fields"):
                entity_descriptions.append(f"  Optional: {', '.join(config['optional_fields'])}")
        
        entity_list = "\n".join(entity_descriptions)
        entity_type_names = ", ".join(CORE_FOUNDATION_TYPES.keys())
        
        prompt = f"""You are an expert at extracting entities from documents.

Given the following text, extract all entities of these UNIVERSAL types:
{entity_list}

For each entity, provide:
1. entity_type: One of {entity_type_names}
2. canonical_name: The standardized name of the entity
3. properties: Additional properties (as listed above for each type)
4. source_span: The exact text span where this entity appears
5. confidence: Your confidence in this extraction (0.0 to 1.0)

IMPORTANT RULES:
- Extract ALL meaningful entities from the text
- Include people, organizations, concepts, processes, dates mentioned
- Use the exact text span where the entity appears
- Assign confidence based on how clearly the entity type is indicated

Return the result as a JSON array of objects.

TEXT:
{text}

Respond with ONLY valid JSON, no markdown code blocks or other text. Format:
[
  {{
    "entity_type": "ENTITY_TYPE",
    "canonical_name": "Entity Name",
    "properties": {{}},
    "source_span": "exact text",
    "confidence": 0.95
  }}
]"""
        return prompt
    
    def extract_with_core_foundation(
        self,
        text: str,
        document_id: str,
        chunk_id: str = "",
        sentence_idx: int = 0,
    ) -> List[ExtractedEntity]:
        """
        Extract entities using Core Foundation types (fallback for domain-agnostic extraction).
        
        Args:
            text: Text to extract entities from
            document_id: ID of the source document
            chunk_id: ID of the source chunk
            sentence_idx: Index of the source sentence
            
        Returns:
            List of ExtractedEntity objects
        """
        if not text.strip():
            return []
        
        prompt = self._build_core_foundation_prompt(text)
        system_prompt = "You are an expert at extracting universal entities. Respond only with valid JSON."
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=4000,
                )
                
                response_text = response.choices[0].message.content or ""
                raw_entities = self._parse_llm_response(response_text)
                
                entities = []
                valid_types = set(CORE_FOUNDATION_TYPES.keys())
                
                for raw in raw_entities:
                    if "entity_type" not in raw:
                        continue
                    if "canonical_name" not in raw and "name" not in raw:
                        continue
                    if raw["entity_type"].upper() not in valid_types:
                        continue
                    
                    normalized = self._normalize_entity(raw)
                    
                    entity = ExtractedEntity(
                        id=self._generate_entity_id(
                            normalized["entity_type"],
                            normalized["canonical_name"]
                        ),
                        entity_type=normalized["entity_type"],
                        canonical_name=normalized["canonical_name"],
                        properties=normalized["properties"],
                        source_span=normalized["source_span"],
                        source_document_id=document_id,
                        source_chunk_id=chunk_id,
                        source_sentence_idx=sentence_idx,
                        confidence=normalized["confidence"],
                    )
                    entities.append(entity)
                
                print(f"[CoreFoundation] Extracted {len(entities)} entities using fallback types")
                return entities
                
            except Exception as e:
                if attempt == self.max_retries - 1:
                    print(f"Core Foundation extraction failed after {self.max_retries} attempts: {e}")
                    return []
        
        return []
