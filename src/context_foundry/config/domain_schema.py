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
class TraversalRule:
    """Defines how a relationship is traversed in a specific mode.
    
    For example, for 'impact' mode (what breaks if X fails):
    - from_source=True means: if we're at source, traverse to target
    - from_target=True means: if we're at target, traverse to source
    """
    from_source: bool = False  # If True, traverse Source -> Target
    from_target: bool = False  # If True, traverse Target -> Source
    include: bool = True       # If False, ignore this relationship in this mode


@dataclass
class RelationshipSemantics:
    """Holds traversal rules for different query modes.
    
    Modes are schema-defined (e.g., 'impact', 'dependency', 'ownership').
    Each mode defines how relationships should be traversed.
    """
    modes: Dict[str, TraversalRule] = field(default_factory=dict)
    properties: Dict[str, Any] = field(default_factory=dict)


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
    semantics: Optional[RelationshipSemantics] = None
    
    def is_valid_source(self, entity_type: str) -> bool:
        """Check if entity type is a valid source for this relationship."""
        return entity_type in self.source_types
    
    def is_valid_target(self, entity_type: str) -> bool:
        """Check if entity type is a valid target for this relationship."""
        return entity_type in self.target_types
    
    def is_many_to_one(self) -> bool:
        """Check if this relationship enforces single target per source."""
        return self.cardinality == Cardinality.MANY_TO_ONE
    
    def get_traversal_rule(self, mode: str) -> Optional[TraversalRule]:
        """Get traversal rule for a specific mode."""
        if self.semantics is None:
            return None
        return self.semantics.modes.get(mode)


@dataclass
class ValidationRuleConfig:
    """Configuration for a validation rule."""
    name: str
    description: str = ""
    applies_to: str = ""
    constraint: str = ""
    condition: Optional[str] = None
    requires: Optional[str] = None


class FrontierReason(str, Enum):
    """Reasons why traversal stopped at a node.
    
    These reasons are domain-agnostic and apply to any traversal mode.
    """
    NO_RELATIONSHIPS = "no_relationships"  # Entity has no relationships at all
    NO_EDGES_FOR_MODE = "no_edges_for_mode"  # Relationships exist, but none match mode's rules
    BELOW_CONFIDENCE_THRESHOLD = "below_confidence_threshold"  # All edges below threshold
    MAX_DEPTH_REACHED = "max_depth_reached"  # Hit the traversal depth limit
    ALL_NEIGHBORS_VISITED = "all_neighbors_visited"  # All valid neighbors already in visited set


def generate_frontier_message(
    reason: FrontierReason,
    mode: str,
    entity_name: str,
    entity_type: str
) -> str:
    """Generate a human-readable message explaining why traversal stopped.
    
    This is domain-agnostic - it works for any entity type and traversal mode.
    
    Args:
        reason: Why traversal stopped
        mode: The traversal mode being used (e.g., 'impact', 'dependency', 'ownership')
        entity_name: Name of the frontier entity
        entity_type: Type of the frontier entity (e.g., 'SERVICE', 'CHARACTER', 'COMPANY')
    
    Returns:
        Human-readable explanation string
    """
    mode_descriptions = {
        "impact": "affected by",
        "dependency": "dependent on", 
        "ownership": "owned by or owning",
        "organizational": "organizationally connected to",
        "incident": "related to incidents involving"
    }
    
    mode_phrase = mode_descriptions.get(mode, f"connected to (via '{mode}' mode)")
    entity_type_lower = entity_type.lower().replace("_", " ")
    
    if reason == FrontierReason.NO_RELATIONSHIPS:
        return (
            f"{entity_name} has no documented relationships. "
            f"This {entity_type_lower} may need further documentation."
        )
    
    elif reason == FrontierReason.NO_EDGES_FOR_MODE:
        return (
            f"No entities documented as {mode_phrase} {entity_name}. "
            f"This may indicate incomplete documentation for this {entity_type_lower}."
        )
    
    elif reason == FrontierReason.BELOW_CONFIDENCE_THRESHOLD:
        return (
            f"Relationships exist for {entity_name}, but all are below the confidence threshold. "
            f"Consider reviewing low-confidence connections for this {entity_type_lower}."
        )
    
    elif reason == FrontierReason.MAX_DEPTH_REACHED:
        return (
            f"Traversal stopped at {entity_name} due to depth limit. "
            f"The full {mode} chain may extend further from this {entity_type_lower}."
        )
    
    elif reason == FrontierReason.ALL_NEIGHBORS_VISITED:
        return (
            f"All entities {mode_phrase} {entity_name} have already been visited. "
            f"Traversal complete for this {entity_type_lower}."
        )
    
    return f"Traversal stopped at {entity_name} ({reason.value})."


