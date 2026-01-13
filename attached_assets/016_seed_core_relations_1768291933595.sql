-- =============================================================================
-- Migration 016: Seed ALL Core Business Relationship Types
-- =============================================================================
-- Purpose: Stop playing whack-a-mole with missing relationship types.
--          Seed ALL core business types that should exist in EVERY CF deployment.
--
-- History: CF started with IT Ops domain template, but core business relationship
--          types were never properly seeded. This caused repeated bugs:
--          - HAS_COMPENSATION missing → fix it
--          - HOLDS_POSITION missing → fix it
--          - BOARD_MEMBER_OF missing → fix it
--          - LOCATED_IN missing → fix it
--
-- This migration fixes the bucket, not the holes.
-- Date: 2026-01-13
-- =============================================================================

-- =============================================================================
-- PART 1: ENSURE ALL CORE ENTITY TYPES EXIST
-- =============================================================================

INSERT INTO ontology.types (id, type_name, layer, display_name, description, status, confidence, version)
VALUES
    -- Core entities
    (gen_random_uuid(), 'PERSON', 1, 'Person', 'A human individual', 'ACTIVE', 0.95, '1.0.0'),
    (gen_random_uuid(), 'ORGANIZATION', 1, 'Organization', 'A company, team, or organizational unit', 'ACTIVE', 0.95, '1.0.0'),
    (gen_random_uuid(), 'LOCATION', 1, 'Location', 'A physical or logical place', 'ACTIVE', 0.95, '1.0.0'),
    -- Business entities
    (gen_random_uuid(), 'JOB_TITLE', 1, 'Job Title', 'A job title or role', 'ACTIVE', 0.95, '1.0.0'),
    (gen_random_uuid(), 'COMPENSATION', 1, 'Compensation', 'A compensation package', 'ACTIVE', 0.95, '1.0.0'),
    (gen_random_uuid(), 'MONEY', 1, 'Money', 'A monetary amount', 'ACTIVE', 0.95, '1.0.0'),
    (gen_random_uuid(), 'PRODUCT', 1, 'Product', 'A product or offering', 'ACTIVE', 0.95, '1.0.0'),
    (gen_random_uuid(), 'SERVICE', 1, 'Service', 'A service offering', 'ACTIVE', 0.95, '1.0.0'),
    (gen_random_uuid(), 'EVENT', 1, 'Event', 'An event or occurrence', 'ACTIVE', 0.95, '1.0.0'),
    (gen_random_uuid(), 'DATE', 1, 'Date', 'A date or time period', 'ACTIVE', 0.95, '1.0.0'),
    (gen_random_uuid(), 'DOCUMENT', 1, 'Document', 'A document or record', 'ACTIVE', 0.95, '1.0.0')
ON CONFLICT (type_name) DO NOTHING;

-- =============================================================================
-- PART 2: CORE BUSINESS RELATIONSHIP TYPES
-- These should exist in EVERY Context Foundry deployment
-- =============================================================================

-- Helper function to insert relation with error handling
-- (Handles case where source/target types might not exist yet)

DO $$
DECLARE
    v_person_id UUID;
    v_org_id UUID;
    v_location_id UUID;
    v_job_title_id UUID;
    v_compensation_id UUID;
    v_money_id UUID;
    v_product_id UUID;
    v_service_id UUID;
