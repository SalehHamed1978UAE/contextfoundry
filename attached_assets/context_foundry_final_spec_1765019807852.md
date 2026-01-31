# Context Foundry: Ontology Architecture Implementation Specification
## Final Version — Incorporating All Reviewer Feedback

**Version:** 2.0 (Final)  
**Status:** Ready for Implementation  
**Reviewers:** Claude, ChatGPT, Perplexity, Manus  
**Verdict:** Unanimous approval with corrections applied

---

## Executive Summary

This specification defines the complete implementation of Context Foundry's modular ontology architecture, using IT Operations as the first domain template. The goal is to build a production-ready system that prevents semantic pollution, enables constrained LLM extraction, and delivers the three-tier query responses (Confirmed / Inferred / Boundaries).

**Core Principle: Schema is Law.** The ontology is not descriptive — it is the execution grammar for extraction, traversal, and reasoning. Every fact must pass through this grammar.

---

## Consolidated Feedback Summary

| Source | Critical Issues Fixed | Recommendations Incorporated |
|--------|----------------------|------------------------------|
| **Manus** | SQL bug in validate_relationship(), SQL injection prevention | RLS policies, dynamic prompt generation, enhanced conflict resolution |
| **Perplexity** | — | RLS policies, metrics/monitoring, shadow mode deployment, O(n) type checking optimization |
| **ChatGPT** | — | Relation semantics fields, tenant extension guardrails, type-weighted promotion thresholds |

---

## Part 0: Week 0 — Shadow Mode Deployment Plan

**NEW SECTION** (Per Perplexity feedback: "No feature flag for cutover")

Before Week 1 begins, establish the migration strategy:

### 0.1 Shadow Mode Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Document Ingestion                        │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
              ┌───────────────┴───────────────┐
              │                               │
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│   OLD Extraction Path    │     │   NEW Extraction Path    │
│   (unconstrained)        │     │   (constrained)          │
│   WRITES to entities     │     │   WRITES to entities_v2  │
└─────────────────────────┘     └─────────────────────────┘
              │                               │
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────┐
│   entities (current)     │     │   entities_v2 (shadow)   │
│   Active, queryable      │     │   Metrics only           │
└─────────────────────────┘     └─────────────────────────┘
```

### 0.2 Feature Flags

```python
# src/context_foundry/config/feature_flags.py

from enum import Enum

class ExtractionMode(str, Enum):
    LEGACY = "legacy"           # Old unconstrained extraction
    SHADOW = "shadow"           # Both paths, compare results
    CONSTRAINED = "constrained" # New path only

# Environment variable controls
EXTRACTION_MODE = os.getenv("CF_EXTRACTION_MODE", ExtractionMode.LEGACY.value)
SHADOW_WRITE_ENABLED = os.getenv("CF_SHADOW_WRITE", "false").lower() == "true"
```

### 0.3 Shadow Mode Comparison Metrics

```python
# Log comparison metrics between old and new extraction
async def compare_extractions(old_result, new_result, document_id: UUID):
    metrics = {
        "document_id": str(document_id),
        "old_entity_count": len(old_result.entities),
        "new_entity_count": len(new_result.entities),
        "old_types": [e.entity_type for e in old_result.entities],
        "new_types": [e.entity_type for e in new_result.entities],
        "new_rejected_count": len(new_result.rejected_entities),
        "overlap_ratio": calculate_overlap(old_result, new_result),
    }
    logger.info("shadow_extraction_comparison", **metrics)
    prometheus_shadow_comparison.observe(metrics)
```

### 0.4 Cutover Checklist

| Phase | Duration | Criteria to Proceed |
|-------|----------|---------------------|
| Shadow Mode | 1 week | < 5% precision drop, < 2% false rejections |
| Parallel Write | 3 days | New path stable, no errors |
| Cutover | 1 day | Switch feature flag, monitor |
| Cleanup | 1 week | Remove old path, archive shadow tables |

---

## Part 1: Four-Layer Ontology Model

### Layer 0: Meta-Core (System Primitives)

Immutable, hardcoded into Context Foundry. Never modified by tenants.

```sql
-- Layer 0: Meta-Core Types (immutable)
INSERT INTO ontology_types (id, type_name, layer, display_name, description, parent_type_id, properties_schema) VALUES
('00000000-0000-0000-0000-000000000001', 'Entity', 0, 'Entity', 'Abstract root for all nodes in the graph', NULL, 
 '{"type": "object", "properties": {"id": {"type": "string", "format": "uuid"}, "name": {"type": "string"}, "description": {"type": "string"}, "created_at": {"type": "string", "format": "date-time"}, "updated_at": {"type": "string", "format": "date-time"}}, "required": ["id", "name"]}'),

('00000000-0000-0000-0000-000000000002', 'Event', 0, 'Event', 'An occurrence at a point in time', NULL,
 '{"type": "object", "properties": {"id": {"type": "string", "format": "uuid"}, "name": {"type": "string"}, "timestamp": {"type": "string", "format": "date-time"}, "duration_seconds": {"type": "integer"}}, "required": ["id", "timestamp"]}'),

('00000000-0000-0000-0000-000000000003', 'Record', 0, 'Record', 'A piece of evidence or documentation', NULL,
 '{"type": "object", "properties": {"id": {"type": "string", "format": "uuid"}, "name": {"type": "string"}, "source_uri": {"type": "string"}, "ingested_at": {"type": "string", "format": "date-time"}}, "required": ["id", "name"]}'),

('00000000-0000-0000-0000-000000000004', 'Relation', 0, 'Relation', 'Abstract root for all edges', NULL,
 '{"type": "object", "properties": {"source_id": {"type": "string", "format": "uuid"}, "target_id": {"type": "string", "format": "uuid"}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}}, "required": ["source_id", "target_id"]}');
```

### Layer 1: Common Core (Universal Concepts)

```sql
INSERT INTO ontology_types (id, type_name, layer, display_name, description, parent_type_id, properties_schema) VALUES
('10000000-0000-0000-0000-000000000001', 'Asset', 1, 'Asset', 'A physical or digital resource with value', 
 '00000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"asset_type": {"type": "string"}, "status": {"type": "string", "enum": ["active", "inactive", "deprecated", "planned"]}, "owner_id": {"type": "string", "format": "uuid"}}}'),

('10000000-0000-0000-0000-000000000002', 'Agent', 1, 'Agent', 'An actor that can perform actions',
 '00000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"agent_type": {"type": "string", "enum": ["person", "organization", "software", "team"]}}}'),

('10000000-0000-0000-0000-000000000003', 'Location', 1, 'Location', 'A physical or logical place',
 '00000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"location_type": {"type": "string", "enum": ["physical", "logical", "virtual"]}, "coordinates": {"type": "object"}, "address": {"type": "string"}}}'),

('10000000-0000-0000-0000-000000000004', 'Person', 1, 'Person', 'A human individual',
 '10000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"email": {"type": "string", "format": "email"}, "role": {"type": "string"}, "department": {"type": "string"}}}'),

('10000000-0000-0000-0000-000000000005', 'Organization', 1, 'Organization', 'A company, team, or organizational unit',
 '10000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"org_type": {"type": "string"}, "parent_org_id": {"type": "string", "format": "uuid"}}}'),

('10000000-0000-0000-0000-000000000006', 'Document', 1, 'Document', 'A written or digital document',
 '00000000-0000-0000-0000-000000000003',
 '{"type": "object", "properties": {"document_type": {"type": "string"}, "file_path": {"type": "string"}, "content_hash": {"type": "string"}}}');
```

### Layer 2: IT Operations Domain Template

```sql
INSERT INTO ontology_types (id, type_name, layer, display_name, description, parent_type_id, properties_schema, tenant_id) VALUES
('20000000-0001-0000-0000-000000000001', 'Service', 2, 'Service', 'A software service or application',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"service_type": {"type": "string", "enum": ["api", "web", "backend", "worker", "gateway", "database", "cache", "queue", "storage"]}, "tier": {"type": "string", "enum": ["tier1", "tier2", "tier3"]}, "slo_target": {"type": "number"}, "repository_url": {"type": "string"}, "documentation_url": {"type": "string"}}}',
 NULL),

