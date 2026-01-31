# Context Foundry Interface Contracts
## Complete System Communication Specification

**Version:** 1.0  
**Status:** Specification  
**Purpose:** Define every communication boundary in the system

---

## 1. System Boundaries

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL WORLD                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │ Claude/GPT   │  │  Web UI      │  │ Mobile App   │  │ External API │    │
│  │ (MCP Client) │  │              │  │              │  │   Clients    │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
══════════════════════════════════════════════════════════════════════════════
          │              CONTRACT A: External API              │
══════════════════════════════════════════════════════════════════════════════
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PLATFORM FOUNDATION                                  │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  MCP Server │  │   REST API  │  │  Auth Layer │  │  Metering   │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                        │
│  │  Documents  │  │   Tenancy   │  │   Storage   │                        │
│  └──────┬──────┘  └─────────────┘  └─────────────┘                        │
└─────────┼───────────────────────────────────────────────────────────────────┘
          │
══════════════════════════════════════════════════════════════════════════════
          │              CONTRACT B: Platform ↔ Brain              │
══════════════════════════════════════════════════════════════════════════════
          │
          ├─────────────────────────┬─────────────────────────┐
          │                         │                         │
          ▼                         ▼                         ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  Extraction      │    │  Query           │    │  Health          │
│  Queue           │    │  Endpoint        │    │  Endpoint        │
│  (Async)         │    │  (Sync)          │    │  (Sync)          │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              BRAIN                                           │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │ Extraction  │  │  Ontology   │  │ Tri-Memory  │  │  Retrieval  │       │
│  │  Pipeline   │  │  Foundry    │  │ Architecture│  │   Engine    │       │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘       │
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐                                          │
│  │ Validation  │  │  Embedding  │                                          │
│  │   Agents    │  │  Generation │                                          │
│  └─────────────┘  └─────────────┘                                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Contract A: External API

### 2.1 MCP Protocol (for AI Agents)

**Transport:** stdio or HTTP/SSE  
**Authentication:** API Key in header

#### Connection Handshake

```typescript
// Client → Server: Initialize
interface MCPInitialize {
  jsonrpc: "2.0";
  id: number;
  method: "initialize";
  params: {
    protocolVersion: "2024-11-05";
    capabilities: {
      roots?: { listChanged?: boolean };
      sampling?: {};
    };
    clientInfo: {
      name: string;
      version: string;
    };
  };
}

// Server → Client: Initialize Response
interface MCPInitializeResponse {
  jsonrpc: "2.0";
  id: number;
  result: {
    protocolVersion: "2024-11-05";
    capabilities: {
      tools?: { listChanged?: boolean };
      resources?: { subscribe?: boolean; listChanged?: boolean };
      prompts?: { listChanged?: boolean };
    };
    serverInfo: {
      name: "context-foundry";
      version: "1.0.0";
    };
  };
}
```

#### Available Tools

```typescript
// Tool: query_context
interface QueryContextParams {
  query: string;                    // Required: semantic search query
  max_results?: number;             // Default: 10, Max: 100
  entity_type?: string;             // Filter by ontology type
  include_provenance?: boolean;     // Include source document refs
  similarity_threshold?: number;    // Default: 0.7
}

interface QueryContextResult {
  results: Array<{
    entity_id: string;
    entity_type: string;
    content: Record<string, any>;
    similarity_score: number;
    source?: {
      document_id: string;
      document_name: string;
      extracted_at: string;
    };
  }>;
  total_count: number;
  query_tokens_used: number;
}

// Tool: verify_statement
interface VerifyStatementParams {
  statement: string;                // Required: statement to verify
  strict?: boolean;                 // Require high confidence
}

interface VerifyStatementResult {
  verified: boolean;
  confidence: number;               // 0.0 - 1.0
  supporting_evidence: Array<{
    entity_id: string;
    relevance: string;
  }>;
  contradicting_evidence: Array<{
    entity_id: string;
    contradiction: string;
  }>;
  explanation: string;
  query_tokens_used: number;
}

// Tool: ingest_document
interface IngestDocumentParams {
  content: string;                  // Base64 encoded
  filename: string;
  mime_type: string;
  folder_path?: string;             // e.g., "/contracts/2025"
  tags?: string[];
  priority?: "low" | "normal" | "high";
}

interface IngestDocumentResult {
  document_id: string;
  status: "queued";
  estimated_completion_seconds: number;
  position_in_queue: number;
}

// Tool: get_document_status
interface GetDocumentStatusParams {
  document_id: string;
}

interface GetDocumentStatusResult {
  document_id: string;
  name: string;
  status: "uploaded" | "queued" | "processing" | "extracted" | "partial" | "failed";
  entities_extracted?: number;
  error_message?: string;
  created_at: string;
  updated_at: string;
}

// Tool: list_entity_types
interface ListEntityTypesParams {
  domain?: string;                  // e.g., "fibo", "fhir", "dcsa"
}

interface ListEntityTypesResult {
  types: Array<{
    type_id: string;
    name: string;
    domain: string;
    description: string;
    property_count: number;
  }>;
}
```

