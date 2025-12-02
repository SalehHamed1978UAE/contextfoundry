"""
Entity Extractor for Context Foundry MVP2.
Uses LLM-powered NER to extract IT operations entities.

Uses Replit AI Integrations for OpenAI access (no API key required, billed to credits).
"""
import json
import os
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
import hashlib

from openai import OpenAI

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")


ENTITY_TYPES = {
    "SERVICE": {
        "description": "A software service or microservice (e.g., Payment Service, Auth Service)",
        "required_fields": ["canonical_name"],
        "optional_fields": ["language", "framework", "tier", "description"],
    },
    "COMPONENT": {
        "description": "An infrastructure component (e.g., Redis cache, Kafka queue, Load Balancer)",
        "required_fields": ["canonical_name", "component_type"],
        "optional_fields": ["version", "description"],
    },
    "DATABASE": {
        "description": "A database instance (e.g., Payments Database, User Database)",
        "required_fields": ["canonical_name", "db_type"],
        "optional_fields": ["version", "description"],
    },
    "TEAM": {
        "description": "An engineering or operations team (e.g., Payments Team, SRE Team)",
        "required_fields": ["name"],
        "optional_fields": ["slack_channel", "description"],
    },
    "PERSON": {
        "description": "A person (engineer, manager, on-call contact)",
        "required_fields": ["canonical_name"],
        "optional_fields": ["role", "team", "email", "phone", "expertise"],
    },
    "INCIDENT": {
        "description": "An incident or outage (e.g., INC-2024-001)",
        "required_fields": ["external_id", "title"],
        "optional_fields": ["severity", "status", "date", "duration_minutes", "description"],
    },
}


ENTITY_EXTRACTION_PROMPT = """You are an expert at extracting IT operations entities from technical documents.

Given the following text, extract all entities of these types:
- SERVICE: Software services or microservices
- COMPONENT: Infrastructure components (caches, queues, load balancers)
- DATABASE: Database instances
- TEAM: Engineering or operations teams
- PERSON: People (engineers, managers, on-call contacts)
- INCIDENT: Incidents or outages

For each entity, provide:
1. entity_type: One of SERVICE, COMPONENT, DATABASE, TEAM, PERSON, INCIDENT
2. canonical_name: The standardized name of the entity
3. properties: Additional properties like role, severity, etc.
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
    "entity_type": "SERVICE",
    "canonical_name": "Payment Service",
    "properties": {{"language": "Python", "tier": "critical"}},
    "source_span": "Payment Service",
    "confidence": 0.95
  }}
]
"""


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
    LLM-powered entity extractor for IT operations entities.
    
    Supports: SERVICE, COMPONENT, DATABASE, TEAM, PERSON, INCIDENT
    """
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_retries: int = 3,
    ):
        """
        Initialize the entity extractor.
        
        Args:
            model: OpenAI model to use
            temperature: Temperature for generation (lower = more deterministic)
            max_retries: Maximum retries on API errors
        """
        self.client = OpenAI(
            api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
            base_url=AI_INTEGRATIONS_OPENAI_BASE_URL,
        )
        self.model = model
        self.temperature = temperature
        self.max_retries = max_retries
    
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
        """Validate extracted entity has required fields."""
        if "entity_type" not in entity:
            return False
        if "canonical_name" not in entity and "name" not in entity:
            return False
        if entity["entity_type"] not in ENTITY_TYPES:
            return False
        return True
    
    def _normalize_entity(self, entity: Dict) -> Dict:
        """Normalize entity fields."""
        if "name" in entity and "canonical_name" not in entity:
            entity["canonical_name"] = entity.pop("name")
        
        entity["canonical_name"] = entity["canonical_name"].strip()
        
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
        
        prompt = ENTITY_EXTRACTION_PROMPT.format(text=text)
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert at extracting IT operations entities. Respond only with valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=2000,
                )
                
                response_text = response.choices[0].message.content
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