('20000000-0001-0000-0000-000000000002', 'Database', 2, 'Database', 'A database or data store',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"database_type": {"type": "string", "enum": ["postgresql", "mysql", "mongodb", "redis", "elasticsearch", "dynamodb", "other"]}, "version": {"type": "string"}, "cluster_name": {"type": "string"}, "replica_count": {"type": "integer"}}}',
 NULL),

('20000000-0001-0000-0000-000000000003', 'Component', 2, 'Component', 'A software component or module',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"component_type": {"type": "string", "enum": ["library", "module", "package", "container", "function"]}, "version": {"type": "string"}, "language": {"type": "string"}}}',
 NULL),

('20000000-0001-0000-0000-000000000004', 'Infrastructure', 2, 'Infrastructure', 'Infrastructure resource',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"infra_type": {"type": "string", "enum": ["server", "cluster", "vpc", "load_balancer", "cdn", "dns"]}, "provider": {"type": "string", "enum": ["aws", "azure", "gcp", "on_prem", "other"]}, "region": {"type": "string"}}}',
 NULL),

('20000000-0001-0000-0000-000000000005', 'Team', 2, 'Team', 'An engineering or operations team',
 '10000000-0000-0000-0000-000000000005',
 '{"type": "object", "properties": {"team_type": {"type": "string", "enum": ["engineering", "sre", "platform", "security", "data", "devops"]}, "slack_channel": {"type": "string"}, "oncall_rotation": {"type": "string"}}}',
 NULL),

('20000000-0001-0000-0000-000000000006', 'Incident', 2, 'Incident', 'A service incident or outage',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"severity": {"type": "string", "enum": ["sev1", "sev2", "sev3", "sev4"]}, "status": {"type": "string", "enum": ["open", "investigating", "mitigated", "resolved", "postmortem"]}, "incident_commander_id": {"type": "string", "format": "uuid"}, "customer_impact": {"type": "boolean"}, "root_cause": {"type": "string"}}}',
 NULL),

('20000000-0001-0000-0000-000000000007', 'Deployment', 2, 'Deployment', 'A software deployment event',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"version": {"type": "string"}, "environment": {"type": "string", "enum": ["development", "staging", "production"]}, "deployer_id": {"type": "string", "format": "uuid"}, "rollback_version": {"type": "string"}, "success": {"type": "boolean"}}}',
 NULL),

('20000000-0001-0000-0000-000000000008', 'Change', 2, 'Change', 'A configuration or infrastructure change',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"change_type": {"type": "string", "enum": ["config", "infrastructure", "code", "permission", "network"]}, "approver_id": {"type": "string", "format": "uuid"}, "ticket_id": {"type": "string"}, "rollback_plan": {"type": "string"}}}',
 NULL),

('20000000-0001-0000-0000-000000000009', 'Runbook', 2, 'Runbook', 'An operational runbook or playbook',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"runbook_type": {"type": "string", "enum": ["incident_response", "deployment", "maintenance", "recovery"]}, "last_tested": {"type": "string", "format": "date-time"}, "owner_team_id": {"type": "string", "format": "uuid"}}}',
 NULL),

('20000000-0001-0000-0000-000000000010', 'Postmortem', 2, 'Postmortem', 'An incident postmortem document',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"incident_id": {"type": "string", "format": "uuid"}, "action_items": {"type": "array", "items": {"type": "string"}}, "lessons_learned": {"type": "array", "items": {"type": "string"}}}}',
 NULL);
```

### Layer 2: IT Operations Relationships (ENHANCED)

**NEW:** Added `semantics` and `extraction_hints` fields per ChatGPT feedback.

```sql
-- Enhanced ontology_relations table with semantics
CREATE TABLE ontology_relations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    relation_name TEXT NOT NULL,
    tenant_id UUID,
    layer INT NOT NULL CHECK (layer BETWEEN 0 AND 3),
    source_type_id UUID NOT NULL REFERENCES ontology_types(id),
    target_type_id UUID NOT NULL REFERENCES ontology_types(id),
    cardinality TEXT CHECK (cardinality IN ('ONE_TO_ONE', 'ONE_TO_MANY', 'MANY_TO_ONE', 'MANY_TO_MANY')),
    description TEXT,
    properties_schema JSONB DEFAULT '{}',
    
    -- NEW: Relation semantics for traversal and reasoning
    semantics JSONB DEFAULT '{}',  -- {"traversal_mode": "impact", "direction": "forward", "weight": 1.0}
    
    -- NEW: Extraction hints for LLM
    extraction_hints JSONB DEFAULT '{}',  -- {"trigger_phrases": ["depends on", "uses"], "anti_patterns": ["might use"]}
    
    -- NEW: Symbolic constraints (Phase 2 - SHACL-like rules)
    constraints JSONB DEFAULT '{}',  -- {"min_cardinality": 0, "max_cardinality": null, "required": false}
    
    is_deprecated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant_id, relation_name, source_type_id, target_type_id)
);

-- Insert IT Operations relationships with semantics
INSERT INTO ontology_relations (id, relation_name, layer, source_type_id, target_type_id, cardinality, description, semantics, extraction_hints, tenant_id) VALUES

('30000000-0001-0000-0000-000000000001', 'DEPENDS_ON', 2, 
 '20000000-0001-0000-0000-000000000001', '20000000-0001-0000-0000-000000000001',
 'MANY_TO_MANY', 'Service depends on another service',
 '{"traversal_mode": "impact", "direction": "reverse", "weight": 1.0, "transitive": true}',
 '{"trigger_phrases": ["depends on", "requires", "calls", "uses"], "anti_patterns": ["might depend", "could use"]}',
 NULL),

('30000000-0001-0000-0000-000000000002', 'DEPENDS_ON', 2,
 '20000000-0001-0000-0000-000000000001', '20000000-0001-0000-0000-000000000002',
 'MANY_TO_MANY', 'Service depends on a database',
 '{"traversal_mode": "impact", "direction": "reverse", "weight": 1.0, "transitive": false}',
 '{"trigger_phrases": ["connects to", "reads from", "writes to", "stores in"], "anti_patterns": []}',
 NULL),

('30000000-0001-0000-0000-000000000003', 'RUNS_ON', 2,
 '20000000-0001-0000-0000-000000000001', '20000000-0001-0000-0000-000000000004',
 'MANY_TO_MANY', 'Service runs on infrastructure',
 '{"traversal_mode": "dependency", "direction": "forward", "weight": 0.8}',
 '{"trigger_phrases": ["runs on", "deployed to", "hosted on"], "anti_patterns": []}',
 NULL),

('30000000-0001-0000-0000-000000000004', 'CONTAINS', 2,
 '20000000-0001-0000-0000-000000000001', '20000000-0001-0000-0000-000000000003',
 'ONE_TO_MANY', 'Service contains components',
 '{"traversal_mode": "composition", "direction": "forward", "weight": 0.5}',
 '{"trigger_phrases": ["contains", "includes", "consists of"], "anti_patterns": []}',
 NULL),

('30000000-0001-0000-0000-000000000005', 'OWNS', 2,
 '20000000-0001-0000-0000-000000000005', '20000000-0001-0000-0000-000000000001',
 'ONE_TO_MANY', 'Team owns a service',
 '{"traversal_mode": "ownership", "direction": "forward", "weight": 1.0}',
 '{"trigger_phrases": ["owns", "maintains", "is responsible for", "manages"], "anti_patterns": ["uses"]}',
 NULL),

('30000000-0001-0000-0000-000000000006', 'OWNS', 2,
 '20000000-0001-0000-0000-000000000005', '20000000-0001-0000-0000-000000000002',
 'ONE_TO_MANY', 'Team owns a database',
 '{"traversal_mode": "ownership", "direction": "forward", "weight": 1.0}',
 '{"trigger_phrases": ["owns", "maintains", "manages"], "anti_patterns": []}',
 NULL),

