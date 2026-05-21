-- ============================================
-- CONTEXT FOUNDRY DATABASE SCHEMA
-- Tri-Memory Architecture: Semantic + Episodic + Symbolic
-- ============================================

-- ============================================
-- SEMANTIC MEMORY (Knowledge Graph Metadata)
-- ============================================

-- Graph lifecycle states (actual graph stored in Apache AGE)
CREATE TABLE IF NOT EXISTS graph_lifecycle (
    entity_id UUID PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    lifecycle_state VARCHAR(20) NOT NULL CHECK (lifecycle_state IN ('STAGING', 'TRUSTED', 'ARCHIVED')),
    confidence FLOAT NOT NULL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),

    -- Provenance
    source_document_id VARCHAR(255),
    source_section TEXT,
    source_sentence TEXT,
    source_span_start INT,
    source_span_end INT,
    extracted_text TEXT,
    extraction_method VARCHAR(50),
    extraction_confidence FLOAT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    promoted_at TIMESTAMP,
    archived_at TIMESTAMP,
    last_accessed TIMESTAMP,
    access_count INT DEFAULT 0,

    -- Conflict tracking
    conflicts JSONB DEFAULT '[]'::jsonb,
    resolved BOOLEAN DEFAULT true
);

CREATE INDEX idx_lifecycle_state ON graph_lifecycle(lifecycle_state);
CREATE INDEX idx_entity_type ON graph_lifecycle(entity_type);
CREATE INDEX idx_confidence ON graph_lifecycle(confidence);
CREATE INDEX idx_resolved ON graph_lifecycle(resolved);

-- Relationship metadata
CREATE TABLE IF NOT EXISTS relationship_metadata (
    relationship_id UUID PRIMARY KEY,
    source_entity_id UUID NOT NULL,
    target_entity_id UUID NOT NULL,
    relationship_type VARCHAR(50) NOT NULL,
    lifecycle_state VARCHAR(20) NOT NULL CHECK (lifecycle_state IN ('STAGING', 'TRUSTED', 'ARCHIVED')),
    confidence FLOAT NOT NULL DEFAULT 0.5,

    -- Provenance
    source_document_id VARCHAR(255),
    source_sentence TEXT,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (source_entity_id) REFERENCES graph_lifecycle(entity_id),
    FOREIGN KEY (target_entity_id) REFERENCES graph_lifecycle(entity_id)
);

CREATE INDEX idx_rel_source ON relationship_metadata(source_entity_id);
CREATE INDEX idx_rel_target ON relationship_metadata(target_entity_id);
CREATE INDEX idx_rel_type ON relationship_metadata(relationship_type);
CREATE INDEX idx_rel_lifecycle ON relationship_metadata(lifecycle_state);

-- ============================================
-- EPISODIC MEMORY - CORPUS (Long-term)
-- ============================================

