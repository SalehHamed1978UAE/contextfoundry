-- Migration 004: Validation Triggers
-- Context Foundry - Session 1, Week 1h/1i
-- Creates: validate_entity_type, validate_relationship (MANUS FIX), check_extension_collision

-- ============================================
-- TENANT CONTEXT FUNCTION FOR RLS
-- ============================================

CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS UUID AS $$
    SELECT NULLIF(current_setting('app.current_tenant_id', true), '')::UUID;
$$ LANGUAGE SQL STABLE;

-- ============================================
-- TRIGGER 1: Validate Entity Type
-- Rejects entities with types not in ontology_types
-- ============================================

CREATE OR REPLACE FUNCTION validate_entity_type()
RETURNS TRIGGER AS $$
DECLARE
    valid_type BOOLEAN;
    type_id UUID;
BEGIN
    -- If entity_type_id is provided, use it directly
    IF NEW.entity_type_id IS NOT NULL THEN
        SELECT EXISTS (
            SELECT 1 FROM ontology_types
            WHERE id = NEW.entity_type_id
            AND NOT is_deprecated
        ) INTO valid_type;
        
        IF NOT valid_type THEN
            RAISE EXCEPTION 'Invalid entity_type_id: %. Type does not exist or is deprecated.', NEW.entity_type_id;
        END IF;
        
        RETURN NEW;
    END IF;
    
    -- If only entity_type string is provided, validate against ontology_types.type_name
    IF NEW.entity_type IS NOT NULL THEN
        SELECT id INTO type_id
        FROM ontology_types
        WHERE type_name = NEW.entity_type
        AND NOT is_deprecated
        LIMIT 1;
        
        IF type_id IS NULL THEN
            RAISE EXCEPTION 'Invalid entity_type: %. Type "%" is not defined in the ontology.', NEW.entity_type, NEW.entity_type;
        END IF;
        
        -- Auto-populate entity_type_id if the column exists
        IF TG_TABLE_NAME = 'entities_v2' THEN
            NEW.entity_type_id := type_id;
        END IF;
        
        RETURN NEW;
    END IF;
    
    -- Neither provided
    RAISE EXCEPTION 'Entity must have either entity_type_id or entity_type specified';
END;
$$ LANGUAGE plpgsql;

-- Apply to entities_v2 (shadow table with new schema)
DROP TRIGGER IF EXISTS validate_entity_type_trigger ON entities_v2;
CREATE TRIGGER validate_entity_type_trigger
    BEFORE INSERT OR UPDATE ON entities_v2
    FOR EACH ROW
    EXECUTE FUNCTION validate_entity_type();

-- ============================================
-- TRIGGER 2: Validate Relationship (MANUS FIX)
-- CORRECTED: Use table alias and compare table columns to local variables
-- Prevents invalid relationships like DATABASE -> PERSON
-- ============================================

CREATE OR REPLACE FUNCTION validate_relationship()
RETURNS TRIGGER AS $$
DECLARE
    v_source_type_id UUID;
    v_target_type_id UUID;
    v_source_type_name VARCHAR;
    v_target_type_name VARCHAR;
    valid_relation BOOLEAN;
BEGIN
    -- Get source entity type
    SELECT entity_type_id, entity_type INTO v_source_type_id, v_source_type_name 
    FROM entities_v2 
    WHERE id = NEW.source_entity_id;
    
    -- Get target entity type
    SELECT entity_type_id, entity_type INTO v_target_type_id, v_target_type_name 
    FROM entities_v2 
    WHERE id = NEW.target_entity_id;
    
    -- If entity_type_ids are available, use them
    IF v_source_type_id IS NOT NULL AND v_target_type_id IS NOT NULL THEN
        -- CORRECTED: Use table alias 'r' and compare table columns to local variables
        SELECT EXISTS (
            SELECT 1 FROM ontology_relations r
            WHERE r.id = NEW.relation_type_id
            AND r.source_type_id = v_source_type_id  -- Compare table column to local variable
            AND r.target_type_id = v_target_type_id  -- Compare table column to local variable
            AND NOT r.is_deprecated
        ) INTO valid_relation;
        
        IF NOT valid_relation THEN
            -- Check if the relation name exists at all
            IF EXISTS (SELECT 1 FROM ontology_relations WHERE id = NEW.relation_type_id) THEN
                RAISE EXCEPTION 'Relationship type % not allowed between entity types % and %. Check ontology_relations for valid source/target pairs.',
                    NEW.relation_type_id, v_source_type_id, v_target_type_id;
            ELSE
                RAISE EXCEPTION 'Unknown relationship type: %', NEW.relation_type_id;
            END IF;
        END IF;
    ELSE
        -- Fallback: Log warning but allow (for migration compatibility)
        RAISE WARNING 'Cannot validate relationship - entities lack entity_type_id. Source: %, Target: %', 
            NEW.source_entity_id, NEW.target_entity_id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- NOTE: This trigger will be applied to relationships_v2 when we create that table
-- For now, we create it but don't attach (relationships table uses old schema)

-- ============================================
-- TRIGGER 3: Tenant Extension Guardrails
-- Prevents Layer 3 extensions from colliding with Core/Domain types
-- ============================================

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

DROP TRIGGER IF EXISTS check_extension_collision ON ontology_types;
CREATE TRIGGER check_extension_collision
    BEFORE INSERT ON ontology_types
    FOR EACH ROW
    EXECUTE FUNCTION check_extension_name_collision();

-- ============================================
-- RLS POLICIES (Week 1g)
-- Multi-tenant isolation
-- ============================================

-- Note: RLS can only be enabled when roles are properly configured
-- For now, we create the policies but don't enable RLS
-- (Enable with: ALTER TABLE entities_v2 ENABLE ROW LEVEL SECURITY;)

-- entities_v2: Tenants can only see their own entities
DROP POLICY IF EXISTS tenant_isolation_entities_v2 ON entities_v2;
CREATE POLICY tenant_isolation_entities_v2 ON entities_v2
    FOR ALL
    USING (tenant_id IS NULL OR tenant_id = current_tenant_id())
    WITH CHECK (tenant_id IS NULL OR tenant_id = current_tenant_id());

-- ontology_types: Tenants can see global types (tenant_id IS NULL) and their own
DROP POLICY IF EXISTS tenant_ontology_types ON ontology_types;
CREATE POLICY tenant_ontology_types ON ontology_types
    FOR SELECT
    USING (tenant_id IS NULL OR tenant_id = current_tenant_id());

-- Only allow tenants to INSERT their own extensions (Layer 3)
DROP POLICY IF EXISTS tenant_ontology_insert ON ontology_types;
CREATE POLICY tenant_ontology_insert ON ontology_types
    FOR INSERT
    WITH CHECK (
        tenant_id IS NULL  -- Allow system inserts
        OR (tenant_id = current_tenant_id() AND layer = 3)  -- Only Layer 3 for tenants
    );

-- ontology_relations: Same pattern
DROP POLICY IF EXISTS tenant_ontology_relations ON ontology_relations;
CREATE POLICY tenant_ontology_relations ON ontology_relations
    FOR SELECT
    USING (tenant_id IS NULL OR tenant_id = current_tenant_id());
