# Context Foundry Platform Foundation
## Replit Implementation Plan

**Purpose:** Step-by-step build instructions for Platform Foundation that integrates cleanly with existing Context Foundry Brain.

**Critical Rule:** Platform Foundation is a separate module. It communicates with Brain through the Interface Contract only. No spaghetti.

---

## Pre-Implementation Setup

### 1. Repository Structure

Create this structure before writing any code:

```
context-foundry/
├── packages/
│   └── interface-types/           # CREATE THIS FIRST
│
├── platform-foundation/           # NEW - all Platform code here
│   ├── src/
│   ├── tests/
│   └── package.json
│
├── brain/                         # EXISTING - do not modify structure
│   └── (existing extraction, ontology, memory code)
│
└── test/
    ├── integration/               # Tests requiring both modules
    └── e2e/                       # Full journey tests
```

### 2. Supabase Project Setup

```bash
# Create new Supabase project: "context-foundry-platform"
# Note these values:
# - SUPABASE_URL
# - SUPABASE_ANON_KEY
# - SUPABASE_SERVICE_ROLE_KEY
# - DATABASE_URL (for direct Postgres access)
```

### 3. Environment Configuration

```env
# platform-foundation/.env
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=xxx
SUPABASE_SERVICE_ROLE_KEY=xxx
DATABASE_URL=postgresql://...

# Queue config (using Postgres NOTIFY for pilot)
QUEUE_TYPE=postgres_notify
EXTRACTION_QUEUE_CHANNEL=extraction_requests
RESULTS_QUEUE_CHANNEL=extraction_results

# Brain query endpoint (internal)
BRAIN_QUERY_URL=http://localhost:3001/api/v1/query
BRAIN_INTERNAL_KEY=xxx
```

---

## Phase 0: Interface Types (Day 1)

**Goal:** Establish the contract before writing any implementation.

### Deliverable: `packages/interface-types`

```typescript
// packages/interface-types/src/extraction.ts

export interface ExtractionRequest {
  request_id: string;
  document_id: string;
  tenant_id: string;
  file_path: string;
  file_name: string;
  mime_type: string;
  file_size_bytes: number;
  ontology_hints?: string[];
  extraction_mode?: 'full' | 'incremental';
  submitted_at: string;
  priority?: 'low' | 'normal' | 'high';
}

export interface ExtractionResult {
  request_id: string;
  document_id: string;
  tenant_id: string;
  status: 'success' | 'partial' | 'failed';
  entities_extracted: number;
  relationships_extracted: number;
  tokens_consumed: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  started_at: string;
  completed_at: string;
  duration_ms: number;
  error?: {
    code: string;
    message: string;
    recoverable: boolean;
  };
  extraction_version: string;
  model_used: string;
}

export type ExtractionErrorCode = 
  | 'EXTRACTION_SUCCESS'
  | 'EXTRACTION_PARTIAL'
  | 'UNSUPPORTED_FORMAT'
  | 'FILE_NOT_FOUND'
  | 'EXTRACTION_TIMEOUT'
  | 'TOKEN_LIMIT_EXCEEDED'
  | 'MODEL_ERROR'
  | 'INTERNAL_ERROR';
```

```typescript
// packages/interface-types/src/query.ts

export interface QueryRequest {
  tenant_id: string;
  query_type: 'semantic_search' | 'verify_statement' | 'retrieve_entities' | 'get_schema';
  query_text?: string;
  max_results?: number;
  similarity_threshold?: number;
  statement?: string;
  entity_type?: string;
  filters?: Record<string, any>;
  ontology_domain?: string;
  include_provenance?: boolean;
  include_confidence?: boolean;
}

export interface QueryResponse {
  success: boolean;
  results: any[];
  total_count: number;
  tokens_consumed: {
    input_tokens: number;
    output_tokens: number;
    total_tokens: number;
  };
  duration_ms: number;
  error?: {
    code: string;
    message: string;
  };
}

export type QueryErrorCode =
  | 'QUERY_SUCCESS'
  | 'NO_RESULTS'
  | 'INVALID_QUERY'
  | 'TENANT_NOT_FOUND'
  | 'MODEL_ERROR'
  | 'INTERNAL_ERROR';
```

```typescript
// packages/interface-types/src/index.ts
export * from './extraction';
export * from './query';
```

### Test: Type Validation

```typescript
// packages/interface-types/src/__tests__/types.test.ts
import { ExtractionRequest, QueryRequest } from '../index';

describe('Interface Types', () => {
  describe('ExtractionRequest', () => {
    it('accepts valid minimal request', () => {
      const request: ExtractionRequest = {
        request_id: '123e4567-e89b-12d3-a456-426614174000',
        document_id: '123e4567-e89b-12d3-a456-426614174001',
        tenant_id: '123e4567-e89b-12d3-a456-426614174002',
        file_path: '/tenants/xxx/documents/yyy/v1/original.pdf',
        file_name: 'contract.pdf',
        mime_type: 'application/pdf',
        file_size_bytes: 1024000,
        submitted_at: '2025-12-07T10:00:00Z'
      };
      expect(request.tenant_id).toBeDefined();
    });
  });
  
  describe('QueryRequest', () => {
    it('accepts semantic_search request', () => {
      const request: QueryRequest = {
        tenant_id: '123e4567-e89b-12d3-a456-426614174002',
        query_type: 'semantic_search',
        query_text: 'financial instruments',
        max_results: 10
      };
      expect(request.query_type).toBe('semantic_search');
    });
  });
});
```

### Completion Criteria Phase 0:
- [ ] `packages/interface-types` exists with all types
- [ ] Types compile without errors
- [ ] Type tests pass
- [ ] Package can be imported by both platform-foundation and brain

---

## Phase 1: Database Schema (Day 2-3)