CREATE TABLE IF NOT EXISTS document_embeddings (
    id UUID PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL,
    document_type VARCHAR(50) NOT NULL, -- 'incident', 'runbook', 'cmdb_entry'
    document_title TEXT,
    chunk_text TEXT NOT NULL,
    chunk_index INT,

    -- Vector embedding (384 dimensions for BGE-small)
    embedding vector(384),

    -- Metadata
    entity_ids UUID[] DEFAULT ARRAY[]::UUID[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_accessed TIMESTAMP,
    access_count INT DEFAULT 0
);

CREATE INDEX idx_doc_id ON document_embeddings(document_id);
CREATE INDEX idx_doc_type ON document_embeddings(document_type);
CREATE INDEX idx_embedding_cosine ON document_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ============================================
-- EPISODIC MEMORY - SESSION (Short-term)
-- ============================================

-- Session memory is primarily stored in Redis for fast access
-- This table is for persistence/logging only
CREATE TABLE IF NOT EXISTS session_memory (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL,
    query_text TEXT NOT NULL,
    response_text TEXT,
    context_bundle_id UUID,

    -- Entities accessed in this session
    accessed_entities UUID[],

    -- Session lifecycle
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,

    -- Query metadata
    latency_ms INT,
    success BOOLEAN
);

CREATE INDEX idx_session_id ON session_memory(session_id);
CREATE INDEX idx_session_created ON session_memory(created_at);

-- ============================================
-- SYMBOLIC MEMORY (Rules)
-- ============================================

CREATE TABLE IF NOT EXISTS symbolic_rules (
    id UUID PRIMARY KEY,
    rule_name VARCHAR(255) NOT NULL UNIQUE,
    rule_type VARCHAR(50) NOT NULL, -- 'invariant', 'safety', 'escalation', 'validation'

    -- Rule definition
    rule_expression TEXT NOT NULL, -- JSON or Python expression
    rule_description TEXT,

    -- Priority and application
    priority INT DEFAULT 0, -- higher number = higher priority
    enabled BOOLEAN DEFAULT true,

    -- Entity/relationship scoping
    applies_to_entity_types VARCHAR(50)[],
    applies_to_relationship_types VARCHAR(50)[],

    -- Tracking
    times_applied INT DEFAULT 0,
    times_violated INT DEFAULT 0,
    last_applied TIMESTAMP,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_rule_type ON symbolic_rules(rule_type);
CREATE INDEX idx_rule_enabled ON symbolic_rules(enabled);
CREATE INDEX idx_rule_priority ON symbolic_rules(priority DESC);

-- ============================================
-- FEEDBACK & LEARNING LOOP
-- ============================================

CREATE TABLE IF NOT EXISTS feedback_records (
    id UUID PRIMARY KEY,

    -- What was evaluated
    bundle_id UUID,
    query_text TEXT NOT NULL,
    response_text TEXT NOT NULL,

    -- Human judgment
    judgment VARCHAR(20) NOT NULL CHECK (judgment IN ('correct', 'incorrect', 'partial', 'uncertain')),
    error_type VARCHAR(50), -- 'wrong_entity', 'missing_context', 'wrong_relationship', etc.
    human_correction TEXT,
    severity VARCHAR(20) CHECK (severity IN ('critical', 'major', 'minor')),

    -- Context for learning
    confidence_was FLOAT,
    entities_involved UUID[],
    rules_applied UUID[],

    -- Learning status
    processed BOOLEAN DEFAULT FALSE,
    learning_action TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    processed_at TIMESTAMP
);

CREATE INDEX idx_feedback_judgment ON feedback_records(judgment);
CREATE INDEX idx_feedback_processed ON feedback_records(processed);
CREATE INDEX idx_feedback_error_type ON feedback_records(error_type);

-- Learning log (tracks threshold adjustments and pattern discoveries)
CREATE TABLE IF NOT EXISTS learning_log (
    id UUID PRIMARY KEY,
    cycle_date DATE NOT NULL,

    -- Aggregate statistics
    total_feedback INT,
    correct_count INT,
    incorrect_count INT,
    partial_count INT,
    uncertain_count INT,

    -- Calibration metrics
    calibration_error FLOAT,
    confidence_buckets JSONB, -- {"0.0-0.5": {"predicted": 0.25, "actual": 0.3}, ...}

    -- Actions taken
    threshold_adjustments JSONB,
    patterns_identified JSONB,

    -- Recommendations
    recommendations TEXT[],

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_learning_cycle_date ON learning_log(cycle_date);

-- ============================================
-- CONTEXT BUNDLES (Query Execution Artifacts)
-- ============================================

CREATE TABLE IF NOT EXISTS context_bundles (
    id UUID PRIMARY KEY,
    query_text TEXT NOT NULL,
    session_id UUID,

    -- Retrieved context
    semantic_entities JSONB, -- entities from graph
    semantic_relationships JSONB, -- relationships from graph
    episodic_documents JSONB, -- similar documents from vector search
    symbolic_rules_applied JSONB, -- rules that applied
    session_context JSONB, -- recent conversation turns

    -- Uncertainty report
    overall_confidence FLOAT,
    recommendation VARCHAR(20), -- 'proceed', 'caution', 'insufficient_context'
    high_confidence_facts INT,
    medium_confidence_facts INT,
    low_confidence_facts INT,
    low_confidence_items JSONB,
    unresolved_entities TEXT[],
    missing_relationships TEXT[],
    stale_facts JSONB,
    uncertainty_reasons TEXT[],

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    retrieval_latency_ms INT,
    reasoning_latency_ms INT
);

CREATE INDEX idx_bundle_session ON context_bundles(session_id);
CREATE INDEX idx_bundle_created ON context_bundles(created_at);

-- ============================================
-- QUERY RESPONSES
-- ============================================

CREATE TABLE IF NOT EXISTS query_responses (
    id UUID PRIMARY KEY,
    bundle_id UUID NOT NULL,

    -- Response
    answer TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    confidence_level VARCHAR(20) NOT NULL, -- 'high', 'medium', 'low', 'very_low'

    -- Uncertainty details
    uncertain_facts TEXT[],
    uncertainty_reasons TEXT[],
    would_help TEXT[], -- what would reduce uncertainty
    caveats TEXT[],

    -- Evidence chain
    evidence_chain JSONB NOT NULL, -- [{fact, source, confidence}, ...]

    -- Validation
    rules_checked UUID[],
    rules_passed BOOLEAN,
    validation_failures JSONB,

    -- Alternatives (if confidence < 0.7)
    alternatives JSONB,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total_latency_ms INT,

    FOREIGN KEY (bundle_id) REFERENCES context_bundles(id)
);

CREATE INDEX idx_response_bundle ON query_responses(bundle_id);
CREATE INDEX idx_response_confidence ON query_responses(confidence);
CREATE INDEX idx_response_created ON query_responses(created_at);

-- ============================================
-- UTILITY FUNCTIONS
-- ============================================

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER update_graph_lifecycle_updated_at BEFORE UPDATE ON graph_lifecycle
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_relationship_metadata_updated_at BEFORE UPDATE ON relationship_metadata
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_symbolic_rules_updated_at BEFORE UPDATE ON symbolic_rules
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