('30000000-0001-0000-0000-000000000007', 'MEMBER_OF', 2,
 '10000000-0000-0000-0000-000000000004', '20000000-0001-0000-0000-000000000005',
 'MANY_TO_MANY', 'Person is member of team',
 '{"traversal_mode": "membership", "direction": "forward", "weight": 0.7}',
 '{"trigger_phrases": ["is on", "works on", "member of", "part of"], "anti_patterns": []}',
 NULL),

('30000000-0001-0000-0000-000000000008', 'AFFECTS', 2,
 '20000000-0001-0000-0000-000000000006', '20000000-0001-0000-0000-000000000001',
 'MANY_TO_MANY', 'Incident affects a service',
 '{"traversal_mode": "impact", "direction": "forward", "weight": 1.0}',
 '{"trigger_phrases": ["affects", "impacts", "caused outage in", "degraded"], "anti_patterns": []}',
 NULL),

('30000000-0001-0000-0000-000000000009', 'CAUSED_BY', 2,
 '20000000-0001-0000-0000-000000000006', '20000000-0001-0000-0000-000000000007',
 'MANY_TO_ONE', 'Incident caused by a deployment',
 '{"traversal_mode": "causation", "direction": "reverse", "weight": 1.0}',
 '{"trigger_phrases": ["caused by", "triggered by", "resulted from", "due to"], "anti_patterns": []}',
 NULL),

('30000000-0001-0000-0000-000000000010', 'CAUSED_BY', 2,
 '20000000-0001-0000-0000-000000000006', '20000000-0001-0000-0000-000000000008',
 'MANY_TO_ONE', 'Incident caused by a change',
 '{"traversal_mode": "causation", "direction": "reverse", "weight": 1.0}',
 '{"trigger_phrases": ["caused by", "triggered by", "resulted from"], "anti_patterns": []}',
 NULL),

('30000000-0001-0000-0000-000000000011', 'DOCUMENTS', 2,
 '20000000-0001-0000-0000-000000000009', '20000000-0001-0000-0000-000000000001',
 'MANY_TO_MANY', 'Runbook documents a service',
 '{"traversal_mode": "documentation", "direction": "forward", "weight": 0.5}',
 '{"trigger_phrases": ["documents", "describes", "covers"], "anti_patterns": []}',
 NULL),

('30000000-0001-0000-0000-000000000012', 'DOCUMENTS', 2,
 '20000000-0001-0000-0000-000000000010', '20000000-0001-0000-0000-000000000006',
 'ONE_TO_ONE', 'Postmortem documents an incident',
 '{"traversal_mode": "documentation", "direction": "forward", "weight": 0.5}',
 '{"trigger_phrases": ["postmortem for", "analysis of"], "anti_patterns": []}',
 NULL);
```

---

## Part 2: Database Schema

### Core Tables with Row-Level Security

**NEW:** Added RLS policies per Manus/Perplexity feedback.

```sql
-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS pg_jsonschema;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Tenant context for RLS
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS UUID AS $$
    SELECT NULLIF(current_setting('app.current_tenant_id', true), '')::UUID;
$$ LANGUAGE SQL STABLE;

-- Ontology type definitions
CREATE TABLE ontology_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type_name TEXT NOT NULL,
    tenant_id UUID,
    layer INT NOT NULL CHECK (layer BETWEEN 0 AND 3),
    display_name TEXT,
    description TEXT,
    parent_type_id UUID REFERENCES ontology_types(id),
    properties_schema JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    is_deprecated BOOLEAN DEFAULT FALSE,
    deprecated_at TIMESTAMPTZ,
    version INT DEFAULT 1,
    UNIQUE(tenant_id, type_name)
);

-- Tenant domain template installations
CREATE TABLE tenant_domain_templates (
    tenant_id UUID NOT NULL,
    template_name TEXT NOT NULL,
    template_version TEXT NOT NULL,
    installed_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (tenant_id, template_name)
);

-- Lifecycle states
CREATE TYPE lifecycle_state AS ENUM ('STAGING', 'TRUSTED', 'ARCHIVED', 'REJECTED');

-- Main entity table
CREATE TABLE entities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    name TEXT NOT NULL,
    entity_type_id UUID NOT NULL REFERENCES ontology_types(id),
    lifecycle_state lifecycle_state NOT NULL DEFAULT 'STAGING',
    confidence FLOAT NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
    properties JSONB NOT NULL DEFAULT '{}',
    
    -- Provenance
    source_document_id UUID,
    extraction_event_id UUID,
    extracted_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Lifecycle tracking
    staged_at TIMESTAMPTZ DEFAULT NOW(),
    promoted_at TIMESTAMPTZ,
    promoted_by UUID,
    archived_at TIMESTAMPTZ,
    
    -- Corroboration tracking
    corroboration_count INT DEFAULT 1,
    last_corroborated_at TIMESTAMPTZ DEFAULT NOW(),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Relationship storage
CREATE TABLE relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    relation_type_id UUID NOT NULL REFERENCES ontology_relations(id),
    source_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    lifecycle_state lifecycle_state NOT NULL DEFAULT 'STAGING',
    confidence FLOAT NOT NULL DEFAULT 0.5 CHECK (confidence BETWEEN 0 AND 1),
    properties JSONB DEFAULT '{}',
    
    -- Provenance
    source_document_id UUID,
    extraction_event_id UUID,
    
    -- Lifecycle tracking
    staged_at TIMESTAMPTZ DEFAULT NOW(),
    promoted_at TIMESTAMPTZ,
    
    -- Speculative inference tracking
    is_speculative BOOLEAN DEFAULT FALSE,
    inference_rule TEXT,
    user_confirmed BOOLEAN,
    confirmed_at TIMESTAMPTZ,
    confirmed_by UUID,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(tenant_id, source_entity_id, target_entity_id, relation_type_id)
);

-- Extraction events (audit trail)
CREATE TABLE extraction_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL,
    source_document_id UUID,
    source_text TEXT,
    
    model_used TEXT NOT NULL,
    prompt_template_version TEXT,
    schema_version INT,
    
    raw_extraction JSONB NOT NULL,
    validated_entities JSONB,
    rejected_entities JSONB,
    rejection_reasons JSONB,
    
    -- NEW: Track what the LLM skipped and why
    skipped_entities JSONB,  -- Per ChatGPT feedback on rejection path
    skip_reasons JSONB,
    
    entities_extracted INT DEFAULT 0,
    entities_validated INT DEFAULT 0,
    entities_rejected INT DEFAULT 0,
    validation_errors JSONB,
    
    extraction_started_at TIMESTAMPTZ,
    extraction_completed_at TIMESTAMPTZ,
    validation_completed_at TIMESTAMPTZ,
    
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_ontology_types_tenant_layer ON ontology_types(tenant_id, layer);
CREATE INDEX idx_ontology_types_parent ON ontology_types(parent_type_id);
CREATE INDEX idx_ontology_relations_source ON ontology_relations(source_type_id);
CREATE INDEX idx_ontology_relations_target ON ontology_relations(target_type_id);
CREATE INDEX idx_entities_tenant_state ON entities(tenant_id, lifecycle_state);
CREATE INDEX idx_entities_type ON entities(entity_type_id);
CREATE INDEX idx_entities_confidence ON entities(confidence);
CREATE INDEX idx_relationships_source ON relationships(source_entity_id);
CREATE INDEX idx_relationships_target ON relationships(target_entity_id);
CREATE INDEX idx_relationships_speculative ON relationships(is_speculative) WHERE is_speculative = TRUE;
CREATE INDEX idx_extraction_events_tenant ON extraction_events(tenant_id);
```

### Row-Level Security Policies

**NEW SECTION** (Per Manus/Perplexity: "Implement RLS in PostgreSQL")

```sql
-- Enable RLS on all tenant-scoped tables
ALTER TABLE entities ENABLE ROW LEVEL SECURITY;
ALTER TABLE relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE extraction_events ENABLE ROW LEVEL SECURITY;

-- Entities: Tenants can only see their own entities
CREATE POLICY tenant_isolation_entities ON entities
    FOR ALL
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

-- Relationships: Tenants can only see their own relationships
CREATE POLICY tenant_isolation_relationships ON relationships
    FOR ALL
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

