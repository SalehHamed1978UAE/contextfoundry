-- =============================================================================
-- Migration 007: RFC v2 Dual-System Cognitive Architecture
-- =============================================================================
-- Purpose: Implement Ontology Foundry + Context Foundry separation
-- Conforms to: RFC v2 Dual-System Architecture (2025-12-06)
-- =============================================================================

-- =============================================================================
-- PART 1: CREATE SCHEMAS
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS ontology;
CREATE SCHEMA IF NOT EXISTS context;
CREATE SCHEMA IF NOT EXISTS shared;

-- =============================================================================
-- PART 2: LAYER 0 - IMMUTABLE META-ONTOLOGY
-- =============================================================================
-- These types define the governance substrate itself.
-- DO NOT MODIFY through Ontology Foundry. Migration-only changes.
-- =============================================================================

CREATE TABLE IF NOT EXISTS ontology.meta_ontology (
    id UUID PRIMARY KEY,
    meta_type VARCHAR(50) NOT NULL,
    meta_name VARCHAR(100) NOT NULL,
    definition JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT immutable_meta_type CHECK (meta_type IN (
        'META_TYPE',
        'META_RELATION', 
        'META_RULE',
        'META_VERSION',
        'META_LIFECYCLE'
    ))
);

-- Seed Layer 0 (immutable - run once)
INSERT INTO ontology.meta_ontology (id, meta_type, meta_name, definition) VALUES

-- What is a Type?
('00000000-0000-0000-0000-000000000001', 'META_TYPE', 'OntologyType',
 '{
    "description": "Definition of an entity type in the ontology",
    "required_properties": ["type_name", "layer", "parent_type_id", "properties_schema"],
    "lifecycle_states": ["PROPOSED", "VALIDATING", "CONTESTED", "APPROVED", "ACTIVE", "DEPRECATED"],
    "governance": "ontology_foundry"
 }'),

-- What is a Relation?
('00000000-0000-0000-0000-000000000002', 'META_RELATION', 'OntologyRelation',
 '{
    "description": "Definition of a relationship type between entity types",
    "required_properties": ["relation_type", "source_type_id", "target_type_id", "cardinality"],
    "lifecycle_states": ["PROPOSED", "APPROVED", "ACTIVE", "DEPRECATED"],
    "governance": "ontology_foundry"
 }'),

-- What is a Rule?
('00000000-0000-0000-0000-000000000003', 'META_RULE', 'ValidationRule',
 '{
    "description": "Constraint rule for validating types or instances",
    "rule_types": ["HIERARCHY", "PROPERTY", "NAMING", "NAMESPACE", "CARDINALITY"],
    "severity_levels": ["ERROR", "WARNING", "INFO"],
    "governance": "ontology_foundry"
 }'),

-- What is a Version?
('00000000-0000-0000-0000-000000000004', 'META_VERSION', 'OntologyVersion',
 '{
    "description": "Versioned snapshot of the ontology at a point in time",
    "versioning": "semantic",
    "format": "major.minor.patch",
    "governance": "ontology_foundry"
 }'),

-- What are Lifecycle States?
('00000000-0000-0000-0000-000000000005', 'META_LIFECYCLE', 'LifecycleState',
 '{
    "description": "Valid states for governed entities",
    "ontology_states": ["PROPOSED", "VALIDATING", "CONTESTED", "APPROVED", "ACTIVE", "DEPRECATED"],
    "context_states": ["STAGING", "CORROBORATED", "TRUSTED", "CONTESTED", "RETRACTED"],
    "governance": "system"
 }')

ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- PART 3: ONTOLOGY FOUNDRY TABLES
-- =============================================================================

