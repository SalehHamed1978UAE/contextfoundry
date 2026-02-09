-- Migration 017: Add Supply Chain Relationship Types
-- =============================================================================
-- Purpose: Add CUSTOMER_OF and SUPPLIER_OF relationship types to ontology.relations
-- Issue: These are being extracted but blocked because they're not in schema
-- Date: 2026-02-09
-- =============================================================================

BEGIN;

-- Ensure we have the Organization type ID
DO $$
DECLARE
    v_org_id UUID;
BEGIN
    SELECT id INTO v_org_id FROM ontology.entity_types
    WHERE entity_type = 'ORGANIZATION' LIMIT 1;

    IF v_org_id IS NULL THEN
        -- Create ORGANIZATION type if it doesn't exist
        INSERT INTO ontology.entity_types (id, entity_type, display_name, description, confidence, status, version)
        VALUES (gen_random_uuid(), 'ORGANIZATION', 'Organization', 'Business entity or company', 0.95, 'ACTIVE', '1.0.0')
        RETURNING id INTO v_org_id;
    END IF;

    -- CUSTOMER_OF: Organization is customer of another organization
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
    )
    VALUES (
        gen_random_uuid(),
        'CUSTOMER_OF',
        'Customer Of',
        'Organization purchases from or is client of another organization',
        v_org_id,
        v_org_id,
        'MANY_TO_MANY',
        'ACTIVE',
        0.95,
        '1.0.0'
    )
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- SUPPLIER_OF: Organization supplies to another organization (inverse of CUSTOMER_OF)
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
    )
    VALUES (
        gen_random_uuid(),
        'SUPPLIER_OF',
        'Supplier Of',
        'Organization provides products or services to another organization',
        v_org_id,
        v_org_id,
        'MANY_TO_MANY',
        'ACTIVE',
        0.95,
        '1.0.0'
    )
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

    -- SUPPLIES_TO: Alternative form of SUPPLIES (for clarity)
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
    )
    VALUES (
        gen_random_uuid(),
        'SUPPLIES_TO',
        'Supplies To',
        'Organization supplies products or services to another organization',
        v_org_id,
        v_org_id,
        'MANY_TO_MANY',
        'ACTIVE',
        0.95,
        '1.0.0'
    )
    ON CONFLICT (relation_type, source_type_id, target_type_id) DO NOTHING;

END $$;

COMMIT;

-- Verify the new relations were added
SELECT relation_type, display_name, description
FROM ontology.relations
WHERE relation_type IN ('CUSTOMER_OF', 'SUPPLIER_OF', 'SUPPLIES', 'SUPPLIES_TO')
ORDER BY relation_type;