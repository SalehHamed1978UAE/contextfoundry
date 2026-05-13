-- Stage 3A — Property Facts table
-- Materializes entity.properties JSON into a queryable relational table.
-- Enables the property plane to answer scalar attribute questions
-- (revenue, budget, capacity, qubits, etc.) without LLM synthesis.
--
-- Not applied to production — migration file only.
-- Apply manually:  psql $DATABASE_URL -f migrations/add_property_facts.sql

BEGIN;

CREATE TABLE IF NOT EXISTS property_facts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id               UUID NOT NULL,
    entity_id               UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    entity_name             VARCHAR(255) NOT NULL,
    entity_type             VARCHAR(100) NOT NULL,
    lifecycle_state         VARCHAR(20) NOT NULL DEFAULT 'STAGING',
    attribute_name          VARCHAR(255) NOT NULL,      -- normalized key: "revenue", "budget"
    attribute_value         TEXT NOT NULL,               -- human-readable: "$8.45 billion"
    numeric_value           DOUBLE PRECISION,            -- parsed float: 8450000000.0
    unit                    VARCHAR(100),                -- "USD", "kg/hr", "Wh/kg"
    value_type              VARCHAR(50),                 -- CURRENCY, PERCENTAGE, COUNT, SPEC, DATE
    period                  VARCHAR(50),                 -- "FY2025", "Q3 2025"
    fiscal_year             VARCHAR(10),                 -- "2025"
    valid_from              TIMESTAMP,
    valid_to                TIMESTAMP,
    source_document_id      VARCHAR(255),
    source_entity_properties JSONB,
    confidence              DOUBLE PRECISION DEFAULT 0.8,
    created_at              TIMESTAMP DEFAULT now(),
    updated_at              TIMESTAMP DEFAULT now()
);

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_property_facts_tenant
    ON property_facts(tenant_id);

CREATE INDEX IF NOT EXISTS idx_property_facts_attribute
    ON property_facts(tenant_id, attribute_name);

CREATE INDEX IF NOT EXISTS idx_property_facts_entity
    ON property_facts(tenant_id, entity_name);

CREATE INDEX IF NOT EXISTS idx_property_facts_entity_id
    ON property_facts(entity_id);

CREATE INDEX IF NOT EXISTS idx_property_facts_lifecycle
    ON property_facts(tenant_id, lifecycle_state);

CREATE INDEX IF NOT EXISTS idx_property_facts_fiscal_year
    ON property_facts(tenant_id, attribute_name, fiscal_year);

-- Row-Level Security (mirrors entities table RLS)
ALTER TABLE property_facts ENABLE ROW LEVEL SECURITY;

-- RLS policy: tenant isolation
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies
        WHERE tablename = 'property_facts'
          AND policyname = 'property_facts_tenant_isolation'
    ) THEN
        CREATE POLICY property_facts_tenant_isolation ON property_facts
            USING (tenant_id = current_setting('app.current_tenant_id')::uuid);
    END IF;
END $$;

COMMIT;
