"""
Domain Schema Loader - Configurable entity and relationship types for domain-agnostic operation.

This module loads entity types, relationship types, and validation rules from YAML config,
making Context Foundry work with any domain (IT Operations, Investment Portfolio, Healthcare, etc.).
"""
import os
import yaml
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ..utils.logger import logger


class Cardinality(str, Enum):
    """Relationship cardinality types."""
    MANY_TO_MANY = "many-to-many"
    MANY_TO_ONE = "many-to-one"
    ONE_TO_MANY = "one-to-many"
    ONE_TO_ONE = "one-to-one"


@dataclass
class EntityTypeConfig:
    """Configuration for an entity type."""
    name: str
    description: str = ""
    required_fields: List[str] = field(default_factory=list)
    optional_fields: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    
    def get_all_fields(self) -> List[str]:
        """Get all fields (required + optional)."""
        return self.required_fields + self.optional_fields


@dataclass
class RelationshipTypeConfig:
    """Configuration for a relationship type."""
    name: str
    description: str = ""
    source_types: List[str] = field(default_factory=list)
    target_types: List[str] = field(default_factory=list)
    cardinality: Cardinality = Cardinality.MANY_TO_MANY
    
    def is_valid_source(self, entity_type: str) -> bool:
        """Check if entity type is a valid source for this relationship."""
        return entity_type in self.source_types
    
    def is_valid_target(self, entity_type: str) -> bool:
        """Check if entity type is a valid target for this relationship."""
        return entity_type in self.target_types
    
    def is_many_to_one(self) -> bool:
        """Check if this relationship enforces single target per source."""
        return self.cardinality == Cardinality.MANY_TO_ONE


@dataclass
class ValidationRuleConfig:
    """Configuration for a validation rule."""
    name: str
    description: str = ""
    applies_to: str = ""
    constraint: str = ""
    condition: Optional[str] = None
    requires: Optional[str] = None


@dataclass
class DomainSchema:
    """Complete domain schema configuration."""
    schema_version: str
    domain: str
    description: str
    entity_types: Dict[str, EntityTypeConfig]
    relationship_types: Dict[str, RelationshipTypeConfig]
    validation_rules: List[ValidationRuleConfig]
    example_queries: List[str] = field(default_factory=list)
    
    def get_entity_type(self, name: str) -> Optional[EntityTypeConfig]:
        """Get entity type config by name."""
        return self.entity_types.get(name.upper())
    
    def get_relationship_type(self, name: str) -> Optional[RelationshipTypeConfig]:
        """Get relationship type config by name."""
        return self.relationship_types.get(name.upper())
    
    def get_entity_type_names(self) -> List[str]:
        """Get list of all entity type names."""
        return list(self.entity_types.keys())
    
    def get_relationship_type_names(self) -> List[str]:
        """Get list of all relationship type names."""
        return list(self.relationship_types.keys())
    
    def get_many_to_one_relationships(self) -> List[str]:
        """Get names of relationships with many-to-one cardinality."""
        return [
            name for name, rel in self.relationship_types.items()
            if rel.is_many_to_one()
        ]
    
    def validate_relationship(self, rel_type: str, source_type: str, target_type: str) -> tuple[bool, str]:
        """Validate if a relationship is valid for given source and target types."""
        rel_config = self.get_relationship_type(rel_type)
        if not rel_config:
            return False, f"Unknown relationship type: {rel_type}"
        
        if not rel_config.is_valid_source(source_type):
            return False, f"Invalid source type {source_type} for {rel_type}. Valid: {rel_config.source_types}"
        
        if not rel_config.is_valid_target(target_type):
            return False, f"Invalid target type {target_type} for {rel_type}. Valid: {rel_config.target_types}"
        
        return True, ""