**Goal:** Create all Platform Foundation tables with RLS.

### Deliverable: Supabase Migrations

```sql
-- supabase/migrations/001_tenants.sql

-- Tenants table
CREATE TABLE tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('opco_production', 'opco_pilot', 'personal_sandbox', 'demo', 'qdata_internal')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
  settings JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Enable RLS
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;

-- Policy: Only platform admins can see all tenants
CREATE POLICY "Platform admins see all tenants" ON tenants
  FOR SELECT USING (
    auth.jwt() ->> 'role' = 'platform_admin'
  );

-- Policy: Users see own tenant
CREATE POLICY "Users see own tenant" ON tenants
  FOR SELECT USING (
    id = (auth.jwt() ->> 'tenant_id')::UUID
  );
```

```sql
-- supabase/migrations/002_users.sql

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  role TEXT NOT NULL CHECK (role IN ('platform_admin', 'tenant_admin', 'knowledge_steward', 'user', 'viewer')),
  tenant_id UUID REFERENCES tenants(id),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'invited', 'suspended')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_login TIMESTAMPTZ
);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Users can see themselves
CREATE POLICY "Users see self" ON users
  FOR SELECT USING (id = auth.uid());

-- Tenant admins see users in their tenant
CREATE POLICY "Tenant admins see tenant users" ON users
  FOR SELECT USING (
    tenant_id = (auth.jwt() ->> 'tenant_id')::UUID
    AND (auth.jwt() ->> 'role') IN ('tenant_admin', 'platform_admin')
  );
```

```sql
-- supabase/migrations/003_documents.sql

CREATE TABLE folders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  parent_id UUID REFERENCES folders(id),
  name TEXT NOT NULL,
  path TEXT NOT NULL,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  folder_id UUID REFERENCES folders(id),
  name TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  storage_path TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'uploaded' 
    CHECK (status IN ('uploaded', 'queued', 'processing', 'extracted', 'partial', 'failed')),
  current_version INTEGER NOT NULL DEFAULT 1,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE document_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL REFERENCES documents(id),
  version_number INTEGER NOT NULL,
  storage_path TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  extraction_request_id UUID,
  UNIQUE(document_id, version_number)
);

-- RLS for documents
ALTER TABLE folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Tenant isolation for folders" ON folders
  FOR ALL USING (tenant_id = (auth.jwt() ->> 'tenant_id')::UUID);

CREATE POLICY "Tenant isolation for documents" ON documents
  FOR ALL USING (tenant_id = (auth.jwt() ->> 'tenant_id')::UUID);

CREATE POLICY "Tenant isolation for versions" ON document_versions
  FOR ALL USING (
    document_id IN (
      SELECT id FROM documents 
      WHERE tenant_id = (auth.jwt() ->> 'tenant_id')::UUID
    )
  );
```

```sql
-- supabase/migrations/004_usage_metering.sql

CREATE TABLE tenant_quotas (
  tenant_id UUID PRIMARY KEY REFERENCES tenants(id),
  extraction_tokens_daily BIGINT NOT NULL DEFAULT 100000,
  extraction_tokens_monthly BIGINT NOT NULL DEFAULT 2000000,
  query_tokens_daily BIGINT NOT NULL DEFAULT 50000,
  query_tokens_monthly BIGINT NOT NULL DEFAULT 1000000,
  document_limit INTEGER NOT NULL DEFAULT 500,
  storage_gb_limit INTEGER NOT NULL DEFAULT 10,
  api_rate_limit_per_min INTEGER NOT NULL DEFAULT 60,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE usage_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  user_id UUID REFERENCES users(id),
  api_key_id UUID,
  event_type TEXT NOT NULL CHECK (event_type IN ('extraction', 'query', 'upload')),
  tokens_consumed INTEGER NOT NULL DEFAULT 0,
  document_id UUID,
  request_id UUID,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE usage_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  snapshot_date DATE NOT NULL,
  extraction_tokens_used BIGINT NOT NULL DEFAULT 0,
  query_tokens_used BIGINT NOT NULL DEFAULT 0,
  documents_count INTEGER NOT NULL DEFAULT 0,
  storage_bytes_used BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(tenant_id, snapshot_date)
);

-- RLS
ALTER TABLE tenant_quotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE usage_snapshots ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Tenant sees own quotas" ON tenant_quotas
  FOR SELECT USING (tenant_id = (auth.jwt() ->> 'tenant_id')::UUID);

CREATE POLICY "Tenant sees own usage" ON usage_events
  FOR SELECT USING (tenant_id = (auth.jwt() ->> 'tenant_id')::UUID);

CREATE POLICY "Tenant sees own snapshots" ON usage_snapshots
  FOR SELECT USING (tenant_id = (auth.jwt() ->> 'tenant_id')::UUID);

-- Function to get current daily usage
CREATE OR REPLACE FUNCTION get_tenant_daily_usage(p_tenant_id UUID)
RETURNS TABLE (
  extraction_tokens BIGINT,
  query_tokens BIGINT
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    COALESCE(SUM(CASE WHEN event_type = 'extraction' THEN tokens_consumed ELSE 0 END), 0) as extraction_tokens,
    COALESCE(SUM(CASE WHEN event_type = 'query' THEN tokens_consumed ELSE 0 END), 0) as query_tokens
  FROM usage_events
  WHERE tenant_id = p_tenant_id
    AND created_at >= CURRENT_DATE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
```

