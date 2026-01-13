-- Migration 002: Seed Ontology Types
-- Context Foundry - Multi-Domain Knowledge Graph System
--
-- Context Foundry supports ANY domain/industry:
--   - Venture Capital & Private Equity
--   - Healthcare & Life Sciences
--   - Legal & Compliance
--   - Human Resources & Talent
--   - Finance & Banking
--   - Technology & IT Operations
--   - Real Estate & Property Management
--
-- Seeds: Layer 0 (Meta-Core), Layer 1 (Common Core), Layer 2 (Domain Templates)
-- This migration includes IT Operations as ONE example domain template.
-- Other domain templates (VC, Healthcare, Legal, etc.) can be added via additional migrations.
--
-- IMPORTANT: UUIDs are DETERMINISTIC per spec - do not change

-- ============================================
-- LAYER 0: Meta-Core (System Primitives)
-- Immutable, hardcoded. Never modified by tenants.
-- ============================================

INSERT INTO ontology_types (id, type_name, layer, display_name, description, parent_type_id, properties_schema, origin) VALUES
('00000000-0000-0000-0000-000000000001', 'Entity', 0, 'Entity', 
 'Abstract root for all nodes in the graph', NULL, 
 '{"type": "object", "properties": {"id": {"type": "string", "format": "uuid"}, "name": {"type": "string"}, "description": {"type": "string"}, "created_at": {"type": "string", "format": "date-time"}, "updated_at": {"type": "string", "format": "date-time"}}, "required": ["id", "name"]}',
 'system'),

('00000000-0000-0000-0000-000000000002', 'Event', 0, 'Event', 
 'An occurrence at a point in time', NULL,
 '{"type": "object", "properties": {"id": {"type": "string", "format": "uuid"}, "name": {"type": "string"}, "timestamp": {"type": "string", "format": "date-time"}, "duration_seconds": {"type": "integer"}}, "required": ["id", "timestamp"]}',
 'system'),

('00000000-0000-0000-0000-000000000003', 'Record', 0, 'Record', 
 'A piece of evidence or documentation', NULL,
 '{"type": "object", "properties": {"id": {"type": "string", "format": "uuid"}, "name": {"type": "string"}, "source_uri": {"type": "string"}, "ingested_at": {"type": "string", "format": "date-time"}}, "required": ["id", "name"]}',
 'system'),

('00000000-0000-0000-0000-000000000004', 'Relation', 0, 'Relation', 
 'Abstract root for all edges', NULL,
 '{"type": "object", "properties": {"source_id": {"type": "string", "format": "uuid"}, "target_id": {"type": "string", "format": "uuid"}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}}, "required": ["source_id", "target_id"]}',
 'system')
ON CONFLICT (tenant_id, type_name) DO NOTHING;

-- ============================================
-- LAYER 1: Common Core (Universal Concepts)
-- Shared across all domains
-- ============================================

INSERT INTO ontology_types (id, type_name, layer, display_name, description, parent_type_id, properties_schema, origin) VALUES
('10000000-0000-0000-0000-000000000001', 'Asset', 1, 'Asset', 
 'A physical or digital resource with value', 
 '00000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"asset_type": {"type": "string"}, "status": {"type": "string", "enum": ["active", "inactive", "deprecated", "planned"]}, "owner_id": {"type": "string", "format": "uuid"}}}',
 'system'),

('10000000-0000-0000-0000-000000000002', 'Agent', 1, 'Agent', 
 'An actor that can perform actions',
 '00000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"agent_type": {"type": "string", "enum": ["person", "organization", "software", "team"]}}}',
 'system'),

('10000000-0000-0000-0000-000000000003', 'Location', 1, 'Location', 
 'A physical or logical place',
 '00000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"location_type": {"type": "string", "enum": ["physical", "logical", "virtual"]}, "coordinates": {"type": "object"}, "address": {"type": "string"}}}',
 'system'),

('10000000-0000-0000-0000-000000000004', 'Person', 1, 'Person', 
 'A human individual',
 '10000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"email": {"type": "string", "format": "email"}, "role": {"type": "string"}, "department": {"type": "string"}}}',
 'system'),

('10000000-0000-0000-0000-000000000005', 'Organization', 1, 'Organization', 
 'A company, team, or organizational unit',
 '10000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"org_type": {"type": "string"}, "parent_org_id": {"type": "string", "format": "uuid"}}}',
 'system'),

('10000000-0000-0000-0000-000000000006', 'Document', 1, 'Document', 
 'A written or digital document',
 '00000000-0000-0000-0000-000000000003',
 '{"type": "object", "properties": {"document_type": {"type": "string"}, "file_path": {"type": "string"}, "content_hash": {"type": "string"}}}',
 'system')
ON CONFLICT (tenant_id, type_name) DO NOTHING;

