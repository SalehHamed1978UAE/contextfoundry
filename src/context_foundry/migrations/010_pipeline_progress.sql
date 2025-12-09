-- Migration: 010_pipeline_progress
-- Description: Add pipeline_progress table for long-running ingestion tracking
-- Following Anthropic's "long-running agent harness" pattern

CREATE TYPE ingestion_step AS ENUM (
    'queued',
    'reading',
    'classifying', 
    'chunking',
    'extracting',
    'relating',
    'staging',
    'verifying',
    'promoting',
    'completed',
    'failed'
);

CREATE TABLE IF NOT EXISTS pipeline_progress (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id VARCHAR(36) UNIQUE NOT NULL,
    tenant_id VARCHAR(36) NOT NULL,
    current_step ingestion_step NOT NULL DEFAULT 'queued',
    steps_completed JSONB DEFAULT '[]'::jsonb,
    step_metadata JSONB DEFAULT '{}'::jsonb,
    started_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error TEXT,
    retry_count INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_pipeline_progress_document ON pipeline_progress(document_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_progress_tenant ON pipeline_progress(tenant_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_progress_step ON pipeline_progress(current_step);
CREATE INDEX IF NOT EXISTS idx_pipeline_progress_tenant_step ON pipeline_progress(tenant_id, current_step);
CREATE INDEX IF NOT EXISTS idx_pipeline_progress_updated ON pipeline_progress(updated_at);

COMMENT ON TABLE pipeline_progress IS 'Tracks document ingestion progress with checkpoint/resume capability';
