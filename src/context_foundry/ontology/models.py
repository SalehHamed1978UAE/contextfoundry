"""
Pydantic models for ontology-constrained extraction validation.

These models validate LLM extractions against the database-backed ontology
before writing to entities_v2.
"""

from typing import Dict, List, Optional, Any, Set
from pydantic import BaseModel, Field, field_validator, model_validator
from uuid import UUID
from datetime import datetime


class OntologyType(BaseModel):
    """Represents an entity type from ontology_types table."""
    id: UUID
    type_name: str
    layer: int
    display_name: str
    description: Optional[str] = None
    parent_type_id: Optional[UUID] = None
    properties_schema: Optional[Dict[str, Any]] = None
    origin: str = "system"
    
    class Config:
        from_attributes = True


class OntologyRelation(BaseModel):
    """Represents a relationship type from ontology_relations table."""
    id: UUID
    relation_name: str
    layer: int
    source_type_id: UUID
    target_type_id: UUID
    source_type_name: Optional[str] = None
    target_type_name: Optional[str] = None
    cardinality: str = "MANY_TO_MANY"
    description: Optional[str] = None
    semantics: Optional[Dict[str, Any]] = None
    extraction_hints: Optional[Dict[str, Any]] = None
    origin: str = "domain_template"
    
    class Config:
        from_attributes = True
    
    def get_trigger_phrases(self) -> List[str]:
        """Get extraction trigger phrases from hints."""
        if self.extraction_hints and "trigger_phrases" in self.extraction_hints:
            return self.extraction_hints["trigger_phrases"]
        return []
    
    def get_anti_patterns(self) -> List[str]:
        """Get anti-patterns that should NOT trigger this relationship."""
        if self.extraction_hints and "anti_patterns" in self.extraction_hints:
            return self.extraction_hints["anti_patterns"]
        return []


class EntityExtraction(BaseModel):
    """Validated entity extraction from LLM output."""
    entity_type: str
    canonical_name: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    source_span: str
    confidence: float = Field(ge=0.0, le=1.0)
    entity_type_id: Optional[UUID] = None
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))
    
    @field_validator('entity_type')
    @classmethod
    def normalize_entity_type(cls, v: str) -> str:
        return v.strip()


class RelationshipExtraction(BaseModel):
    """Validated relationship extraction from LLM output."""
    relation_type: str
    source_name: str
    target_name: str
    source_span: str
    confidence: float = Field(ge=0.0, le=1.0)
    relation_type_id: Optional[UUID] = None
    
    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, v))


class ExtractionResult(BaseModel):
    """Complete extraction result with validation status."""
    entities: List[EntityExtraction] = Field(default_factory=list)
    relationships: List[RelationshipExtraction] = Field(default_factory=list)
    rejected_entities: List[Dict[str, Any]] = Field(default_factory=list)
    rejected_relationships: List[Dict[str, Any]] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    extraction_mode: str = "constrained"
    model_used: str = "gpt-4o-mini"
    extraction_started_at: Optional[datetime] = None
    extraction_completed_at: Optional[datetime] = None
    
    @property
    def total_extracted(self) -> int:
        return len(self.entities) + len(self.relationships)
    
    @property
    def total_rejected(self) -> int:
        return len(self.rejected_entities) + len(self.rejected_relationships)
    
    @property
    def has_errors(self) -> bool:
        return len(self.validation_errors) > 0


class OntologySnapshot(BaseModel):
    """A point-in-time snapshot of the ontology for extraction."""
    types: Dict[str, OntologyType] = Field(default_factory=dict)
    relations: List[OntologyRelation] = Field(default_factory=list)
    type_hierarchy: Dict[str, List[str]] = Field(default_factory=dict)
    loaded_at: datetime = Field(default_factory=datetime.utcnow)
    _type_name_map: Dict[str, str] = {}
    
    def model_post_init(self, __context) -> None:
        """Build case-insensitive type name mapping after initialization."""
        self._type_name_map = {k.lower(): k for k in self.types.keys()}
    
    def get_valid_type_names(self) -> Set[str]:
        """Get set of all valid entity type names."""
        return set(self.types.keys())
    
    def normalize_type_name(self, input_type: str) -> Optional[str]:
        """
        Normalize type name to exact ontology_types.type_name (case-insensitive).
        
        Args:
            input_type: Type name from LLM output (any casing)
            
        Returns:
            Canonical type_name from ontology, or None if not found
        """
        return self._type_name_map.get(input_type.strip().lower())
    
    def get_type_by_name(self, name: str) -> Optional[OntologyType]:
        """Get type definition by name (case-insensitive lookup)."""
        canonical = self.normalize_type_name(name)
        if canonical:
            return self.types.get(canonical)
        return self.types.get(name)
    
    def get_relations_for_types(self, source_type: str, target_type: str) -> List[OntologyRelation]:
        """Get valid relations between two entity types."""
        source_type_obj = self.types.get(source_type)
        target_type_obj = self.types.get(target_type)
        if not source_type_obj or not target_type_obj:
            return []
        
        return [
            r for r in self.relations
            if r.source_type_id == source_type_obj.id 
            and r.target_type_id == target_type_obj.id
        ]
    
    def is_valid_type(self, type_name: str) -> bool:
        """Check if type name is valid in ontology."""
        return type_name in self.types
    
    def get_layer_types(self, layer: int) -> List[OntologyType]:
        """Get all types at a specific layer."""
        return [t for t in self.types.values() if t.layer == layer]
