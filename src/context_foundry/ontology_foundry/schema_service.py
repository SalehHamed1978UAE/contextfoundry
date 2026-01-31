"""
Ontology Schema Service - Consolidated schema provider using ontology tables.

This service replaces YAML-based schema loading with database-backed schema
from the ontology.types and ontology.relations tables.

Week 3 Stabilization: Schema Consolidation
"""
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from uuid import UUID
import os

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..utils.logger import logger
from ..config.domain_schema import (
    EntityTypeConfig,
    RelationshipTypeConfig,
    RelationshipSemantics,
    TraversalRule,
    Cardinality,
    DomainSchema,
    ValidationRuleConfig,
)


@dataclass
class TypeMapping:
    """A mapping from deprecated/alternate type name to current canonical type."""
    deprecated_name: str
    current_name: str
    migration_type: str = "alias"


class OntologySchemaService:
    """
    Service for loading schema definitions from ontology tables.
    
    Consolidates schema from:
    - ontology.types (entity types)
    - ontology.relations (relationship types)
    - ontology.type_translation (type mappings for LLM correction)
    
    This replaces:
    - config/domain_schema.yaml
    - Hardcoded TYPE_MAPPING in entity_extractor.py
    - Hardcoded TYPE_MAPPING in graph_builder.py
    """
    
    _instance: Optional['OntologySchemaService'] = None
    _initialized: bool = False
    
    def __new__(cls, session: Session = None, force_reload: bool = False):
        if cls._instance is None or force_reload:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self, session: Session = None, force_reload: bool = False):
        if self._initialized and not force_reload:
            return
        
        self._session = session
        self._entity_types: Dict[str, EntityTypeConfig] = {}
        self._relationship_types: Dict[str, RelationshipTypeConfig] = {}
        self._type_mappings: Dict[str, str] = {}
        self._loaded = False
        self._initialized = True
    
    def load(self, session: Session = None) -> 'OntologySchemaService':
        """Load schema from ontology tables."""
        if session:
            self._session = session
        
        if not self._session:
            logger.warning("No database session provided, schema not loaded")
            return self
        
        try:
            self._load_entity_types()
            self._load_relationship_types()
            self._load_type_mappings()
            self._loaded = True
            
            logger.info(
                f"Loaded ontology schema: "
                f"{len(self._entity_types)} entity types, "
                f"{len(self._relationship_types)} relationship types, "
                f"{len(self._type_mappings)} type mappings"
            )
        except Exception as e:
            logger.error(f"Failed to load ontology schema: {e}")
            self._loaded = False
        
        return self
    
    def _load_entity_types(self):
        """Load entity types from ontology.types table."""
        query = text("""
            SELECT 
                id,
                type_name,
                display_name,
                description,
                extraction_hints,
                properties_schema,
                layer,
                status
            FROM ontology.types
            WHERE status = 'ACTIVE'
            ORDER BY type_name
        """)
        
        result = self._session.execute(query)
        
        for row in result:
            name = row.type_name.upper()
            hints = row.extraction_hints
            
            if isinstance(hints, list):
                keywords = hints
                required_fields = ['canonical_name']
                optional_fields = []
            elif isinstance(hints, dict):
                keywords = hints.get('keywords', [])
                required_fields = hints.get('required_fields', ['canonical_name'])
                optional_fields = hints.get('optional_fields', [])
            else:
                keywords = []
                required_fields = ['canonical_name']
                optional_fields = []
            
            self._entity_types[name] = EntityTypeConfig(
                name=name,
                description=row.description or row.display_name or name,
                required_fields=required_fields,
                optional_fields=optional_fields,
                keywords=keywords
            )
    
    def _load_relationship_types(self):
        """Load relationship types from ontology.relations table."""
        query = text("""
            SELECT 
                r.id,
                r.relation_type,
                r.display_name,
                r.description,
                r.cardinality,
                r.semantics,
                r.status,
                st.type_name as source_type,
                tt.type_name as target_type
            FROM ontology.relations r
            LEFT JOIN ontology.types st ON r.source_type_id = st.id
            LEFT JOIN ontology.types tt ON r.target_type_id = tt.id
            WHERE r.status = 'ACTIVE'
            ORDER BY r.relation_type
        """)
        
        result = self._session.execute(query)
        
        rel_types: Dict[str, Dict] = {}
        
        for row in result:
            name = row.relation_type.upper()
            
            if name not in rel_types:
                rel_types[name] = {
                    'name': name,
                    'description': row.description or row.display_name or name,
                    'cardinality': self._parse_cardinality(row.cardinality),
                    'source_types': set(),
                    'target_types': set(),
                    'semantics': self._parse_semantics(row.semantics),
                }
            
            if row.source_type:
                rel_types[name]['source_types'].add(row.source_type.upper())
            if row.target_type:
                rel_types[name]['target_types'].add(row.target_type.upper())
        
        for name, data in rel_types.items():
            self._relationship_types[name] = RelationshipTypeConfig(
                name=name,
                description=data['description'],
                source_types=sorted(list(data['source_types'])),
                target_types=sorted(list(data['target_types'])),
                cardinality=data['cardinality'],
                semantics=data['semantics']
            )
    
    def _load_type_mappings(self):
        """Load type mappings from ontology.type_translation table."""
        query = text("""
            SELECT deprecated_name, current_name
            FROM ontology.type_translation
            WHERE migration_type IN ('alias', 'synonym', 'correction')
        """)
        
        result = self._session.execute(query)
        
        for row in result:
            self._type_mappings[row.deprecated_name.upper()] = row.current_name.upper()
        
        if not self._type_mappings:
            self._type_mappings = self._get_default_type_mappings()
            logger.info("Using default type mappings (type_translation table empty)")
    
    def _get_default_type_mappings(self) -> Dict[str, str]:
        """Get default type mappings for LLM correction."""
        return {
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
    
    def _parse_cardinality(self, cardinality_str: Optional[str]) -> Cardinality:
        """Parse cardinality string to enum."""
        if not cardinality_str:
            return Cardinality.MANY_TO_MANY
        
        mapping = {
            'MANY_TO_MANY': Cardinality.MANY_TO_MANY,
            'MANY_TO_ONE': Cardinality.MANY_TO_ONE,
            'ONE_TO_MANY': Cardinality.ONE_TO_MANY,
            'ONE_TO_ONE': Cardinality.ONE_TO_ONE,
            'many-to-many': Cardinality.MANY_TO_MANY,
            'many-to-one': Cardinality.MANY_TO_ONE,
            'one-to-many': Cardinality.ONE_TO_MANY,
            'one-to-one': Cardinality.ONE_TO_ONE,
        }
        
        return mapping.get(cardinality_str, Cardinality.MANY_TO_MANY)
    
    def _parse_semantics(self, semantics_str: Optional[str]) -> Optional[RelationshipSemantics]:
        """Parse semantics string (could be JSON or text)."""
        if not semantics_str:
            return None
        
        return None
    
    @property
    def entity_types(self) -> Dict[str, EntityTypeConfig]:
        """Get all loaded entity types."""
        return self._entity_types
    
    @property
    def relationship_types(self) -> Dict[str, RelationshipTypeConfig]:
        """Get all loaded relationship types."""
        return self._relationship_types
    
    @property
    def type_mappings(self) -> Dict[str, str]:
        """Get type mappings for LLM correction."""
        return self._type_mappings
    
    def get_valid_entity_types(self) -> Set[str]:
        """Get set of valid entity type names."""
        return set(self._entity_types.keys())
    
    def get_valid_relationship_types(self) -> Set[str]:
        """Get set of valid relationship type names."""
        return set(self._relationship_types.keys())
    
    def correct_entity_type(self, extracted_type: str, entity_name: str = "") -> str:
        """Correct an extracted entity type using type mappings.
        
        Args:
            extracted_type: The type extracted by LLM
            entity_name: The entity name for pattern matching
            
        Returns:
            Corrected type name
        """
        extracted_type = extracted_type.upper()
        
        if extracted_type in self._type_mappings:
            corrected = self._type_mappings[extracted_type]
            logger.debug(f"Type mapping: {extracted_type} → {corrected} for '{entity_name}'")
            return corrected
        
        return extracted_type
    
    def is_valid_entity_type(self, type_name: str) -> bool:
        """Check if type name is a valid entity type."""
        return type_name.upper() in self._entity_types
    
    def is_valid_relationship_type(self, type_name: str) -> bool:
        """Check if type name is a valid relationship type."""
        return type_name.upper() in self._relationship_types
    
    def validate_relationship(
        self, 
        rel_type: str, 
        source_type: str, 
        target_type: str
    ) -> Tuple[bool, str]:
        """Validate if a relationship is valid for given source and target types."""
        rel_config = self._relationship_types.get(rel_type.upper())
        
        if not rel_config:
            return False, f"Unknown relationship type: {rel_type}"
        
        source_valid = not rel_config.source_types or source_type.upper() in [s.upper() for s in rel_config.source_types]
        target_valid = not rel_config.target_types or target_type.upper() in [t.upper() for t in rel_config.target_types]
        
        if not source_valid:
            return False, f"Invalid source type {source_type} for {rel_type}"
        
        if not target_valid:
            return False, f"Invalid target type {target_type} for {rel_type}"
        
        return True, ""
    
    def to_domain_schema(self, domain: str = "Ontology") -> DomainSchema:
        """Convert to DomainSchema for compatibility with existing code."""
        return DomainSchema(
            schema_version="3.0",
            domain=domain,
            description="Schema loaded from ontology tables",
            entity_types=self._entity_types,
            relationship_types=self._relationship_types,
            validation_rules=[],
            example_queries=[]
        )
    
    def build_entity_extraction_prompt(self) -> str:
        """Build LLM prompt for entity extraction based on loaded schema."""
        prompt_parts = ["ENTITY TYPES:"]
        
        for name, entity in sorted(self._entity_types.items()):
            desc = entity.description or f"A {name.lower()}"
            prompt_parts.append(f"- {name}: {desc}")
            
            if entity.keywords:
                prompt_parts.append(f"  Keywords: {', '.join(entity.keywords[:5])}")
            prompt_parts.append("")
        
        return "\n".join(prompt_parts)
    
    def build_relationship_extraction_prompt(self) -> str:
        """Build LLM prompt for relationship extraction based on loaded schema."""
        prompt_parts = ["RELATIONSHIP TYPES (with valid source → target):"]
        
        for name, rel in sorted(self._relationship_types.items()):
            sources = "/".join(rel.source_types[:5]) if rel.source_types else "ANY"
            targets = "/".join(rel.target_types[:5]) if rel.target_types else "ANY"
            desc = rel.description or f"{name} relationship"
            cardinality_note = " (one target only)" if rel.is_many_to_one() else ""
            
            prompt_parts.append(f"- {name}: {sources} → {targets}{cardinality_note}")
            prompt_parts.append(f"  {desc}")
            prompt_parts.append("")
        
        return "\n".join(prompt_parts)


def get_ontology_schema_service(
    session: Session = None, 
    force_reload: bool = False
) -> OntologySchemaService:
    """Get the singleton OntologySchemaService instance.
    
    If no session is provided and service is not loaded, attempts to create
    a session using the default session factory.
    """
    service = OntologySchemaService(session=session, force_reload=force_reload)
    
    if not service._loaded and session:
        service.load(session)
    elif not service._loaded and not session:
        try:
            from ..models.schema import get_session
            with get_session() as db_session:
                service.load(db_session)
        except Exception as e:
            logger.warning(f"Could not auto-load ontology schema: {e}")
    
    return service


def populate_type_translations(session: Session):
    """Populate type_translation table with default mappings.
    
    This migrates hardcoded TYPE_MAPPING to the ontology table.
    """
    default_mappings = [
        ("APPLICATION", "SERVICE", "alias"),
        ("API", "SERVICE", "alias"),
        ("PLATFORM", "SERVICE", "alias"),
        ("GATEWAY", "SERVICE", "alias"),
        ("MICROSERVICE", "SERVICE", "alias"),
        ("GROUP", "TEAM", "alias"),
        ("SQUAD", "TEAM", "alias"),
        ("DEPARTMENT", "TEAM", "alias"),
        ("OUTAGE", "INCIDENT", "alias"),
        ("ISSUE", "INCIDENT", "alias"),
        ("FAILURE", "INCIDENT", "alias"),
        ("DATASTORE", "DATABASE", "alias"),
        ("REPOSITORY", "DATABASE", "alias"),
        ("CACHE", "DATABASE", "alias"),
        ("TECHNOLOGY", "SERVICE", "alias"),
    ]
    
    for deprecated, current, migration_type in default_mappings:
        query = text("""
            INSERT INTO ontology.type_translation 
                (deprecated_name, current_name, migration_type, executed_at)
            VALUES 
                (:deprecated, :current, :migration_type, NOW())
            ON CONFLICT (deprecated_name) DO UPDATE 
                SET current_name = :current,
                    migration_type = :migration_type,
                    executed_at = NOW()
        """)
        
        session.execute(query, {
            'deprecated': deprecated,
            'current': current,
            'migration_type': migration_type
        })
    
    session.commit()
    logger.info(f"Populated {len(default_mappings)} type translations")
