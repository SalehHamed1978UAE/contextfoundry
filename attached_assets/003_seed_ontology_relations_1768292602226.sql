-- Migration 003: Seed Ontology Relations
-- Context Foundry - Multi-Domain Knowledge Graph System
--
-- Context Foundry supports ANY domain/industry:
--   - Venture Capital: INVESTED_IN, BOARD_MEMBER_OF, HAS_PORTFOLIO_COMPANY
--   - Healthcare: TREATS, PRESCRIBED_BY, DIAGNOSED_WITH
--   - Legal: PARTY_TO, GOVERNED_BY, AMENDS
--   - Human Resources: WORKS_AT, REPORTS_TO, HAS_COMPENSATION
--   - Finance: HOLDS_ACCOUNT, TRANSACTED_WITH, REGULATED_BY
--   - IT Operations: DEPENDS_ON, RUNS_ON, OWNS
--   - Real Estate: LEASED_BY, LOCATED_IN, MANAGED_BY
--
-- This migration includes IT Operations relationships as ONE example domain template.
-- Core business relationships (WORKS_AT, INVESTED_IN, etc.) are in migration 016.
--
-- IMPORTANT: UUIDs are DETERMINISTIC per spec - do not change

-- ============================================
-- LAYER 2: Domain Template Relationships (Example: IT Operations)
-- These are OPTIONAL - one of many possible domain relationship sets.
-- With semantics for traversal and extraction hints for LLM.
-- ============================================

INSERT INTO ontology_relations (id, relation_name, layer, source_type_id, target_type_id, cardinality, description, semantics, extraction_hints, origin, tenant_id) VALUES

-- Service -> Service: DEPENDS_ON
('30000000-0001-0000-0000-000000000001', 'DEPENDS_ON', 2, 
 '20000000-0001-0000-0000-000000000001', '20000000-0001-0000-0000-000000000001',
 'MANY_TO_MANY', 'Service depends on another service',
 '{"traversal_mode": "impact", "direction": "reverse", "weight": 1.0, "transitive": true}',
 '{"trigger_phrases": ["depends on", "requires", "calls", "uses"], "anti_patterns": ["might depend", "could use"]}',
 'domain_template', NULL),

-- Service -> Database: DEPENDS_ON
('30000000-0001-0000-0000-000000000002', 'DEPENDS_ON', 2,
 '20000000-0001-0000-0000-000000000001', '20000000-0001-0000-0000-000000000002',
 'MANY_TO_MANY', 'Service depends on a database',
 '{"traversal_mode": "impact", "direction": "reverse", "weight": 1.0, "transitive": false}',
 '{"trigger_phrases": ["connects to", "reads from", "writes to", "stores in"], "anti_patterns": []}',
 'domain_template', NULL),

-- Service -> Infrastructure: RUNS_ON
('30000000-0001-0000-0000-000000000003', 'RUNS_ON', 2,
 '20000000-0001-0000-0000-000000000001', '20000000-0001-0000-0000-000000000004',
 'MANY_TO_MANY', 'Service runs on infrastructure',
 '{"traversal_mode": "dependency", "direction": "forward", "weight": 0.8}',
 '{"trigger_phrases": ["runs on", "deployed to", "hosted on"], "anti_patterns": []}',
 'domain_template', NULL),

-- Service -> Component: CONTAINS
('30000000-0001-0000-0000-000000000004', 'CONTAINS', 2,
 '20000000-0001-0000-0000-000000000001', '20000000-0001-0000-0000-000000000003',
 'ONE_TO_MANY', 'Service contains components',
 '{"traversal_mode": "composition", "direction": "forward", "weight": 0.5}',
 '{"trigger_phrases": ["contains", "includes", "consists of"], "anti_patterns": []}',
 'domain_template', NULL),

-- Team -> Service: OWNS
('30000000-0001-0000-0000-000000000005', 'OWNS', 2,
 '20000000-0001-0000-0000-000000000005', '20000000-0001-0000-0000-000000000001',
 'ONE_TO_MANY', 'Team owns a service',
 '{"traversal_mode": "ownership", "direction": "forward", "weight": 1.0}',
 '{"trigger_phrases": ["owns", "maintains", "is responsible for", "manages"], "anti_patterns": ["uses"]}',
 'domain_template', NULL),

-- Team -> Database: OWNS
('30000000-0001-0000-0000-000000000006', 'OWNS', 2,
 '20000000-0001-0000-0000-000000000005', '20000000-0001-0000-0000-000000000002',
 'ONE_TO_MANY', 'Team owns a database',
 '{"traversal_mode": "ownership", "direction": "forward", "weight": 1.0}',
 '{"trigger_phrases": ["owns", "maintains", "manages"], "anti_patterns": []}',
 'domain_template', NULL),

