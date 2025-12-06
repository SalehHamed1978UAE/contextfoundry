-- Migration 010: Schema Versioning & Type Migrations (RFC v2 §8)
-- Enables query translation for deprecated types and version history tracking

-- Track version history of each type
CREATE TABLE IF NOT EXISTS ontology.type_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_id UUID NOT NULL REFERENCES ontology.types(id) ON DELETE CASCADE,
    version VARCHAR(20) NOT NULL,
    schema_snapshot JSONB NOT NULL,
    valid_from TIMESTAMP NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMP,
    migration_notes TEXT,
    breaking_change BOOLEAN DEFAULT FALSE,
    created_by UUID REFERENCES shared.users(id),
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT unique_type_version UNIQUE (type_id, version)
);

-- Track migrations between types (rename, merge, split)
CREATE TABLE IF NOT EXISTS ontology.type_migrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type_id UUID NOT NULL REFERENCES ontology.types(id),
    target_type_id UUID NOT NULL REFERENCES ontology.types(id),
    migration_type VARCHAR(20) NOT NULL CHECK (migration_type IN ('RENAME', 'MERGE', 'SPLIT', 'SUPERSEDE')),
    mapping_rules JSONB,
    executed_at TIMESTAMP,
    entities_migrated INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT no_self_migration CHECK (source_type_id != target_type_id)
);

-- Index for fast lineage queries
CREATE INDEX IF NOT EXISTS idx_type_versions_type_id ON ontology.type_versions(type_id);
CREATE INDEX IF NOT EXISTS idx_type_versions_valid_range ON ontology.type_versions(valid_from, valid_until);
CREATE INDEX IF NOT EXISTS idx_type_migrations_source ON ontology.type_migrations(source_type_id);
CREATE INDEX IF NOT EXISTS idx_type_migrations_target ON ontology.type_migrations(target_type_id);

-- View for easy deprecated-to-current type lookup
-- Includes both DEPRECATED and ARCHIVED source types so translations persist after migration
CREATE OR REPLACE VIEW ontology.type_translation AS
SELECT 
    s.type_name as deprecated_name,
    t.type_name as current_name,
    m.migration_type,
    m.executed_at
FROM ontology.type_migrations m
JOIN ontology.types s ON m.source_type_id = s.id
JOIN ontology.types t ON m.target_type_id = t.id
WHERE s.status IN ('DEPRECATED', 'ARCHIVED')
  AND t.status = 'ACTIVE';
