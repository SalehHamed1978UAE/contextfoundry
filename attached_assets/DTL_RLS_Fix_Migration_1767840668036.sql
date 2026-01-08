-- =============================================================================
-- DTL RLS FIX MIGRATION
-- 
-- Purpose: Fix RLS recursion by adding tenant_id to child tables
-- Apply: Run this directly against the CF database
-- After: Re-enable use_rls_role=True in all API calls
-- =============================================================================

BEGIN;

-- =============================================================================
-- STEP 1: Add tenant_id column to all child tables
-- =============================================================================

ALTER TABLE decision_evidence ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE decision_exceptions ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE decision_results ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE decision_assessments ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE decision_executions ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE decision_entity_links ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE decision_precedent_links ADD COLUMN IF NOT EXISTS tenant_id UUID;
ALTER TABLE decision_confidence_scores ADD COLUMN IF NOT EXISTS tenant_id UUID;

-- =============================================================================
-- STEP 2: Backfill tenant_id from parent decision_traces
-- =============================================================================

UPDATE decision_evidence de 
SET tenant_id = dt.tenant_id 
FROM decision_traces dt 
WHERE de.decision_id = dt.id AND de.tenant_id IS NULL;

UPDATE decision_exceptions de 
SET tenant_id = dt.tenant_id 
FROM decision_traces dt 
WHERE de.decision_id = dt.id AND de.tenant_id IS NULL;

UPDATE decision_results dr 
SET tenant_id = dt.tenant_id 
FROM decision_traces dt 
WHERE dr.decision_id = dt.id AND dr.tenant_id IS NULL;

UPDATE decision_assessments da 
SET tenant_id = dt.tenant_id 
FROM decision_traces dt 
WHERE da.decision_id = dt.id AND da.tenant_id IS NULL;

UPDATE decision_executions de 
SET tenant_id = dt.tenant_id 
FROM decision_traces dt 
WHERE de.decision_id = dt.id AND de.tenant_id IS NULL;

UPDATE decision_entity_links del 
SET tenant_id = dt.tenant_id 
FROM decision_traces dt 
WHERE del.decision_id = dt.id AND del.tenant_id IS NULL;

UPDATE decision_precedent_links dpl 
SET tenant_id = dt.tenant_id 
FROM decision_traces dt 
WHERE dpl.decision_id = dt.id AND dpl.tenant_id IS NULL;

UPDATE decision_confidence_scores dcs 
SET tenant_id = dt.tenant_id 
FROM decision_traces dt 
WHERE dcs.decision_id = dt.id AND dcs.tenant_id IS NULL;

-- =============================================================================
-- STEP 3: Make tenant_id NOT NULL (after backfill)
-- =============================================================================

ALTER TABLE decision_evidence ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE decision_exceptions ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE decision_results ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE decision_assessments ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE decision_executions ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE decision_entity_links ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE decision_precedent_links ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE decision_confidence_scores ALTER COLUMN tenant_id SET NOT NULL;

-- =============================================================================
-- STEP 4: Auto-populate tenant_id on insert via trigger
-- =============================================================================

CREATE OR REPLACE FUNCTION dtl_set_child_tenant_id()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.tenant_id IS NULL THEN
    SELECT tenant_id INTO NEW.tenant_id 
    FROM decision_traces 
    WHERE id = NEW.decision_id;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing triggers if any
DROP TRIGGER IF EXISTS trg_evidence_tenant ON decision_evidence;
DROP TRIGGER IF EXISTS trg_exceptions_tenant ON decision_exceptions;
DROP TRIGGER IF EXISTS trg_results_tenant ON decision_results;
DROP TRIGGER IF EXISTS trg_assessments_tenant ON decision_assessments;
DROP TRIGGER IF EXISTS trg_executions_tenant ON decision_executions;
DROP TRIGGER IF EXISTS trg_entity_links_tenant ON decision_entity_links;
DROP TRIGGER IF EXISTS trg_precedent_links_tenant ON decision_precedent_links;
DROP TRIGGER IF EXISTS trg_confidence_tenant ON decision_confidence_scores;

-- Create triggers
CREATE TRIGGER trg_evidence_tenant 
BEFORE INSERT ON decision_evidence 
FOR EACH ROW EXECUTE FUNCTION dtl_set_child_tenant_id();

CREATE TRIGGER trg_exceptions_tenant 
BEFORE INSERT ON decision_exceptions 
FOR EACH ROW EXECUTE FUNCTION dtl_set_child_tenant_id();

CREATE TRIGGER trg_results_tenant 
BEFORE INSERT ON decision_results 
FOR EACH ROW EXECUTE FUNCTION dtl_set_child_tenant_id();

CREATE TRIGGER trg_assessments_tenant 
BEFORE INSERT ON decision_assessments 
FOR EACH ROW EXECUTE FUNCTION dtl_set_child_tenant_id();

CREATE TRIGGER trg_executions_tenant 
BEFORE INSERT ON decision_executions 
FOR EACH ROW EXECUTE FUNCTION dtl_set_child_tenant_id();

