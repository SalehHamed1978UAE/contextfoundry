-- ============================================================
-- Migration 002: Users
-- Platform Foundation - User Management
-- ============================================================

CREATE TABLE platform.users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  role TEXT NOT NULL CHECK (role IN ('platform_admin', 'tenant_admin', 'knowledge_steward', 'user', 'viewer')),
  tenant_id UUID REFERENCES platform.tenants(id),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'invited', 'suspended')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  last_login TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON platform.users(email);
CREATE INDEX idx_users_tenant ON platform.users(tenant_id);
CREATE INDEX idx_users_status ON platform.users(status);

COMMENT ON TABLE platform.users IS 'User accounts - Platform Foundation owns authentication';
