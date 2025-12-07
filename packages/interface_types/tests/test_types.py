"""
Interface Types Tests

Validates that interface types are correctly defined and can be
imported by both Platform Foundation and Brain.
"""

import pytest
from packages.interface_types.src import (
    ExtractionRequest,
    ExtractionResult,
    ExtractionErrorCode,
    TokensConsumed,
    QueryRequest,
    QueryResponse,
    QueryType,
    QueryErrorCode,
)
from packages.interface_types.src.extraction import (
    ExtractionMode,
    Priority,
    ExtractionError,
)
from packages.interface_types.src.query import (
    SemanticSearchResult,
    VerifyStatementResult,
)


class TestExtractionTypes:
    """Test extraction interface types."""

    def test_extraction_request_minimal_valid(self):
        """Test that minimal valid ExtractionRequest is accepted."""
        request = ExtractionRequest(
            request_id="123e4567-e89b-12d3-a456-426614174000",
            document_id="123e4567-e89b-12d3-a456-426614174001",
            tenant_id="123e4567-e89b-12d3-a456-426614174002",
            file_path="/tenants/xxx/documents/yyy/v1/original.pdf",
            file_name="contract.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024000,
            submitted_at="2025-12-07T10:00:00Z"
        )
        
        assert request.tenant_id == "123e4567-e89b-12d3-a456-426614174002"
        assert request.extraction_mode == ExtractionMode.FULL
        assert request.priority == Priority.NORMAL

    def test_extraction_request_with_options(self):
        """Test ExtractionRequest with optional fields."""
        request = ExtractionRequest(
            request_id="123e4567-e89b-12d3-a456-426614174000",
            document_id="123e4567-e89b-12d3-a456-426614174001",
            tenant_id="123e4567-e89b-12d3-a456-426614174002",
            file_path="/tenants/xxx/documents/yyy/v1/original.pdf",
            file_name="contract.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024000,
            submitted_at="2025-12-07T10:00:00Z",
            ontology_hints=["fibo:financial", "dcsa:shipping"],
            extraction_mode=ExtractionMode.INCREMENTAL,
            priority=Priority.HIGH
        )
        
        assert request.ontology_hints == ["fibo:financial", "dcsa:shipping"]
        assert request.extraction_mode == ExtractionMode.INCREMENTAL
        assert request.priority == Priority.HIGH

    def test_extraction_result_success(self):
        """Test successful ExtractionResult."""
        result = ExtractionResult(
            request_id="123e4567-e89b-12d3-a456-426614174000",
            document_id="123e4567-e89b-12d3-a456-426614174001",
            tenant_id="123e4567-e89b-12d3-a456-426614174002",
            status="success",
            entities_extracted=15,
            relationships_extracted=8,
            tokens_consumed=TokensConsumed(
                input_tokens=3000,
                output_tokens=2000,
                total_tokens=5000
            ),
            started_at="2025-12-07T10:00:00Z",
            completed_at="2025-12-07T10:00:30Z",
            duration_ms=30000,
            extraction_version="1.0.0",
            model_used="gpt-4o-mini"
        )
        
        assert result.status == "success"
        assert result.entities_extracted == 15
        assert result.tokens_consumed.total_tokens == 5000
        assert result.error is None

    def test_extraction_result_with_error(self):
        """Test ExtractionResult with error."""
        result = ExtractionResult(
            request_id="123e4567-e89b-12d3-a456-426614174000",
            document_id="123e4567-e89b-12d3-a456-426614174001",
            tenant_id="123e4567-e89b-12d3-a456-426614174002",
            status="failed",
            entities_extracted=0,
            relationships_extracted=0,
            tokens_consumed=TokensConsumed(
                input_tokens=100,
                output_tokens=0,
                total_tokens=100
            ),
            started_at="2025-12-07T10:00:00Z",
            completed_at="2025-12-07T10:00:05Z",
            duration_ms=5000,
            error=ExtractionError(
                code=ExtractionErrorCode.UNSUPPORTED_FORMAT,
                message="Cannot process .exe files",
                recoverable=False
            )
        )
        
        assert result.status == "failed"
        assert result.error is not None
        assert result.error.code == ExtractionErrorCode.UNSUPPORTED_FORMAT
        assert result.error.recoverable is False

    def test_tokens_consumed_from_total(self):
        """Test TokensConsumed.from_total helper."""
        tokens = TokensConsumed.from_total(1000)
        
        assert tokens.total_tokens == 1000
        assert tokens.input_tokens == 600
        assert tokens.output_tokens == 400


