-- Migration: 014_aggregation_framework.sql
-- Aggregation Framework Database Migration
-- Creates the tables required for v1.3 spec:
-- - agg_definitions: Semantic contract registry (§4.1)
-- - aggregation_metadata: Result cache (§6.2)
-- - doc_entity_mentions: Document mention index (§6.3)

-- ==========================================================================
-- 1. agg_definitions - Semantic contract registry (§4.1)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS agg_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    concept_key TEXT NOT NULL,
    synonyms TEXT[] NOT NULL DEFAULT '{}',
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    candidates JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_agg_defs_tenant_concept_version UNIQUE (tenant_id, concept_key, version)
);

CREATE INDEX IF NOT EXISTS idx_agg_defs_tenant_concept ON agg_definitions (tenant_id, concept_key);

ALTER TABLE agg_definitions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agg_defs_tenant_isolation ON agg_definitions;
CREATE POLICY agg_defs_tenant_isolation ON agg_definitions
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- ==========================================================================
-- 2. aggregation_metadata - Result cache (§6.2)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS aggregation_metadata (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    plan_hash TEXT NOT NULL,
    plan_version INTEGER NOT NULL,
    result_kind TEXT NOT NULL,
    value NUMERIC,
    lower_bound NUMERIC,
    upper_bound NUMERIC,
    confidence NUMERIC NOT NULL,
    evidence_envelope JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    CONSTRAINT uq_aggmeta_tenant_plan UNIQUE (tenant_id, plan_hash, plan_version)
);

CREATE INDEX IF NOT EXISTS idx_aggmeta_tenant_expires ON aggregation_metadata (tenant_id, expires_at);

ALTER TABLE aggregation_metadata ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS aggmeta_tenant_isolation ON aggregation_metadata;
CREATE POLICY aggmeta_tenant_isolation ON aggregation_metadata
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- ==========================================================================
-- 3. doc_entity_mentions - Document mention index (§6.3)
-- ==========================================================================
CREATE TABLE IF NOT EXISTS doc_entity_mentions (
    tenant_id UUID NOT NULL,
    doc_id UUID NOT NULL,
    entity_id UUID NOT NULL,
    mention_count INTEGER,
    first_seen_at TIMESTAMPTZ,
    PRIMARY KEY (tenant_id, doc_id, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_mentions_tenant_entity ON doc_entity_mentions (tenant_id, entity_id);

ALTER TABLE doc_entity_mentions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS mentions_tenant_isolation ON doc_entity_mentions;
CREATE POLICY mentions_tenant_isolation ON doc_entity_mentions
    USING (tenant_id = current_setting('app.current_tenant', true)::uuid);

-- ==========================================================================
-- 4. Additional indices for aggregation queries (§6.1)
-- ==========================================================================

-- Entities index for aggregation
CREATE INDEX IF NOT EXISTS idx_entities_tenant_type ON entities (tenant_id, entity_type);

-- Relationships indices for aggregation (both directions)
CREATE INDEX IF NOT EXISTS idx_rel_tenant_src_type ON relationships (tenant_id, source_id, relationship_type);
CREATE INDEX IF NOT EXISTS idx_rel_tenant_tgt_type ON relationships (tenant_id, target_id, relationship_type);

-- DTL decisions index for aggregation (if table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'dtl_decisions') THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_decisions_tenant_type_time ON dtl_decisions (tenant_id, decision_type, created_at)';
    END IF;
END $$;
