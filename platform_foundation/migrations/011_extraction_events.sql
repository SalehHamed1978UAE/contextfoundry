-- Migration: Add extraction events tracking
-- Created: 2026-01-25

-- Add timestamp columns to documents table
ALTER TABLE platform.documents 
ADD COLUMN IF NOT EXISTS single_extracted_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS multi_extracted_at TIMESTAMP;

-- Create extraction events log table
CREATE TABLE IF NOT EXISTS platform.extraction_events (
    id SERIAL PRIMARY KEY,
    vault_id UUID NOT NULL,
    vault_name VARCHAR(255),
    document_id UUID,
    document_name VARCHAR(255),
    event_type VARCHAR(50) NOT NULL,
    extraction_level VARCHAR(20),
    details TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_extraction_events_vault ON platform.extraction_events(vault_id);
CREATE INDEX IF NOT EXISTS idx_extraction_events_created ON platform.extraction_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_extraction_events_type ON platform.extraction_events(event_type);
