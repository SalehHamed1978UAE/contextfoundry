# Context Foundry External API

## Overview

The Context Foundry External API allows external applications to query the knowledge graph and retrieve structured context bundles.

**Base URL:** `https://your-instance.com/api/v1`

**Authentication:** API key required in `X-CF-API-Key` header

---

## Authentication

All endpoints (except `/health`) require an API key:

```bash
curl -H "X-CF-API-Key: cf_your_api_key_here" \
     https://your-instance.com/api/v1/entities/API%20Gateway
```

### Getting an API Key

Contact your Context Foundry administrator to obtain an API key for your application.

---

## Endpoints

### GET /health

System health check. No authentication required.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-12-10T04:30:00Z",
  "components": {
    "database": "connected",
    "api": "operational"
  }
}
```

---

### POST /query

Natural language query with GROUNDED/GAP/INFERRED response structure.

**Request:**
```json
{
  "query": "What is the blast radius if API Gateway fails?",
  "options": {
    "include_inferred": true,
    "max_depth": 3,
    "confidence_threshold": 0.7
  }
}
```

**Response:**
```json
{
  "answer": "GROUNDED:\n- Auth Service depends on API Gateway\n- User Portal depends on API Gateway\n\nGAP IDENTIFIED:\n- No SLA documentation found\n\nINFERRED:\n- Approximately 3 downstream services affected",
  "confidence": 0.85,
  "grounded": [
    {"fact": "Auth Service depends on API Gateway", "source": "knowledge_graph"},
    {"fact": "User Portal depends on API Gateway", "source": "knowledge_graph"}
  ],
  "inferred": [
    {"fact": "Approximately 3 downstream services affected", "reasoning": "Derived from graph structure"}
  ],
  "gaps": [
    {"topic": "SLA documentation", "suggestion": "Document this relationship"}
  ],
  "query_type": "blast_radius",
  "entities_found": ["API Gateway", "Auth Service", "User Portal"]
}
```

**Query Types Supported:**
- `blast_radius` - What breaks if X fails?
- `dependency` - What does X depend on?
- `ownership` - Who owns X?
- `general` - Open-ended questions

---

### POST /context

Get a structured context bundle for an entity.

**Request:**
```json
{
  "entity": "API Gateway",
  "depth": 2,
  "include": ["relationships", "properties", "sources"]
}
```

**Parameters:**
- `entity` (required): Entity name to retrieve
- `depth` (optional): How many relationship hops to include (1-5, default: 1)
- `include` (optional): What to include in response

**Response:**
```json
{
  "entity": {
    "id": "abc123",
    "name": "API Gateway",
    "type": "SERVICE",
    "properties": {
      "version": "2.1.0",
      "port": 8080
    }
  },
  "relationships": [
    {
      "type": "DEPENDS_ON",
      "target": "Auth Service",
      "confidence": 0.95
    }
  ],
  "related_entities": [
    {
      "id": "def456",
      "name": "Auth Service",
      "type": "SERVICE"
    }
  ],
  "sources": [
    {
      "document": "architecture.md",
      "section": "Service Dependencies"
    }
  ]
}
```

---

### GET /entities/{name}

Get entity details by name.

**URL:** `/api/v1/entities/API%20Gateway`

**Query Parameters:**
- `include_relationships` (optional): Include relationships (default: true)
- `include_properties` (optional): Include properties (default: true)

**Response:**
```json
{
  "id": "abc123",
  "name": "API Gateway",
  "type": "SERVICE",
  "confidence": 0.92,
  "lifecycle_state": "TRUSTED",
  "properties": {
    "version": "2.1.0",
    "port": 8080
  },
  "description": "Central API gateway handling all external requests",
  "relationships": {
    "incoming": [
      {"type": "MANAGES", "source": "Platform Team", "confidence": 0.9}
    ],
    "outgoing": [
      {"type": "DEPENDS_ON", "target": "Auth Service", "confidence": 0.95}
    ]
  }
}
```

---

### GET /entities

Search entities by query.

**URL:** `/api/v1/entities?q=gateway&type=SERVICE&limit=10`

**Query Parameters:**
- `q` (required): Search query
- `type` (optional): Filter by entity type
- `limit` (optional): Max results (default: 10, max: 100)
- `offset` (optional): Pagination offset

**Response:**
```json
{
  "entities": [
    {
      "id": "abc123",
      "name": "API Gateway",
      "type": "SERVICE",
      "confidence": 0.92,
      "similarity": 0.95
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

---

## Error Responses

All errors follow this format:

```json
{
  "error": "Error type",
  "message": "Human-readable description",
  "suggestion": "Optional suggestion for resolution"
}
```

**Common HTTP Status Codes:**
- `400` - Bad request (missing parameters)
- `401` - Authentication failed
- `404` - Entity not found
- `500` - Server error

---

## Rate Limits

- 100 requests per minute per API key
- 1000 requests per hour per API key

Rate limit headers included in response:
- `X-RateLimit-Limit`: Max requests per window
- `X-RateLimit-Remaining`: Requests remaining
- `X-RateLimit-Reset`: Unix timestamp when limit resets

---

## Examples

### Python

```python
import requests

API_KEY = "cf_your_api_key"
BASE_URL = "https://contextfoundry.app/api/v1"

headers = {"X-CF-API-Key": API_KEY}

# Query
response = requests.post(
    f"{BASE_URL}/query",
    headers=headers,
    json={"query": "What depends on the User Database?"}
)
print(response.json())

# Get entity
response = requests.get(
    f"{BASE_URL}/entities/User%20Database",
    headers=headers
)
print(response.json())
```

### JavaScript

```javascript
const API_KEY = "cf_your_api_key";
const BASE_URL = "https://contextfoundry.app/api/v1";

// Query
const response = await fetch(`${BASE_URL}/query`, {
  method: "POST",
  headers: {
    "X-CF-API-Key": API_KEY,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    query: "What depends on the User Database?"
  })
});
const data = await response.json();
console.log(data);
```

### cURL

```bash
# Health check
curl https://contextfoundry.app/api/v1/health

# Query
curl -X POST https://contextfoundry.app/api/v1/query \
  -H "X-CF-API-Key: cf_your_api_key" \
  -H "Content-Type: application/json" \
  -d '{"query": "What depends on the User Database?"}'

# Get entity
curl https://contextfoundry.app/api/v1/entities/User%20Database \
  -H "X-CF-API-Key: cf_your_api_key"
```