def generate_gap_description(
    reason: FrontierReason,
    mode: str,
    entity_name: str,
    entity_type: str
) -> Optional[str]:
    """Generate a gap description for documentation improvement.
    
    Not all frontier nodes represent documentation gaps - only some reasons
    indicate missing information that should be added.
    
    Returns:
        Gap description if this represents a documentation gap, None otherwise
    """
    entity_type_lower = entity_type.lower().replace("_", " ")
    
    if reason == FrontierReason.NO_RELATIONSHIPS:
        return f"{entity_name} ({entity_type_lower}) has no documented relationships"
    
    elif reason == FrontierReason.NO_EDGES_FOR_MODE:
        mode_descriptions = {
            "impact": "dependents",
            "dependency": "dependencies",
            "ownership": "ownership relationships",
        }
        mode_word = mode_descriptions.get(mode, f"{mode} relationships")
        return f"{entity_name} ({entity_type_lower}) has no documented {mode_word}"
    
    return None


@dataclass
class FrontierNode:
    """A node where traversal stopped, with the reason why.
    
    Frontier nodes represent the boundary of confirmed knowledge.
    They're candidates for inference expansion in later phases.
    """
    entity_id: str
    entity_name: str
    entity_type: str
    reason: FrontierReason
    message: str  # Human-readable explanation
    depth: int = 0  # How deep in traversal this node was reached
    last_documented: Optional[str] = None  # Staleness indicator
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "reason": self.reason.value,
            "message": self.message,
            "depth": self.depth,
            "last_documented": self.last_documented
        }


@dataclass
class ConfirmedEntity:
    """An entity confirmed through explicit graph traversal."""
    entity_id: str
    entity_name: str
    entity_type: str
    confidence: float
    depth: int  # How many hops from the starting entity
    path: List[str] = field(default_factory=list)  # Relationship types traversed to reach this
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "entity_id": self.entity_id,
            "entity_name": self.entity_name,
            "entity_type": self.entity_type,
            "confidence": self.confidence,
            "depth": self.depth,
            "path": self.path
        }


