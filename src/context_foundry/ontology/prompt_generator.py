"""
SchemaPromptGenerator - Dynamically builds LLM prompts from database-backed ontology.

Queries ontology_types at extraction time to build prompts without hardcoding
entity types. This replaces the YAML-based prompt building in the legacy extractors.
"""

from typing import List, Optional, Dict, Any
from .repository import OntologyRepository, get_ontology_repository
from .models import OntologySnapshot, OntologyType, OntologyRelation
from ..utils.logger import logger


class SchemaPromptGenerator:
    """
    Generates LLM extraction prompts dynamically from the database ontology.
    
    Unlike the legacy YAML-based approach, this queries ontology_types
    and ontology_relations at extraction time, ensuring prompts always
    reflect the current schema state.
    """
    
    def __init__(
        self, 
        repository: Optional[OntologyRepository] = None,
        domain_name: str = "Core Foundation"
    ):
        """
        Initialize the prompt generator.
        
        Args:
            repository: OntologyRepository instance (uses singleton if not provided)
            domain_name: Human-readable domain name for prompts (auto-detected if not set)
        """
        self._repository = repository
        self.domain_name = domain_name
    
    @property
    def repository(self) -> OntologyRepository:
        """Get ontology repository (lazy initialization)."""
        if self._repository is None:
            self._repository = get_ontology_repository()
        return self._repository
    
    def get_snapshot(self, force_refresh: bool = False) -> OntologySnapshot:
        """Get current ontology snapshot."""
        return self.repository.get_snapshot(force_refresh=force_refresh)
    
    def _format_type_description(self, type_obj: OntologyType) -> str:
        """Format a single entity type for the prompt."""
        desc = type_obj.description or f"A {type_obj.display_name.lower()}"
        line = f"- {type_obj.type_name}: {desc}"
        
        if type_obj.properties_schema:
            props = type_obj.properties_schema.get("properties", {})
            if props:
                prop_names = list(props.keys())
                if "required" in type_obj.properties_schema:
                    required = type_obj.properties_schema["required"]
                    req_props = [p for p in prop_names if p in required]
                    opt_props = [p for p in prop_names if p not in required]
                    if req_props:
                        line += f"\n  Required: {', '.join(req_props)}"
                    if opt_props:
                        line += f"\n  Optional: {', '.join(opt_props)}"
                else:
                    line += f"\n  Properties: {', '.join(prop_names)}"
        
        return line
    
    def _format_relation_description(self, rel: OntologyRelation) -> str:
        """Format a single relationship type for the prompt."""
        desc = rel.description or f"{rel.relation_name} relationship"
        source = rel.source_type_name or "any"
        target = rel.target_type_name or "any"
        
        cardinality_note = ""
        if rel.cardinality == "MANY_TO_ONE":
            cardinality_note = " (one target only)"
        elif rel.cardinality == "ONE_TO_MANY":
            cardinality_note = " (one source only)"
        elif rel.cardinality == "ONE_TO_ONE":
            cardinality_note = " (one-to-one)"
        
        lines = [
            f"- {rel.relation_name}: {desc}",
            f"  Source: {source} → Target: {target}{cardinality_note}"
        ]
        
        trigger_phrases = rel.get_trigger_phrases()
        if trigger_phrases:
            phrases_str = '", "'.join(trigger_phrases)
            lines.append(f'  Trigger phrases: "{phrases_str}"')
        
        return "\n".join(lines)
    
    def build_entity_extraction_prompt(
        self, 
        text: str,
        layer_filter: Optional[int] = None,
        type_filter: Optional[List[str]] = None
    ) -> str:
        """
        Build a dynamic entity extraction prompt from the current ontology.
        
        Args:
            text: The text to extract entities from
            layer_filter: Only include types from this layer (None = all layers)
            type_filter: Only include these specific type names (None = all types)
        
        Returns:
            Complete prompt string for LLM entity extraction
        """
        snapshot = self.get_snapshot()
        
        types_to_include: List[OntologyType] = []
        for type_obj in snapshot.types.values():
            if layer_filter is not None and type_obj.layer != layer_filter:
                continue
            if type_filter is not None and type_obj.type_name not in type_filter:
                continue
            if type_obj.layer == 0:
                continue
            types_to_include.append(type_obj)
        
        types_to_include.sort(key=lambda t: (t.layer, t.type_name))
        
        type_descriptions = [self._format_type_description(t) for t in types_to_include]
        type_list = "\n".join(type_descriptions)
        type_names = ", ".join(t.type_name for t in types_to_include)
        
        logger.info(f"Building entity extraction prompt with {len(types_to_include)} types from ontology")
        
        prompt = f"""You are an expert at extracting entities from documents in the {self.domain_name} domain.

Given the following text, extract all entities of these types:
{type_list}

For each entity, provide:
1. entity_type: One of {type_names}
2. canonical_name: The standardized name of the entity
3. properties: Additional properties (as listed above for each type)
4. source_span: The exact text span where this entity appears
5. confidence: Your confidence in this extraction (0.0 to 1.0)

IMPORTANT RULES:
- Only extract entities that are EXPLICITLY mentioned in the text
- Do NOT infer or hallucinate entities that aren't mentioned
- entity_type MUST be exactly one of the listed types - do not create new types
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
    
    def build_relationship_extraction_prompt(
        self,
        text: str,
        entities_str: str,
        layer_filter: Optional[int] = None
    ) -> str:
        """
        Build a dynamic relationship extraction prompt from the current ontology.
        
        Args:
            text: The text to extract relationships from
            entities_str: String representation of known entities
            layer_filter: Only include relations from this layer (None = all layers)
        
        Returns:
            Complete prompt string for LLM relationship extraction
        """
        snapshot = self.get_snapshot()
        
        relations_to_include: List[OntologyRelation] = []
        for rel in snapshot.relations:
            if layer_filter is not None and rel.layer != layer_filter:
                continue
            relations_to_include.append(rel)
        
        relation_descriptions = [self._format_relation_description(r) for r in relations_to_include]
        relation_list = "\n".join(relation_descriptions)
        relation_names = ", ".join(sorted(set(r.relation_name for r in relations_to_include)))
        
        logger.info(f"Building relationship extraction prompt with {len(relations_to_include)} relations from ontology")
        
        prompt = f"""You are an expert at extracting relationships between entities from documents in the {self.domain_name} domain.

