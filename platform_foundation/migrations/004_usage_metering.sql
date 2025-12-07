-- ============================================================
-- Migration 004: Usage Metering
-- Platform Foundation - Token & Quota Tracking
-- ============================================================

CREATE TABLE platform.tenant_quotas (
  tenant_id UUID PRIMARY KEY REFERENCES platform.tenants(id),
  extraction_tokens_daily BIGINT NOT NULL DEFAULT 100000,
  extraction_tokens_monthly BIGINT NOT NULL DEFAULT 2000000,
  query_tokens_daily BIGINT NOT NULL DEFAULT 50000,
  query_tokens_monthly BIGINT NOT NULL DEFAULT 1000000,
  document_limit INTEGER NOT NULL DEFAULT 500,
  storage_gb_limit INTEGER NOT NULL DEFAULT 10,
  api_rate_limit_per_min INTEGER NOT NULL DEFAULT 60,
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE platform.usage_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES platform.tenants(id),
  user_id UUID REFERENCES platform.users(id),
  api_key_id UUID,
  event_type TEXT NOT NULL CHECK (event_type IN ('extraction', 'query', 'upload')),
  tokens_consumed INTEGER NOT NULL DEFAULT 0,
  document_id UUID,
  request_id UUID,
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE platform.usage_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES platform.tenants(id),
  snapshot_date DATE NOT NULL,
  extraction_tokens_used BIGINT NOT NULL DEFAULT 0,
  query_tokens_used BIGINT NOT NULL DEFAULT 0,
  documents_count INTEGER NOT NULL DEFAULT 0,
  storage_bytes_used BIGINT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(tenant_id, snapshot_date)
);

CREATE INDEX idx_usage_events_tenant ON platform.usage_events(tenant_id);
CREATE INDEX idx_usage_events_created ON platform.usage_events(created_at);
CREATE INDEX idx_usage_events_type ON platform.usage_events(event_type);
CREATE INDEX idx_usage_snapshots_tenant ON platform.usage_snapshots(tenant_id);
CREATE INDEX idx_usage_snapshots_date ON platform.usage_snapshots(snapshot_date);

-- Function to get current daily usage for a tenant
CREATE OR REPLACE FUNCTION platform.get_tenant_daily_usage(p_tenant_id UUID)
RETURNS TABLE (
  extraction_tokens BIGINT,
  query_tokens BIGINT
) AS $$
BEGIN
  RETURN QUERY
  SELECT 
    COALESCE(SUM(CASE WHEN event_type = 'extraction' THEN tokens_consumed ELSE 0 END), 0)::BIGINT as extraction_tokens,
    COALESCE(SUM(CASE WHEN event_type = 'query' THEN tokens_consumed ELSE 0 END), 0)::BIGINT as query_tokens
  FROM platform.usage_events
  WHERE tenant_id = p_tenant_id
    AND created_at >= CURRENT_DATE;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE platform.tenant_quotas IS 'Per-tenant usage limits - Platform enforces, Brain reports consumption';
COMMENT ON TABLE platform.usage_events IS 'Individual usage events for billing - tokens, uploads, queries';
COMMENT ON TABLE platform.usage_snapshots IS 'Daily aggregated snapshots for reporting and billing';
