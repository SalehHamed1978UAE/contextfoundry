"""
Database-backed ontology system for Context Foundry.

This module replaces YAML-based schema loading with dynamic PostgreSQL queries,
enabling trigger-enforced type validation and multi-tenant ontology extensions.
"""

from .repository import OntologyRepository, get_ontology_repository
from .prompt_generator import SchemaPromptGenerator
from .models import EntityExtraction, RelationshipExtraction, ExtractionResult
from .constrained_extractor import ConstrainedExtractor
from .shadow_adapter import ShadowAdapter
from .normalizer import CandidateNormalizer
from .candidate_store import CandidateStore

from .schema import (
    EntityType,
    RelationshipType,
    ValueType,
    ExtractedEntity,
    ExtractedRelationship,
    ExtractionOutput,
    ENTITY_PROPERTY_MAP,
    VALID_RELATIONSHIP_SOURCES,
    VALID_RELATIONSHIP_TARGETS,
)

from .validator import (
    OntologyValidator,
    ValidationError,
    normalize_entity_type,
    normalize_relationship_type,
)

__all__ = [
    'OntologyRepository',
    'get_ontology_repository',
    'SchemaPromptGenerator',
    'EntityExtraction',
    'RelationshipExtraction',
    'ExtractionResult',
    'ConstrainedExtractor',
    'ShadowAdapter',
    'CandidateNormalizer',
    'CandidateStore',
    'EntityType',
    'RelationshipType',
    'ValueType',
    'ExtractedEntity',
    'ExtractedRelationship',
    'ExtractionOutput',
    'ENTITY_PROPERTY_MAP',
    'VALID_RELATIONSHIP_SOURCES',
    'VALID_RELATIONSHIP_TARGETS',
    'OntologyValidator',
    'ValidationError',
    'normalize_entity_type',
    'normalize_relationship_type',
]