-- Extraction events: Tenants can only see their own
CREATE POLICY tenant_isolation_extraction_events ON extraction_events
    FOR ALL
    USING (tenant_id = current_tenant_id())
    WITH CHECK (tenant_id = current_tenant_id());

-- Ontology types: Tenants can see global types (tenant_id IS NULL) and their own
CREATE POLICY tenant_ontology_types ON ontology_types
    FOR SELECT
    USING (tenant_id IS NULL OR tenant_id = current_tenant_id());

-- Only allow tenants to INSERT their own extensions (Layer 3)
CREATE POLICY tenant_ontology_insert ON ontology_types
    FOR INSERT
    WITH CHECK (
        tenant_id = current_tenant_id() 
        AND layer = 3  -- Only Layer 3 (extensions)
    );

-- Ontology relations: Same pattern
CREATE POLICY tenant_ontology_relations ON ontology_relations
    FOR SELECT
    USING (tenant_id IS NULL OR tenant_id = current_tenant_id());

-- Application role for normal operations
CREATE ROLE cf_app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON entities, relationships, extraction_events TO cf_app_user;
GRANT SELECT ON ontology_types, ontology_relations TO cf_app_user;
GRANT INSERT ON ontology_types, ontology_relations TO cf_app_user;  -- For Layer 3 extensions