```sql
-- supabase/migrations/005_api_keys.sql

CREATE TABLE api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  name TEXT NOT NULL,
  key_hash TEXT NOT NULL,  -- Store hash only, never plaintext
  key_prefix TEXT NOT NULL,  -- First 8 chars for identification: "cf_live_..."
  scopes TEXT[] NOT NULL DEFAULT ARRAY['read'],
  rate_limit_per_min INTEGER NOT NULL DEFAULT 60,
  expires_at TIMESTAMPTZ,
  last_used_at TIMESTAMPTZ,
  created_by UUID REFERENCES users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  revoked_at TIMESTAMPTZ
);

ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Tenant admins manage API keys" ON api_keys
  FOR ALL USING (
    tenant_id = (auth.jwt() ->> 'tenant_id')::UUID
    AND (auth.jwt() ->> 'role') IN ('tenant_admin', 'platform_admin')
  );

-- Index for fast key lookup
CREATE INDEX idx_api_keys_prefix ON api_keys(key_prefix) WHERE revoked_at IS NULL;
```

```sql
-- supabase/migrations/006_extraction_queue.sql

-- Queue table for extraction requests (Postgres-based queue)
CREATE TABLE extraction_queue (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id UUID NOT NULL UNIQUE,
  tenant_id UUID NOT NULL REFERENCES tenants(id),
  document_id UUID NOT NULL REFERENCES documents(id),
  payload JSONB NOT NULL,  -- Full ExtractionRequest
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
  attempts INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3,
  priority INTEGER NOT NULL DEFAULT 5,  -- 1=high, 5=normal, 10=low
  created_at TIMESTAMPTZ DEFAULT NOW(),
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  worker_id TEXT
);

CREATE TABLE extraction_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id UUID NOT NULL UNIQUE,
  tenant_id UUID NOT NULL,
  document_id UUID NOT NULL,
  payload JSONB NOT NULL,  -- Full ExtractionResult
  processed_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for queue polling
CREATE INDEX idx_extraction_queue_pending 
  ON extraction_queue(priority, created_at) 
  WHERE status = 'pending';

-- Function to claim next job (atomic)
CREATE OR REPLACE FUNCTION claim_extraction_job(p_worker_id TEXT)
RETURNS extraction_queue AS $$
DECLARE
  v_job extraction_queue;
BEGIN
  SELECT * INTO v_job
  FROM extraction_queue
  WHERE status = 'pending'
    AND attempts < max_attempts
  ORDER BY priority, created_at
  LIMIT 1
  FOR UPDATE SKIP LOCKED;
  
  IF v_job.id IS NOT NULL THEN
    UPDATE extraction_queue
    SET status = 'processing',
        started_at = NOW(),
        worker_id = p_worker_id,
        attempts = attempts + 1
    WHERE id = v_job.id;
  END IF;
  
  RETURN v_job;
END;
$$ LANGUAGE plpgsql;

-- NOTIFY trigger for real-time queue
CREATE OR REPLACE FUNCTION notify_extraction_queue()
RETURNS TRIGGER AS $$
BEGIN
  PERFORM pg_notify('extraction_requests', NEW.request_id::TEXT);
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER extraction_queue_notify
  AFTER INSERT ON extraction_queue
  FOR EACH ROW EXECUTE FUNCTION notify_extraction_queue();
```

### Test: Schema Validation

```typescript
// platform-foundation/src/__tests__/schema.test.ts
import { createClient } from '@supabase/supabase-js';

describe('Database Schema', () => {
  const supabase = createClient(process.env.SUPABASE_URL!, process.env.SUPABASE_SERVICE_ROLE_KEY!);
  
  it('tenants table exists with correct columns', async () => {
    const { data, error } = await supabase
      .from('tenants')
      .select('id, name, slug, type, status')
      .limit(0);
    
    expect(error).toBeNull();
  });
  
  it('documents table has tenant_id foreign key', async () => {
    const { error } = await supabase
      .from('documents')
      .insert({
        tenant_id: '00000000-0000-0000-0000-000000000000', // Non-existent
        name: 'test.pdf',
        original_filename: 'test.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1000,
        storage_path: '/test'
      });
    
    // Should fail due to foreign key constraint
    expect(error).not.toBeNull();
  });
  
  it('RLS prevents cross-tenant access', async () => {
    // Create two tenants
    const { data: tenant1 } = await supabase
      .from('tenants')
      .insert({ name: 'Tenant 1', slug: 'tenant-1', type: 'pilot' })
      .select()
      .single();
    
    const { data: tenant2 } = await supabase
      .from('tenants')
      .insert({ name: 'Tenant 2', slug: 'tenant-2', type: 'pilot' })
      .select()
      .single();
    
    // Insert document as tenant1
    await supabase
      .from('documents')
      .insert({
        tenant_id: tenant1.id,
        name: 'secret.pdf',
        original_filename: 'secret.pdf',
        mime_type: 'application/pdf',
        size_bytes: 1000,
        storage_path: '/tenant1/secret.pdf'
      });
    
    // Try to access as tenant2 (simulate with RLS context)
    // This requires setting up proper auth context
    // For now, verify at application level
  });
  
  it('usage_events tracks token consumption', async () => {
    const { error } = await supabase
      .from('usage_events')
      .insert({
        tenant_id: testTenantId,
        event_type: 'extraction',
        tokens_consumed: 5000,
        document_id: testDocId
      });
    
    expect(error).toBeNull();
    
    // Verify aggregation function works
    const { data } = await supabase
      .rpc('get_tenant_daily_usage', { p_tenant_id: testTenantId });
    
    expect(data[0].extraction_tokens).toBe(5000);
  });
});
```

### Completion Criteria Phase 1:
- [ ] All migrations applied successfully
- [ ] RLS policies active on all tables
- [ ] Foreign key constraints working
- [ ] `get_tenant_daily_usage` function returns correct values
- [ ] Queue claim function works atomically
- [ ] Schema tests pass

---

## Phase 2: Authentication (Day 4-5)

**Goal:** Magic link login working end-to-end.

### Deliverable: Auth Module