@dataclass
class TraversalResult:
    """Complete result of a schema-driven traversal operation.
    
    Separates confirmed knowledge from speculative inference,
    and explicitly tracks where knowledge ends (frontier nodes).
    """
    # The starting entity
    start_entity_id: str
    start_entity_name: str
    start_entity_type: str
    
    # Traversal parameters
    mode: str
    max_depth: int
    confidence_threshold: float = 0.0
    
    # Tier 1: Confirmed knowledge (explicit graph relationships)
    confirmed_entities: List[ConfirmedEntity] = field(default_factory=list)
    traversed_relationships: List[Dict] = field(default_factory=list)
    
    # Frontier: Where knowledge ends
    frontier_nodes: List[FrontierNode] = field(default_factory=list)
    
    # Gaps identified (for documentation improvement)
    gaps_identified: List[str] = field(default_factory=list)
    
    # Metadata
    traversal_complete: bool = True
    timestamp: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to structured API response format."""
        return {
            "confirmed": {
                "entities": [e.to_dict() for e in self.confirmed_entities],
                "count": len(self.confirmed_entities),
                "complete": self.traversal_complete
            },
            "frontier": [f.to_dict() for f in self.frontier_nodes],
            "gaps_identified": self.gaps_identified,
            "relationships": self.traversed_relationships,
            "metadata": {
                "start_entity": {
                    "id": self.start_entity_id,
                    "name": self.start_entity_name,
                    "type": self.start_entity_type
                },
                "mode": self.mode,
                "max_depth": self.max_depth,
                "confidence_threshold": self.confidence_threshold,
                "timestamp": self.timestamp
            }
        }


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
    Supports loading from YAML files, ontology tables, or hot-reloading.
    
    Week 3 Stabilization: Added ontology table support as primary source.
    """
    
    DEFAULT_CONFIG_PATH = "config/domain_schema.yaml"
    
    _instance: Optional['DomainSchemaLoader'] = None
    _schema: Optional[DomainSchema] = None
    
    def __new__(cls, config_path: Optional[str] = None, force_reload: bool = False, 
                use_ontology: bool = True):
        """Singleton pattern - one schema loader per process."""
        if cls._instance is None or force_reload:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, config_path: Optional[str] = None, force_reload: bool = False,
                 use_ontology: bool = True):
        if self._initialized and not force_reload:
            return
        
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self._schema = None
        self._use_ontology = use_ontology
        self._initialized = True
        
        self.load()
    
    def load(self, config_path: Optional[str] = None) -> DomainSchema:
        """Load schema from ontology tables (preferred) or YAML config file.
        
        Week 3 Stabilization: Now tries ontology tables first, then falls back to YAML.
        """
        if self._use_ontology:
            ontology_schema = self._load_from_ontology()
            if ontology_schema:
                self._schema = ontology_schema
                return self._schema
            logger.warning(
                "SCHEMA FALLBACK: Ontology tables not available, using YAML. "
                "This may cause schema drift if ontology tables are the intended source of truth."
            )
        
        return self._load_from_yaml(config_path)
    
    def _load_from_ontology(self) -> Optional[DomainSchema]:
        """Load schema from ontology tables.
        
        Week 3 Stabilization: OntologySchemaService as source of truth.
        """
        try:
            from ..ontology_foundry.schema_service import get_ontology_schema_service
            
            service = get_ontology_schema_service()
            
            if service._loaded and len(service.entity_types) > 0:
                schema = service.to_domain_schema(domain="Ontology Foundation")
                logger.info(
                    f"Loaded domain schema from ontology tables: "
                    f"{len(schema.entity_types)} entity types, "
                    f"{len(schema.relationship_types)} relationship types"
                )
                return schema
            
            return None
        except Exception as e:
            logger.warning(f"Could not load from ontology tables: {e}")
            return None
    
    def _load_from_yaml(self, config_path: Optional[str] = None) -> DomainSchema:
        """Load schema from YAML config file (fallback)."""
        path = config_path or self.config_path
        
        if not os.path.exists(path):
            logger.warning(f"Schema config not found at {path}, using defaults")
            self._schema = self._create_default_schema()
            return self._schema
        
        try:
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
            
            self._schema = self._parse_config(config)
            logger.info(f"Loaded domain schema from YAML: {self._schema.domain} "
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
            
            semantics = self._parse_relationship_semantics(rt.get('semantics'))
            
            rel_config = RelationshipTypeConfig(
                name=rt['name'].upper(),
                description=rt.get('description', ''),
                source_types=[s.upper() for s in rt.get('source_types', [])],
                target_types=[t.upper() for t in rt.get('target_types', [])],
                cardinality=cardinality,
                semantics=semantics
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
    
    def _parse_relationship_semantics(self, sem_data: Optional[Dict]) -> Optional[RelationshipSemantics]:
        """Parse relationship semantics from YAML config."""
        if sem_data is None:
            return None
        
        modes = {}
        for mode_name, mode_data in sem_data.get('modes', {}).items():
            modes[mode_name] = TraversalRule(
                from_source=mode_data.get('from_source', False),
                from_target=mode_data.get('from_target', False),
                include=mode_data.get('include', True)
            )
        
        return RelationshipSemantics(
            modes=modes,
            properties=sem_data.get('properties', {})
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