-- Ontology Types (RFC v2 structure)
CREATE TABLE IF NOT EXISTS ontology.types (
    id UUID PRIMARY KEY,
    type_name VARCHAR(100) NOT NULL,
    layer INTEGER NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    parent_type_id UUID REFERENCES ontology.types(id),
    properties_schema JSONB NOT NULL DEFAULT '{}',
    extraction_hints JSONB,
    
    -- RFC v2 governance columns
    status VARCHAR(20) NOT NULL DEFAULT 'PROPOSED',
    confidence DECIMAL(3,2) NOT NULL DEFAULT 0.50,
    version VARCHAR(20) NOT NULL DEFAULT '0.0.1',
    
    -- Bi-temporal tracking
    valid_from TIMESTAMP NOT NULL DEFAULT NOW(),
    valid_to TIMESTAMP,
    
    -- Governance metadata
    proposed_by VARCHAR(100),
    approved_by VARCHAR(100),
    approved_at TIMESTAMP,
    
    -- Deprecation handling
    deprecation_action VARCHAR(20),
    deprecation_target_type_id UUID,
    deprecation_reason TEXT,
    deprecated_at TIMESTAMP,
    
    -- Domain tracking
    domain_id VARCHAR(10),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT valid_status CHECK (status IN (
        'PROPOSED', 'VALIDATING', 'CONTESTED', 'APPROVED', 'ACTIVE', 'DEPRECATED'
    )),
    CONSTRAINT valid_layer CHECK (layer BETWEEN 0 AND 4),
    CONSTRAINT valid_deprecation_action CHECK (deprecation_action IS NULL OR deprecation_action IN (
        'MIGRATE', 'ARCHIVE', 'DELETE'
    )),
    CONSTRAINT unique_type_name UNIQUE (type_name)
);

-- Ontology Relations (RFC v2 structure)
CREATE TABLE IF NOT EXISTS ontology.relations (
    id UUID PRIMARY KEY,
    relation_type VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    description TEXT,
    source_type_id UUID REFERENCES ontology.types(id),
    target_type_id UUID REFERENCES ontology.types(id),
    cardinality VARCHAR(20) DEFAULT 'MANY_TO_MANY',
    properties_schema JSONB DEFAULT '{}',
    
    -- RFC v2 governance columns
    status VARCHAR(20) NOT NULL DEFAULT 'PROPOSED',
    confidence DECIMAL(3,2) NOT NULL DEFAULT 0.50,
    version VARCHAR(20) NOT NULL DEFAULT '0.0.1',
    
    -- Bi-temporal tracking
    valid_from TIMESTAMP NOT NULL DEFAULT NOW(),
    valid_to TIMESTAMP,
    
    -- Governance metadata
    proposed_by VARCHAR(100),
    approved_by VARCHAR(100),
    approved_at TIMESTAMP,
    
    -- Domain tracking
    domain_id VARCHAR(10),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT valid_relation_status CHECK (status IN (
        'PROPOSED', 'APPROVED', 'ACTIVE', 'DEPRECATED'
    )),
    CONSTRAINT valid_cardinality CHECK (cardinality IN (
        'ONE_TO_ONE', 'ONE_TO_MANY', 'MANY_TO_ONE', 'MANY_TO_MANY'
    )),
    CONSTRAINT unique_relation_type UNIQUE (relation_type)
);

-- =============================================================================
-- PART 4: VALIDATION RULES (SHACL-INSPIRED)
-- =============================================================================

CREATE TABLE IF NOT EXISTS ontology.rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    rule_name VARCHAR(100) NOT NULL UNIQUE,
    rule_type VARCHAR(50) NOT NULL,
    
    target_type VARCHAR(50) NOT NULL,
    target_filter JSONB,
    
    constraint_definition JSONB NOT NULL,
    
    severity VARCHAR(10) DEFAULT 'ERROR',
    
    status VARCHAR(20) DEFAULT 'ACTIVE',
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT valid_rule_type CHECK (rule_type IN (
        'HIERARCHY_DEPTH', 'PROPERTY_REQUIRED', 'PROPERTY_TYPE',
        'NAMING_PATTERN', 'NAMESPACE_ALLOCATION', 'CARDINALITY',
        'NO_ORPHANS', 'NO_COLLISIONS', 'CUSTOM'
    )),
    CONSTRAINT valid_rule_severity CHECK (severity IN ('ERROR', 'WARNING', 'INFO')),
    CONSTRAINT valid_rule_status CHECK (status IN ('ACTIVE', 'DISABLED'))
);

-- Seed 6 base validation rules
INSERT INTO ontology.rules (rule_name, rule_type, target_type, constraint_definition, severity) VALUES

('hierarchy_minimum_depth', 'HIERARCHY_DEPTH', 'TYPE',
 '{
    "constraint": "minDepth",
    "value": 3,
    "message": "Type must have hierarchy depth >= 3 (no direct Layer 1 inheritance)"
 }',
 'ERROR'),

