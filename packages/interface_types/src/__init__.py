"""
Interface Types Package
Shared types between Platform Foundation and Brain.

This is the ONLY package that both modules may import.
"""

from .extraction import (
    ExtractionRequest,
    ExtractionResult,
    ExtractionErrorCode,
    ExtractionMode,
    Priority,
    TokensConsumed,
)
from .query import (
    QueryRequest,
    QueryResponse,
    QueryType,
    QueryErrorCode,
    SemanticSearchResult,
    VerifyStatementResult,
    RetrieveEntitiesResult,
    GetSchemaResult,
)

__all__ = [
    # Extraction types
    "ExtractionRequest",
    "ExtractionResult",
    "ExtractionErrorCode",
    "ExtractionMode",
    "Priority",
    "TokensConsumed",
    # Query types
    "QueryRequest",
    "QueryResponse",
    "QueryType",
    "QueryErrorCode",
    "SemanticSearchResult",
    "VerifyStatementResult",
    "RetrieveEntitiesResult",
    "GetSchemaResult",
]