```typescript
// platform-foundation/src/auth/magic-link.ts
import { createClient } from '@supabase/supabase-js';

const supabase = createClient(
  process.env.SUPABASE_URL!,
  process.env.SUPABASE_ANON_KEY!
);

export async function sendMagicLink(email: string): Promise<{ success: boolean; error?: string }> {
  // Validate email domain (whitelist for pilot)
  const allowedDomains = process.env.ALLOWED_EMAIL_DOMAINS?.split(',') || [];
  const domain = email.split('@')[1];
  
  if (allowedDomains.length > 0 && !allowedDomains.includes(domain)) {
    return { success: false, error: 'Email domain not authorized' };
  }
  
  // Check rate limit (5 per hour per email)
  const rateLimitKey = `magic_link:${email}`;
  const attempts = await checkRateLimit(rateLimitKey, 5, 3600);
  if (attempts > 5) {
    return { success: false, error: 'Too many login attempts. Try again later.' };
  }
  
  // Send magic link via Supabase
  const { error } = await supabase.auth.signInWithOtp({
    email,
    options: {
      emailRedirectTo: `${process.env.APP_URL}/auth/callback`
    }
  });
  
  if (error) {
    return { success: false, error: error.message };
  }
  
  return { success: true };
}

export async function verifyMagicLink(token: string): Promise<{
  success: boolean;
  session?: Session;
  user?: User;
  error?: string;
}> {
  const { data, error } = await supabase.auth.verifyOtp({
    token_hash: token,
    type: 'email'
  });
  
  if (error) {
    return { success: false, error: error.message };
  }
  
  // Fetch user's tenant_id and role
  const { data: userData } = await supabase
    .from('users')
    .select('id, tenant_id, role')
    .eq('email', data.user?.email)
    .single();
  
  if (!userData) {
    return { success: false, error: 'User not found in system' };
  }
  
  // Update last_login
  await supabase
    .from('users')
    .update({ last_login: new Date().toISOString() })
    .eq('id', userData.id);
  
  return {
    success: true,
    session: data.session,
    user: {
      ...data.user,
      tenant_id: userData.tenant_id,
      role: userData.role
    }
  };
}
```

```typescript
// platform-foundation/src/auth/api-keys.ts
import { createHash, randomBytes } from 'crypto';

export async function createApiKey(
  tenantId: string,
  createdBy: string,
  options: {
    name: string;
    scopes?: string[];
    expiresInDays?: number;
  }
): Promise<{ key: string; keyId: string }> {
  // Generate key: cf_live_xxxxxxxxxxxxxxxxxxxx
  const keyBytes = randomBytes(24);
  const key = `cf_live_${keyBytes.toString('base64url')}`;
  const keyPrefix = key.substring(0, 16);
  const keyHash = createHash('sha256').update(key).digest('hex');
  
  const expiresAt = options.expiresInDays
    ? new Date(Date.now() + options.expiresInDays * 24 * 60 * 60 * 1000)
    : null;
  
  const { data, error } = await supabase
    .from('api_keys')
    .insert({
      tenant_id: tenantId,
      name: options.name,
      key_hash: keyHash,
      key_prefix: keyPrefix,
      scopes: options.scopes || ['read'],
      expires_at: expiresAt,
      created_by: createdBy
    })
    .select('id')
    .single();
  
  if (error) throw error;
  
  // Return key ONCE - never stored in plaintext
  return { key, keyId: data.id };
}

export async function validateApiKey(key: string): Promise<{
  valid: boolean;
  tenantId?: string;
  scopes?: string[];
  error?: string;
}> {
  if (!key.startsWith('cf_live_')) {
    return { valid: false, error: 'Invalid key format' };
  }
  
  const keyHash = createHash('sha256').update(key).digest('hex');
  const keyPrefix = key.substring(0, 16);
  
  const { data, error } = await supabase
    .from('api_keys')
    .select('id, tenant_id, scopes, expires_at, revoked_at')
    .eq('key_hash', keyHash)
    .eq('key_prefix', keyPrefix)
    .single();
  
  if (error || !data) {
    return { valid: false, error: 'Invalid API key' };
  }
  
  if (data.revoked_at) {
    return { valid: false, error: 'API key has been revoked' };
  }
  
  if (data.expires_at && new Date(data.expires_at) < new Date()) {
    return { valid: false, error: 'API key has expired' };
  }
  
  // Update last_used_at
  await supabase
    .from('api_keys')
    .update({ last_used_at: new Date().toISOString() })
    .eq('id', data.id);
  
  return {
    valid: true,
    tenantId: data.tenant_id,
    scopes: data.scopes
  };
}
```

### Test: Authentication

```typescript
// platform-foundation/src/__tests__/auth.test.ts

describe('Magic Link Authentication', () => {
  it('sends magic link for valid email', async () => {
    const result = await sendMagicLink('test@allowed-domain.com');
    expect(result.success).toBe(true);
  });
  
  it('rejects unauthorized email domain', async () => {
    const result = await sendMagicLink('hacker@evil.com');
    expect(result.success).toBe(false);
    expect(result.error).toContain('not authorized');
  });
  
  it('rate limits excessive attempts', async () => {
    const email = 'ratelimit@test.com';
    
    // Send 6 attempts
    for (let i = 0; i < 6; i++) {
      await sendMagicLink(email);
    }
    
    const result = await sendMagicLink(email);
    expect(result.success).toBe(false);
    expect(result.error).toContain('Too many');
  });
});

describe('API Key Authentication', () => {
  let testKey: string;
  let testKeyId: string;
  
  beforeAll(async () => {
    const result = await createApiKey(testTenantId, testUserId, {
      name: 'Test Key',
      scopes: ['read', 'write']
    });
    testKey = result.key;
    testKeyId = result.keyId;
  });
  
  it('creates key with correct format', () => {
    expect(testKey).toMatch(/^cf_live_[A-Za-z0-9_-]{32}$/);
  });
  
  it('validates correct key', async () => {
    const result = await validateApiKey(testKey);
    expect(result.valid).toBe(true);
    expect(result.tenantId).toBe(testTenantId);
    expect(result.scopes).toContain('read');
  });
  
  it('rejects invalid key', async () => {
    const result = await validateApiKey('cf_live_invalid');
    expect(result.valid).toBe(false);
  });
  
  it('rejects revoked key', async () => {
    // Revoke the key
    await supabase
      .from('api_keys')
      .update({ revoked_at: new Date().toISOString() })
      .eq('id', testKeyId);
    
    const result = await validateApiKey(testKey);
    expect(result.valid).toBe(false);
    expect(result.error).toContain('revoked');
  });
});
```