#### Available Resources

```typescript
// Resource: context://schema/{domain}
// Returns ontology schema for a domain
interface SchemaResource {
  uri: "context://schema/fibo" | "context://schema/fhir" | "context://schema/dcsa";
  name: string;
  description: string;
  mimeType: "application/json";
  contents: {
    domain: string;
    version: string;
    entity_types: Array<{
      type_id: string;
      properties: Array<{
        name: string;
        type: string;
        required: boolean;
        description: string;
      }>;
      relationships: Array<{
        name: string;
        target_type: string;
        cardinality: "one" | "many";
      }>;
    }>;
  };
}

// Resource: context://usage
// Returns current quota usage
interface UsageResource {
  uri: "context://usage";
  name: "Quota Usage";
  mimeType: "application/json";
  contents: {
    tenant_id: string;
    period: "daily";
    extraction_tokens: {
      used: number;
      limit: number;
      percent: number;
    };
    query_tokens: {
      used: number;
      limit: number;
      percent: number;
    };
    documents: {
      count: number;
      limit: number;
    };
    resets_at: string;              // ISO 8601
  };
}
```

---

### 2.2 REST API (for Web/Mobile)

**Base URL:** `https://api.contextfoundry.ai/v1`  
**Authentication:** Bearer token (session) or API key

#### Authentication Endpoints

```typescript
// POST /auth/magic-link
// Request magic link email
interface MagicLinkRequest {
  email: string;
}
interface MagicLinkResponse {
  success: boolean;
  message: string;
}

// POST /auth/verify
// Verify magic link token
interface VerifyRequest {
  token: string;
}
interface VerifyResponse {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  user: {
    id: string;
    email: string;
    name: string;
    role: string;
    tenant_id: string;
    tenant_name: string;
  };
}

// POST /auth/refresh
// Refresh access token
interface RefreshRequest {
  refresh_token: string;
}
interface RefreshResponse {
  access_token: string;
  expires_in: number;
}

// POST /auth/logout
// Invalidate tokens
interface LogoutRequest {}
interface LogoutResponse {
  success: boolean;
}
```

#### Document Endpoints

```typescript
// POST /documents
// Upload document
// Content-Type: multipart/form-data
interface UploadDocumentRequest {
  file: File;
  folder_id?: string;
  tags?: string[];
}
interface UploadDocumentResponse {
  document: {
    id: string;
    name: string;
    size_bytes: number;
    mime_type: string;
    status: "queued";
    created_at: string;
  };
}

// GET /documents
// List documents
interface ListDocumentsRequest {
  folder_id?: string;
  status?: string;
  limit?: number;               // Default: 50, Max: 200
  offset?: number;
  sort_by?: "name" | "created_at" | "status";
  sort_order?: "asc" | "desc";
}
interface ListDocumentsResponse {
  documents: Array<{
    id: string;
    name: string;
    status: string;
    size_bytes: number;
    created_at: string;
    folder_path: string;
  }>;
  total: number;
  limit: number;
  offset: number;
}

// GET /documents/{id}
// Get document details
interface GetDocumentResponse {
  document: {
    id: string;
    name: string;
    original_filename: string;
    mime_type: string;
    size_bytes: number;
    status: string;
    current_version: number;
    folder: {
      id: string;
      path: string;
    };
    tags: string[];
    extraction?: {
      entities_count: number;
      relationships_count: number;
      tokens_consumed: number;
      completed_at: string;
    };
    created_by: {
      id: string;
      name: string;
    };
    created_at: string;
    updated_at: string;
  };
}

// DELETE /documents/{id}
interface DeleteDocumentResponse {
  success: boolean;
}

// POST /documents/{id}/reextract
// Trigger re-extraction
interface ReextractResponse {
  document_id: string;
  status: "queued";
  request_id: string;
}
```

