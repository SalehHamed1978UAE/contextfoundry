-- =============================================================================
-- Migration 017: Extraction Job Tracking
-- =============================================================================
-- Purpose: Track extraction jobs with status, progress, retries, and verification
-- Date: 2026-01-13
-- =============================================================================

CREATE TABLE IF NOT EXISTS extraction_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES platform.tenants(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES platform.documents(id) ON DELETE CASCADE,
    
    -- Status tracking
    status VARCHAR(20) DEFAULT 'PENDING' 
        CHECK (status IN ('PENDING', 'RUNNING', 'COMPLETE', 'PARTIAL', 'FAILED', 'TIMEOUT')),
    
    -- Progress tracking (for UI progress bar)
    chunks_total INTEGER DEFAULT 0,
    chunks_processed INTEGER DEFAULT 0,
    
    -- Results
    entities_extracted INTEGER DEFAULT 0,
    relationships_extracted INTEGER DEFAULT 0,
    
    -- Timing
    created_at TIMESTAMP DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    timeout_at TIMESTAMP,
    
    -- Retry handling
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,
    error_message TEXT,
    
    -- Cache optimization (skip re-extraction if unchanged)
    content_hash VARCHAR(64),
    
    -- Metadata
    extraction_config JSONB DEFAULT '{}'
);

-- Prevent duplicate active jobs for same document
CREATE UNIQUE INDEX IF NOT EXISTS idx_extraction_jobs_active_document 
ON extraction_jobs(document_id) 
WHERE status IN ('PENDING', 'RUNNING');

-- Query by tenant and status
CREATE INDEX IF NOT EXISTS idx_extraction_jobs_tenant_status 
ON extraction_jobs(tenant_id, status, created_at DESC);

-- Query job history for a document
CREATE INDEX IF NOT EXISTS idx_extraction_jobs_document_history 
ON extraction_jobs(document_id, created_at DESC);

-- Find timed-out jobs
CREATE INDEX IF NOT EXISTS idx_extraction_jobs_timeout 
ON extraction_jobs(timeout_at) 
WHERE status = 'RUNNING';

-- =============================================================================
-- Helper view for document status
-- =============================================================================
CREATE OR REPLACE VIEW document_extraction_status AS
SELECT 
    d.id as document_id,
    d.name as document_name,
    d.tenant_id,
    j.id as job_id,
    j.status,
    j.chunks_total,
    j.chunks_processed,
    CASE 
        WHEN j.chunks_total > 0 
        THEN (j.chunks_processed * 100 / j.chunks_total) 
        ELSE 0 
    END as progress_pct,
    j.entities_extracted,
    j.relationships_extracted,
    j.started_at,
    j.completed_at,
    j.error_message,
    j.retry_count
FROM platform.documents d
LEFT JOIN LATERAL (
    SELECT * FROM extraction_jobs ej
    WHERE ej.document_id = d.id
    ORDER BY ej.created_at DESC
    LIMIT 1
) j ON true;

-- =============================================================================
-- End Migration 017
-- =============================================================================
