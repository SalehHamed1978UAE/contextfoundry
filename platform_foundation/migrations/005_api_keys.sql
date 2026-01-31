-- ============================================================
-- Migration 005: API Keys
-- Platform Foundation - API Key Management
-- ============================================================

CREATE TABLE platform.api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES platform.tenants(id),
  name TEXT NOT NULL,
  key_hash TEXT NOT NULL,
  key_prefix TEXT NOT NULL,
  scopes TEXT[] NOT NULL DEFAULT ARRAY['read'],
  rate_limit_per_min INTEGER NOT NULL DEFAULT 60,
  expires_at TIMESTAMPTZ,
  last_used_at TIMESTAMPTZ,
  created_by UUID REFERENCES platform.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  revoked_at TIMESTAMPTZ
);

CREATE INDEX idx_api_keys_tenant ON platform.api_keys(tenant_id);
CREATE INDEX idx_api_keys_prefix ON platform.api_keys(key_prefix) WHERE revoked_at IS NULL;

COMMENT ON TABLE platform.api_keys IS 'API keys for programmatic access - key_hash stored, never plaintext';
COMMENT ON COLUMN platform.api_keys.key_prefix IS 'First 8 chars for identification: cf_live_... or cf_test_...';
COMMENT ON COLUMN platform.api_keys.key_hash IS 'bcrypt hash of full key - never store plaintext';
