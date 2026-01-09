-- Stage 2: Context-Attached Knowledge
-- Add context fields to relationships table

ALTER TABLE relationships ADD COLUMN IF NOT EXISTS provenance_text TEXT;
ALTER TABLE relationships ADD COLUMN IF NOT EXISTS event_context TEXT;
ALTER TABLE relationships ADD COLUMN IF NOT EXISTS qualifiers JSONB;

CREATE INDEX IF NOT EXISTS idx_relationships_temporal 
ON relationships (tenant_id, valid_from, valid_to);

COMMENT ON COLUMN relationships.valid_from IS 'When this relationship became true';
COMMENT ON COLUMN relationships.valid_to IS 'When this relationship ended (NULL = still active)';
COMMENT ON COLUMN relationships.provenance_text IS 'The actual text that supports this relationship';
COMMENT ON COLUMN relationships.event_context IS 'The situation or event this relationship belongs to';
COMMENT ON COLUMN relationships.qualifiers IS 'Additional context (role details, conditions, etc.)';
