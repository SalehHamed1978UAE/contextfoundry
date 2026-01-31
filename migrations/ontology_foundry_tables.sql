-- ============================================================
-- ONTOLOGY CANDIDATES TABLE
-- Stores detected patterns that aren't in the current schema
-- ============================================================

CREATE TABLE IF NOT EXISTS ontology_candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    
    -- What was detected
    candidate_type VARCHAR(50) NOT NULL,      -- 'RELATIONSHIP' | 'ENTITY' | 'ATTRIBUTE'
    proposed_name VARCHAR(100) NOT NULL,      -- Name as proposed by LLM
    normalized_name VARCHAR(100) NOT NULL,    -- Canonical name after synonym mapping
    
    -- For relationships
    source_entity_type VARCHAR(100),          -- e.g., 'ORGANIZATION'
    target_entity_type VARCHAR(100),          -- e.g., 'COMPANY'
    
    -- Evidence
    detected_properties JSONB DEFAULT '{}',   -- {amount: 'currency', date: 'date', ...}
    example_mentions JSONB DEFAULT '[]',      -- [{text: '...', document_id: '...'}, ...]
    document_count INT DEFAULT 1,
    mention_count INT DEFAULT 1,
    
    -- Confidence
    confidence_score FLOAT DEFAULT 0.5,
    
    -- Governance
    status VARCHAR(20) DEFAULT 'PENDING',     -- 'PENDING'|'APPROVED'|'REJECTED'|'MERGED'
    reviewed_by UUID,
    reviewed_at TIMESTAMP,
    merged_into UUID REFERENCES ontology_candidates(id),
    
    -- Scope
    is_global BOOLEAN DEFAULT FALSE,          -- Can be promoted to all tenants
    
    -- Cleanup
    expires_at TIMESTAMP,                     -- Auto-delete pending candidates after this
    
    -- Metadata
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_candidate_type CHECK (candidate_type IN ('RELATIONSHIP', 'ENTITY', 'ATTRIBUTE')),
    CONSTRAINT valid_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'MERGED'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_ontology_candidates_tenant_status 
    ON ontology_candidates(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_ontology_candidates_normalized_name 
    ON ontology_candidates(tenant_id, normalized_name);
CREATE INDEX IF NOT EXISTS idx_ontology_candidates_confidence 
    ON ontology_candidates(tenant_id, confidence_score DESC);
CREATE INDEX IF NOT EXISTS idx_ontology_candidates_expires 
    ON ontology_candidates(expires_at) WHERE status = 'PENDING';

-- ============================================================
-- PENDING EXTRACTIONS TABLE
-- Stores actual extracted data waiting for schema approval
-- ============================================================

CREATE TABLE IF NOT EXISTS pending_extractions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    candidate_id UUID NOT NULL REFERENCES ontology_candidates(id) ON DELETE CASCADE,
    
    -- The actual extracted data
    source_entity_name VARCHAR(255),
    source_entity_type VARCHAR(100),
    target_entity_name VARCHAR(255),
    target_entity_type VARCHAR(100),
    relationship_type VARCHAR(100),           -- The normalized type name
    properties JSONB DEFAULT '{}',
    
    -- Provenance
    document_id UUID,
    chunk_id UUID,
    chunk_text TEXT,                          -- The text that triggered this extraction
    
    -- Status
    status VARCHAR(20) DEFAULT 'PENDING',     -- 'PENDING' | 'APPLIED' | 'DISCARDED'
    applied_at TIMESTAMP,                     -- When backfilled to KG
    
    created_at TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT valid_extraction_status CHECK (status IN ('PENDING', 'APPLIED', 'DISCARDED'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_pending_extractions_tenant 
    ON pending_extractions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_pending_extractions_candidate 
    ON pending_extractions(candidate_id);
CREATE INDEX IF NOT EXISTS idx_pending_extractions_status 
    ON pending_extractions(status);