class TestQueryTypes:
    """Test query interface types."""

    def test_query_request_semantic_search(self):
        """Test semantic search QueryRequest."""
        request = QueryRequest(
            tenant_id="123e4567-e89b-12d3-a456-426614174002",
            query_type=QueryType.SEMANTIC_SEARCH,
            query_text="financial instruments",
            max_results=10,
            include_provenance=True
        )
        
        assert request.query_type == QueryType.SEMANTIC_SEARCH
        assert request.query_text == "financial instruments"
        assert request.include_provenance is True

    def test_query_request_verify_statement(self):
        """Test verify statement QueryRequest."""
        request = QueryRequest(
            tenant_id="123e4567-e89b-12d3-a456-426614174002",
            query_type=QueryType.VERIFY_STATEMENT,
            statement="ACME Corp signed contract ABC on January 1, 2025"
        )
        
        assert request.query_type == QueryType.VERIFY_STATEMENT
        assert request.statement is not None

    def test_query_request_retrieve_entities(self):
        """Test retrieve entities QueryRequest."""
        request = QueryRequest(
            tenant_id="123e4567-e89b-12d3-a456-426614174002",
            query_type=QueryType.RETRIEVE_ENTITIES,
            entity_type="fibo:FinancialInstrument",
            filters={"currency": "USD"}
        )
        
        assert request.query_type == QueryType.RETRIEVE_ENTITIES
        assert request.entity_type == "fibo:FinancialInstrument"
        assert request.filters == {"currency": "USD"}

    def test_query_request_get_schema(self):
        """Test get schema QueryRequest."""
        request = QueryRequest(
            tenant_id="123e4567-e89b-12d3-a456-426614174002",
            query_type=QueryType.GET_SCHEMA,
            ontology_domain="fibo"
        )
        
        assert request.query_type == QueryType.GET_SCHEMA
        assert request.ontology_domain == "fibo"

    def test_query_response_success(self):
        """Test successful QueryResponse."""
        from packages.interface_types.src.query import TokensConsumed as QueryTokens
        
        response = QueryResponse(
            success=True,
            results=[
                {
                    "entity_id": "ent-123",
                    "entity_type": "fibo:Contract",
                    "content": {"name": "Service Agreement"},
                    "similarity_score": 0.95
                }
            ],
            total_count=1,
            tokens_consumed=QueryTokens(
                input_tokens=100,
                output_tokens=50,
                total_tokens=150
            ),
            duration_ms=250
        )
        
        assert response.success is True
        assert len(response.results) == 1
        assert response.tokens_consumed.total_tokens == 150
        assert response.error is None

    def test_query_response_error(self):
        """Test QueryResponse with error."""
        from packages.interface_types.src.query import (
            TokensConsumed as QueryTokens,
            QueryError,
        )
        
        response = QueryResponse(
            success=False,
            results=[],
            total_count=0,
            tokens_consumed=QueryTokens(
                input_tokens=0,
                output_tokens=0,
                total_tokens=0
            ),
            duration_ms=10,
            error=QueryError(
                code=QueryErrorCode.INVALID_QUERY,
                message="Query text cannot be empty for semantic search"
            )
        )
        
        assert response.success is False
        assert response.error is not None
        assert response.error.code == QueryErrorCode.INVALID_QUERY

    def test_semantic_search_result(self):
        """Test SemanticSearchResult type."""
        result = SemanticSearchResult(
            entity_id="ent-123",
            entity_type="fibo:Contract",
            content={"name": "Test Contract", "value": 100000},
            similarity_score=0.92,
            source_document_id="doc-456",
            confidence=0.88
        )
        
        assert result.similarity_score == 0.92
        assert result.confidence == 0.88

    def test_verify_statement_result(self):
        """Test VerifyStatementResult type."""
        result = VerifyStatementResult(
            verified=True,
            confidence=0.95,
            supporting_entities=["ent-123", "ent-456"],
            contradicting_entities=[],
            explanation="Statement is supported by contract and signature records."
        )
        
        assert result.verified is True
        assert len(result.supporting_entities) == 2


class TestTypesSerialization:
    """Test JSON serialization of interface types."""

    def test_extraction_request_json_roundtrip(self):
        """Test ExtractionRequest JSON serialization."""
        request = ExtractionRequest(
            request_id="123e4567-e89b-12d3-a456-426614174000",
            document_id="123e4567-e89b-12d3-a456-426614174001",
            tenant_id="123e4567-e89b-12d3-a456-426614174002",
            file_path="/tenants/xxx/documents/yyy/v1/original.pdf",
            file_name="contract.pdf",
            mime_type="application/pdf",
            file_size_bytes=1024000,
            submitted_at="2025-12-07T10:00:00Z"
        )
        
        json_str = request.model_dump_json()
        restored = ExtractionRequest.model_validate_json(json_str)
        
        assert restored.request_id == request.request_id
        assert restored.tenant_id == request.tenant_id

    def test_query_response_json_roundtrip(self):
        """Test QueryResponse JSON serialization."""
        from packages.interface_types.src.query import TokensConsumed as QueryTokens
        
        response = QueryResponse(
            success=True,
            results=[{"entity_id": "ent-123"}],
            total_count=1,
            tokens_consumed=QueryTokens(
                input_tokens=100,
                output_tokens=50,
                total_tokens=150
            ),
            duration_ms=250
        )
        
        json_str = response.model_dump_json()
        restored = QueryResponse.model_validate_json(json_str)
        
        assert restored.success == response.success
        assert restored.tokens_consumed.total_tokens == 150