class DomainSchemaLoader:
    """
    Loads and manages domain schema configuration.
    
    Provides typed access to entity types, relationship types, and validation rules.
    Supports loading from YAML files and hot-reloading.
    """
    
    DEFAULT_CONFIG_PATH = "config/domain_schema.yaml"
    
    _instance: Optional['DomainSchemaLoader'] = None
    _schema: Optional[DomainSchema] = None
    
    def __new__(cls, config_path: Optional[str] = None, force_reload: bool = False):
        """Singleton pattern - one schema loader per process."""
        if cls._instance is None or force_reload:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: Optional[str] = None, force_reload: bool = False):
        if self._initialized and not force_reload:
            return
        
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._schema = None
        self._initialized = True
        
        self.load()
    
    def load(self, config_path: Optional[str] = None) -> DomainSchema:
        """Load schema from YAML config file."""
        path = config_path or self.config_path
        
        if not os.path.exists(path):
            logger.warning(f"Schema config not found at {path}, using defaults")
            self._schema = self._create_default_schema()
            return self._schema
        
        try:
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
            
            self._schema = self._parse_config(config)
            logger.info(f"Loaded domain schema: {self._schema.domain} "
                       f"({len(self._schema.entity_types)} entity types, "
                       f"{len(self._schema.relationship_types)} relationship types)")
            
            return self._schema
            
        except Exception as e:
            logger.error(f"Failed to load schema config: {e}")
            raise ValueError(f"Invalid schema configuration: {e}")
    
    def reload(self, config_path: Optional[str] = None) -> DomainSchema:
        """Hot-reload schema from config file."""
        return self.load(config_path)
    
    @property
    def schema(self) -> DomainSchema:
        """Get the current loaded schema."""
        if self._schema is None:
            self.load()
        return self._schema
    
    def _parse_config(self, config: Dict) -> DomainSchema:
        """Parse YAML config into DomainSchema."""
        entity_types = {}
        for et in config.get('entity_types', []):
            entity_config = EntityTypeConfig(
                name=et['name'].upper(),
                description=et.get('description', ''),
                required_fields=et.get('required_fields', []),
                optional_fields=et.get('optional_fields', []),
                keywords=et.get('keywords', [])
            )
            entity_types[entity_config.name] = entity_config
        
        relationship_types = {}
        for rt in config.get('relationship_types', []):
            cardinality_str = rt.get('cardinality', 'many-to-many')
            try:
                cardinality = Cardinality(cardinality_str)
            except ValueError:
                logger.warning(f"Unknown cardinality {cardinality_str}, defaulting to many-to-many")
                cardinality = Cardinality.MANY_TO_MANY
            
            rel_config = RelationshipTypeConfig(
                name=rt['name'].upper(),
                description=rt.get('description', ''),
                source_types=[s.upper() for s in rt.get('source_types', [])],
                target_types=[t.upper() for t in rt.get('target_types', [])],
                cardinality=cardinality
            )
            relationship_types[rel_config.name] = rel_config
        
        validation_rules = []
        for vr in config.get('validation_rules', []):
            rule_config = ValidationRuleConfig(
                name=vr['name'],
                description=vr.get('description', ''),
                applies_to=vr.get('applies_to', ''),
                constraint=vr.get('constraint', ''),
                condition=vr.get('condition'),
                requires=vr.get('requires')
            )
            validation_rules.append(rule_config)
        
        return DomainSchema(
            schema_version=config.get('schema_version', '1.0'),
            domain=config.get('domain', 'Unknown'),
            description=config.get('description', ''),
            entity_types=entity_types,
            relationship_types=relationship_types,
            validation_rules=validation_rules,
            example_queries=config.get('example_queries', [])
        )
    
    def _create_default_schema(self) -> DomainSchema:
        """Create a minimal default schema if no config is found."""
        return DomainSchema(
            schema_version="1.0",
            domain="Default",
            description="Minimal default schema",
            entity_types={
                "ENTITY": EntityTypeConfig(
                    name="ENTITY",
                    description="Generic entity",
                    required_fields=["name"]
                )
            },
            relationship_types={
                "RELATES_TO": RelationshipTypeConfig(
                    name="RELATES_TO",
                    description="Generic relationship",
                    source_types=["ENTITY"],
                    target_types=["ENTITY"],
                    cardinality=Cardinality.MANY_TO_MANY
                )
            },
            validation_rules=[]
        )
    
    def build_entity_extraction_prompt(self) -> str:
        """Build LLM prompt for entity extraction based on loaded schema."""
        prompt_parts = ["ENTITY TYPES:"]
        
        for name, entity in self.schema.entity_types.items():
            desc = entity.description or f"A {name.lower()}"
            prompt_parts.append(f"- {name}: {desc}")
            
            if entity.required_fields:
                prompt_parts.append(f"  Required: {', '.join(entity.required_fields)}")
            if entity.optional_fields:
                prompt_parts.append(f"  Optional: {', '.join(entity.optional_fields)}")
            prompt_parts.append("")
        
        return "\n".join(prompt_parts)
    
    def build_relationship_extraction_prompt(self) -> str:
        """Build LLM prompt for relationship extraction based on loaded schema."""
        prompt_parts = ["RELATIONSHIP TYPES (with valid source → target):"]
        
        for name, rel in self.schema.relationship_types.items():
            sources = "/".join(rel.source_types)
            targets = "/".join(rel.target_types)
            desc = rel.description or f"{name} relationship"
            cardinality_note = " (one target only)" if rel.is_many_to_one() else ""
            
            prompt_parts.append(f"- {name}: {sources} → {targets}{cardinality_note}")
            prompt_parts.append(f"  {desc}")
            prompt_parts.append("")
        
        return "\n".join(prompt_parts)
    
    def get_valid_entity_types(self) -> Set[str]:
        """Get set of valid entity type names."""
        return set(self.schema.entity_types.keys())
    
    def get_valid_relationship_types(self) -> Set[str]:
        """Get set of valid relationship type names."""
        return set(self.schema.relationship_types.keys())
    
    def get_cardinality_constraints(self) -> Dict[str, str]:
        """Get relationship types with their cardinality constraints."""
        return {
            name: rel.cardinality.value
            for name, rel in self.schema.relationship_types.items()
        }


def get_schema_loader(config_path: Optional[str] = None, force_reload: bool = False) -> DomainSchemaLoader:
    """Get the singleton schema loader instance."""
    return DomainSchemaLoader(config_path=config_path, force_reload=force_reload)


def get_schema(config_path: Optional[str] = None) -> DomainSchema:
    """Convenience function to get the current domain schema."""
    return get_schema_loader(config_path).schema
