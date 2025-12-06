-- Session 3: Promotion Thresholds and Gardener Metrics Tables
-- These tables configure per-type promotion requirements and track gardener activity

-- Promotion thresholds table - configurable per entity type
CREATE TABLE IF NOT EXISTS promotion_thresholds (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type_id UUID REFERENCES ontology_types(id),
    entity_type_name VARCHAR(100) NOT NULL,
    min_confidence DECIMAL(3,2) NOT NULL DEFAULT 0.70,
    min_corroboration_count INTEGER NOT NULL DEFAULT 1,
    min_staging_hours INTEGER NOT NULL DEFAULT 1,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(entity_type_name)
);

-- Create index for fast lookups
CREATE INDEX IF NOT EXISTS idx_promotion_thresholds_type_name 
ON promotion_thresholds(entity_type_name);

-- Gardener run history
CREATE TABLE IF NOT EXISTS gardener_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMP WITH TIME ZONE NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    
    -- Pass counts
    corroboration_updates INTEGER DEFAULT 0,
    conflicts_detected INTEGER DEFAULT 0,
    conflicts_resolved INTEGER DEFAULT 0,
    entities_promoted INTEGER DEFAULT 0,
    entities_decayed INTEGER DEFAULT 0,
    entities_demoted INTEGER DEFAULT 0,
    
    -- Timing
    corroboration_pass_ms INTEGER,
    conflict_pass_ms INTEGER,
    promotion_pass_ms INTEGER,
    decay_pass_ms INTEGER,
    
    -- Error tracking
    errors TEXT[],
    
    CHECK (status IN ('running', 'completed', 'failed', 'partial'))
);

-- Gardener metrics aggregated by type
CREATE TABLE IF NOT EXISTS gardener_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recorded_at DATE NOT NULL DEFAULT CURRENT_DATE,
    entity_type_name VARCHAR(100) NOT NULL,
    
    -- Promotion metrics
    total_in_staging INTEGER DEFAULT 0,
    promoted_count INTEGER DEFAULT 0,
    promotion_rate DECIMAL(5,4),
    avg_staging_hours DECIMAL(10,2),
    
    -- Rejection metrics
    rejected_count INTEGER DEFAULT 0,
    rejection_rate DECIMAL(5,4),
    
    -- Conflict metrics
    conflict_count INTEGER DEFAULT 0,
    auto_resolved_count INTEGER DEFAULT 0,
    human_review_count INTEGER DEFAULT 0,
    
    UNIQUE(recorded_at, entity_type_name)
);

-- Conflict resolution audit log
CREATE TABLE IF NOT EXISTS conflict_resolutions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id_a UUID NOT NULL,
    entity_id_b UUID NOT NULL,
    conflict_type VARCHAR(50) NOT NULL,
    resolution_method VARCHAR(50) NOT NULL,
    winner_id UUID,
    confidence_delta DECIMAL(5,4),
    resolved_by VARCHAR(50) NOT NULL,
    resolved_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    notes TEXT,
    gardener_run_id UUID REFERENCES gardener_runs(id),
    
    CHECK (conflict_type IN ('duplicate', 'contradicting_property', 'type_mismatch', 'temporal_overlap')),
    CHECK (resolution_method IN ('authority_based', 'recency', 'confidence', 'merge', 'human_review')),
    CHECK (resolved_by IN ('gardener', 'human'))
);

-- Insert default and per-type thresholds from spec
INSERT INTO promotion_thresholds (entity_type_name, min_confidence, min_corroboration_count, min_staging_hours, is_default)
VALUES 
    ('_default', 0.70, 1, 1, TRUE),
    ('Person', 0.85, 2, 4, FALSE),
    ('Incident', 0.80, 3, 2, FALSE),
    ('Service', 0.75, 1, 1, FALSE)
ON CONFLICT (entity_type_name) DO UPDATE SET
    min_confidence = EXCLUDED.min_confidence,
    min_corroboration_count = EXCLUDED.min_corroboration_count,
    min_staging_hours = EXCLUDED.min_staging_hours,
    updated_at = NOW();

-- Link thresholds to ontology_types where they exist
UPDATE promotion_thresholds pt
SET entity_type_id = ot.id
FROM ontology_types ot
WHERE pt.entity_type_name = ot.type_name;

-- Function to get threshold for a type (falls back to default)
CREATE OR REPLACE FUNCTION get_promotion_threshold(p_type_name VARCHAR)
RETURNS TABLE (
    min_confidence DECIMAL,
    min_corroboration_count INTEGER,
    min_staging_hours INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT pt.min_confidence, pt.min_corroboration_count, pt.min_staging_hours
    FROM promotion_thresholds pt
    WHERE pt.entity_type_name = p_type_name
    LIMIT 1;
    
    IF NOT FOUND THEN
        RETURN QUERY
        SELECT pt.min_confidence, pt.min_corroboration_count, pt.min_staging_hours
        FROM promotion_thresholds pt
        WHERE pt.is_default = TRUE
        LIMIT 1;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Comment explaining the thresholds
COMMENT ON TABLE promotion_thresholds IS 
'Per-entity-type configuration for promotion from STAGING to TRUSTED.
Thresholds: Person=0.85/2/4h (strict), Incident=0.80/3/2h (requires corroboration), 
Service=0.75/1/1h (faster), default=0.70/1/1h';
