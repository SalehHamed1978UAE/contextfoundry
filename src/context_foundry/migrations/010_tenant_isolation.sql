-- ============================================================
-- Migration 010: Tenant Isolation for Brain Tables
-- Adds tenant_id to entities and relationships for multi-tenancy
-- ============================================================

-- Add tenant_id column to entities
ALTER TABLE entities ADD COLUMN IF NOT EXISTS tenant_id UUID;
CREATE INDEX IF NOT EXISTS idx_entities_tenant_id ON entities(tenant_id);

-- Add tenant_id column to relationships
ALTER TABLE relationships ADD COLUMN IF NOT EXISTS tenant_id UUID;
CREATE INDEX IF NOT EXISTS idx_relationships_tenant_id ON relationships(tenant_id);

-- Add tenant_id to other Brain tables
ALTER TABLE documents ADD COLUMN IF NOT EXISTS tenant_id UUID;
CREATE INDEX IF NOT EXISTS idx_documents_tenant_id ON documents(tenant_id);

ALTER TABLE gardener_runs ADD COLUMN IF NOT EXISTS tenant_id UUID;
CREATE INDEX IF NOT EXISTS idx_gardener_runs_tenant_id ON gardener_runs(tenant_id);

ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS tenant_id UUID;
CREATE INDEX IF NOT EXISTS idx_query_logs_tenant_id ON query_logs(tenant_id);

-- ============================================================
-- RLS Helper for Brain tables (uses same session variable)
-- ============================================================

CREATE OR REPLACE FUNCTION brain_current_tenant_id()
RETURNS UUID AS $$
BEGIN
  RETURN NULLIF(current_setting('app.current_tenant_id', true), '')::UUID;
EXCEPTION
  WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION brain_current_tenant_id IS 'Get tenant_id from session variable for Brain RLS';

-- ============================================================
-- Enable RLS on Brain tables (optional, for strict isolation)
-- Note: Can be enabled later when all records have tenant_id
-- ============================================================

-- ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE relationships ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Tenant isolation for entities" ON entities
--   FOR ALL USING (tenant_id = brain_current_tenant_id() OR tenant_id IS NULL);
-- CREATE POLICY "Tenant isolation for relationships" ON relationships
--   FOR ALL USING (tenant_id = brain_current_tenant_id() OR tenant_id IS NULL);