#### Folder Endpoints

```typescript
// POST /folders
interface CreateFolderRequest {
  name: string;
  parent_id?: string;           // null for root
}
interface CreateFolderResponse {
  folder: {
    id: string;
    name: string;
    path: string;
    parent_id: string | null;
    created_at: string;
  };
}

// GET /folders
interface ListFoldersResponse {
  folders: Array<{
    id: string;
    name: string;
    path: string;
    document_count: number;
    children_count: number;
  }>;
}

// GET /folders/{id}/tree
// Get folder tree structure
interface FolderTreeResponse {
  folder: {
    id: string;
    name: string;
    path: string;
    children: FolderTreeNode[];
    documents: DocumentSummary[];
  };
}
```

#### API Key Endpoints

```typescript
// POST /api-keys
interface CreateApiKeyRequest {
  name: string;
  scopes: ("read" | "write" | "admin")[];
  expires_in_days?: number;     // null for no expiry
}
interface CreateApiKeyResponse {
  id: string;
  name: string;
  key: string;                  // Only returned ONCE
  key_prefix: string;
  scopes: string[];
  expires_at: string | null;
  created_at: string;
}

// GET /api-keys
interface ListApiKeysResponse {
  api_keys: Array<{
    id: string;
    name: string;
    key_prefix: string;         // "cf_live_xxxx..."
    scopes: string[];
    last_used_at: string | null;
    expires_at: string | null;
    created_at: string;
  }>;
}

// DELETE /api-keys/{id}
interface RevokeApiKeyResponse {
  success: boolean;
  revoked_at: string;
}
```

#### Usage Endpoints

```typescript
// GET /usage/current
interface CurrentUsageResponse {
  tenant_id: string;
  period: {
    start: string;
    end: string;
  };
  extraction: {
    tokens_used: number;
    tokens_limit: number;
    documents_processed: number;
  };
  query: {
    tokens_used: number;
    tokens_limit: number;
    queries_count: number;
  };
  storage: {
    bytes_used: number;
    bytes_limit: number;
    documents_count: number;
    documents_limit: number;
  };
}

// GET /usage/history
interface UsageHistoryRequest {
  start_date: string;           // ISO date
  end_date: string;
  granularity: "day" | "week" | "month";
}
interface UsageHistoryResponse {
  periods: Array<{
    period_start: string;
    period_end: string;
    extraction_tokens: number;
    query_tokens: number;
    documents_uploaded: number;
  }>;
}
```

---

### 2.3 Error Response Format

All external APIs use consistent error format:

```typescript
interface APIError {
  error: {
    code: string;               // Machine-readable code
    message: string;            // Human-readable message
    details?: Record<string, any>;
    request_id: string;         // For support reference
  };
}

// Standard error codes
type ErrorCode =
  // Authentication (401)
  | "UNAUTHORIZED"
  | "INVALID_TOKEN"
  | "TOKEN_EXPIRED"
  | "INVALID_API_KEY"
  | "API_KEY_REVOKED"
  | "API_KEY_EXPIRED"
  
  // Authorization (403)
  | "FORBIDDEN"
  | "INSUFFICIENT_SCOPE"
  | "TENANT_SUSPENDED"
  
  // Quota (429)
  | "EXTRACTION_QUOTA_EXCEEDED"
  | "QUERY_QUOTA_EXCEEDED"
  | "DOCUMENT_LIMIT_EXCEEDED"
  | "STORAGE_LIMIT_EXCEEDED"
  | "RATE_LIMIT_EXCEEDED"
  
  // Validation (400)
  | "INVALID_REQUEST"
  | "MISSING_REQUIRED_FIELD"
  | "INVALID_FIELD_VALUE"
  | "UNSUPPORTED_FILE_TYPE"
  | "FILE_TOO_LARGE"
  
  // Not Found (404)
  | "DOCUMENT_NOT_FOUND"
  | "FOLDER_NOT_FOUND"
  | "ENTITY_NOT_FOUND"
  
  // Server (500)
  | "INTERNAL_ERROR"
  | "SERVICE_UNAVAILABLE"
  | "EXTRACTION_FAILED";

// HTTP Status mapping
const errorStatusMap = {
  UNAUTHORIZED: 401,
  INVALID_TOKEN: 401,
  TOKEN_EXPIRED: 401,
  INVALID_API_KEY: 401,
  FORBIDDEN: 403,
  INSUFFICIENT_SCOPE: 403,
  EXTRACTION_QUOTA_EXCEEDED: 429,
  QUERY_QUOTA_EXCEEDED: 429,
  RATE_LIMIT_EXCEEDED: 429,
  INVALID_REQUEST: 400,
  DOCUMENT_NOT_FOUND: 404,
  INTERNAL_ERROR: 500
};
```

---

## 3. Contract B: Platform ↔ Brain

### 3.1 Extraction Queue Contract

**Direction:** Platform → Brain (async)  
**Transport:** PostgreSQL NOTIFY/LISTEN or Redis Streams  
**Guarantee:** At-least-once delivery

#### Request Message

```typescript
interface ExtractionRequest {
  // === Identity (Required) ===
  request_id: string;           // UUID v4, generated by Platform
  document_id: string;          // Platform's document record ID
  tenant_id: string;            // From authenticated session
  
  // === Document Location (Required) ===
  file_path: string;            // Storage path: /tenants/{tenant}/docs/{doc}/v{n}/file.pdf
  file_name: string;            // Original filename for context
  mime_type: string;            // IANA media type
  file_size_bytes: number;      // For estimation
  
  // === Extraction Hints (Optional) ===
  ontology_hints?: string[];    // Prioritize: ["fibo:loan", "fibo:collateral"]
  extraction_mode?: "full" | "incremental";  // Default: "full"
  schema_version?: string;      // Lock to specific ontology version
  
  // === Processing Control (Optional) ===
  priority?: "low" | "normal" | "high";  // Default: "normal"
  callback_url?: string;        // Webhook for completion (future)
  
  // === Metadata (Required) ===
  submitted_at: string;         // ISO 8601 timestamp
  source?: string;              // "web_upload" | "api" | "mcp" | "bulk"
}

// Validation rules
const extractionRequestRules = {
  request_id: "UUID v4 format",
  document_id: "UUID v4 format", 
  tenant_id: "UUID v4 format",
  file_path: "Must start with /tenants/",
  file_name: "Non-empty string, max 255 chars",
  mime_type: "Valid IANA media type",
  file_size_bytes: "Positive integer",
  submitted_at: "Valid ISO 8601 timestamp"
};
```

#### Result Message

```typescript
interface ExtractionResult {
  // === Identity (Echo Back) ===
  request_id: string;           // From request
  document_id: string;          // From request
  tenant_id: string;            // From request
  
  // === Status ===
  status: "success" | "partial" | "failed";
  
  // === Results (if success/partial) ===
  entities_extracted: number;
  relationships_extracted: number;
  entity_types_found: string[]; // ["fibo:Loan", "fibo:Party"]
  
  // === Cost Tracking (CRITICAL) ===
  tokens_consumed: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
    model_breakdown?: Record<string, number>;  // If multiple models used
  };
  
  // === Timing ===
  started_at: string;
  completed_at: string;
  duration_ms: number;
  
  // === Error Info (if failed/partial) ===
  error?: {
    code: ExtractionErrorCode;
    message: string;
    recoverable: boolean;
    retry_after_seconds?: number;
  };
  
  // === Provenance ===
  extraction_version: string;
  model_used: string;
  ontology_version: string;
}

type ExtractionErrorCode =
  | "FILE_NOT_FOUND"            // Storage path invalid
  | "FILE_UNREADABLE"           // Corrupted or encrypted
  | "UNSUPPORTED_FORMAT"        // Can't process this type
  | "TOKEN_LIMIT_EXCEEDED"      // Single doc too large
  | "EXTRACTION_TIMEOUT"        // Took too long
  | "MODEL_ERROR"               // LLM returned error
  | "SCHEMA_VALIDATION_FAILED"  // Extracted data invalid
  | "INTERNAL_ERROR";           // Unexpected failure
```