Given the following text and the list of known entities, extract all relationships of these types:
{relation_list}

KNOWN ENTITIES:
{entities_str}

For each relationship, provide:
1. relation_type: One of {relation_names}
2. source_name: The name of the source entity (must be from KNOWN ENTITIES)
3. target_name: The name of the target entity (must be from KNOWN ENTITIES)
4. source_span: The exact text that indicates this relationship
5. confidence: Your confidence in this extraction (0.0 to 1.0)

IMPORTANT RULES:
- relation_type MUST be exactly one of the listed types - do not create new relation types
- Both source and target entities must be from the KNOWN ENTITIES list
- The source entity type must match the allowed Source types for that relation
- The target entity type must match the allowed Target types for that relation
- When text mentions multiple targets (e.g., "X, Y, and Z"), extract a SEPARATE relationship for each target
- Assign lower confidence (0.5-0.7) if the relationship is implied but not explicit
- Assign higher confidence (0.8-1.0) if the relationship is explicitly stated
- Only extract relationships that are EXPLICITLY mentioned or clearly implied in the text

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
    
    def build_system_prompt(self) -> str:
        """Build system prompt for extraction."""
        return f"""You are a precise information extraction system for the {self.domain_name} domain. 
Your task is to extract structured entities and relationships from text, following the schema exactly.
Never invent entity types or relationship types that aren't in the provided schema.
Return only valid JSON with no additional commentary."""
    
    def get_valid_type_names(self) -> List[str]:
        """Get list of valid entity type names from current ontology."""
        snapshot = self.get_snapshot()
        return sorted(snapshot.get_valid_type_names())
    
    def get_valid_relation_names(self) -> List[str]:
        """Get list of valid relationship type names from current ontology."""
        snapshot = self.get_snapshot()
        return sorted(set(r.relation_name for r in snapshot.relations))
    
    def validate_entity_type(self, type_name: str) -> bool:
        """Check if an entity type is valid in the current ontology."""
        return self.get_snapshot().is_valid_type(type_name)
    
    def get_type_id(self, type_name: str) -> Optional[str]:
        """Get the UUID for an entity type name."""
        type_obj = self.get_snapshot().get_type_by_name(type_name)
        return str(type_obj.id) if type_obj else None