-- Admin role bypasses RLS for migrations/maintenance
CREATE ROLE cf_admin;
ALTER ROLE cf_admin BYPASSRLS;
```

### Tenant Extension Guardrails

**NEW SECTION** (Per ChatGPT: "Guardrail on Tenant Extensions")

```sql
-- Prevent tenant extensions from colliding with Core/Domain types
CREATE OR REPLACE FUNCTION check_extension_name_collision()
RETURNS TRIGGER AS $$
BEGIN
    -- Only check Layer 3 (tenant extensions)
    IF NEW.layer = 3 THEN
        -- Check if name exists in Layers 0, 1, or 2
        IF EXISTS (
            SELECT 1 FROM ontology_types
            WHERE type_name = NEW.type_name
            AND layer < 3
            AND NOT is_deprecated
        ) THEN
            RAISE EXCEPTION 'Cannot create extension type "%" - name conflicts with Core/Domain type', NEW.type_name;
        END IF;
        
        -- Ensure parent_type exists and is from Layer 0, 1, or 2 (or same tenant's L3)
        IF NEW.parent_type_id IS NOT NULL THEN
            IF NOT EXISTS (
                SELECT 1 FROM ontology_types
                WHERE id = NEW.parent_type_id
                AND (layer < 3 OR tenant_id = NEW.tenant_id)
            ) THEN
                RAISE EXCEPTION 'Extension type must inherit from Core, Domain, or own tenant types';
            END IF;
        END IF;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER check_extension_collision
    BEFORE INSERT ON ontology_types
    FOR EACH ROW
    EXECUTE FUNCTION check_extension_name_collision();
```

### Database Validation Triggers (CORRECTED)

**CRITICAL FIX** (Per Manus: "SQL bug in validate_relationship")

```sql
-- Validate entity properties against ontology schema
CREATE OR REPLACE FUNCTION validate_entity_properties()
RETURNS TRIGGER AS $$
DECLARE
    type_schema JSONB;
    combined_schema JSONB;
BEGIN
    -- Get the schema for this entity type
    SELECT properties_schema INTO type_schema
    FROM ontology_types
    WHERE id = NEW.entity_type_id;
    
    IF type_schema IS NULL THEN
        RAISE EXCEPTION 'Invalid entity_type_id: %', NEW.entity_type_id;
    END IF;
    
    -- Get parent schemas and merge (inheritance)
    WITH RECURSIVE type_hierarchy AS (
        SELECT id, parent_type_id, properties_schema
        FROM ontology_types
        WHERE id = NEW.entity_type_id
        
        UNION ALL
        
        SELECT ot.id, ot.parent_type_id, ot.properties_schema
        FROM ontology_types ot
        JOIN type_hierarchy th ON ot.id = th.parent_type_id
    )
    SELECT jsonb_merge_agg(properties_schema) INTO combined_schema
    FROM type_hierarchy;
    
    -- Validate using pg_jsonschema
    IF NOT jsonb_matches_schema(combined_schema, NEW.properties) THEN
        RAISE EXCEPTION 'Entity properties do not match schema for type %', 
            (SELECT type_name FROM ontology_types WHERE id = NEW.entity_type_id);
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER validate_entity_before_insert
    BEFORE INSERT OR UPDATE ON entities
    FOR EACH ROW
    EXECUTE FUNCTION validate_entity_properties();

-- CORRECTED: Validate relationships against allowed ontology relations
-- Fixed the variable comparison bug identified by Manus
CREATE OR REPLACE FUNCTION validate_relationship()
RETURNS TRIGGER AS $$
DECLARE
    v_source_type_id UUID;
    v_target_type_id UUID;
    valid_relation BOOLEAN;
BEGIN
    -- Get entity types
    SELECT entity_type_id INTO v_source_type_id FROM entities WHERE id = NEW.source_entity_id;
    SELECT entity_type_id INTO v_target_type_id FROM entities WHERE id = NEW.target_entity_id;
    
    -- CORRECTED: Use table alias 'r' and compare table columns to local variables
    SELECT EXISTS (
        SELECT 1 FROM ontology_relations r
        WHERE r.id = NEW.relation_type_id
        AND r.source_type_id = v_source_type_id  -- Compare table column to local variable
        AND r.target_type_id = v_target_type_id  -- Compare table column to local variable
        AND NOT r.is_deprecated
    ) INTO valid_relation;
    
    IF NOT valid_relation THEN
        RAISE EXCEPTION 'Relationship type % not allowed between entity types % and %',
            NEW.relation_type_id, v_source_type_id, v_target_type_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER validate_relationship_before_insert
    BEFORE INSERT OR UPDATE ON relationships
    FOR EACH ROW
    EXECUTE FUNCTION validate_relationship();
```

---

## Part 3: Constrained Extraction Pipeline

### Pydantic Models

```python
# src/context_foundry/ontology/models.py

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Literal, Union
from uuid import UUID
from datetime import datetime
from enum import Enum

# ============================================
# Layer 0: Meta-Core (Abstract Base Types)
# ============================================

class EntityBase(BaseModel):
    """Abstract root for all entities"""
    name: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

class EventBase(BaseModel):
    """Abstract root for all events"""
    name: str = Field(..., min_length=1, max_length=500)
    timestamp: datetime
    duration_seconds: Optional[int] = None
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

# ============================================
# Layer 1: Common Core
# ============================================

class Person(EntityBase):
    entity_type: Literal["Person"] = "Person"
    email: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None

# ============================================
# Layer 2: IT Operations Domain
# ============================================

class ServiceType(str, Enum):
    API = "api"
    WEB = "web"
    BACKEND = "backend"
    WORKER = "worker"
    GATEWAY = "gateway"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    STORAGE = "storage"

class Service(EntityBase):
    entity_type: Literal["Service"] = "Service"
    service_type: Optional[ServiceType] = None
    tier: Optional[str] = None
    repository_url: Optional[str] = None

class DatabaseType(str, Enum):
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    MONGODB = "mongodb"
    REDIS = "redis"
    ELASTICSEARCH = "elasticsearch"
    DYNAMODB = "dynamodb"
    OTHER = "other"

class Database(EntityBase):
    entity_type: Literal["Database"] = "Database"
    database_type: Optional[DatabaseType] = None
    version: Optional[str] = None
    cluster_name: Optional[str] = None

class Component(EntityBase):
    entity_type: Literal["Component"] = "Component"
    component_type: Optional[str] = None
    version: Optional[str] = None
    language: Optional[str] = None

class Infrastructure(EntityBase):
    entity_type: Literal["Infrastructure"] = "Infrastructure"
    infra_type: Optional[str] = None
    provider: Optional[str] = None
    region: Optional[str] = None

class Team(EntityBase):
    entity_type: Literal["Team"] = "Team"
    team_type: Optional[str] = None
    slack_channel: Optional[str] = None

class Severity(str, Enum):
    SEV1 = "sev1"
    SEV2 = "sev2"
    SEV3 = "sev3"
    SEV4 = "sev4"

class Incident(EventBase):
    entity_type: Literal["Incident"] = "Incident"
    severity: Optional[Severity] = None
    status: Optional[str] = None
    customer_impact: Optional[bool] = None

class Deployment(EventBase):
    entity_type: Literal["Deployment"] = "Deployment"
    version: Optional[str] = None
    environment: Optional[str] = None
    success: Optional[bool] = None

# ============================================
# Relationships
# ============================================

class RelationType(str, Enum):
    DEPENDS_ON = "DEPENDS_ON"
    RUNS_ON = "RUNS_ON"
    CONTAINS = "CONTAINS"
    OWNS = "OWNS"
    MEMBER_OF = "MEMBER_OF"
    AFFECTS = "AFFECTS"
    CAUSED_BY = "CAUSED_BY"
    DOCUMENTS = "DOCUMENTS"

class ExtractedRelationship(BaseModel):
    source_name: str
    source_type: str
    relation_type: RelationType
    target_name: str
    target_type: str
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

# ============================================
# Extraction Response
# ============================================

ITOpsEntity = Union[Service, Database, Component, Infrastructure, Team, Person, Incident, Deployment]

class SkippedEntity(BaseModel):
    """NEW: Track what was skipped and why (per ChatGPT feedback)"""
    text_fragment: str
    reason: str
    confidence_in_skip: float = Field(default=0.5, ge=0.0, le=1.0)

class ExtractionResponse(BaseModel):
    entities: List[ITOpsEntity] = Field(default_factory=list)
    relationships: List[ExtractedRelationship] = Field(default_factory=list)
    skipped_entities: List[SkippedEntity] = Field(default_factory=list)  # NEW
    extraction_notes: Optional[str] = None
```

### Dynamic Schema Prompt Generator

**NEW SECTION** (Per Manus: "Decouple Prompt from Code")

```python
# src/context_foundry/extraction/schema_prompt_generator.py

from typing import List, Dict
from uuid import UUID

class SchemaPromptGenerator:
    """
    Generates LLM prompts dynamically from the ontology database.
    Ensures prompts are always in sync with the current schema.
    """
    
    def __init__(self, db):
        self.db = db
    
    async def generate_extraction_prompt(self, tenant_id: UUID) -> str:
        """Generate a complete extraction prompt from current ontology state"""
        
        # Get all valid types for this tenant
        types = await self.db.fetch("""
            SELECT type_name, display_name, description, layer, properties_schema
            FROM ontology_types
            WHERE (tenant_id IS NULL OR tenant_id = $1)
            AND NOT is_deprecated
            ORDER BY layer, type_name
        """, tenant_id)
        
        # Get all valid relations with extraction hints
        relations = await self.db.fetch("""
            SELECT 
                r.relation_name,
                r.description,
                r.extraction_hints,
                s.type_name as source_type,
                t.type_name as target_type
            FROM ontology_relations r
            JOIN ontology_types s ON r.source_type_id = s.id
            JOIN ontology_types t ON r.target_type_id = t.id
            WHERE (r.tenant_id IS NULL OR r.tenant_id = $1)
            AND NOT r.is_deprecated
            ORDER BY r.relation_name
        """, tenant_id)
        
        # Build the prompt
        prompt = self._build_prompt(types, relations)
        return prompt
    
    def _build_prompt(self, types: List[Dict], relations: List[Dict]) -> str:
        """Build the actual prompt text"""
        
        # Group types by layer
        layer_names = {0: "System", 1: "Common", 2: "Domain", 3: "Custom"}
        types_by_layer = {}
        for t in types:
            layer = t['layer']
            if layer not in types_by_layer:
                types_by_layer[layer] = []
            types_by_layer[layer].append(t)
        
        # Build entity types section
        entity_section = "VALID ENTITY TYPES (you MUST only extract these):\n\n"
        for layer in sorted(types_by_layer.keys()):
            if layer == 0:
                continue  # Skip meta-core, not directly extractable
            entity_section += f"--- {layer_names.get(layer, 'Unknown')} Types ---\n"
            for t in types_by_layer[layer]:
                entity_section += f"- {t['type_name']}: {t['description']}\n"
            entity_section += "\n"
        
        # Build relations section with trigger phrases
        relation_section = "VALID RELATIONSHIP TYPES (you MUST only use these):\n\n"
        seen_relations = set()
        for r in relations:
            key = r['relation_name']
            if key not in seen_relations:
                seen_relations.add(key)
                hints = r.get('extraction_hints', {}) or {}
                triggers = hints.get('trigger_phrases', [])
                anti = hints.get('anti_patterns', [])
                
                relation_section += f"- {r['relation_name']}: {r['description']}\n"
                if triggers:
                    relation_section += f"  Look for phrases like: {', '.join(triggers)}\n"
                if anti:
                    relation_section += f"  Avoid if you see: {', '.join(anti)}\n"
        
        # Build rules section
        rules_section = """
CRITICAL RULES:
1. Only extract entities that clearly match the defined types above
2. Only create relationships between extracted entities
3. Assign confidence scores (0.0-1.0) based on how explicit the information is
4. If something is ambiguous, use lower confidence or add to skipped_entities with reason
5. Never invent information not present in the text
6. For any entity you choose NOT to extract, add it to skipped_entities with your reasoning
"""
        
        return f"""You are a knowledge extractor. Extract entities and relationships from the following text.

{entity_section}
{relation_section}
{rules_section}
"""
```

### Constrained Extractor with Dynamic Prompts

```python
# src/context_foundry/extraction/constrained_extractor.py

import instructor
from anthropic import Anthropic
from typing import Tuple
from uuid import UUID

from ..ontology.models import ExtractionResponse
from .schema_prompt_generator import SchemaPromptGenerator

class ConstrainedExtractor:
    """Extracts entities and relationships constrained to the ontology"""
    
    def __init__(self, db, tenant_id: UUID):
        self.db = db
        self.tenant_id = tenant_id
        self.client = instructor.from_anthropic(Anthropic())
        self.prompt_generator = SchemaPromptGenerator(db)
        self._cached_prompt = None
    
    async def _get_schema_prompt(self) -> str:
        """Get or refresh the schema prompt"""
        if self._cached_prompt is None:
            self._cached_prompt = await self.prompt_generator.generate_extraction_prompt(
                self.tenant_id
            )
        return self._cached_prompt
    
    def refresh_schema(self):
        """Call when ontology changes to refresh cached prompt"""
        self._cached_prompt = None
    
    async def extract(self, text: str) -> Tuple[ExtractionResponse, dict]:
        """Extract entities and relationships from text"""
        
        schema_prompt = await self._get_schema_prompt()
        
        full_prompt = f"""{schema_prompt}

TEXT TO EXTRACT FROM:
{text}
"""
        
        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                messages=[{"role": "user", "content": full_prompt}],
                response_model=ExtractionResponse
            )
            
            metadata = {
                "model": "claude-sonnet-4-20250514",
                "input_length": len(text),
                "entities_extracted": len(response.entities),
                "relationships_extracted": len(response.relationships),
                "entities_skipped": len(response.skipped_entities),
                "validation_passed": True
            }
            
            return response, metadata
            
        except Exception as e:
            metadata = {
                "model": "claude-sonnet-4-20250514",
                "input_length": len(text),
                "validation_passed": False,
                "error": str(e)
            }
            return ExtractionResponse(entities=[], relationships=[]), metadata
```

---

## Part 4: Gardener Agent (Enhanced)

### Configuration with Type-Weighted Thresholds

**ENHANCED** (Per ChatGPT: "Promotion Thresholds May Need Tuning")

```python
# src/context_foundry/gardener/config.py

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Dict