### Completion Criteria Phase 2:
- [ ] Magic link sends email successfully
- [ ] Magic link verification creates session
- [ ] Session includes tenant_id and role
- [ ] API key creation returns key only once
- [ ] API key validation works correctly
- [ ] Rate limiting prevents abuse
- [ ] Domain whitelist enforced
- [ ] Auth tests pass

---

## Phase 3: Document Management (Day 6-8)

**Goal:** Upload documents, track status, trigger extraction.

### Deliverable: Document Module

```typescript
// platform-foundation/src/documents/upload.ts

export async function uploadDocument(
  tenantId: string,
  userId: string,
  file: {
    buffer: Buffer;
    originalName: string;
    mimeType: string;
  },
  options?: {
    folderId?: string;
    tags?: string[];
  }
): Promise<{ document: Document; error?: string }> {
  
  // 1. Check document quota
  const quotaCheck = await checkDocumentQuota(tenantId);
  if (!quotaCheck.allowed) {
    return { document: null, error: 'Document limit exceeded' };
  }
  
  // 2. Validate file
  const validation = await validateFile(file);
  if (!validation.valid) {
    return { document: null, error: validation.error };
  }
  
  // 3. Generate storage path
  const docId = crypto.randomUUID();
  const storagePath = `/tenants/${tenantId}/documents/${docId}/v1/${sanitizeFilename(file.originalName)}`;
  
  // 4. Upload to storage
  const { error: uploadError } = await supabase.storage
    .from('documents')
    .upload(storagePath, file.buffer, {
      contentType: file.mimeType
    });
  
  if (uploadError) {
    return { document: null, error: 'Failed to upload file' };
  }
  
  // 5. Create document record
  const { data: doc, error: dbError } = await supabase
    .from('documents')
    .insert({
      id: docId,
      tenant_id: tenantId,
      folder_id: options?.folderId,
      name: file.originalName,
      original_filename: file.originalName,
      mime_type: file.mimeType,
      size_bytes: file.buffer.length,
      storage_path: storagePath,
      status: 'uploaded',
      current_version: 1,
      created_by: userId
    })
    .select()
    .single();
  
  if (dbError) {
    // Rollback: delete uploaded file
    await supabase.storage.from('documents').remove([storagePath]);
    return { document: null, error: 'Failed to create document record' };
  }
  
  // 6. Create version record
  await supabase
    .from('document_versions')
    .insert({
      document_id: docId,
      version_number: 1,
      storage_path: storagePath,
      size_bytes: file.buffer.length,
      created_by: userId
    });
  
  // 7. Log usage event
  await logUsageEvent(tenantId, 'upload', {
    document_id: docId,
    size_bytes: file.buffer.length
  });
  
  // 8. Queue for extraction
  await queueExtraction(doc);
  
  return { document: doc };
}

async function validateFile(file: { buffer: Buffer; mimeType: string }): Promise<{
  valid: boolean;
  error?: string;
}> {
  // Magic byte validation
  const magicBytes = file.buffer.slice(0, 8);
  const detectedType = detectMimeType(magicBytes);
  
  if (detectedType !== file.mimeType) {
    return { valid: false, error: 'File type mismatch' };
  }
  
  // Size limit
  if (file.buffer.length > 100 * 1024 * 1024) {
    return { valid: false, error: 'File exceeds 100MB limit' };
  }
  
  // Allowed types
  const allowedTypes = [
    'application/pdf',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
    'text/csv',
    'application/json'
  ];
  
  if (!allowedTypes.includes(file.mimeType)) {
    return { valid: false, error: 'File type not supported' };
  }
  
  return { valid: true };
}
```

```typescript
// platform-foundation/src/documents/extraction-queue.ts

export async function queueExtraction(document: Document): Promise<void> {
  const request: ExtractionRequest = {
    request_id: crypto.randomUUID(),
    document_id: document.id,
    tenant_id: document.tenant_id,
    file_path: document.storage_path,
    file_name: document.original_filename,
    mime_type: document.mime_type,
    file_size_bytes: document.size_bytes,
    submitted_at: new Date().toISOString(),
    priority: 'normal'
  };
  
  // Insert into queue
  await supabase
    .from('extraction_queue')
    .insert({
      request_id: request.request_id,
      tenant_id: request.tenant_id,
      document_id: request.document_id,
      payload: request,
      priority: 5
    });
  
  // Update document status
  await supabase
    .from('documents')
    .update({ status: 'queued' })
    .eq('id', document.id);
  
  // Update version with request_id
  await supabase
    .from('document_versions')
    .update({ extraction_request_id: request.request_id })
    .eq('document_id', document.id)
    .eq('version_number', document.current_version);
}

export async function processExtractionResult(result: ExtractionResult): Promise<void> {
  // Update document status
  const newStatus = result.status === 'success' ? 'extracted' 
    : result.status === 'partial' ? 'partial'
    : 'failed';
  
  await supabase
    .from('documents')
    .update({ 
      status: newStatus,
      updated_at: new Date().toISOString()
    })
    .eq('id', result.document_id);
  
  // Log usage event with token consumption
  await logUsageEvent(result.tenant_id, 'extraction', {
    document_id: result.document_id,
    request_id: result.request_id,
    tokens_consumed: result.tokens_consumed.total_tokens,
    entities_extracted: result.entities_extracted,
    duration_ms: result.duration_ms
  });
  
  // Update extraction queue status
  await supabase
    .from('extraction_queue')
    .update({
      status: result.status === 'success' ? 'completed' : 'failed',
      completed_at: new Date().toISOString()
    })
    .eq('request_id', result.request_id);
}
```