('type_naming_convention', 'NAMING_PATTERN', 'TYPE',
 '{
    "constraint": "pattern",
    "field": "type_name",
    "regex": "^[A-Z][a-zA-Z0-9]*$",
    "message": "Type name must be PascalCase"
 }',
 'ERROR'),

('uuid_namespace_allocation', 'NAMESPACE_ALLOCATION', 'TYPE',
 '{
    "constraint": "uuidPattern",
    "patterns": {
        "layer_0": "00000000-*",
        "layer_1": "10000000-*",
        "shared": "20000000-0000-*",
        "domain": "20000000-00[0-9][0-9]-*"
    },
    "message": "UUID must follow namespace allocation rules"
 }',
 'ERROR'),

('no_orphan_types', 'NO_ORPHANS', 'TYPE',
 '{
    "constraint": "minRelationships",
    "value": 0,
    "message": "Type should participate in at least one relationship"
 }',
 'WARNING'),

('extraction_hints_required', 'PROPERTY_REQUIRED', 'TYPE',
 '{
    "constraint": "required",
    "field": "extraction_hints",
    "allowEmpty": false,
    "message": "Type must have extraction hints for NLP pipeline"
 }',
 'WARNING'),

('valid_properties_schema', 'PROPERTY_TYPE', 'TYPE',
 '{
    "constraint": "jsonSchema",
    "field": "properties_schema",
    "message": "properties_schema must be valid JSON Schema"
 }',
 'ERROR')

ON CONFLICT (rule_name) DO UPDATE SET
    constraint_definition = EXCLUDED.constraint_definition,
    severity = EXCLUDED.severity,
    updated_at = NOW();

-- =============================================================================
-- PART 5: ONTOLOGY VERSIONING
-- =============================================================================

CREATE TABLE IF NOT EXISTS ontology.versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_number VARCHAR(20) NOT NULL,
    
    change_type VARCHAR(30) NOT NULL,
    change_target_id UUID NOT NULL,
    change_payload JSONB NOT NULL,
    
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP,
    transaction_time TIMESTAMP DEFAULT NOW(),
    
    approved_by VARCHAR(100),
    change_reason TEXT,
    
    CONSTRAINT valid_change_type CHECK (change_type IN (
        'TYPE_ADDED', 'TYPE_MODIFIED', 'TYPE_DEPRECATED',
        'RELATION_ADDED', 'RELATION_MODIFIED', 'RELATION_DEPRECATED',
        'RULE_ADDED', 'RULE_MODIFIED', 'RULE_DEPRECATED'
    ))
);

CREATE INDEX IF NOT EXISTS idx_ontology_versions_number ON ontology.versions(version_number);
CREATE INDEX IF NOT EXISTS idx_ontology_versions_valid ON ontology.versions(valid_from, valid_to);

-- =============================================================================
-- PART 6: TYPE MIGRATION MAP (for deprecation handling)
-- =============================================================================

CREATE TABLE IF NOT EXISTS ontology.type_migration_map (
    old_type_id UUID NOT NULL PRIMARY KEY,
    old_type_name VARCHAR(100) NOT NULL,
    new_type_id UUID,
    new_type_name VARCHAR(100),
    action VARCHAR(20) NOT NULL,
    migrated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT valid_migration_action CHECK (action IN ('MIGRATE', 'ARCHIVE', 'DELETE'))
);

-- =============================================================================
-- PART 7: INDEXES FOR ONTOLOGY FOUNDRY
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_ontology_types_status ON ontology.types(status);
CREATE INDEX IF NOT EXISTS idx_ontology_types_layer ON ontology.types(layer);
CREATE INDEX IF NOT EXISTS idx_ontology_types_parent ON ontology.types(parent_type_id);
CREATE INDEX IF NOT EXISTS idx_ontology_types_domain ON ontology.types(domain_id);

CREATE INDEX IF NOT EXISTS idx_ontology_relations_status ON ontology.relations(status);
CREATE INDEX IF NOT EXISTS idx_ontology_relations_source ON ontology.relations(source_type_id);
CREATE INDEX IF NOT EXISTS idx_ontology_relations_target ON ontology.relations(target_type_id);

CREATE INDEX IF NOT EXISTS idx_ontology_rules_type ON ontology.rules(rule_type);
CREATE INDEX IF NOT EXISTS idx_ontology_rules_status ON ontology.rules(status);

-- =============================================================================
-- DONE: Migration 007 Complete
-- =============================================================================
