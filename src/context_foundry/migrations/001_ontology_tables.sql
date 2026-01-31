-- Migration 001: Ontology Architecture Tables
-- Context Foundry - Session 1, Week 0 + Week 1
-- Creates: entities_v2 (shadow), ontology_types, ontology_relations

-- ============================================
-- WEEK 0: Shadow Mode Infrastructure
-- ============================================

-- Shadow table mirrors entities with new ontology columns
CREATE TABLE IF NOT EXISTS entities_v2 (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID,
    name VARCHAR(500) NOT NULL,
    
    -- NEW: Link to ontology type (replaces string entity_type)
    entity_type_id UUID,
    -- LEGACY: Keep for migration comparison
    entity_type VARCHAR(100),
    
    lifecycle_state VARCHAR(20) DEFAULT 'STAGING',
    confidence FLOAT DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    properties JSONB DEFAULT '{}',
    description TEXT,
    
    -- Provenance
    source_document_id VARCHAR(255),
    source_section VARCHAR(255),
    source_sentence TEXT,
    extraction_event_id UUID,
    extracted_at TIMESTAMP DEFAULT NOW(),
    extraction_method VARCHAR(100),
    
    -- Lifecycle tracking
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    staged_at TIMESTAMP DEFAULT NOW(),
    promoted_at TIMESTAMP,
    promoted_by UUID,
    archived_at TIMESTAMP,
    last_validated_at TIMESTAMP,
    
    -- NEW: Corroboration tracking (per spec)
    corroboration_count INT DEFAULT 1,
    last_corroborated_at TIMESTAMP DEFAULT NOW(),
    
    -- Temporal tracking
    valid_from TIMESTAMP DEFAULT NOW(),
    valid_to TIMESTAMP,
    superseded_by UUID,
    change_reason TEXT,
    
    validation_status VARCHAR(20) DEFAULT 'PENDING'
);

CREATE INDEX IF NOT EXISTS idx_entities_v2_tenant ON entities_v2(tenant_id);
CREATE INDEX IF NOT EXISTS idx_entities_v2_type_id ON entities_v2(entity_type_id);
CREATE INDEX IF NOT EXISTS idx_entities_v2_state ON entities_v2(lifecycle_state);

-- ============================================
-- WEEK 1: Ontology Type System
-- ============================================

-- Ontology Types: Four-layer type hierarchy
CREATE TABLE IF NOT EXISTS ontology_types (
    id UUID PRIMARY KEY,
    type_name VARCHAR(100) NOT NULL,
    tenant_id UUID,
    layer INT NOT NULL CHECK (layer BETWEEN 0 AND 3),
    display_name VARCHAR(200),
    description TEXT,
    parent_type_id UUID REFERENCES ontology_types(id),
    properties_schema JSONB NOT NULL DEFAULT '{}',
    
    -- NEW: Origin tracking (per user request)
    origin VARCHAR(50) DEFAULT 'system',
    -- Values: 'system', 'domain_template', 'tenant_extension', 'fibo_import', 'fhir_import', 'ai_induced'
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    is_deprecated BOOLEAN DEFAULT FALSE,
    deprecated_at TIMESTAMP,
    version INT DEFAULT 1,
    
    UNIQUE(tenant_id, type_name)
);

CREATE INDEX IF NOT EXISTS idx_ontology_types_tenant_layer ON ontology_types(tenant_id, layer);
CREATE INDEX IF NOT EXISTS idx_ontology_types_parent ON ontology_types(parent_type_id);
CREATE INDEX IF NOT EXISTS idx_ontology_types_origin ON ontology_types(origin);

-- Ontology Relations: Relationship type definitions with semantics
CREATE TABLE IF NOT EXISTS ontology_relations (
    id UUID PRIMARY KEY,
    relation_name VARCHAR(100) NOT NULL,
    tenant_id UUID,
    layer INT NOT NULL CHECK (layer BETWEEN 0 AND 3),
    source_type_id UUID NOT NULL REFERENCES ontology_types(id),
    target_type_id UUID NOT NULL REFERENCES ontology_types(id),
    cardinality VARCHAR(20) CHECK (cardinality IN ('ONE_TO_ONE', 'ONE_TO_MANY', 'MANY_TO_ONE', 'MANY_TO_MANY')),
    description TEXT,
    properties_schema JSONB DEFAULT '{}',
    
    -- Relation semantics for traversal and reasoning
    semantics JSONB DEFAULT '{}',
    -- Format: {"traversal_mode": "impact", "direction": "forward", "weight": 1.0, "transitive": true}
    
    -- Extraction hints for LLM
    extraction_hints JSONB DEFAULT '{}',
    -- Format: {"trigger_phrases": ["depends on", "uses"], "anti_patterns": ["might use"]}
    
    -- Symbolic constraints (Phase 2 - SHACL-like rules)
    constraints JSONB DEFAULT '{}',
    -- Format: {"min_cardinality": 0, "max_cardinality": null, "required": false}
    
    -- Origin tracking
    origin VARCHAR(50) DEFAULT 'domain_template',
    
    is_deprecated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(tenant_id, relation_name, source_type_id, target_type_id)
);

CREATE INDEX IF NOT EXISTS idx_ontology_relations_source ON ontology_relations(source_type_id);
CREATE INDEX IF NOT EXISTS idx_ontology_relations_target ON ontology_relations(target_type_id);
CREATE INDEX IF NOT EXISTS idx_ontology_relations_name ON ontology_relations(relation_name);

-- Extraction events audit table (enhanced)
CREATE TABLE IF NOT EXISTS extraction_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID,
    source_document_id UUID,
    source_text TEXT,
    
    model_used VARCHAR(100) NOT NULL,
    prompt_template_version VARCHAR(50),
    schema_version INT,
    extraction_mode VARCHAR(20) DEFAULT 'legacy',
    
    raw_extraction JSONB,
    validated_entities JSONB,
    rejected_entities JSONB,
    rejection_reasons JSONB,
    
    -- Track what the LLM skipped and why
    skipped_entities JSONB,
    skip_reasons JSONB,
    
    entities_extracted INT DEFAULT 0,
    entities_validated INT DEFAULT 0,
    entities_rejected INT DEFAULT 0,
    validation_errors JSONB,
    
    extraction_started_at TIMESTAMP,
    extraction_completed_at TIMESTAMP,
    validation_completed_at TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_extraction_events_tenant ON extraction_events(tenant_id);
CREATE INDEX IF NOT EXISTS idx_extraction_events_mode ON extraction_events(extraction_mode);
CREATE INDEX IF NOT EXISTS idx_extraction_events_doc ON extraction_events(source_document_id);

-- Tenant domain template installations
CREATE TABLE IF NOT EXISTS tenant_domain_templates (
    tenant_id UUID NOT NULL,
    template_name VARCHAR(100) NOT NULL,
    template_version VARCHAR(50) NOT NULL,
    installed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (tenant_id, template_name)
);
