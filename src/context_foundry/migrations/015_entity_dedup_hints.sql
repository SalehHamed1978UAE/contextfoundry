-- Migration: Add entity_dedup_hints table
--
-- Backs the FUZZY_HINTS dedup policy in the aggregation framework.
-- Stores entity resolution hints (merge/keep/uncertain decisions)
-- used by the sufficiency gate to penalize confidence when dedup is ambiguous.

-- =============================================================================
-- entity_dedup_hints - Backs FUZZY_HINTS dedup policy
-- =============================================================================

CREATE TABLE IF NOT EXISTS entity_dedup_hints (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    entity1_id UUID NOT NULL,
    entity2_id UUID NOT NULL,
    
    -- Similarity assessment
    similarity_score NUMERIC NOT NULL CHECK (similarity_score >= 0 AND similarity_score <= 1),
    similarity_method TEXT NOT NULL DEFAULT 'embedding',  -- embedding, fuzzy_name, attribute_match
    
    -- Resolution decision
    decision TEXT NOT NULL CHECK (decision IN ('merge', 'keep_separate', 'uncertain')),
    decision_confidence NUMERIC NOT NULL DEFAULT 1.0,
    decided_by TEXT,  -- 'auto', 'human', 'rule'
    decided_at TIMESTAMPTZ DEFAULT now(),
    
    -- Audit
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Prevent duplicate pairs (order-independent)
    CONSTRAINT uq_dedup_hint_pair UNIQUE (tenant_id, entity1_id, entity2_id),
    CONSTRAINT entity_order CHECK (entity1_id < entity2_id)  -- Canonical ordering
);

-- Indices for lookup patterns
CREATE INDEX IF NOT EXISTS idx_dedup_hints_tenant ON entity_dedup_hints (tenant_id);
CREATE INDEX IF NOT EXISTS idx_dedup_hints_entity1 ON entity_dedup_hints (tenant_id, entity1_id);
CREATE INDEX IF NOT EXISTS idx_dedup_hints_entity2 ON entity_dedup_hints (tenant_id, entity2_id);
CREATE INDEX IF NOT EXISTS idx_dedup_hints_uncertain ON entity_dedup_hints (tenant_id, decision) 
    WHERE decision = 'uncertain';

-- RLS
ALTER TABLE entity_dedup_hints ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS dedup_hints_tenant_isolation ON entity_dedup_hints;
CREATE POLICY dedup_hints_tenant_isolation ON entity_dedup_hints
    USING (tenant_id = current_setting('app.current_tenant')::uuid);

-- =============================================================================
-- Helper view: Get all hints for an entity (either side of pair)
-- =============================================================================

CREATE OR REPLACE VIEW v_entity_dedup_hints AS
SELECT 
    tenant_id,
    entity1_id AS entity_id,
    entity2_id AS related_entity_id,
    similarity_score,
    similarity_method,
    decision,
    decision_confidence
FROM entity_dedup_hints
UNION ALL
SELECT 
    tenant_id,
    entity2_id AS entity_id,
    entity1_id AS related_entity_id,
    similarity_score,
    similarity_method,
    decision,
    decision_confidence
FROM entity_dedup_hints;

-- =============================================================================
-- Helper function: Get ambiguous merge rate for an entity set
-- Used by sufficiency gate to penalize confidence
-- =============================================================================

CREATE OR REPLACE FUNCTION get_ambiguous_merge_rate(
    p_tenant_id UUID,
    p_entity_ids UUID[]
) RETURNS NUMERIC AS $$
DECLARE
    total_pairs INTEGER;
    uncertain_pairs INTEGER;
BEGIN
    SELECT COUNT(*), COUNT(*) FILTER (WHERE decision = 'uncertain')
    INTO total_pairs, uncertain_pairs
    FROM entity_dedup_hints
    WHERE tenant_id = p_tenant_id
      AND (entity1_id = ANY(p_entity_ids) OR entity2_id = ANY(p_entity_ids));
    
    IF total_pairs = 0 THEN
        RETURN 0.0;
    END IF;
    
    RETURN uncertain_pairs::NUMERIC / total_pairs::NUMERIC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