#### Queue Protocol

```typescript
// PostgreSQL Implementation
interface QueueOperations {
  // Platform: Submit job
  submit(request: ExtractionRequest): Promise<void>;
  
  // Brain: Claim next job (atomic)
  claim(workerId: string): Promise<ExtractionRequest | null>;
  
  // Brain: Complete job
  complete(requestId: string, result: ExtractionResult): Promise<void>;
  
  // Brain: Fail job (with retry logic)
  fail(requestId: string, error: ExtractionError): Promise<void>;
  
  // Platform: Poll for results
  getResult(requestId: string): Promise<ExtractionResult | null>;
  
  // Platform: Subscribe to results
  subscribeResults(callback: (result: ExtractionResult) => void): void;
}

// Queue Table Schema
/*
CREATE TABLE extraction_queue (
  id UUID PRIMARY KEY,
  request_id UUID UNIQUE NOT NULL,
  tenant_id UUID NOT NULL,
  document_id UUID NOT NULL,
  payload JSONB NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  priority INTEGER NOT NULL DEFAULT 5,
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  worker_id TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  next_retry_at TIMESTAMPTZ
);

CREATE TABLE extraction_results (
  id UUID PRIMARY KEY,
  request_id UUID UNIQUE NOT NULL,
  tenant_id UUID NOT NULL,
  document_id UUID NOT NULL,
  payload JSONB NOT NULL,
  processed_by_platform BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
*/

// Retry Logic
const retryPolicy = {
  maxAttempts: 3,
  backoffSeconds: [60, 300, 900],  // 1min, 5min, 15min
  retryableCodes: [
    "EXTRACTION_TIMEOUT",
    "MODEL_ERROR",
    "INTERNAL_ERROR"
  ],
  nonRetryableCodes: [
    "FILE_NOT_FOUND",
    "UNSUPPORTED_FORMAT",
    "TOKEN_LIMIT_EXCEEDED"
  ]
};
```

---

### 3.2 Query Endpoint Contract

**Direction:** Platform → Brain (sync)  
**Transport:** HTTP POST  
**Timeout:** 30 seconds

#### Endpoint Definition

```
POST /internal/v1/query
Authorization: Bearer {BRAIN_INTERNAL_KEY}
Content-Type: application/json
X-Request-ID: {uuid}
```

#### Request Schema

```typescript
interface QueryRequest {
  // === Identity (Required) ===
  tenant_id: string;
  
  // === Query Type (Required) ===
  query_type: QueryType;
  
  // === Type-Specific Parameters ===
  
  // For semantic_search
  query_text?: string;
  max_results?: number;           // Default: 10, Max: 100
  similarity_threshold?: number;  // Default: 0.7, Range: 0.0-1.0
  
  // For verify_statement
  statement?: string;
  
  // For retrieve_entities
  entity_type?: string;
  entity_ids?: string[];          // Specific IDs to retrieve
  filters?: EntityFilters;
  
  // For get_schema
  ontology_domain?: string;
  
  // For relationship_query (traverse graph)
  start_entity_id?: string;
  relationship_type?: string;
  max_depth?: number;             // Default: 1, Max: 5
  
  // === Common Options ===
  include_provenance?: boolean;
  include_confidence?: boolean;
  include_embeddings?: boolean;   // Return vectors (large!)
}

type QueryType = 
  | "semantic_search"
  | "verify_statement"
  | "retrieve_entities"
  | "get_schema"
  | "relationship_query"
  | "aggregate";

interface EntityFilters {
  created_after?: string;
  created_before?: string;
  source_document_id?: string;
  properties?: Record<string, any>;  // Exact match on properties
}
```