### Test: Document Management

```typescript
// platform-foundation/src/__tests__/documents.test.ts

describe('Document Upload', () => {
  it('uploads document and creates records', async () => {
    const file = {
      buffer: fs.readFileSync('test-fixtures/sample.pdf'),
      originalName: 'sample.pdf',
      mimeType: 'application/pdf'
    };
    
    const result = await uploadDocument(testTenantId, testUserId, file);
    
    expect(result.document).toBeDefined();
    expect(result.document.status).toBe('uploaded');
    expect(result.document.tenant_id).toBe(testTenantId);
  });
  
  it('queues document for extraction after upload', async () => {
    const file = { /* ... */ };
    const result = await uploadDocument(testTenantId, testUserId, file);
    
    // Check document is now queued
    const { data: doc } = await supabase
      .from('documents')
      .select('status')
      .eq('id', result.document.id)
      .single();
    
    expect(doc.status).toBe('queued');
    
    // Check queue has the request
    const { data: queueItem } = await supabase
      .from('extraction_queue')
      .select('*')
      .eq('document_id', result.document.id)
      .single();
    
    expect(queueItem).toBeDefined();
    expect(queueItem.payload.tenant_id).toBe(testTenantId);
  });
  
  it('rejects file type mismatch', async () => {
    // PDF content but wrong mime type
    const file = {
      buffer: fs.readFileSync('test-fixtures/sample.pdf'),
      originalName: 'fake.txt',
      mimeType: 'text/plain'
    };
    
    const result = await uploadDocument(testTenantId, testUserId, file);
    
    expect(result.error).toContain('type mismatch');
  });
  
  it('enforces document quota', async () => {
    // Set quota to 1
    await supabase
      .from('tenant_quotas')
      .update({ document_limit: 1 })
      .eq('tenant_id', testTenantId);
    
    // Upload first document (should work)
    const result1 = await uploadDocument(testTenantId, testUserId, sampleFile);
    expect(result1.document).toBeDefined();
    
    // Upload second document (should fail)
    const result2 = await uploadDocument(testTenantId, testUserId, sampleFile);
    expect(result2.error).toContain('limit exceeded');
  });
});

describe('Extraction Result Processing', () => {
  it('updates document status on success', async () => {
    const result: ExtractionResult = {
      request_id: testRequestId,
      document_id: testDocId,
      tenant_id: testTenantId,
      status: 'success',
      entities_extracted: 15,
      relationships_extracted: 8,
      tokens_consumed: { input_tokens: 3000, output_tokens: 2000, total_tokens: 5000 },
      started_at: '2025-12-07T10:00:00Z',
      completed_at: '2025-12-07T10:00:30Z',
      duration_ms: 30000,
      extraction_version: '1.0.0',
      model_used: 'claude-3-5-sonnet'
    };
    
    await processExtractionResult(result);
    
    const { data: doc } = await supabase
      .from('documents')
      .select('status')
      .eq('id', testDocId)
      .single();
    
    expect(doc.status).toBe('extracted');
  });
  
  it('logs token consumption', async () => {
    await processExtractionResult(testResult);
    
    const { data: events } = await supabase
      .from('usage_events')
      .select('*')
      .eq('document_id', testDocId)
      .eq('event_type', 'extraction');
    
    expect(events.length).toBe(1);
    expect(events[0].tokens_consumed).toBe(5000);
  });
});
```

### Completion Criteria Phase 3:
- [ ] Document upload creates storage file and DB records
- [ ] File validation blocks invalid uploads
- [ ] Document quota enforced
- [ ] Upload triggers extraction queue
- [ ] Extraction results update document status
- [ ] Token consumption logged
- [ ] Document tests pass

---

## Phase 4: MCP Server (Day 9-11)

**Goal:** Query surface operational.

### Deliverable: MCP Server

```typescript
// platform-foundation/src/mcp/server.ts
import { MCPServer, Tool, Resource } from '@modelcontextprotocol/server';

export function createMCPServer() {
  const server = new MCPServer({
    name: 'context-foundry',
    version: '1.0.0'
  });
  
  // Resources
  server.addResource({
    uri: 'context://entities/{tenant}',
    name: 'Tenant Entities',
    description: 'All extracted entities for the authenticated tenant',
    handler: handleEntitiesResource
  });
  
  server.addResource({
    uri: 'context://ontology/types',
    name: 'Ontology Types',
    description: 'Available entity types and schemas',
    handler: handleOntologyResource
  });
  
  server.addResource({
    uri: 'context://usage',
    name: 'Usage Stats',
    description: 'Current quota usage',
    handler: handleUsageResource
  });
  
  // Tools
  server.addTool({
    name: 'query_context',
    description: 'Semantic search across extracted entities',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Search query' },
        max_results: { type: 'number', default: 10 },
        entity_type: { type: 'string', description: 'Filter by entity type' }
      },
      required: ['query']
    },
    handler: handleQueryContext
  });
  
  server.addTool({
    name: 'verify_statement',
    description: 'Verify a statement against the knowledge base',
    inputSchema: {
      type: 'object',
      properties: {
        statement: { type: 'string', description: 'Statement to verify' }
      },
      required: ['statement']
    },
    handler: handleVerifyStatement
  });
  
  server.addTool({
    name: 'ingest_document',
    description: 'Upload and extract a document',
    inputSchema: {
      type: 'object',
      properties: {
        content: { type: 'string', description: 'Base64 encoded document' },
        filename: { type: 'string' },
        mime_type: { type: 'string' }
      },
      required: ['content', 'filename', 'mime_type']
    },
    handler: handleIngestDocument
  });
  
  return server;
}
```