@dataclass
class GardenerConfig:
    """Configuration for the Gardener agent"""
    
    # Default promotion thresholds
    min_confidence_for_promotion: float = 0.7
    min_corroboration_count: int = 2
    min_dwell_time: timedelta = timedelta(hours=1)
    
    # NEW: Type-weighted thresholds (per ChatGPT feedback)
    # Higher-risk types require more stringent promotion
    type_promotion_overrides: Dict[str, dict] = field(default_factory=lambda: {
        "Incident": {"min_confidence": 0.8, "min_corroboration": 3, "min_dwell_hours": 2},
        "Deployment": {"min_confidence": 0.75, "min_corroboration": 2, "min_dwell_hours": 1},
        "Person": {"min_confidence": 0.85, "min_corroboration": 2, "min_dwell_hours": 4},
        # Add more as needed for sensitive types
    })
    
    # Decay settings
    confidence_half_life_days: int = 35
    archive_after_days: int = 84
    
    # Conflict resolution weights (ENHANCED per Manus)
    authority_weight: float = 0.3
    corroboration_weight: float = 0.3
    recency_weight: float = 0.2
    completeness_weight: float = 0.2  # NEW: semantic completeness
    
    # Source authority scores
    source_authority: Dict[str, float] = field(default_factory=lambda: {
        "git_repository": 1.0,
        "confluence": 0.9,
        "pagerduty": 0.9,
        "datadog": 0.85,
        "slack_message": 0.6,
        "email": 0.5,
        "unknown": 0.3,
    })
    
    # Batch processing
    batch_size: int = 100
    run_interval_minutes: int = 5
```

### Enhanced Gardener Implementation

```python
# src/context_foundry/gardener/agent.py

from datetime import datetime, timedelta
from typing import List, Optional, Dict
from uuid import UUID
import math

from .config import GardenerConfig

class GardenerAgent:
    """
    Maintains graph health through four passes:
    1. Decay: Reduce confidence of stale entities
    2. Promotion: Move validated entities from STAGING to TRUSTED
    3. Conflict Resolution: Handle contradictory information
    4. Cleanup: Archive or prune low-value nodes
    """
    
    def __init__(self, db, config: GardenerConfig = None):
        self.db = db
        self.config = config or GardenerConfig()
    
    async def run_cycle(self, tenant_id: UUID):
        """Run all four Gardener passes"""
        await self._pass_decay(tenant_id)
        await self._pass_promotion(tenant_id)
        await self._pass_conflict_resolution(tenant_id)
        await self._pass_cleanup(tenant_id)
    
    async def _pass_decay(self, tenant_id: UUID):
        """Pass 1: Apply temporal decay to entity confidence"""
        half_life = self.config.confidence_half_life_days
        
        # Use parameterized query (per Manus SQL injection concern)
        await self.db.execute("""
            UPDATE entities
            SET confidence = confidence * POWER(0.5, 
                EXTRACT(EPOCH FROM (NOW() - last_corroborated_at)) / 86400.0 / $1
            ),
            updated_at = NOW()
            WHERE tenant_id = $2
            AND lifecycle_state IN ('STAGING', 'TRUSTED')
            AND last_corroborated_at < NOW() - INTERVAL '1 day'
        """, half_life, tenant_id)
    
    async def _pass_promotion(self, tenant_id: UUID):
        """Pass 2: Promote entities that meet all criteria"""
        
        # Get candidates with their type names for type-specific thresholds
        candidates = await self.db.fetch("""
            SELECT e.id, e.confidence, e.corroboration_count, e.staged_at,
                   e.properties, ot.type_name
            FROM entities e
            JOIN ontology_types ot ON e.entity_type_id = ot.id
            WHERE e.tenant_id = $1
            AND e.lifecycle_state = 'STAGING'
        """, tenant_id)
        
        promoted_ids = []
        for entity in candidates:
            type_name = entity['type_name']
            
            # Get type-specific thresholds or defaults
            overrides = self.config.type_promotion_overrides.get(type_name, {})
            min_conf = overrides.get('min_confidence', self.config.min_confidence_for_promotion)
            min_corr = overrides.get('min_corroboration', self.config.min_corroboration_count)
            min_dwell_hours = overrides.get('min_dwell_hours', 
                                            self.config.min_dwell_time.total_seconds() / 3600)
            
            # Check basic thresholds
            if entity['confidence'] < min_conf:
                continue
            if entity['corroboration_count'] < min_corr:
                continue
            
            hours_in_staging = (datetime.now() - entity['staged_at']).total_seconds() / 3600
            if hours_in_staging < min_dwell_hours:
                continue
            
            # Calculate promotion score
            conf_score = entity['confidence'] * 0.4
            corr_score = min(entity['corroboration_count'] / min_corr, 1.0) * 0.3
            dwell_score = min(hours_in_staging / min_dwell_hours, 1.0) * 0.3
            
            total_score = conf_score + corr_score + dwell_score
            
            if total_score >= 0.7:
                promoted_ids.append(entity['id'])
        
        if promoted_ids:
            await self.db.execute("""
                UPDATE entities
                SET lifecycle_state = 'TRUSTED',
                    promoted_at = NOW(),
                    updated_at = NOW()
                WHERE id = ANY($1)
            """, promoted_ids)
    
    async def _pass_conflict_resolution(self, tenant_id: UUID):
        """Pass 3: Resolve conflicting facts (ENHANCED per Manus)"""
        
        conflicts = await self.db.fetch("""
            SELECT e1.id as id1, e2.id as id2,
                   e1.name, e1.properties as props1, e2.properties as props2,
                   e1.confidence as conf1, e2.confidence as conf2,
                   e1.corroboration_count as corr1, e2.corroboration_count as corr2,
                   e1.created_at as created1, e2.created_at as created2,
                   e1.source_document_id as source1, e2.source_document_id as source2
            FROM entities e1
            JOIN entities e2 ON e1.name = e2.name 
                AND e1.entity_type_id = e2.entity_type_id
                AND e1.id < e2.id
            WHERE e1.tenant_id = $1
            AND e1.lifecycle_state IN ('STAGING', 'TRUSTED')
            AND e2.lifecycle_state IN ('STAGING', 'TRUSTED')
            AND e1.properties != e2.properties
        """, tenant_id)
        
        for conflict in conflicts:
            winner_id = await self._resolve_conflict(conflict)
            loser_id = conflict['id1'] if winner_id == conflict['id2'] else conflict['id2']
            
            await self.db.execute("""
                UPDATE entities
                SET corroboration_count = corroboration_count + 1,
                    last_corroborated_at = NOW(),
                    updated_at = NOW()
                WHERE id = $1
            """, winner_id)
            
            await self.db.execute("""
                UPDATE entities
                SET lifecycle_state = 'ARCHIVED',
                    archived_at = NOW()
                WHERE id = $1
            """, loser_id)
    
    async def _resolve_conflict(self, conflict: dict) -> UUID:
        """
        Enhanced conflict resolution (per Manus feedback):
        - Authority score
        - Corroboration count
        - Recency
        - Semantic completeness (non-null properties)
        """
        scores = {conflict['id1']: 0.0, conflict['id2']: 0.0}
        
        # Authority score
        auth1 = await self._get_source_authority(conflict['source1'])
        auth2 = await self._get_source_authority(conflict['source2'])
        if auth1 > auth2:
            scores[conflict['id1']] += self.config.authority_weight
        elif auth2 > auth1:
            scores[conflict['id2']] += self.config.authority_weight
        else:
            # Split evenly
            scores[conflict['id1']] += self.config.authority_weight / 2
            scores[conflict['id2']] += self.config.authority_weight / 2
        
        # Corroboration count
        if conflict['corr1'] > conflict['corr2']:
            scores[conflict['id1']] += self.config.corroboration_weight
        elif conflict['corr2'] > conflict['corr1']:
            scores[conflict['id2']] += self.config.corroboration_weight
        else:
            scores[conflict['id1']] += self.config.corroboration_weight / 2
            scores[conflict['id2']] += self.config.corroboration_weight / 2
        
        # Recency
        if conflict['created1'] > conflict['created2']:
            scores[conflict['id1']] += self.config.recency_weight
        else:
            scores[conflict['id2']] += self.config.recency_weight
        
        # Semantic completeness (count non-null properties)
        completeness1 = self._count_non_null_properties(conflict['props1'])
        completeness2 = self._count_non_null_properties(conflict['props2'])
        if completeness1 > completeness2:
            scores[conflict['id1']] += self.config.completeness_weight
        elif completeness2 > completeness1:
            scores[conflict['id2']] += self.config.completeness_weight
        else:
            scores[conflict['id1']] += self.config.completeness_weight / 2
            scores[conflict['id2']] += self.config.completeness_weight / 2
        
        # Return winner
        return conflict['id1'] if scores[conflict['id1']] >= scores[conflict['id2']] else conflict['id2']
    
    async def _get_source_authority(self, source_document_id: Optional[UUID]) -> float:
        """Get authority score for a source document"""
        if source_document_id is None:
            return self.config.source_authority.get('unknown', 0.3)
        
        # Look up source type from document
        doc = await self.db.fetchrow("""
            SELECT properties->>'source_type' as source_type
            FROM documents
            WHERE id = $1
        """, source_document_id)
        
        if doc and doc['source_type']:
            return self.config.source_authority.get(doc['source_type'], 0.5)
        return self.config.source_authority.get('unknown', 0.3)
    
    def _count_non_null_properties(self, props: dict) -> int:
        """Count non-null property values"""
        if not props:
            return 0
        return sum(1 for v in props.values() if v is not None and v != "")
    
    async def _pass_cleanup(self, tenant_id: UUID):
        """Pass 4: Archive stale entities and prune orphans"""
        archive_threshold = timedelta(days=self.config.archive_after_days)
        
        await self.db.execute("""
            UPDATE entities
            SET lifecycle_state = 'ARCHIVED',
                archived_at = NOW()
            WHERE tenant_id = $1
            AND lifecycle_state IN ('STAGING', 'TRUSTED')
            AND last_corroborated_at < NOW() - $2::INTERVAL
            AND confidence < 0.3
        """, tenant_id, archive_threshold)
        
        await self.db.execute("""
            UPDATE entities e
            SET lifecycle_state = 'ARCHIVED',
                archived_at = NOW()
            WHERE e.tenant_id = $1
            AND e.lifecycle_state = 'STAGING'
            AND e.staged_at < NOW() - INTERVAL '7 days'
            AND NOT EXISTS (
                SELECT 1 FROM relationships r
                WHERE r.source_entity_id = e.id OR r.target_entity_id = e.id
            )
        """, tenant_id)
