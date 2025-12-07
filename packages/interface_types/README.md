# Interface Types

Shared interface types between Platform Foundation and Context Foundry Brain.

## Critical Rule

**This is the ONLY package that both modules may import.**

Platform Foundation and Brain must never import from each other directly. All communication happens through these interface types and the message queue/query endpoint.

## Types

### Extraction Types (Async Flow)

- `ExtractionRequest` - Platform → Queue → Brain
- `ExtractionResult` - Brain → Results Queue → Platform
- `TokensConsumed` - Token metering structure
- `ExtractionErrorCode` - Error codes for extraction operations

### Query Types (Sync Flow)

- `QueryRequest` - Platform → Brain (HTTP)
- `QueryResponse` - Brain → Platform (HTTP response)
- `QueryType` - Supported query types (semantic_search, verify_statement, retrieve_entities, get_schema)
- `QueryErrorCode` - Error codes for query operations

## Usage

```python
from packages.interface_types.src import (
    ExtractionRequest,
    ExtractionResult,
    QueryRequest,
    QueryResponse,
    TokensConsumed,
)

# Create an extraction request
request = ExtractionRequest(
    request_id="uuid-here",
    document_id="doc-uuid",
    tenant_id="tenant-uuid",
    file_path="/tenants/xxx/documents/yyy/v1/file.pdf",
    file_name="contract.pdf",
    mime_type="application/pdf",
    file_size_bytes=1024000,
    submitted_at="2025-12-07T10:00:00Z"
)

# Serialize to JSON for queue
json_str = request.model_dump_json()
```

## Testing

```bash
pytest packages/interface_types/tests/
```
