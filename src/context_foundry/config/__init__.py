"""
Context Foundry Configuration Module.

Provides domain-agnostic schema configuration for entity types,
relationship types, and validation rules.
"""
from .domain_schema import (
    DomainSchema,
    DomainSchemaLoader,
    EntityTypeConfig,
    RelationshipTypeConfig,
    ValidationRuleConfig,
    Cardinality,
    get_schema_loader,
    get_schema,
)

__all__ = [
    'DomainSchema',
    'DomainSchemaLoader',
    'EntityTypeConfig',
    'RelationshipTypeConfig',
    'ValidationRuleConfig',
    'Cardinality',
    'get_schema_loader',
    'get_schema',
]