```typescript
// platform-foundation/src/mcp/handlers.ts

async function handleQueryContext(
  params: { query: string; max_results?: number; entity_type?: string },
  context: MCPContext
): Promise<MCPResult> {
  const { tenantId, apiKeyId } = context.auth;
  
  // Check quota
  const quotaCheck = await checkQueryQuota(tenantId);
  if (!quotaCheck.allowed) {
    return {
      error: {
        code: 'QUERY_QUOTA_EXCEEDED',
        message: `Daily query quota exceeded. Resets at midnight UTC.`
      }
    };
  }
  
  // Call Brain query endpoint
  const queryRequest: QueryRequest = {
    tenant_id: tenantId,
    query_type: 'semantic_search',
    query_text: params.query,
    max_results: params.max_results || 10,
    entity_type: params.entity_type
  };
  
  const response = await callBrainQuery(queryRequest);
  
  // Log usage
  await logUsageEvent(tenantId, 'query', {
    api_key_id: apiKeyId,
    tokens_consumed: response.tokens_consumed.total_tokens,
    query_type: 'semantic_search'
  });
  
  return {
    results: response.results,
    tokens_consumed: response.tokens_consumed.total_tokens
  };
}

async function handleVerifyStatement(
  params: { statement: string },
  context: MCPContext
): Promise<MCPResult> {
  const { tenantId, apiKeyId } = context.auth;
  
  // Check quota
  const quotaCheck = await checkQueryQuota(tenantId);
  if (!quotaCheck.allowed) {
    return {
      error: { code: 'QUERY_QUOTA_EXCEEDED', message: 'Quota exceeded' }
    };
  }
  
  const queryRequest: QueryRequest = {
    tenant_id: tenantId,
    query_type: 'verify_statement',
    statement: params.statement
  };
  
  const response = await callBrainQuery(queryRequest);
  
  await logUsageEvent(tenantId, 'query', {
    api_key_id: apiKeyId,
    tokens_consumed: response.tokens_consumed.total_tokens,
    query_type: 'verify_statement'
  });
  
  return {
    verified: response.results[0]?.verified,
    confidence: response.results[0]?.confidence,
    explanation: response.results[0]?.explanation,
    tokens_consumed: response.tokens_consumed.total_tokens
  };
}

async function callBrainQuery(request: QueryRequest): Promise<QueryResponse> {
  const response = await fetch(process.env.BRAIN_QUERY_URL!, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${process.env.BRAIN_INTERNAL_KEY}`
    },
    body: JSON.stringify(request)
  });
  
  if (!response.ok) {
    throw new Error(`Brain query failed: ${response.status}`);
  }
  
  return response.json();
}
```

### Test: MCP Server

```typescript
// platform-foundation/src/__tests__/mcp.test.ts

describe('MCP Server', () => {
  let server: MCPServer;
  let testApiKey: string;
  
  beforeAll(async () => {
    server = createMCPServer();
    const { key } = await createApiKey(testTenantId, testUserId, {
      name: 'MCP Test Key',
      scopes: ['read', 'write']
    });
    testApiKey = key;
  });
  
  describe('query_context tool', () => {
    it('returns search results', async () => {
      const result = await server.callTool('query_context', {
        query: 'financial instruments'
      }, { apiKey: testApiKey });
      
      expect(result.results).toBeDefined();
      expect(Array.isArray(result.results)).toBe(true);
    });
    
    it('respects max_results parameter', async () => {
      const result = await server.callTool('query_context', {
        query: 'contracts',
        max_results: 3
      }, { apiKey: testApiKey });
      
      expect(result.results.length).toBeLessThanOrEqual(3);
    });
    
    it('logs token consumption', async () => {
      const before = await getUsageSnapshot(testTenantId);
      
      await server.callTool('query_context', {
        query: 'test'
      }, { apiKey: testApiKey });
      
      const after = await getUsageSnapshot(testTenantId);
      expect(after.query_tokens_used).toBeGreaterThan(before.query_tokens_used);
    });
    
    it('enforces quota limits', async () => {
      // Set quota to 0
      await setTenantQuota(testTenantId, { query_tokens_daily: 0 });
      
      const result = await server.callTool('query_context', {
        query: 'test'
      }, { apiKey: testApiKey });
      
      expect(result.error.code).toBe('QUERY_QUOTA_EXCEEDED');
    });
  });
  
  describe('verify_statement tool', () => {
    it('returns verification result', async () => {
      const result = await server.callTool('verify_statement', {
        statement: 'The contract value is $1 million'
      }, { apiKey: testApiKey });
      
      expect(result.verified).toBeDefined();
      expect(result.confidence).toBeDefined();
      expect(typeof result.confidence).toBe('number');
    });
  });
  
  describe('Authentication', () => {
    it('rejects invalid API key', async () => {
      const result = await server.callTool('query_context', {
        query: 'test'
      }, { apiKey: 'invalid_key' });
      
      expect(result.error.code).toBe('UNAUTHORIZED');
    });
    
    it('respects API key scopes', async () => {
      // Create read-only key
      const { key: readOnlyKey } = await createApiKey(testTenantId, testUserId, {
        name: 'Read Only',
        scopes: ['read']
      });
      
      // Query should work
      const queryResult = await server.callTool('query_context', {
        query: 'test'
      }, { apiKey: readOnlyKey });
      expect(queryResult.error).toBeUndefined();
      
      // Ingest should fail
      const ingestResult = await server.callTool('ingest_document', {
        content: 'base64...',
        filename: 'test.txt',
        mime_type: 'text/plain'
      }, { apiKey: readOnlyKey });
      expect(ingestResult.error.code).toBe('FORBIDDEN');
    });
  });
});
```

### Completion Criteria Phase 4:
- [ ] MCP server starts and accepts connections
- [ ] query_context returns results from Brain
- [ ] verify_statement returns structured verification
- [ ] API key authentication working
- [ ] Scopes enforced
- [ ] Quota enforcement working
- [ ] Token consumption logged for all queries
- [ ] MCP tests pass

---

## Phase 5: Integration Testing (Day 12-14)

**Goal:** Verify Platform and Brain work together correctly.

### Full Flow Integration Tests

```typescript
// test/integration/full-flow.test.ts