-- ============================================
-- LAYER 2: Domain Templates (Example: IT Operations)
-- These are OPTIONAL templates - one of many possible domains.
-- Other domains (VC, Healthcare, Legal, HR, Finance) use different templates.
-- Installable per-tenant based on their industry/use case.
-- ============================================

INSERT INTO ontology_types (id, type_name, layer, display_name, description, parent_type_id, properties_schema, origin, tenant_id) VALUES
('20000000-0001-0000-0000-000000000001', 'Service', 2, 'Service', 
 'A software service or application',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"service_type": {"type": "string", "enum": ["api", "web", "backend", "worker", "gateway", "database", "cache", "queue", "storage"]}, "tier": {"type": "string", "enum": ["tier1", "tier2", "tier3"]}, "slo_target": {"type": "number"}, "repository_url": {"type": "string"}, "documentation_url": {"type": "string"}}}',
 'domain_template', NULL),

('20000000-0001-0000-0000-000000000002', 'Database', 2, 'Database', 
 'A database or data store',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"database_type": {"type": "string", "enum": ["postgresql", "mysql", "mongodb", "redis", "elasticsearch", "dynamodb", "other"]}, "version": {"type": "string"}, "cluster_name": {"type": "string"}, "replica_count": {"type": "integer"}}}',
 'domain_template', NULL),

('20000000-0001-0000-0000-000000000003', 'Component', 2, 'Component', 
 'A software component or module',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"component_type": {"type": "string", "enum": ["library", "module", "package", "container", "function"]}, "version": {"type": "string"}, "language": {"type": "string"}}}',
 'domain_template', NULL),

('20000000-0001-0000-0000-000000000004', 'Infrastructure', 2, 'Infrastructure', 
 'Infrastructure resource',
 '10000000-0000-0000-0000-000000000001',
 '{"type": "object", "properties": {"infra_type": {"type": "string", "enum": ["server", "cluster", "vpc", "load_balancer", "cdn", "dns"]}, "provider": {"type": "string", "enum": ["aws", "azure", "gcp", "on_prem", "other"]}, "region": {"type": "string"}}}',
 'domain_template', NULL),

('20000000-0001-0000-0000-000000000005', 'Team', 2, 'Team', 
 'An engineering or operations team',
 '10000000-0000-0000-0000-000000000005',
 '{"type": "object", "properties": {"team_type": {"type": "string", "enum": ["engineering", "sre", "platform", "security", "data", "devops"]}, "slack_channel": {"type": "string"}, "oncall_rotation": {"type": "string"}}}',
 'domain_template', NULL),

('20000000-0001-0000-0000-000000000006', 'Incident', 2, 'Incident', 
 'A service incident or outage',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"severity": {"type": "string", "enum": ["sev1", "sev2", "sev3", "sev4"]}, "status": {"type": "string", "enum": ["open", "investigating", "mitigated", "resolved", "postmortem"]}, "incident_commander_id": {"type": "string", "format": "uuid"}, "customer_impact": {"type": "boolean"}, "root_cause": {"type": "string"}}}',
 'domain_template', NULL),

('20000000-0001-0000-0000-000000000007', 'Deployment', 2, 'Deployment', 
 'A software deployment event',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"version": {"type": "string"}, "environment": {"type": "string", "enum": ["development", "staging", "production"]}, "deployer_id": {"type": "string", "format": "uuid"}, "rollback_version": {"type": "string"}, "success": {"type": "boolean"}}}',
 'domain_template', NULL),

('20000000-0001-0000-0000-000000000008', 'Change', 2, 'Change', 
 'A configuration or infrastructure change',
 '00000000-0000-0000-0000-000000000002',
 '{"type": "object", "properties": {"change_type": {"type": "string", "enum": ["config", "infrastructure", "code", "permission", "network"]}, "approver_id": {"type": "string", "format": "uuid"}, "ticket_id": {"type": "string"}, "rollback_plan": {"type": "string"}}}',
 'domain_template', NULL),

('20000000-0001-0000-0000-000000000009', 'Runbook', 2, 'Runbook', 
 'An operational runbook or playbook',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"runbook_type": {"type": "string", "enum": ["incident_response", "deployment", "maintenance", "recovery"]}, "last_tested": {"type": "string", "format": "date-time"}, "owner_team_id": {"type": "string", "format": "uuid"}}}',
 'domain_template', NULL),

('20000000-0001-0000-0000-000000000010', 'Postmortem', 2, 'Postmortem', 
 'An incident postmortem document',
 '10000000-0000-0000-0000-000000000006',
 '{"type": "object", "properties": {"incident_id": {"type": "string", "format": "uuid"}, "action_items": {"type": "array", "items": {"type": "string"}}, "lessons_learned": {"type": "array", "items": {"type": "string"}}}}',
 'domain_template', NULL)
ON CONFLICT (tenant_id, type_name) DO NOTHING;