CREATE TRIGGER trg_entity_links_tenant 
BEFORE INSERT ON decision_entity_links 
FOR EACH ROW EXECUTE FUNCTION dtl_set_child_tenant_id();

CREATE TRIGGER trg_precedent_links_tenant 
BEFORE INSERT ON decision_precedent_links 
FOR EACH ROW EXECUTE FUNCTION dtl_set_child_tenant_id();

CREATE TRIGGER trg_confidence_tenant 
BEFORE INSERT ON decision_confidence_scores 
FOR EACH ROW EXECUTE FUNCTION dtl_set_child_tenant_id();

-- =============================================================================
-- STEP 5: Precedent same-tenant validation (CRITICAL)
-- Prevents cross-tenant graph contamination
-- =============================================================================

CREATE OR REPLACE FUNCTION dtl_validate_precedent_tenant()
RETURNS TRIGGER AS $$
DECLARE 
  precedent_tenant UUID;
BEGIN
  -- Get tenant of the precedent decision
  SELECT tenant_id INTO precedent_tenant 
  FROM decision_traces 
  WHERE id = NEW.precedent_decision_id;
  
  -- Validate same tenant
  IF precedent_tenant IS NULL THEN
    RAISE EXCEPTION 'Precedent decision % not found', NEW.precedent_decision_id;
  END IF;
  
  IF precedent_tenant <> NEW.tenant_id THEN
    RAISE EXCEPTION 'Cannot link to precedent from different tenant (decision tenant: %, precedent tenant: %)', 
      NEW.tenant_id, precedent_tenant;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_validate_precedent_tenant ON decision_precedent_links;
CREATE TRIGGER trg_validate_precedent_tenant
BEFORE INSERT OR UPDATE ON decision_precedent_links
FOR EACH ROW EXECUTE FUNCTION dtl_validate_precedent_tenant();

-- =============================================================================
-- STEP 6: Drop old recursive RLS policies
-- =============================================================================

DROP POLICY IF EXISTS evidence_via_decision ON decision_evidence;
DROP POLICY IF EXISTS exceptions_via_decision ON decision_exceptions;
DROP POLICY IF EXISTS results_via_decision ON decision_results;
DROP POLICY IF EXISTS assessments_via_decision ON decision_assessments;
DROP POLICY IF EXISTS executions_via_decision ON decision_executions;
DROP POLICY IF EXISTS entity_links_via_decision ON decision_entity_links;
DROP POLICY IF EXISTS precedent_links_via_decision ON decision_precedent_links;
DROP POLICY IF EXISTS confidence_via_decision ON decision_confidence_scores;

-- =============================================================================
-- STEP 7: Create simple non-recursive RLS policies
-- =============================================================================

CREATE POLICY evidence_tenant_isolation ON decision_evidence 
FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY exceptions_tenant_isolation ON decision_exceptions 
FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY results_tenant_isolation ON decision_results 
FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY assessments_tenant_isolation ON decision_assessments 
FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY executions_tenant_isolation ON decision_executions 
FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY entity_links_tenant_isolation ON decision_entity_links 
FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY precedent_links_tenant_isolation ON decision_precedent_links 
FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

CREATE POLICY confidence_tenant_isolation ON decision_confidence_scores 
FOR ALL USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- =============================================================================
-- STEP 8: Re-enable RLS on all child tables
-- =============================================================================

ALTER TABLE decision_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_exceptions ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_entity_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_precedent_links ENABLE ROW LEVEL SECURITY;
ALTER TABLE decision_confidence_scores ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- STEP 9: Add indexes on tenant_id for performance
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_evidence_tenant ON decision_evidence(tenant_id);
CREATE INDEX IF NOT EXISTS idx_exceptions_tenant ON decision_exceptions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_results_tenant ON decision_results(tenant_id);
CREATE INDEX IF NOT EXISTS idx_assessments_tenant ON decision_assessments(tenant_id);
CREATE INDEX IF NOT EXISTS idx_executions_tenant ON decision_executions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_entity_links_tenant ON decision_entity_links(tenant_id);
CREATE INDEX IF NOT EXISTS idx_precedent_links_tenant ON decision_precedent_links(tenant_id);
CREATE INDEX IF NOT EXISTS idx_confidence_tenant ON decision_confidence_scores(tenant_id);

COMMIT;

-- =============================================================================
-- VERIFICATION QUERIES (run after migration)
-- =============================================================================

-- Check all child tables have tenant_id
-- SELECT table_name, column_name FROM information_schema.columns 
-- WHERE column_name = 'tenant_id' AND table_schema = 'public'
-- ORDER BY table_name;

-- Check RLS is enabled
-- SELECT tablename, rowsecurity FROM pg_tables 
-- WHERE schemaname = 'public' AND tablename LIKE 'decision_%';

-- Check policies exist
-- SELECT tablename, policyname FROM pg_policies 
-- WHERE schemaname = 'public' AND tablename LIKE 'decision_%';
