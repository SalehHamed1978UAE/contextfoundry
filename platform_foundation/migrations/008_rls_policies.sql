-- ============================================================
-- Migration 008: RLS Policies
-- Platform Foundation - Row Level Security for all tables
-- ============================================================

-- Enable RLS on all Platform Foundation tables
ALTER TABLE platform.tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.folders ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.tenant_quotas ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.usage_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.usage_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.api_keys ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.extraction_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE platform.extraction_results ENABLE ROW LEVEL SECURITY;

-- ============================================================
-- Tenants Policies
-- ============================================================

CREATE POLICY "Platform admins see all tenants" ON platform.tenants
  FOR SELECT USING (
    platform.current_user_role() = 'platform_admin'
  );

CREATE POLICY "Users see own tenant" ON platform.tenants
  FOR SELECT USING (
    id = platform.current_tenant_id()
  );

-- ============================================================
-- Users Policies
-- ============================================================

CREATE POLICY "Users see themselves" ON platform.users
  FOR SELECT USING (
    tenant_id = platform.current_tenant_id()
  );

CREATE POLICY "Tenant admins manage users" ON platform.users
  FOR ALL USING (
    tenant_id = platform.current_tenant_id()
    AND platform.current_user_role() IN ('tenant_admin', 'platform_admin')
  );

-- ============================================================
-- Folders Policies
-- ============================================================

CREATE POLICY "Tenant isolation for folders" ON platform.folders
  FOR ALL USING (
    tenant_id = platform.current_tenant_id()
  );

-- ============================================================
-- Documents Policies
-- ============================================================

CREATE POLICY "Tenant isolation for documents" ON platform.documents
  FOR ALL USING (
    tenant_id = platform.current_tenant_id()
  );

-- ============================================================
-- Document Versions Policies
-- ============================================================

CREATE POLICY "Tenant isolation for versions" ON platform.document_versions
  FOR ALL USING (
    document_id IN (
      SELECT id FROM platform.documents 
      WHERE tenant_id = platform.current_tenant_id()
    )
  );

-- ============================================================
-- Tenant Quotas Policies
-- ============================================================

CREATE POLICY "Tenant sees own quotas" ON platform.tenant_quotas
  FOR SELECT USING (
    tenant_id = platform.current_tenant_id()
  );

CREATE POLICY "Platform admin manages quotas" ON platform.tenant_quotas
  FOR ALL USING (
    platform.current_user_role() = 'platform_admin'
  );

-- ============================================================
-- Usage Events Policies
-- ============================================================

CREATE POLICY "Tenant sees own usage" ON platform.usage_events
  FOR SELECT USING (
    tenant_id = platform.current_tenant_id()
  );

-- ============================================================
-- Usage Snapshots Policies
-- ============================================================

CREATE POLICY "Tenant sees own snapshots" ON platform.usage_snapshots
  FOR SELECT USING (
    tenant_id = platform.current_tenant_id()
  );

-- ============================================================
-- API Keys Policies
-- ============================================================

CREATE POLICY "Tenant admins manage API keys" ON platform.api_keys
  FOR ALL USING (
    tenant_id = platform.current_tenant_id()
    AND platform.current_user_role() IN ('tenant_admin', 'platform_admin')
  );

-- ============================================================
-- Extraction Requests Policies
-- ============================================================

CREATE POLICY "Tenant sees own extraction requests" ON platform.extraction_requests
  FOR SELECT USING (
    tenant_id = platform.current_tenant_id()
  );

CREATE POLICY "Tenant creates extraction requests" ON platform.extraction_requests
  FOR INSERT WITH CHECK (
    tenant_id = platform.current_tenant_id()
  );

-- ============================================================
-- Extraction Results Policies
-- ============================================================

CREATE POLICY "Tenant sees own extraction results" ON platform.extraction_results
  FOR SELECT USING (
    tenant_id = platform.current_tenant_id()
  );

COMMENT ON POLICY "Tenant isolation for documents" ON platform.documents IS 
  'Enforces multi-tenant data isolation at database level';