```

---

## Part 5: Inference Engine with Optimized Type Checking

**ENHANCED** (Per Perplexity: "Inference Engine Type Checking is O(n)")

```python
# src/context_foundry/memory/inference.py

from typing import List, Dict, Set, Optional
from uuid import UUID

class InferenceEngine:
    """Generates speculative inferences with optimized ontology validation"""
    
    def __init__(self, db):
        self.db = db
        self.valid_entity_types: Dict[UUID, dict] = {}
        self.valid_relationships: List[dict] = []
        
        # Pre-computed ancestor sets for O(1) type checking
        self._ancestor_cache: Dict[UUID, Set[UUID]] = {}
    
    async def load_ontology(self, tenant_id: UUID):
        """Load valid types and relationships, pre-compute ancestor sets"""
        
        types = await self.db.fetch("""
            SELECT id, type_name, parent_type_id 
            FROM ontology_types
            WHERE (tenant_id IS NULL OR tenant_id = $1)
            AND NOT is_deprecated
        """, tenant_id)
        
        self.valid_entity_types = {t['id']: t for t in types}
        
        # Pre-compute ancestor sets for all types (O(n) once, then O(1) lookups)
        self._ancestor_cache = {}
        for type_id in self.valid_entity_types:
            self._ancestor_cache[type_id] = self._compute_ancestors(type_id)
        
        self.valid_relationships = await self.db.fetch("""
            SELECT id, relation_name, source_type_id, target_type_id
            FROM ontology_relations
            WHERE (tenant_id IS NULL OR tenant_id = $1)
            AND NOT is_deprecated
        """, tenant_id)
    
    def _compute_ancestors(self, type_id: UUID) -> Set[UUID]:
        """Compute all ancestor types (including self) - called once per type"""
        ancestors = {type_id}
        current = type_id
        
        while current:
            type_info = self.valid_entity_types.get(current)
            if type_info and type_info.get('parent_type_id'):
                parent = type_info['parent_type_id']
                if parent in ancestors:  # Prevent infinite loops
                    break
                ancestors.add(parent)
                current = parent
            else:
                break
        
        return ancestors
    
    def types_compatible(self, allowed_type_id: UUID, actual_type_id: UUID) -> bool:
        """O(1) type compatibility check using pre-computed ancestor sets"""
        ancestors = self._ancestor_cache.get(actual_type_id, set())
        return allowed_type_id in ancestors
    
    def is_valid_inference(self, source_type_id: UUID, target_type_id: UUID, relation_name: str) -> bool:
        """Check if an inferred relationship is valid according to ontology"""
        for rel in self.valid_relationships:
            if (rel['relation_name'] == relation_name and
                self.types_compatible(rel['source_type_id'], source_type_id) and
                self.types_compatible(rel['target_type_id'], target_type_id)):
                return True
        return False
    
    async def generate_inferences(self, frontier_nodes: List[UUID], tenant_id: UUID) -> List[dict]:
        """Generate ontology-valid speculative inferences"""
        await self.load_ontology(tenant_id)
        
        inferences = []
        
        for rule in [self._transitive_dependency, self._co_occurrence, self._shared_dependency]:
            rule_inferences = await rule(frontier_nodes, tenant_id)
            
            for inf in rule_inferences:
                if self.is_valid_inference(
                    inf['source_type_id'], 
                    inf['target_type_id'], 
                    inf['relation_name']
                ):
                    inferences.append(inf)
        
        return inferences
    
    async def _transitive_dependency(self, frontier_nodes: List[UUID], tenant_id: UUID) -> List[dict]:
        """Infer A→C if A→B and B→C exist"""
        # Implementation here
        return []
    
    async def _co_occurrence(self, frontier_nodes: List[UUID], tenant_id: UUID) -> List[dict]:
        """Infer relationship if entities co-occur in documents"""
        # Implementation here
        return []
    
    async def _shared_dependency(self, frontier_nodes: List[UUID], tenant_id: UUID) -> List[dict]:
        """Infer relationship if entities share dependencies"""
        # Implementation here
        return []
```

---

## Part 6: Monitoring and Metrics

**NEW SECTION** (Per Perplexity: "No Metrics/Monitoring Plan")

### Prometheus Metrics

```python
# src/context_foundry/monitoring/metrics.py

from prometheus_client import Counter, Histogram, Gauge

# Extraction metrics
extraction_total = Counter(
    'cf_extraction_total',
    'Total extraction attempts',
    ['tenant_id', 'model', 'status']
)

extraction_entities = Histogram(
    'cf_extraction_entities',
    'Number of entities extracted per document',
    ['tenant_id'],
    buckets=[0, 1, 5, 10, 25, 50, 100]
)

extraction_validation_failures = Counter(
    'cf_extraction_validation_failures',
    'Extraction validation failures',
    ['tenant_id', 'failure_type']
)

extraction_skipped = Counter(
    'cf_extraction_skipped',
    'Entities skipped during extraction',
    ['tenant_id', 'reason']
)

# Gardener metrics
gardener_promotions = Counter(
    'cf_gardener_promotions_total',
    'Entities promoted to TRUSTED',
    ['tenant_id', 'entity_type']
)

gardener_conflicts = Counter(
    'cf_gardener_conflicts_total',
    'Conflicts resolved by Gardener',
    ['tenant_id', 'resolution_method']
)

gardener_archived = Counter(
    'cf_gardener_archived_total',
    'Entities archived by Gardener',
    ['tenant_id', 'reason']
)

gardener_cycle_duration = Histogram(
    'cf_gardener_cycle_duration_seconds',
    'Duration of Gardener cycles',
    ['tenant_id', 'pass_name']
)

# Graph health metrics
staging_entities = Gauge(
    'cf_staging_entities',
    'Current entities in STAGING',
    ['tenant_id']
)

trusted_entities = Gauge(
    'cf_trusted_entities',
    'Current entities in TRUSTED',
    ['tenant_id']
)

