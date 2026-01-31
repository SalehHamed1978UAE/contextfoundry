-- ============================================================
-- Migration 001: Tenants
-- Platform Foundation - Multi-Tenancy Base Table
-- ============================================================

CREATE SCHEMA IF NOT EXISTS platform;

CREATE TABLE platform.tenants (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('opco_production', 'opco_pilot', 'personal_sandbox', 'demo', 'qdata_internal')),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
  settings JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tenants_slug ON platform.tenants(slug);
CREATE INDEX idx_tenants_status ON platform.tenants(status);

COMMENT ON TABLE platform.tenants IS 'Multi-tenant isolation - Platform Foundation owns tenant lifecycle';