#### Response Schema

```typescript
interface QueryResponse {
  // === Status ===
  success: boolean;
  
  // === Results ===
  results: QueryResult[];
  total_count: number;
  has_more: boolean;
  
  // === Cost Tracking (CRITICAL) ===
  tokens_consumed: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  
  // === Performance ===
  duration_ms: number;
  cache_hit?: boolean;
  
  // === Error (if !success) ===
  error?: {
    code: QueryErrorCode;
    message: string;
  };
}

type QueryErrorCode =
  | "INVALID_QUERY"
  | "INVALID_TENANT"
  | "NO_RESULTS"
  | "QUERY_TOO_COMPLEX"
  | "TIMEOUT"
  | "MODEL_ERROR"
  | "INTERNAL_ERROR";

// Result types per query_type
interface SemanticSearchResult {
  entity_id: string;
  entity_type: string;
  content: Record<string, any>;
  similarity_score: number;
  confidence?: number;
  provenance?: {
    document_id: string;
    document_name: string;
    extracted_at: string;
    page_number?: number;
  };
}

interface VerifyStatementResult {
  verified: boolean;
  confidence: number;
  verdict: "confirmed" | "contradicted" | "unverifiable" | "partially_confirmed";
  supporting_entities: Array<{
    entity_id: string;
    relevance: number;
    excerpt?: string;
  }>;
  contradicting_entities: Array<{
    entity_id: string;
    contradiction: string;
  }>;
  explanation: string;
}

interface RetrieveEntitiesResult {
  entity_id: string;
  entity_type: string;
  content: Record<string, any>;
  relationships: Array<{
    type: string;
    target_id: string;
    target_type: string;
  }>;
  created_at: string;
  source_document_id: string;
}

interface SchemaResult {
  domain: string;
  version: string;
  entity_types: Array<{
    type_id: string;
    label: string;
    description: string;
    properties: PropertyDefinition[];
    relationships: RelationshipDefinition[];
  }>;
}

interface RelationshipQueryResult {
  paths: Array<{
    nodes: Array<{
      entity_id: string;
      entity_type: string;
      content: Record<string, any>;
    }>;
    edges: Array<{
      type: string;
      from: string;
      to: string;
    }>;
  }>;
}
```

---

### 3.3 Health Endpoint Contract

**Direction:** Platform → Brain (sync)  
**Purpose:** Readiness and liveness checks

```
GET /internal/v1/health
Authorization: Bearer {BRAIN_INTERNAL_KEY}
```

```typescript
interface HealthResponse {
  status: "healthy" | "degraded" | "unhealthy";
  version: string;
  uptime_seconds: number;
  
  components: {
    database: ComponentHealth;
    embedding_service: ComponentHealth;
    llm_service: ComponentHealth;
    queue_consumer: ComponentHealth;
  };
  
  metrics: {
    queue_depth: number;
    active_extractions: number;
    avg_extraction_time_ms: number;
    entities_count: number;
  };
}

interface ComponentHealth {
  status: "up" | "down" | "degraded";
  latency_ms?: number;
  last_check: string;
  error?: string;
}
```

---

### 3.4 Internal Authentication

All Platform → Brain requests use:

```typescript
// Header
Authorization: Bearer {BRAIN_INTERNAL_KEY}

// Key format
const BRAIN_INTERNAL_KEY = "cf_internal_" + crypto.randomBytes(32).toString('base64url');

// Validation (in Brain)
function validateInternalRequest(authHeader: string): boolean {
  const token = authHeader.replace('Bearer ', '');
  return token === process.env.BRAIN_INTERNAL_KEY;
}
```

---

## 4. Data Contracts

### 4.1 Shared Column: tenant_id

Both Platform and Brain use `tenant_id` on relevant tables:

