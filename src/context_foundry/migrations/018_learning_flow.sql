-- =============================================================================
-- Migration 018: Learning Flow
-- =============================================================================
-- Purpose: Track query gaps, user feedback, and learning opportunities
-- Date: 2026-01-13
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Query Gaps: Questions the system couldn't answer well
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS query_gaps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES platform.tenants(id) ON DELETE CASCADE,
    
    -- The query that revealed the gap
    query_text TEXT NOT NULL,
    query_type VARCHAR(50),  -- 'entity', 'relationship', 'attribute', 'general'
    
    -- What the user was looking for
    expected_entity_type VARCHAR(100),
    expected_entity_name VARCHAR(500),
    expected_relationship_type VARCHAR(100),
    
    -- System's response
    system_response TEXT,
    confidence_score FLOAT,
    
    -- Gap classification
    gap_type VARCHAR(50) NOT NULL,  -- 'missing_entity', 'missing_relationship', 'wrong_answer', 'low_confidence', 'no_answer'
    
    -- Resolution status
    status VARCHAR(20) DEFAULT 'OPEN',  -- 'OPEN', 'QUEUED', 'PROCESSING', 'RESOLVED', 'IGNORED'
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    user_id VARCHAR(100),  -- Optional: track which user encountered the gap
    session_id VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_query_gaps_tenant_status ON query_gaps(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_query_gaps_type ON query_gaps(gap_type, status);
CREATE INDEX IF NOT EXISTS idx_query_gaps_created ON query_gaps(created_at DESC);

-- -----------------------------------------------------------------------------
-- User Feedback: Explicit corrections from users
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES platform.tenants(id) ON DELETE CASCADE,
    
    -- Reference to what's being corrected
    query_gap_id UUID REFERENCES query_gaps(id) ON DELETE SET NULL,
    entity_id UUID REFERENCES entities(id) ON DELETE SET NULL,
    relationship_id UUID REFERENCES relationships(id) ON DELETE SET NULL,
    
    -- The feedback
    feedback_type VARCHAR(50) NOT NULL,  -- 'correction', 'confirmation', 'rejection', 'addition'
    
    -- Correction details
    original_value TEXT,
    corrected_value TEXT,
    correction_field VARCHAR(100),  -- 'name', 'type', 'relationship', 'attribute'
    
    -- Context
    feedback_text TEXT,  -- User's explanation
    confidence FLOAT DEFAULT 1.0,  -- How confident is this feedback
    
    -- Status
    status VARCHAR(20) DEFAULT 'PENDING',  -- 'PENDING', 'APPLIED', 'REJECTED', 'REVIEWING'
    applied_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    user_id VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_user_feedback_tenant ON user_feedback(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_user_feedback_entity ON user_feedback(entity_id);

-- -----------------------------------------------------------------------------
-- Learning Queue: Prioritized list of extraction tasks
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS learning_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES platform.tenants(id) ON DELETE CASCADE,
    
    -- What to learn
    task_type VARCHAR(50) NOT NULL,  -- 'extract_entity', 'extract_relationship', 'verify_entity', 'expand_context'
    
    -- Target information
    target_entity_type VARCHAR(100),
    target_entity_name VARCHAR(500),
    target_relationship_type VARCHAR(100),
    search_terms TEXT[],  -- Keywords to look for in documents
    
    -- Source documents to re-examine
    document_ids UUID[],
    chunk_ids UUID[],
    
    -- Priority and scheduling
    priority INTEGER DEFAULT 50,  -- 0-100, higher = more important
    priority_reason TEXT,
    
    -- Frequency tracking (same gap reported multiple times = higher priority)
    occurrence_count INTEGER DEFAULT 1,
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    
    -- Related gaps
    query_gap_ids UUID[],
    
    -- Processing status
    status VARCHAR(20) DEFAULT 'PENDING',  -- 'PENDING', 'PROCESSING', 'COMPLETED', 'FAILED'
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    error_message TEXT,
    
    -- Results
    entities_found INTEGER DEFAULT 0,
    relationships_found INTEGER DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_queue_tenant_status ON learning_queue(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_learning_queue_priority ON learning_queue(priority DESC, created_at ASC) WHERE status = 'PENDING';

-- -----------------------------------------------------------------------------
-- Learning Results: What was learned from each task
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS learning_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    learning_task_id UUID NOT NULL REFERENCES learning_queue(id) ON DELETE CASCADE,
    tenant_id UUID NOT NULL REFERENCES platform.tenants(id) ON DELETE CASCADE,
    
    -- What was found
    result_type VARCHAR(50) NOT NULL,  -- 'new_entity', 'new_relationship', 'updated_entity', 'no_change'
    
    -- Entity details (if applicable)
    entity_id UUID REFERENCES entities(id) ON DELETE SET NULL,
    entity_name VARCHAR(500),
    entity_type VARCHAR(100),
    
    -- Relationship details (if applicable)
    relationship_id UUID REFERENCES relationships(id) ON DELETE SET NULL,
    source_entity_name VARCHAR(500),
    relationship_type VARCHAR(100),
    target_entity_name VARCHAR(500),
    
    -- Source information
    source_chunk_id UUID,
    source_text TEXT,
    confidence FLOAT,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_results_task ON learning_results(learning_task_id);
CREATE INDEX IF NOT EXISTS idx_learning_results_entity ON learning_results(entity_id);

-- -----------------------------------------------------------------------------
-- Learning Patterns: Patterns discovered that improve extraction
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS learning_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES platform.tenants(id) ON DELETE CASCADE,  -- NULL = global pattern
    
    -- Pattern definition
    pattern_type VARCHAR(50) NOT NULL,  -- 'entity_pattern', 'relationship_pattern', 'section_pattern'
    pattern_name VARCHAR(200),
    pattern_regex TEXT,
    pattern_context TEXT,  -- e.g., "Found in BREAKOUT COMPANIES sections"
    
    -- What this pattern extracts
    extracts_entity_type VARCHAR(100),
    extracts_relationship_type VARCHAR(100),
    
    -- Performance metrics
    times_matched INTEGER DEFAULT 0,
    times_correct INTEGER DEFAULT 0,
    accuracy FLOAT GENERATED ALWAYS AS (
        CASE WHEN times_matched > 0 
             THEN times_correct::FLOAT / times_matched 
             ELSE 0 
        END
    ) STORED,
    
    -- Status
    status VARCHAR(20) DEFAULT 'ACTIVE',  -- 'ACTIVE', 'TESTING', 'DISABLED'
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_learning_patterns_tenant ON learning_patterns(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_learning_patterns_type ON learning_patterns(pattern_type, status);

-- -----------------------------------------------------------------------------
-- View: Learning Dashboard Summary
-- -----------------------------------------------------------------------------
CREATE OR REPLACE VIEW learning_dashboard AS
SELECT 
    t.id as tenant_id,
    t.name as vault_name,
    
    -- Gap counts
    COUNT(DISTINCT qg.id) FILTER (WHERE qg.status = 'OPEN') as open_gaps,
    COUNT(DISTINCT qg.id) FILTER (WHERE qg.status = 'RESOLVED') as resolved_gaps,
    
    -- Feedback counts
    COUNT(DISTINCT uf.id) FILTER (WHERE uf.status = 'PENDING') as pending_feedback,
    COUNT(DISTINCT uf.id) FILTER (WHERE uf.status = 'APPLIED') as applied_feedback,
    
    -- Queue counts
    COUNT(DISTINCT lq.id) FILTER (WHERE lq.status = 'PENDING') as queued_tasks,
    COUNT(DISTINCT lq.id) FILTER (WHERE lq.status = 'COMPLETED') as completed_tasks,
    
    -- Learning metrics
    COALESCE(SUM(lq.entities_found) FILTER (WHERE lq.status = 'COMPLETED'), 0) as total_entities_learned,
    COALESCE(SUM(lq.relationships_found) FILTER (WHERE lq.status = 'COMPLETED'), 0) as total_relationships_learned

FROM platform.tenants t
LEFT JOIN query_gaps qg ON qg.tenant_id = t.id
LEFT JOIN user_feedback uf ON uf.tenant_id = t.id
LEFT JOIN learning_queue lq ON lq.tenant_id = t.id
GROUP BY t.id, t.name;

-- =============================================================================
-- End Migration 018
-- =============================================================================
