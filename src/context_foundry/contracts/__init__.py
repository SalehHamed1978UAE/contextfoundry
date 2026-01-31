"""
Component Contracts for Context Foundry.

This module defines formal contracts (interfaces) for all major components,
enabling contract testing and ensuring behavioral consistency.

Week 1 Contracts:
- QueryParserContract: Query intent classification and entity extraction
- EntityResolverContract: 3-stage entity resolution pipeline
- SemanticMemoryContract: Knowledge graph memory layer
- SymbolicMemoryAPIContract: RLM symbolic memory interface
"""

from .query_parser import QueryParserContract, QueryIntent, QueryType, PatternBasedQueryParser
from .entity_resolver import EntityResolverContract, EntityCandidate, ResolveResult, MatchStage
from .memory import (
    SemanticMemoryContract,
    SymbolicMemoryAPIContract,
    EntityRecord,
    RelationshipRecord,
    LifecycleState,
    verify_relationship_parity,
)

__all__ = [
    'QueryParserContract',
    'QueryIntent',
    'QueryType',
    'PatternBasedQueryParser',
    'EntityResolverContract',
    'EntityCandidate',
    'ResolveResult',
    'MatchStage',
    'SemanticMemoryContract',
    'SymbolicMemoryAPIContract',
    'EntityRecord',
    'RelationshipRecord',
    'LifecycleState',
    'verify_relationship_parity',
]
