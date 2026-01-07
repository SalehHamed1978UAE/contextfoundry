/* ============================================================================
   Context Foundry — Decision Trace Layer (DTL) v1.0 PATCHED DDL
   
   Fixes Applied:
   1. Removes approver_ids array; uses decision_entity_links (entity_role='approver')
   2. Adds sensitivity column (NOT inside JSONB)
   3. Splits outcomes into executions/results/assessments
   4. search_precedents uses decision_type as RANKING BONUS, not a hard filter
   5. Enforces evidence required for enacted decisions via DEFERRABLE constraint trigger
   6. Switches vector index from IVFFLAT to HNSW
   ============================================================================ */

-- ----------------------------------------------------------------------------
-- EXTENSIONS (most already exist in CF)
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "btree_gist";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ----------------------------------------------------------------------------
-- TYPES / ENUMS
-- ----------------------------------------------------------------------------
DO $$ BEGIN
  CREATE TYPE decision_lifecycle AS ENUM (
    'draft','proposed','approved','enacted','superseded','expired','revoked'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE category_lifecycle AS ENUM ('proposed','active','deprecated','merged');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE sensitivity_level AS ENUM ('public','internal','confidential','restricted');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE evidence_type AS ENUM (
    'slack_msg','email','meeting_segment','jira','doc','pr_comment','code_review','manual_note','agent_log'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE decision_entity_role AS ENUM (
    'subject','affected_party','decision_maker','approver','advisor','implementer',
    'policy','system_consulted','context'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE result_status AS ENUM ('positive','neutral','negative','unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ----------------------------------------------------------------------------
-- CORE TABLE: decision_traces (L1 Decision Event)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_traces (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id VARCHAR(50) NOT NULL UNIQUE,

  -- Bi-temporal
  valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
  sys_period TSTZRANGE NOT NULL DEFAULT tstzrange(NOW(), NULL, '[)'),

  -- Core metadata
  decision_timestamp TIMESTAMPTZ NOT NULL,
  decision_summary TEXT NOT NULL,

  -- Decision choice (fast path)
  decision_choice JSONB NOT NULL DEFAULT '{}'::jsonb,

  -- Decision maker (single)
  decision_maker_id UUID NOT NULL,

  -- Category is a hypothesis (nullable)
  decision_type TEXT NULL,
  decision_type_confidence NUMERIC(3,2) NULL,

  -- Rationale (kept here for simplicity + search)
  rationale_summary TEXT NULL,
  rationale_structured JSONB NOT NULL DEFAULT '{}'::jsonb,

  -- Semantic search vector
  rationale_embedding VECTOR(1536),

  -- Context snapshot at time of decision
  context_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,

  -- Lifecycle
  lifecycle_state decision_lifecycle NOT NULL DEFAULT 'draft',

  -- Source tracking
  source_system TEXT NOT NULL,
  source_reference TEXT NULL,
  extraction_confidence NUMERIC(3,2) NULL,

  -- Security classification is a column, not JSON
  sensitivity sensitivity_level NOT NULL DEFAULT 'internal',

  -- Audit / tenancy
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by VARCHAR(255) NOT NULL,
  tenant_id UUID NOT NULL,

  CONSTRAINT valid_time_range CHECK (valid_from < valid_until)
);

-- ----------------------------------------------------------------------------
-- L2: decision_entity_links (replaces approver_ids array)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_entity_links (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  entity_id UUID NOT NULL,
  entity_role decision_entity_role NOT NULL,

  acted_at TIMESTAMPTZ NULL,

  resolution_method VARCHAR(50) NULL,
  resolution_confidence NUMERIC(3,2) NULL,

  entity_state_at_decision JSONB NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- decision_evidence (receipts / provenance)
-- Evidence MUST exist for enacted decisions (enforced by trigger below)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_evidence (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  evidence_type evidence_type NOT NULL,
  source_uri TEXT NULL,
  source_id TEXT NULL,
  excerpt TEXT NULL,
  excerpt_hash TEXT NULL,
  event_timestamp TIMESTAMPTZ NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- L2: decision_precedent_links
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_precedent_links (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,
  precedent_decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  link_type VARCHAR(50) NOT NULL,
  similarity_score NUMERIC(4,3) NULL,
  match_reasoning TEXT NULL,

  precedent_applied BOOLEAN NOT NULL DEFAULT TRUE,
  deviation_reason TEXT NULL,

  discovered_by VARCHAR(50) NOT NULL,
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT no_self_reference CHECK (decision_id != precedent_decision_id),
  CONSTRAINT valid_link_type CHECK (
    link_type IN ('cited','distinguished','overruled','extended','conflicts_with')
  )
);

-- ----------------------------------------------------------------------------
-- L2: decision_exceptions
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_exceptions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  policy_id UUID NULL,
  policy_name VARCHAR(255) NOT NULL,
  policy_version VARCHAR(50) NULL,

  exception_type VARCHAR(100) NOT NULL,
  exception_aspect TEXT NOT NULL,

  policy_limit JSONB NULL,
  actual_value JSONB NULL,
  deviation_magnitude JSONB NULL,

  exception_justification TEXT NOT NULL,

  exception_requested_by UUID NULL,
  exception_approved_by UUID NULL,

  risk_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
  risk_notes TEXT NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- L2: decision_confidence_scores
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_confidence_scores (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  overall_confidence NUMERIC(4,3) NOT NULL,

  extraction_accuracy NUMERIC(4,3) NULL,
  source_reliability NUMERIC(4,3) NULL,
  temporal_certainty NUMERIC(4,3) NULL,
  rationale_completeness NUMERIC(4,3) NULL,
  entity_resolution_confidence NUMERIC(4,3) NULL,

  scoring_model_version VARCHAR(50) NOT NULL,
  human_reviewed BOOLEAN NOT NULL DEFAULT FALSE,
  reviewer_id UUID NULL,
  reviewed_at TIMESTAMPTZ NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Split outcomes into executions/results/assessments
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_executions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  expected_outcome JSONB NULL,

  execution_result JSONB NULL,
  executed_at TIMESTAMPTZ NULL,
  executed_by_entity_id UUID NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decision_results (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  outcome_status result_status NOT NULL DEFAULT 'unknown',
  outcome_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  result_notes TEXT NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decision_assessments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  decision_quality_score NUMERIC(4,3) NULL,
  assessment_notes TEXT NULL,
  assessment_confidence NUMERIC(3,2) NULL,

  assessed_at TIMESTAMPTZ NULL,
  assessed_by_entity_id UUID NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- L4: decision_categories
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_categories (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL,

  name TEXT NOT NULL,
  description TEXT NULL,

  emerged_from_clustering BOOLEAN NOT NULL DEFAULT TRUE,
  cluster_id VARCHAR(100) NULL,

  human_validated BOOLEAN NOT NULL DEFAULT FALSE,
  validated_by UUID NULL,
  validated_at TIMESTAMPTZ NULL,

  prototype_embedding VECTOR(1536) NULL,
  typical_attributes JSONB NOT NULL DEFAULT '{}'::jsonb,

  lifecycle category_lifecycle NOT NULL DEFAULT 'proposed',
  merged_into_id UUID NULL REFERENCES decision_categories(id),

  usage_count INTEGER NOT NULL DEFAULT 0,
  last_used_at TIMESTAMPTZ NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Schema evolution proposals
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_evolution_proposals (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL,

  proposal_type VARCHAR(50) NOT NULL,
  detection_method VARCHAR(50) NULL,

  supporting_decision_count INTEGER NOT NULL,
  supporting_decision_ids UUID[] NULL,
  detection_confidence NUMERIC(3,2) NOT NULL,

  proposal_summary TEXT NOT NULL,
  proposal_details JSONB NOT NULL DEFAULT '{}'::jsonb,
  recommendation TEXT NULL,

  status VARCHAR(20) NOT NULL DEFAULT 'pending',
  reviewed_by UUID NULL,
  reviewed_at TIMESTAMPTZ NULL,
  review_notes TEXT NULL,

  implemented_at TIMESTAMPTZ NULL,
  implementation_notes TEXT NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Access grants + audit
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_access_grants (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL,
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,
  grantee_id UUID NOT NULL,
  granted_by UUID NULL,
  granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decision_access_audit (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL,

  accessor_id UUID NOT NULL,
  accessor_role VARCHAR(100) NULL,

  decision_id UUID NULL REFERENCES decision_traces(id),
  access_type VARCHAR(20) NOT NULL,
  access_granted BOOLEAN NOT NULL,
  denial_reason TEXT NULL,

  access_reason TEXT NULL,
  client_ip VARCHAR(45) NULL,
  user_agent TEXT NULL,

  accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- INDEXES
-- ----------------------------------------------------------------------------

-- Core decision queries
CREATE INDEX IF NOT EXISTS idx_dtl_decisions_tenant_date ON decision_traces(tenant_id, decision_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_dtl_decisions_lifecycle ON decision_traces(lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_dtl_decisions_maker ON decision_traces(decision_maker_id);
CREATE INDEX IF NOT EXISTS idx_dtl_decisions_type ON decision_traces(decision_type) WHERE decision_type IS NOT NULL;

-- Bi-temporal
CREATE INDEX IF NOT EXISTS idx_dtl_decisions_valid_time ON decision_traces USING GIST (tstzrange(valid_from, valid_until, '[)'));
CREATE INDEX IF NOT EXISTS idx_dtl_decisions_sys_period ON decision_traces USING GIST (sys_period);

-- Full-text search (rationale + summary)
CREATE INDEX IF NOT EXISTS idx_dtl_decisions_rationale_fts
ON decision_traces USING GIN (
  to_tsvector('english', COALESCE(decision_summary,'') || ' ' || COALESCE(rationale_summary,''))
);

-- HNSW vector index (preferred over IVFFLAT)
CREATE INDEX IF NOT EXISTS idx_dtl_decisions_rationale_hnsw
ON decision_traces USING hnsw (rationale_embedding vector_cosine_ops);

-- Links
CREATE INDEX IF NOT EXISTS idx_dtl_entity_links_decision ON decision_entity_links(decision_id);
CREATE INDEX IF NOT EXISTS idx_dtl_entity_links_entity ON decision_entity_links(entity_id);
CREATE INDEX IF NOT EXISTS idx_dtl_entity_links_role ON decision_entity_links(entity_role);

CREATE INDEX IF NOT EXISTS idx_dtl_evidence_decision ON decision_evidence(decision_id);
CREATE INDEX IF NOT EXISTS idx_dtl_evidence_type ON decision_evidence(evidence_type);

CREATE INDEX IF NOT EXISTS idx_dtl_precedent_links_decision ON decision_precedent_links(decision_id);
CREATE INDEX IF NOT EXISTS idx_dtl_precedent_links_precedent ON decision_precedent_links(precedent_decision_id);

CREATE INDEX IF NOT EXISTS idx_dtl_exceptions_decision ON decision_exceptions(decision_id);
CREATE INDEX IF NOT EXISTS idx_dtl_exceptions_policy_name ON decision_exceptions(policy_name);

CREATE INDEX IF NOT EXISTS idx_dtl_confidence_decision ON decision_confidence_scores(decision_id);

CREATE INDEX IF NOT EXISTS idx_dtl_exec_decision ON decision_executions(decision_id);
CREATE INDEX IF NOT EXISTS idx_dtl_results_decision ON decision_results(decision_id);
CREATE INDEX IF NOT EXISTS idx_dtl_results_status ON decision_results(outcome_status);
CREATE INDEX IF NOT EXISTS idx_dtl_assess_decision ON decision_assessments(decision_id);

CREATE INDEX IF NOT EXISTS idx_dtl_categories_tenant ON decision_categories(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dtl_categories_lifecycle ON decision_categories(lifecycle);

CREATE INDEX IF NOT EXISTS idx_dtl_access_grants_decision ON decision_access_grants(decision_id);
CREATE INDEX IF NOT EXISTS idx_dtl_access_grants_grantee ON decision_access_grants(grantee_id);

CREATE INDEX IF NOT EXISTS idx_dtl_audit_decision ON decision_access_audit(decision_id);
CREATE INDEX IF NOT EXISTS idx_dtl_audit_accessor ON decision_access_audit(accessor_id);
CREATE INDEX IF NOT EXISTS idx_dtl_audit_time ON decision_access_audit(accessed_at DESC);

-- ----------------------------------------------------------------------------
-- Evidence must exist for enacted decisions (DEFERRABLE constraint)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dtl_enforce_evidence_for_enacted()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.lifecycle_state = 'enacted' THEN
    IF NOT EXISTS (
      SELECT 1 FROM decision_evidence de WHERE de.decision_id = NEW.id
    ) THEN
      RAISE EXCEPTION 'Decision % is enacted but has no evidence. Add at least one decision_evidence row before COMMIT.', NEW.id;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_decision_requires_evidence ON decision_traces;

CREATE CONSTRAINT TRIGGER trg_decision_requires_evidence
AFTER INSERT OR UPDATE OF lifecycle_state ON decision_traces
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION dtl_enforce_evidence_for_enacted();

-- ----------------------------------------------------------------------------
-- ROW LEVEL SECURITY (RLS)
-- ----------------------------------------------------------------------------
ALTER TABLE decision_traces ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS dtl_tenant_isolation ON decision_traces;
CREATE POLICY dtl_tenant_isolation ON decision_traces
  FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

DROP POLICY IF EXISTS dtl_decision_read_policy ON decision_traces;
CREATE POLICY dtl_decision_read_policy ON decision_traces
  FOR SELECT
  USING (
    tenant_id = current_setting('app.current_tenant_id')::uuid
    AND (
      sensitivity = 'public'
      OR sensitivity = 'internal'
      OR (
        sensitivity = 'confidential' AND (
          current_setting('app.current_user_role', true) IN ('admin','compliance','leadership')
          OR EXISTS (
            SELECT 1
            FROM decision_entity_links del
            WHERE del.decision_id = decision_traces.id
              AND del.entity_id = current_setting('app.current_user_id')::uuid
          )
        )
      )
      OR (
        sensitivity = 'restricted' AND (
          decision_maker_id = current_setting('app.current_user_id')::uuid
          OR EXISTS (
            SELECT 1 FROM decision_access_grants dag
            WHERE dag.decision_id = decision_traces.id
              AND dag.grantee_id = current_setting('app.current_user_id')::uuid
          )
        )
      )
    )
  );

-- RLS on child tables with explicit tenant_id checks
ALTER TABLE decision_evidence ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtl_evidence_via_decision ON decision_evidence;
CREATE POLICY dtl_evidence_via_decision ON decision_evidence
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM decision_traces dt
      WHERE dt.id = decision_evidence.decision_id
        AND dt.tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

ALTER TABLE decision_exceptions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtl_exceptions_via_decision ON decision_exceptions;
CREATE POLICY dtl_exceptions_via_decision ON decision_exceptions
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM decision_traces dt
      WHERE dt.id = decision_exceptions.decision_id
        AND dt.tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

ALTER TABLE decision_results ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtl_results_via_decision ON decision_results;
CREATE POLICY dtl_results_via_decision ON decision_results
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM decision_traces dt
      WHERE dt.id = decision_results.decision_id
        AND dt.tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

ALTER TABLE decision_assessments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtl_assessments_via_decision ON decision_assessments;
CREATE POLICY dtl_assessments_via_decision ON decision_assessments
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM decision_traces dt
      WHERE dt.id = decision_assessments.decision_id
        AND dt.tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

ALTER TABLE decision_executions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtl_executions_via_decision ON decision_executions;
CREATE POLICY dtl_executions_via_decision ON decision_executions
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM decision_traces dt
      WHERE dt.id = decision_executions.decision_id
        AND dt.tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

ALTER TABLE decision_entity_links ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtl_entity_links_via_decision ON decision_entity_links;
CREATE POLICY dtl_entity_links_via_decision ON decision_entity_links
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM decision_traces dt
      WHERE dt.id = decision_entity_links.decision_id
        AND dt.tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

ALTER TABLE decision_precedent_links ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtl_precedent_links_via_decision ON decision_precedent_links;
CREATE POLICY dtl_precedent_links_via_decision ON decision_precedent_links
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM decision_traces dt
      WHERE dt.id = decision_precedent_links.decision_id
        AND dt.tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

ALTER TABLE decision_confidence_scores ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtl_confidence_via_decision ON decision_confidence_scores;
CREATE POLICY dtl_confidence_via_decision ON decision_confidence_scores
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM decision_traces dt
      WHERE dt.id = decision_confidence_scores.decision_id
        AND dt.tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

ALTER TABLE decision_categories ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtl_categories_tenant ON decision_categories;
CREATE POLICY dtl_categories_tenant ON decision_categories
  FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

ALTER TABLE schema_evolution_proposals ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtl_proposals_tenant ON schema_evolution_proposals;
CREATE POLICY dtl_proposals_tenant ON schema_evolution_proposals
  FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

ALTER TABLE decision_access_grants ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtl_grants_tenant ON decision_access_grants;
CREATE POLICY dtl_grants_tenant ON decision_access_grants
  FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

ALTER TABLE decision_access_audit ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS dtl_audit_tenant ON decision_access_audit;
CREATE POLICY dtl_audit_tenant ON decision_access_audit
  FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Evidence quality gate (at least one substantive field required)
ALTER TABLE decision_evidence DROP CONSTRAINT IF EXISTS evidence_has_substance;
ALTER TABLE decision_evidence ADD CONSTRAINT evidence_has_substance CHECK (
  source_uri IS NOT NULL 
  OR source_id IS NOT NULL 
  OR (excerpt IS NOT NULL AND LENGTH(excerpt) >= 10)
);

-- Prevent duplicate entity roles per decision
CREATE UNIQUE INDEX IF NOT EXISTS uq_dtl_decision_entity_role
ON decision_entity_links(decision_id, entity_id, entity_role);

-- Prevent evidence deletion when decision is enacted
CREATE OR REPLACE FUNCTION dtl_prevent_evidence_deletion_when_enacted()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM decision_traces dt 
    WHERE dt.id = OLD.decision_id 
      AND dt.lifecycle_state = 'enacted'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM decision_evidence de 
      WHERE de.decision_id = OLD.decision_id 
        AND de.id != OLD.id
    ) THEN
      RAISE EXCEPTION 'Cannot delete last evidence row for enacted decision %', OLD.decision_id;
    END IF;
  END IF;
  RETURN OLD;
END;
$$;

DROP TRIGGER IF EXISTS trg_dtl_prevent_evidence_deletion ON decision_evidence;
CREATE TRIGGER trg_dtl_prevent_evidence_deletion
BEFORE DELETE ON decision_evidence
FOR EACH ROW
EXECUTE FUNCTION dtl_prevent_evidence_deletion_when_enacted();