```typescript
// Platform is SOURCE OF TRUTH for tenant existence
// Brain TRUSTS tenant_id passed in requests

interface TenantIdContract {
  // Platform guarantees:
  platformGuarantees: [
    "tenant_id is always a valid UUID",
    "tenant_id references existing active tenant",
    "tenant_id is extracted from authenticated session/API key",
    "tenant_id is included in every request to Brain"
  ];
  
  // Brain trusts:
  brainTrusts: [
    "tenant_id is valid (no validation needed)",
    "tenant_id scopes all data operations",
    "tenant_id stored on every entity/relationship"
  ];
  
  // Brain NEVER:
  brainNever: [
    "validates tenant_id exists",
    "accesses Platform's tenants table",
    "creates records without tenant_id"
  ];
}
```

### 4.2 Document Reference Contract

Brain stores `source_document_id` but doesn't access Platform's documents table:

```typescript
interface DocumentReferenceContract {
  // On entity records:
  entity: {
    source_document_id: string;   // UUID from Platform
    source_document_name?: string; // Cached for display
    extraction_request_id: string; // Links to specific extraction
  };
  
  // Brain stores these as metadata, never joins to Platform tables
  // If Platform deletes document, Brain entities remain (orphaned)
  // Cleanup is handled by periodic reconciliation job
}
```

---

## 5. Contract Versioning

### Version Header

All requests include version:

```
X-Contract-Version: 1.0
```

### Breaking Changes

Breaking changes require:
1. New major version (2.0)
2. Both sides support old and new for transition period
3. Deprecation notice 30 days before removal

### Non-Breaking Changes

These can be added without version bump:
- New optional fields in requests
- New optional fields in responses
- New error codes
- New query types (if backward compatible)

---

## 6. Contract Tests

### Test: Extraction Contract

```typescript
describe('Extraction Contract', () => {
  it('Platform request meets Brain schema', () => {
    const request = platform.createExtractionRequest(doc);
    expect(validateExtractionRequest(request)).toBe(true);
  });
  
  it('Brain result meets Platform schema', () => {
    const result = brain.createExtractionResult(job);
    expect(validateExtractionResult(result)).toBe(true);
  });
  
  it('Brain includes tenant_id from request', () => {
    const request = { tenant_id: 'test-tenant', /* ... */ };
    const result = await brain.processExtraction(request);
    expect(result.tenant_id).toBe(request.tenant_id);
  });
  
  it('tokens_consumed is always populated', () => {
    const result = await brain.processExtraction(request);
    expect(result.tokens_consumed.total_tokens).toBeGreaterThan(0);
  });
});
```

### Test: Query Contract

```typescript
describe('Query Contract', () => {
  it('Platform request meets Brain schema', () => {
    const query = platform.createQueryRequest('semantic_search', params);
    expect(validateQueryRequest(query)).toBe(true);
  });
  
  it('Brain response meets Platform schema', () => {
    const response = await brain.query(request);
    expect(validateQueryResponse(response)).toBe(true);
  });
  
  it('Results scoped to tenant_id', () => {
    const response = await brain.query({ tenant_id: 'tenant-1', /* ... */ });
    response.results.forEach(r => {
      expect(r.tenant_id || r.provenance?.tenant_id).toBe('tenant-1');
    });
  });
  
  it('tokens_consumed reflects actual usage', () => {
    const response = await brain.query(expensiveQuery);
    expect(response.tokens_consumed.total_tokens).toBeGreaterThan(100);
  });
});
```

### Test: Isolation Contract

```typescript
describe('Tenant Isolation Contract', () => {
  it('Brain never returns other tenant data', async () => {
    // Setup: Create entities for two tenants
    await brain.ingestForTenant('tenant-1', doc1);
    await brain.ingestForTenant('tenant-2', doc2);
    
    // Query as tenant-1
    const response = await brain.query({
      tenant_id: 'tenant-1',
      query_type: 'retrieve_entities'
    });
    
    // Verify no tenant-2 data
    response.results.forEach(entity => {
      expect(entity.tenant_id).toBe('tenant-1');
      expect(entity.tenant_id).not.toBe('tenant-2');
    });
  });
});
```

---

**End of Interface Contracts Specification**
