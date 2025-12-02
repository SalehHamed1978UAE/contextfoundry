"""
Relation Extractor for Context Foundry MVP2.
Uses LLM-powered relation extraction with confidence scoring.

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


RELATION_TYPES = {
    "DEPENDS_ON": {
        "description": "Service/component A depends on service/component B",
        "source_types": ["SERVICE", "COMPONENT"],
        "target_types": ["SERVICE", "COMPONENT", "DATABASE"],
    },
    "OWNS": {
        "description": "Team A owns service/component/database B",
        "source_types": ["TEAM"],
        "target_types": ["SERVICE", "COMPONENT", "DATABASE"],
    },
    "SUPPORTS": {
        "description": "Team A provides support for service B (but doesn't own it)",
        "source_types": ["TEAM"],
        "target_types": ["SERVICE", "COMPONENT"],
    },
    "MEMBER_OF": {
        "description": "Person A is a member of Team B",
        "source_types": ["PERSON"],
        "target_types": ["TEAM"],
    },
    "MANAGES": {
        "description": "Person A manages Team B (is lead/manager)",
        "source_types": ["PERSON"],
        "target_types": ["TEAM"],
    },
    "ESCALATES_TO": {
        "description": "For incidents, Person A escalates to Person B",
        "source_types": ["PERSON"],
        "target_types": ["PERSON"],
    },
    "AFFECTS": {
        "description": "Incident A affects service/component B",
        "source_types": ["INCIDENT"],
        "target_types": ["SERVICE", "COMPONENT", "DATABASE"],
    },
    "RESOLVED_BY": {
        "description": "Incident A was resolved by Person B",
        "source_types": ["INCIDENT"],
        "target_types": ["PERSON"],
    },
    "CAUSED_BY": {
        "description": "Incident A was caused by issue in service/component B",
        "source_types": ["INCIDENT"],
        "target_types": ["SERVICE", "COMPONENT", "DATABASE", "INCIDENT"],
    },
}


RELATION_EXTRACTION_PROMPT = """You are an expert at extracting relationships between IT operations entities from technical documents.

