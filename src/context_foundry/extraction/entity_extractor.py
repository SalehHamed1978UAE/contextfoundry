"""
Entity Extractor for Context Foundry - Domain-Agnostic Version.
Uses LLM-powered NER to extract entities based on active schema configuration.

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
            "extracted_at": self.extracted_at.isoformat(),
        }


class EntityExtractor:
    """
    LLM-powered entity extractor that works with any domain schema.
    
    Loads entity types dynamically from the active domain schema configuration.
    """
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_retries: int = 3,
        schema_loader: Optional[DomainSchemaLoader] = None,
    ):
        """
        Initialize the entity extractor.
        
        Args:
            model: OpenAI model to use
            temperature: Temperature for generation (lower = more deterministic)
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
        """Build dynamic entity extraction prompt from active schema."""
        schema = self.schema_loader.schema
        domain = schema.domain
        
        entity_descriptions = []
        for name, entity_config in schema.entity_types.items():
            desc = entity_config.description or f"A {name.lower()}"
            entity_descriptions.append(f"- {name}: {desc}")
            
            if entity_config.required_fields:
                entity_descriptions.append(f"  Required: {', '.join(entity_config.required_fields)}")
            if entity_config.optional_fields:
                entity_descriptions.append(f"  Optional: {', '.join(entity_config.optional_fields)}")
        
        entity_list = "\n".join(entity_descriptions)
        entity_type_names = ", ".join(schema.entity_types.keys())
        
        prompt = f"""You are an expert at extracting entities from documents in the {domain} domain.

Given the following text, extract all entities of these types:
{entity_list}

For each entity, provide:
1. entity_type: One of {entity_type_names}
2. canonical_name: The standardized name of the entity
3. properties: Additional properties (as listed above for each type)
4. source_span: The exact text span where this entity appears
5. confidence: Your confidence in this extraction (0.0 to 1.0)

IMPORTANT RULES:
- Only extract entities that are EXPLICITLY mentioned in the text
- Do NOT infer or hallucinate entities that aren't mentioned
- Use the exact text span where the entity appears
- Assign lower confidence (0.6-0.8) if the entity type is ambiguous
- Assign higher confidence (0.9-1.0) if the entity type is clearly stated

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
    
    def _build_system_prompt(self) -> str:
        """Build dynamic system prompt from active schema."""
        schema = self.schema_loader.schema
        return f"You are an expert at extracting {schema.domain} entities. Respond only with valid JSON."
    
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
    
    def _normalize_entity(self, entity: Dict) -> Dict:
        """Normalize entity fields."""
        if "name" in entity and "canonical_name" not in entity:
            entity["canonical_name"] = entity.pop("name")
        
        entity["canonical_name"] = entity["canonical_name"].strip()
        entity["entity_type"] = entity["entity_type"].upper()
        
        if "properties" not in entity:
            entity["properties"] = {}
        
        if "confidence" not in entity:
            entity["confidence"] = 0.75
        else:
            entity["confidence"] = min(1.0, max(0.0, float(entity["confidence"])))
        
        if "source_span" not in entity:
            entity["source_span"] = entity["canonical_name"]
        
        return entity
    
    def extract_from_text(
        self,
        text: str,
        document_id: str,
        chunk_id: str = "",
        sentence_idx: int = 0,
    ) -> List[ExtractedEntity]:
        """
        Extract entities from text using LLM.
        
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
        
        prompt = self._build_entity_extraction_prompt(text)
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
                    print(f"Entity extraction failed after {self.max_retries} attempts: {e}")
                    return []
        
        return []
    
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