-- Person -> Team: MEMBER_OF
('30000000-0001-0000-0000-000000000007', 'MEMBER_OF', 2,
 '10000000-0000-0000-0000-000000000004', '20000000-0001-0000-0000-000000000005',
 'MANY_TO_MANY', 'Person is member of team',
 '{"traversal_mode": "membership", "direction": "forward", "weight": 0.7}',
 '{"trigger_phrases": ["is on", "works on", "member of", "part of"], "anti_patterns": []}',
 'domain_template', NULL),

-- Incident -> Service: AFFECTS
('30000000-0001-0000-0000-000000000008', 'AFFECTS', 2,
 '20000000-0001-0000-0000-000000000006', '20000000-0001-0000-0000-000000000001',
 'MANY_TO_MANY', 'Incident affects a service',
 '{"traversal_mode": "impact", "direction": "forward", "weight": 1.0}',
 '{"trigger_phrases": ["affects", "impacts", "caused outage in", "degraded"], "anti_patterns": []}',
 'domain_template', NULL),

-- Incident -> Deployment: CAUSED_BY
('30000000-0001-0000-0000-000000000009', 'CAUSED_BY', 2,
 '20000000-0001-0000-0000-000000000006', '20000000-0001-0000-0000-000000000007',
 'MANY_TO_ONE', 'Incident caused by a deployment',
 '{"traversal_mode": "causation", "direction": "reverse", "weight": 1.0}',
 '{"trigger_phrases": ["caused by", "triggered by", "resulted from", "due to"], "anti_patterns": []}',
 'domain_template', NULL),

-- Incident -> Change: CAUSED_BY
('30000000-0001-0000-0000-000000000010', 'CAUSED_BY', 2,
 '20000000-0001-0000-0000-000000000006', '20000000-0001-0000-0000-000000000008',
 'MANY_TO_ONE', 'Incident caused by a change',
 '{"traversal_mode": "causation", "direction": "reverse", "weight": 1.0}',
 '{"trigger_phrases": ["caused by", "triggered by", "resulted from"], "anti_patterns": []}',
 'domain_template', NULL),

-- Runbook -> Service: DOCUMENTS
('30000000-0001-0000-0000-000000000011', 'DOCUMENTS', 2,
 '20000000-0001-0000-0000-000000000009', '20000000-0001-0000-0000-000000000001',
 'MANY_TO_MANY', 'Runbook documents a service',
 '{"traversal_mode": "documentation", "direction": "forward", "weight": 0.5}',
 '{"trigger_phrases": ["documents", "describes", "covers"], "anti_patterns": []}',
 'domain_template', NULL),

-- Postmortem -> Incident: DOCUMENTS
('30000000-0001-0000-0000-000000000012', 'DOCUMENTS', 2,
 '20000000-0001-0000-0000-000000000010', '20000000-0001-0000-0000-000000000006',
 'ONE_TO_ONE', 'Postmortem documents an incident',
 '{"traversal_mode": "documentation", "direction": "forward", "weight": 0.5}',
 '{"trigger_phrases": ["postmortem for", "analysis of"], "anti_patterns": []}',
 'domain_template', NULL),

-- Database -> Database: REPLICATES_TO (additional useful relation)
('30000000-0001-0000-0000-000000000013', 'REPLICATES_TO', 2,
 '20000000-0001-0000-0000-000000000002', '20000000-0001-0000-0000-000000000002',
 'MANY_TO_MANY', 'Database replicates to another database',
 '{"traversal_mode": "replication", "direction": "forward", "weight": 0.9}',
 '{"trigger_phrases": ["replicates to", "syncs to", "mirrors to"], "anti_patterns": []}',
 'domain_template', NULL),

-- Person -> Service: ONCALL_FOR (ownership variant)
('30000000-0001-0000-0000-000000000014', 'ONCALL_FOR', 2,
 '10000000-0000-0000-0000-000000000004', '20000000-0001-0000-0000-000000000001',
 'MANY_TO_MANY', 'Person is on-call for a service',
 '{"traversal_mode": "ownership", "direction": "forward", "weight": 0.8}',
 '{"trigger_phrases": ["on-call for", "oncall for", "primary for", "backup for"], "anti_patterns": []}',
 'domain_template', NULL),

-- Deployment -> Service: DEPLOYS
('30000000-0001-0000-0000-000000000015', 'DEPLOYS', 2,
 '20000000-0001-0000-0000-000000000007', '20000000-0001-0000-0000-000000000001',
 'MANY_TO_ONE', 'Deployment deploys to a service',
 '{"traversal_mode": "deployment", "direction": "forward", "weight": 1.0}',
 '{"trigger_phrases": ["deployed to", "released to", "pushed to"], "anti_patterns": []}',
 'domain_template', NULL)

ON CONFLICT (tenant_id, relation_name, source_type_id, target_type_id) DO NOTHING;