BEGIN
    -- Get type IDs
    SELECT id INTO v_person_id FROM ontology.types WHERE type_name = 'PERSON' LIMIT 1;
    SELECT id INTO v_org_id FROM ontology.types WHERE type_name = 'ORGANIZATION' LIMIT 1;
    SELECT id INTO v_location_id FROM ontology.types WHERE type_name = 'LOCATION' LIMIT 1;
    SELECT id INTO v_job_title_id FROM ontology.types WHERE type_name = 'JOB_TITLE' LIMIT 1;
    SELECT id INTO v_compensation_id FROM ontology.types WHERE type_name = 'COMPENSATION' LIMIT 1;
    SELECT id INTO v_money_id FROM ontology.types WHERE type_name = 'MONEY' LIMIT 1;
    SELECT id INTO v_product_id FROM ontology.types WHERE type_name = 'PRODUCT' LIMIT 1;
    SELECT id INTO v_service_id FROM ontology.types WHERE type_name = 'SERVICE' LIMIT 1;

    -- ==========================================================================
    -- EMPLOYMENT & ORGANIZATION RELATIONSHIPS
    -- ==========================================================================

    -- WORKS_AT: Person works at Organization
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'WORKS_AT', 'Works At', 'Person is employed by organization', v_person_id, v_org_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- HOLDS_POSITION: Person holds job title
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'HOLDS_POSITION', 'Holds Position', 'Person holds a job title/role', v_person_id, v_job_title_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- HOLDS_POSITION variant: Person holds position at Organization (for when we don't have JOB_TITLE entity)
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'HOLDS_POSITION', 'Holds Position', 'Person holds a position at organization', v_person_id, v_org_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- REPORTS_TO: Person reports to Person
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'REPORTS_TO', 'Reports To', 'Person reports to another person', v_person_id, v_person_id, 'MANY_TO_ONE', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- MANAGES: Person manages Person
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'MANAGES', 'Manages', 'Person manages another person', v_person_id, v_person_id, 'ONE_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- MEMBER_OF: Person is member of Organization
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'MEMBER_OF', 'Member Of', 'Person is member of organization', v_person_id, v_org_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- ==========================================================================
    -- COMPENSATION RELATIONSHIPS
    -- ==========================================================================

    -- HAS_COMPENSATION: Person has compensation
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'HAS_COMPENSATION', 'Has Compensation', 'Person has compensation package', v_person_id, v_compensation_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- HAS_SALARY: Person has salary
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'HAS_SALARY', 'Has Salary', 'Person has base salary', v_person_id, v_money_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- HAS_BONUS: Person has bonus
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'HAS_BONUS', 'Has Bonus', 'Person has bonus', v_person_id, v_money_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- ==========================================================================
    -- BOARD & GOVERNANCE RELATIONSHIPS
    -- ==========================================================================

    -- BOARD_MEMBER_OF: Person serves on board
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'BOARD_MEMBER_OF', 'Board Member Of', 'Person serves on board of organization', v_person_id, v_org_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- FOUNDED: Person founded Organization
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'FOUNDED', 'Founded', 'Person founded organization', v_person_id, v_org_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- OWNS: Person/Org owns Organization
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'OWNS', 'Owns', 'Person owns organization', v_person_id, v_org_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'OWNS', 'Owns', 'Organization owns another organization', v_org_id, v_org_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- ==========================================================================
    -- INVESTMENT RELATIONSHIPS
    -- ==========================================================================

    -- INVESTED_IN: Organization invested in Organization
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'INVESTED_IN', 'Invested In', 'Organization invested in another organization', v_org_id, v_org_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- HAS_PORTFOLIO_COMPANY: VC/PE has portfolio company
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'HAS_PORTFOLIO_COMPANY', 'Has Portfolio Company', 'VC/PE fund has portfolio company', v_org_id, v_org_id, 'ONE_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- ACQUIRED: Organization acquired another
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'ACQUIRED', 'Acquired', 'Organization acquired another organization', v_org_id, v_org_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- ==========================================================================
    -- LOCATION RELATIONSHIPS
    -- ==========================================================================

    -- LOCATED_IN: Organization/Person is located in Location
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'LOCATED_IN', 'Located In', 'Organization is located in location', v_org_id, v_location_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'LOCATED_IN', 'Located In', 'Person is located in location', v_person_id, v_location_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- HEADQUARTERED_IN: Organization HQ location
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'HEADQUARTERED_IN', 'Headquartered In', 'Organization is headquartered in location', v_org_id, v_location_id, 'MANY_TO_ONE', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- ==========================================================================
    -- ORGANIZATIONAL STRUCTURE RELATIONSHIPS
    -- ==========================================================================

    -- SUBSIDIARY_OF: Organization is subsidiary of parent
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'SUBSIDIARY_OF', 'Subsidiary Of', 'Organization is subsidiary of parent organization', v_org_id, v_org_id, 'MANY_TO_ONE', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- DIVISION_OF: Division belongs to org
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'DIVISION_OF', 'Division Of', 'Division belongs to organization', v_org_id, v_org_id, 'MANY_TO_ONE', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- PARTNER_OF: Organizations are partners
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'PARTNER_OF', 'Partner Of', 'Organizations are partners', v_org_id, v_org_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- ==========================================================================
    -- PRODUCT & SERVICE RELATIONSHIPS
    -- ==========================================================================

    -- PRODUCES: Organization produces product
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'PRODUCES', 'Produces', 'Organization produces product', v_org_id, v_product_id, 'ONE_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- PROVIDES_SERVICE: Organization provides service
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'PROVIDES_SERVICE', 'Provides Service', 'Organization provides service', v_org_id, v_service_id, 'ONE_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- SUPPLIES: Organization supplies another
    INSERT INTO ontology.relations (id, relation_type, display_name, description, source_type_id, target_type_id, cardinality, status, confidence, version)
    VALUES (gen_random_uuid(), 'SUPPLIES', 'Supplies', 'Organization supplies another organization', v_org_id, v_org_id, 'MANY_TO_MANY', 'ACTIVE', 0.95, '1.0.0')
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    RAISE NOTICE 'Core business relationship types seeded successfully';
END $$;

-- =============================================================================
-- VERIFICATION QUERY (run after migration)
-- =============================================================================
-- SELECT relation_type, COUNT(*) as variants
-- FROM ontology.relations
-- WHERE relation_type IN (
--   'WORKS_AT', 'HOLDS_POSITION', 'REPORTS_TO', 'MANAGES', 'MEMBER_OF',
--   'HAS_COMPENSATION', 'HAS_SALARY', 'HAS_BONUS',
--   'BOARD_MEMBER_OF', 'FOUNDED', 'OWNS',
--   'INVESTED_IN', 'HAS_PORTFOLIO_COMPANY', 'ACQUIRED',
--   'LOCATED_IN', 'HEADQUARTERED_IN',
--   'SUBSIDIARY_OF', 'DIVISION_OF', 'PARTNER_OF',
--   'PRODUCES', 'PROVIDES_SERVICE', 'SUPPLIES'
-- )
-- GROUP BY relation_type
-- ORDER BY relation_type;
-- =============================================================================
-- End of Migration 016 - Core Business Relationship Types
-- =============================================================================
