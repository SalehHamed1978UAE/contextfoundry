-- Migration 013: Reference Ontologies and Canonical Relations
-- Implements document-aware, ontology-centric extraction pipeline

-- Reference ontologies per document type per tenant
CREATE TABLE IF NOT EXISTS ontology.reference_ontologies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    document_type VARCHAR(100) NOT NULL,
    entity_types JSONB NOT NULL DEFAULT '[]',
    relationship_types JSONB NOT NULL DEFAULT '[]',
    usage_count INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, document_type)
);

-- Canonical relations with semantic embeddings for clustering
CREATE TABLE IF NOT EXISTS ontology.canonical_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    definition TEXT NOT NULL,
    embedding vector(1536),
    source_predicates JSONB NOT NULL DEFAULT '[]',
    source_types JSONB DEFAULT '[]',
    target_types JSONB DEFAULT '[]',
    usage_count INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Canonical entity types with semantic embeddings
CREATE TABLE IF NOT EXISTS ontology.canonical_entity_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name VARCHAR(100) NOT NULL,
    definition TEXT NOT NULL,
    embedding vector(1536),
    source_types JSONB NOT NULL DEFAULT '[]',
    usage_count INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(tenant_id, name)
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ref_ontologies_tenant_doctype 
    ON ontology.reference_ontologies(tenant_id, document_type);

CREATE INDEX IF NOT EXISTS idx_canonical_relations_tenant 
    ON ontology.canonical_relations(tenant_id);

CREATE INDEX IF NOT EXISTS idx_canonical_entity_types_tenant 
    ON ontology.canonical_entity_types(tenant_id);

-- Vector similarity index for embedding lookups
CREATE INDEX IF NOT EXISTS idx_canonical_relations_embedding 
    ON ontology.canonical_relations USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_canonical_entity_types_embedding 
    ON ontology.canonical_entity_types USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Add predicate_definition and predicate_embedding to relationships table
ALTER TABLE public.relationships 
    ADD COLUMN IF NOT EXISTS source_predicate VARCHAR(200),
    ADD COLUMN IF NOT EXISTS predicate_definition TEXT,
    ADD COLUMN IF NOT EXISTS predicate_embedding vector(1536);

COMMENT ON TABLE ontology.reference_ontologies IS 'Per-tenant, per-document-type ontology schemas that grow organically from document processing';
COMMENT ON TABLE ontology.canonical_relations IS 'Canonical relationship types with semantic definitions for embedding-based clustering';
COMMENT ON TABLE ontology.canonical_entity_types IS 'Canonical entity types with semantic definitions for embedding-based clustering';