describe('Full Integration Flow', () => {
  let tenant: Tenant;
  let user: User;
  let apiKey: string;
  
  beforeAll(async () => {
    // Create fresh tenant
    tenant = await createTenant({
      name: 'Integration Test Opco',
      type: 'pilot'
    });
    
    // Create user
    user = await createUser({
      email: 'integration@test.com',
      tenant_id: tenant.id,
      role: 'user'
    });
    
    // Create API key
    const { key } = await createApiKey(tenant.id, user.id, {
      name: 'Integration Test Key',
      scopes: ['read', 'write']
    });
    apiKey = key;
    
    // Set quotas
    await setTenantQuota(tenant.id, {
      extraction_tokens_daily: 100000,
      query_tokens_daily: 50000,
      document_limit: 100
    });
  });
  
  afterAll(async () => {
    // Cleanup
    await deleteTenant(tenant.id);
  });
  
  it('uploads document, extracts, and queries via MCP', async () => {
    // 1. Upload document
    const uploadResult = await uploadDocument(tenant.id, user.id, {
      buffer: fs.readFileSync('test-fixtures/contract.pdf'),
      originalName: 'contract.pdf',
      mimeType: 'application/pdf'
    });
    
    expect(uploadResult.document.status).toBe('queued');
    console.log('Document uploaded:', uploadResult.document.id);
    
    // 2. Wait for extraction (Brain must be running)
    const extracted = await waitForStatus(
      uploadResult.document.id,
      'extracted',
      { timeout: 120000, pollInterval: 2000 }
    );
    
    expect(extracted).toBe(true);
    console.log('Document extracted');
    
    // 3. Verify entities were created (via Brain query)
    const entitiesResult = await mcpServer.callTool('query_context', {
      query: 'all entities',
      max_results: 50
    }, { apiKey });
    
    expect(entitiesResult.results.length).toBeGreaterThan(0);
    console.log(`Found ${entitiesResult.results.length} entities`);
    
    // 4. Verify a statement
    const verifyResult = await mcpServer.callTool('verify_statement', {
      statement: 'This document is a contract'
    }, { apiKey });
    
    expect(verifyResult.verified).toBeDefined();
    console.log('Verification:', verifyResult);
    
    // 5. Check usage was tracked
    const usage = await getUsageSnapshot(tenant.id);
    expect(usage.extraction_tokens_used).toBeGreaterThan(0);
    expect(usage.query_tokens_used).toBeGreaterThan(0);
    expect(usage.documents_count).toBe(1);
    console.log('Usage tracked:', usage);
  });
  
  it('enforces tenant isolation', async () => {
    // Create second tenant
    const tenant2 = await createTenant({
      name: 'Other Opco',
      type: 'pilot'
    });
    
    const { key: otherKey } = await createApiKey(tenant2.id, user.id, {
      name: 'Other Key',
      scopes: ['read']
    });
    
    // Upload doc to tenant1
    await uploadDocument(tenant.id, user.id, testFile);
    await waitForExtraction();
    
    // Query as tenant1 - should find it
    const result1 = await mcpServer.callTool('query_context', {
      query: 'test document'
    }, { apiKey: apiKey }); // tenant1's key
    
    // Query as tenant2 - should NOT find it
    const result2 = await mcpServer.callTool('query_context', {
      query: 'test document'
    }, { apiKey: otherKey }); // tenant2's key
    
    // Verify isolation
    const tenant1Ids = result1.results.map(e => e.entity_id);
    const tenant2Ids = result2.results.map(e => e.entity_id);
    
    const overlap = tenant1Ids.filter(id => tenant2Ids.includes(id));
    expect(overlap.length).toBe(0);
    
    // Cleanup
    await deleteTenant(tenant2.id);
  });
});
```

### Completion Criteria Phase 5:
- [ ] Document uploaded via Platform appears in Brain
- [ ] MCP query returns entities from uploaded document
- [ ] Token consumption tracked end-to-end
- [ ] Tenant isolation verified
- [ ] No data leakage between tenants
- [ ] All integration tests pass

---

## Summary: What Gets Delivered

| Phase | Days | Deliverable | Tests |
|-------|------|-------------|-------|
| 0 | 1 | Interface types package | Type validation |
| 1 | 2 | Database schema + RLS | Schema tests |
| 2 | 2 | Auth (magic link + API keys) | Auth tests |
| 3 | 3 | Document management | Document tests |
| 4 | 3 | MCP server | MCP tests |
| 5 | 3 | Integration validation | Full flow tests |

**Total: 14 days (2 weeks)**

### Definition of Done

1. All tests pass
2. No imports crossing Platform ↔ Brain boundary (except interface types)
3. Tenant isolation verified with multi-tenant test
4. Token consumption tracked on every extraction and query
5. Quota enforcement blocks operations when exceeded
6. MCP server responds to external Claude/GPT agents

---

**Hand this document to Replit. Build in order. Test at each phase before proceeding.**