Given the following text and the list of known entities, extract all relationships of these types:
- DEPENDS_ON: Service/component depends on another service/component/database
- OWNS: Team owns a service/component/database
- SUPPORTS: Team provides support for a service (but doesn't own it)
- MEMBER_OF: Person is a member of a team (including team leads - see clarification below)
- MANAGES: Team or person has management responsibility for a SERVICE/SYSTEM (not a team)
- ESCALATES_TO: Person escalates incidents to another person
- AFFECTS: Incident affects a service/component
- RESOLVED_BY: Incident was resolved by a person
- CAUSED_BY: Incident was caused by issue in another entity

DISTINCTION - MEMBER_OF vs MANAGES:
- MEMBER_OF: Person belongs to a team. This includes team leads and managers OF teams.
  Example: "Sarah Chen is Tech Lead of Payments Team" → Sarah Chen MEMBER_OF Payments Team
  Example: "Mike Rodriguez (SRE Team Lead)" → Mike Rodriguez MEMBER_OF SRE Team
- MANAGES: Team or person has management/operational responsibility for a SERVICE or SYSTEM.
  Example: "Platform Team manages the API Gateway" → Platform Team MANAGES API Gateway
  Example: "SRE Team manages the Kubernetes infrastructure" → SRE Team MANAGES Kubernetes

MULTI-TARGET RELATIONSHIPS:
When text mentions multiple targets (e.g., "routes to X, Y, and Z" or "depends on A, B, and C"), extract a SEPARATE relationship for each target.

KNOWN ENTITIES:
{entities}

For each relationship, provide:
1. relation_type: One of the types above
2. source_name: The name of the source entity (must be from KNOWN ENTITIES)
3. target_name: The name of the target entity (must be from KNOWN ENTITIES)
4. source_span: The exact text that indicates this relationship
5. confidence: Your confidence in this extraction (0.0 to 1.0)

EXAMPLES:

Example 1 - Service Dependencies (multi-target):
Text: "API Gateway routes traffic to Order Service, Inventory Service, and Shipping Service"
Entities: API Gateway (SERVICE), Order Service (SERVICE), Inventory Service (SERVICE), Shipping Service (SERVICE)
Extract:
[
  {{"relation_type": "DEPENDS_ON", "source_name": "API Gateway", "target_name": "Order Service", "source_span": "routes traffic to Order Service", "confidence": 0.95}},
  {{"relation_type": "DEPENDS_ON", "source_name": "API Gateway", "target_name": "Inventory Service", "source_span": "routes traffic to Inventory Service", "confidence": 0.95}},
  {{"relation_type": "DEPENDS_ON", "source_name": "API Gateway", "target_name": "Shipping Service", "source_span": "routes traffic to Shipping Service", "confidence": 0.95}}
]

Example 2 - Incident Relations (AFFECTS, CAUSED_BY):
Text: "INC-2024-042: The Auth Service experienced a major outage. The incident was caused by a deadlock in the Auth Database."
Entities: INC-2024-042 (INCIDENT), Auth Service (SERVICE), Auth Database (DATABASE)
Extract:
[
  {{"relation_type": "AFFECTS", "source_name": "INC-2024-042", "target_name": "Auth Service", "source_span": "Auth Service experienced a major outage", "confidence": 0.95}},
  {{"relation_type": "CAUSED_BY", "source_name": "INC-2024-042", "target_name": "Auth Database", "source_span": "caused by a deadlock in the Auth Database", "confidence": 0.90}}
]

Example 3 - Incident Resolution (RESOLVED_BY):
Text: "Mike Rodriguez resolved the issue by restarting the database cluster."
Entities: INC-2024-042 (INCIDENT), Mike Rodriguez (PERSON)
Extract:
[
  {{"relation_type": "RESOLVED_BY", "source_name": "INC-2024-042", "target_name": "Mike Rodriguez", "source_span": "Mike Rodriguez resolved the issue", "confidence": 0.95}}
]

Example 4 - Team Membership vs Management:
Text: "James Wilson is the Platform Team Manager. The Platform Team manages the API Gateway."
Entities: James Wilson (PERSON), Platform Team (TEAM), API Gateway (SERVICE)
Extract:
[
  {{"relation_type": "MEMBER_OF", "source_name": "James Wilson", "target_name": "Platform Team", "source_span": "James Wilson is the Platform Team Manager", "confidence": 0.95}},
  {{"relation_type": "MANAGES", "source_name": "Platform Team", "target_name": "API Gateway", "source_span": "Platform Team manages the API Gateway", "confidence": 0.95}}
]

IMPORTANT RULES:
- Extract ALL relationships mentioned in the text
- Both source and target entities must be from the KNOWN ENTITIES list
- For incidents, look for: "affected", "impacted", "caused by", "due to", "resolved by", "fixed by"
- For dependencies, look for: "depends on", "requires", "uses", "connects to", "routes to"
- Assign lower confidence (0.5-0.7) if the relationship is implied but not explicit
- Assign higher confidence (0.8-1.0) if the relationship is explicitly stated

TEXT:
{text}

Respond with ONLY valid JSON array, no markdown code blocks or other text.
"""


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
    LLM-powered relation extractor for IT operations relationships.
    
    Supports: DEPENDS_ON, OWNS, SUPPORTS, MEMBER_OF, MANAGES, ESCALATES_TO, AFFECTS, RESOLVED_BY, CAUSED_BY
    """
    
    def __init__(
        self,
        model: str = "gpt-4o-mini",
        temperature: float = 0.1,
        max_retries: int = 3,
    ):
        """
        Initialize the relation extractor.
        
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
    
    def _validate_relation(self, relation: Dict, entity_names: set) -> bool:
        """Validate extracted relation has required fields and valid references."""
        required = ["relation_type", "source_name", "target_name"]
        for field in required:
            if field not in relation:
                return False
        
        if relation["relation_type"] not in RELATION_TYPES:
            return False
        
        source_lower = relation["source_name"].lower()
        target_lower = relation["target_name"].lower()
        entity_names_lower = {n.lower() for n in entity_names}
        
        source_found = source_lower in entity_names_lower
        target_found = target_lower in entity_names_lower
        
        return source_found and target_found
    
    def _normalize_relation(self, relation: Dict) -> Dict:
        """Normalize relation fields."""
        relation["source_name"] = relation["source_name"].strip()
        relation["target_name"] = relation["target_name"].strip()
        
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
    ) -> List[ExtractedRelation]:
        """
        Extract relations from text using LLM.
        
        Args:
            text: Text to extract relations from
            entities: List of known entities (with 'canonical_name' and 'entity_type')
            document_id: ID of the source document
            chunk_id: ID of the source chunk
            
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
        prompt = RELATION_EXTRACTION_PROMPT.format(
            entities=entities_str,
            text=text
        )
        
        for attempt in range(self.max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are an expert at extracting relationships between IT operations entities. Respond only with valid JSON."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.temperature,
                    max_tokens=2000,
                )
                
                response_text = response.choices[0].message.content or ""
                raw_relations = self._parse_llm_response(response_text)
                
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
