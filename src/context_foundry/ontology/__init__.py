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
]