speculative_relationships = Gauge(
    'cf_speculative_relationships',
    'Current speculative relationships',
    ['tenant_id']
)

# Inference metrics
inference_generated = Counter(
    'cf_inference_generated_total',
    'Speculative inferences generated',
    ['tenant_id', 'rule_name']
)

inference_rejected = Counter(
    'cf_inference_rejected_total',
    'Inferences rejected by ontology validation',
    ['tenant_id', 'reason']
)

inference_confirmed = Counter(
    'cf_inference_confirmed_total',
    'User-confirmed inferences',
    ['tenant_id']
)
```

### Health Check Endpoints

```python
# src/context_foundry/api/health.py

from fastapi import APIRouter
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

router = APIRouter()

@router.get("/health")
async def health_check():
    return {"status": "healthy"}

@router.get("/metrics")
async def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )

@router.get("/health/gardener")
async def gardener_health(db):
    """Check Gardener is running correctly"""
    last_run = await db.fetchrow("""
        SELECT MAX(created_at) as last_run
        FROM gardener_runs
        WHERE status = 'completed'
    """)
    
    if not last_run or not last_run['last_run']:
        return {"status": "warning", "message": "No completed Gardener runs"}
    
    minutes_since = (datetime.now() - last_run['last_run']).total_seconds() / 60
    
    if minutes_since > 15:
        return {"status": "critical", "message": f"Gardener not run in {minutes_since:.0f} minutes"}
    
    return {"status": "healthy", "last_run": last_run['last_run'].isoformat()}
```

### Alerting Rules (Prometheus/AlertManager)

```yaml
# alerts/context_foundry.yml

groups:
  - name: context_foundry
    rules:
      - alert: ExtractionFailureRateHigh
        expr: rate(cf_extraction_total{status="failed"}[5m]) / rate(cf_extraction_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High extraction failure rate"
          description: "More than 10% of extractions are failing"
      
      - alert: GardenerNotRunning
        expr: time() - cf_gardener_last_run_timestamp > 900
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "Gardener has not run"
          description: "Gardener has not completed a cycle in 15+ minutes"
      
      - alert: StagingBacklog
        expr: cf_staging_entities > 1000
        for: 30m
        labels:
          severity: warning
        annotations:
          summary: "Large STAGING backlog"
          description: "More than 1000 entities waiting in STAGING"
      
      - alert: PromotionRateLow
        expr: rate(cf_gardener_promotions_total[1h]) < 1
        for: 2h
        labels:
          severity: info
        annotations:
          summary: "Low promotion rate"
          description: "Very few entities being promoted - may indicate extraction quality issues"
```

---

## Part 7: Implementation Sequence (Updated)

### Week 0: Shadow Mode Setup (Pre-Sprint)
1. Create feature flags for extraction mode
2. Set up shadow table for parallel writes
3. Configure comparison metrics logging
4. Establish cutover criteria

### Week 1: Foundation
1. Create ontology tables with RLS policies
2. Insert Layer 0, 1, 2 types and relations
3. Add pg_jsonschema extension
4. Implement validation triggers (with bug fixes applied)
5. Add tenant extension guardrails

### Week 2: Extraction Pipeline
1. Implement Pydantic models
2. Build dynamic SchemaPromptGenerator
3. Build ConstrainedExtractor with Instructor
4. Create extraction_events audit table with skipped_entities
5. Add Prometheus metrics for extraction

### Week 3: Staging & Gardener
1. Implement GardenerAgent with all four passes
2. Add type-weighted promotion thresholds
3. Enhanced conflict resolution with authority scores
4. Create background job for Gardener cycles
5. Add Gardener metrics and alerting

### Week 4: Data Cleanup & Migration
1. Run cleanup scripts on existing garbage
2. Archive invalid entities
3. Reset valid entities to STAGING
4. Enable shadow mode, compare old vs new extraction

### Week 5: Inference & Query Integration
1. Update InferenceEngine with pre-computed ancestor sets
2. Add ontology validation to speculative edges
3. Test three-tier query responses with clean data
4. Implement feedback loop for confirmation

### Week 6: Cutover & Polish
1. Review shadow mode metrics
2. Cut over to constrained extraction
3. End-to-end testing
4. Documentation
5. Remove shadow mode infrastructure

---

## Part 8: Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Extraction precision | > 93% | validated / (validated + rejected) |
| STAGING pollution (invalid types) | < 2% | rejected / total extracted |
| TRUSTED false positives | < 1% | manual audit of promoted entities |
| Speculative inference validity | 100% | All inferences pass ontology check |
| Promotion latency | < 10 minutes | Time from extraction to TRUSTED |
| Gardener cycle time | < 60 seconds | Per-pass timing |
| Query response with tiers | Working | All IT Ops queries show 3 tiers |
| Shadow mode precision delta | < 5% | Compare old vs new extraction |

---

## Appendix A: Data Cleanup Scripts

```sql
-- Step 1: Identify invalid entity types
SELECT DISTINCT entity_type, COUNT(*) 
FROM entities 
GROUP BY entity_type
ORDER BY COUNT(*) DESC;

-- Step 2: Archive entities with invalid types
UPDATE entities
SET lifecycle_state = 'ARCHIVED',
    archived_at = NOW()
WHERE entity_type NOT IN (
    SELECT type_name FROM ontology_types
);

-- Step 3: Remove known garbage
UPDATE entities
SET lifecycle_state = 'REJECTED',
    archived_at = NOW()
WHERE name IN ('cat', 'Ryan Adams')
   OR entity_type IN ('CREATURE');

-- Step 4: Archive orphaned relationships
UPDATE relationships
SET lifecycle_state = 'ARCHIVED'
WHERE source_entity_id IN (
    SELECT id FROM entities WHERE lifecycle_state IN ('ARCHIVED', 'REJECTED')
)
OR target_entity_id IN (
    SELECT id FROM entities WHERE lifecycle_state IN ('ARCHIVED', 'REJECTED')
);

-- Step 5: Reset remaining to STAGING
UPDATE entities
SET lifecycle_state = 'STAGING',
    staged_at = NOW(),
    confidence = 0.5
WHERE lifecycle_state = 'TRUSTED';
```

---

## Appendix B: Migration from Current State

```sql
-- Add new columns
ALTER TABLE entities ADD COLUMN IF NOT EXISTS entity_type_id UUID;
ALTER TABLE entities ADD COLUMN IF NOT EXISTS lifecycle_state lifecycle_state DEFAULT 'STAGING';
ALTER TABLE entities ADD COLUMN IF NOT EXISTS corroboration_count INT DEFAULT 1;
ALTER TABLE entities ADD COLUMN IF NOT EXISTS last_corroborated_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE entities ADD COLUMN IF NOT EXISTS staged_at TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE entities ADD COLUMN IF NOT EXISTS promoted_at TIMESTAMPTZ;

-- Map string entity_type to ontology_types.id
UPDATE entities e
SET entity_type_id = (
    SELECT id FROM ontology_types ot
    WHERE ot.type_name = e.entity_type
    LIMIT 1
)
WHERE e.entity_type_id IS NULL;

-- Mark unmapped entities
UPDATE entities
SET lifecycle_state = 'REJECTED'
WHERE entity_type_id IS NULL;

-- Set mapped entities to STAGING
UPDATE entities
SET lifecycle_state = 'STAGING',
    staged_at = NOW()
WHERE lifecycle_state != 'REJECTED';
```

---

## Appendix C: Phase 2 Roadmap (Post-MVP)

Items deferred to Phase 2 per reviewer recommendations:

| Item | Source | Priority |
|------|--------|----------|
| SHACL symbolic rule layer | ChatGPT | High |
| Grammar-Constrained Decoding (GCD) | All | Medium |
| HITL Ontology Builder UI | ChatGPT | Medium |
| Cost model for multi-tenant scaling | Manus | Medium |
| Ontology Harvester (cross-tenant patterns) | All | Low |

---

**This specification is ready for implementation.**

All critical bugs fixed. All high-priority recommendations incorporated. Unanimous approval from all reviewers.
