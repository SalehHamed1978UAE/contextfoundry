-- =============================================================================
-- Migration 016: Seed Core Relationship Types
-- =============================================================================
-- Purpose: Add universal relationship types to ontology.relations
-- Issue: BOARD_MEMBER_OF and LOCATED_IN are canonical normalizer targets but
--        were not in ontology.relations, causing them to route to candidates
-- Date: 2026-01-13
-- =============================================================================

-- First, ensure the core entity types exist in ontology.types
-- (These may already exist from domain_schema.yaml loading, but ensure they're there)

INSERT INTO ontology.types (
    id, type_name, layer, display_name, description, status, confidence, version
) VALUES
    (gen_random_uuid(), 'PERSON', 1, 'Person', 'A human individual', 'ACTIVE', 0.95, '1.0.0'),
    (gen_random_uuid(), 'ORGANIZATION', 1, 'Organization', 'A company, team, or organizational unit', 'ACTIVE', 0.95, '1.0.0'),
    (gen_random_uuid(), 'LOCATION', 1, 'Location', 'A physical or logical place', 'ACTIVE', 0.95, '1.0.0')
ON CONFLICT (type_name) DO NOTHING;

-- =============================================================================
-- CORE RELATIONSHIP TYPES
-- These are universal relationship types that should always be "known"
-- =============================================================================

-- BOARD_MEMBER_OF: Person serves on board of Organization
INSERT INTO ontology.relations (
    id,
    relation_type,
    display_name,
    description,
    source_type_id,
    target_type_id,
    cardinality,
    status,
    confidence,
    version
) VALUES (
    gen_random_uuid(),
    'BOARD_MEMBER_OF',
    'Board Member Of',
    'Person serves on the board of an organization',
    (SELECT id FROM ontology.types WHERE type_name = 'PERSON' LIMIT 1),
    (SELECT id FROM ontology.types WHERE type_name = 'ORGANIZATION' LIMIT 1),
    'MANY_TO_MANY',
    'ACTIVE',
    0.95,
    '1.0.0'
) ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

-- LOCATED_IN: Organization/Person is located in Location
INSERT INTO ontology.relations (
    id,
    relation_type,
    display_name,
    description,
    source_type_id,
    target_type_id,
    cardinality,
    status,
    confidence,
    version
) VALUES (
    gen_random_uuid(),
    'LOCATED_IN',
    'Located In',
    'Entity is located in a location',
    (SELECT id FROM ontology.types WHERE type_name = 'ORGANIZATION' LIMIT 1),
    (SELECT id FROM ontology.types WHERE type_name = 'LOCATION' LIMIT 1),
    'MANY_TO_MANY',
    'ACTIVE',
    0.95,
    '1.0.0'
) ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

-- LOCATED_IN for Person -> Location (additional variant)
INSERT INTO ontology.relations (
    id,
    relation_type,
    display_name,
    description,
    source_type_id,
    target_type_id,
    cardinality,
    status,
    confidence,
    version
) VALUES (
    gen_random_uuid(),
    'LOCATED_IN',
    'Located In',
    'Person is located in a location',
    (SELECT id FROM ontology.types WHERE type_name = 'PERSON' LIMIT 1),
    (SELECT id FROM ontology.types WHERE type_name = 'LOCATION' LIMIT 1),
    'MANY_TO_MANY',
    'ACTIVE',
    0.95,
    '1.0.0'
) ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

-- =============================================================================
-- Additional core relationship types commonly used in VC/business contexts
-- =============================================================================

-- WORKS_AT: Person works at Organization
INSERT INTO ontology.relations (
    id, relation_type, display_name, description,
    source_type_id, target_type_id, cardinality, status, confidence, version
) VALUES (
    gen_random_uuid(),
    'WORKS_AT',
    'Works At',
    'Person works at an organization',
    (SELECT id FROM ontology.types WHERE type_name = 'PERSON' LIMIT 1),
    (SELECT id FROM ontology.types WHERE type_name = 'ORGANIZATION' LIMIT 1),
    'MANY_TO_MANY',
    'ACTIVE',
    0.95,
    '1.0.0'
) ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

-- HOLDS_POSITION: Person holds position at Organization
INSERT INTO ontology.relations (
    id, relation_type, display_name, description,
    source_type_id, target_type_id, cardinality, status, confidence, version
) VALUES (
    gen_random_uuid(),
    'HOLDS_POSITION',
    'Holds Position',
    'Person holds a position/role at an organization',
    (SELECT id FROM ontology.types WHERE type_name = 'PERSON' LIMIT 1),
    (SELECT id FROM ontology.types WHERE type_name = 'ORGANIZATION' LIMIT 1),
    'MANY_TO_MANY',
    'ACTIVE',
    0.95,
    '1.0.0'
) ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

-- INVESTED_IN: Organization invested in Organization
INSERT INTO ontology.relations (
    id, relation_type, display_name, description,
    source_type_id, target_type_id, cardinality, status, confidence, version
) VALUES (
    gen_random_uuid(),
    'INVESTED_IN',
    'Invested In',
    'Organization invested in another organization',
    (SELECT id FROM ontology.types WHERE type_name = 'ORGANIZATION' LIMIT 1),
    (SELECT id FROM ontology.types WHERE type_name = 'ORGANIZATION' LIMIT 1),
    'MANY_TO_MANY',
    'ACTIVE',
    0.95,
    '1.0.0'
) ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

-- FOUNDED: Person founded Organization
INSERT INTO ontology.relations (
    id, relation_type, display_name, description,
    source_type_id, target_type_id, cardinality, status, confidence, version
) VALUES (
    gen_random_uuid(),
    'FOUNDED',
    'Founded',
    'Person founded an organization',
    (SELECT id FROM ontology.types WHERE type_name = 'PERSON' LIMIT 1),
    (SELECT id FROM ontology.types WHERE type_name = 'ORGANIZATION' LIMIT 1),
    'MANY_TO_MANY',
    'ACTIVE',
    0.95,
    '1.0.0'
) ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

-- =============================================================================
-- End of Migration 016
-- =============================================================================
