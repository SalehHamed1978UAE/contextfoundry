-- =============================================================================
-- MIGRATION 008: Approval Workflow (RFC v2 §10, §11)
-- =============================================================================
-- Purpose: Human-in-the-loop governance for type/relation promotions
-- Conforms to: RFC v2 §10 (Decision Matrix), §11 (Audit Log)
-- Author: Context Foundry
-- Date: 2025-12-06
-- =============================================================================

-- =============================================================================
-- PART 1: USERS TABLE (shared.users)
-- =============================================================================

CREATE TABLE IF NOT EXISTS shared.users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Identity
    email VARCHAR(255) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    external_id VARCHAR(255),          -- Future Azure AD sync
    
    -- Authorization
    role VARCHAR(50) NOT NULL,
    domain_id VARCHAR(10),             -- NULL for cross-domain roles (ARCHITECTURE_TEAM, HEAD_OF_QDATA)
    
    -- Metadata
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT valid_user_role CHECK (role IN (
        'DOMAIN_LEAD',                 -- Stewards a specific domain
        'ARCHITECTURE_TEAM',           -- Cross-domain schema governance
        'HEAD_OF_QDATA'                -- Final escalation authority
    ))
);

-- =============================================================================
-- PART 2: AUDIT LOG (shared.audit_log) - RFC v2 §11
-- =============================================================================

CREATE TABLE IF NOT EXISTS shared.audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- What changed
    table_name VARCHAR(100) NOT NULL,   -- e.g., 'ontology.types'
    record_id UUID NOT NULL,            -- ID of affected record
    action VARCHAR(20) NOT NULL,        -- CREATE, UPDATE, DELETE, APPROVE, REJECT
    
    -- State capture
    old_state JSONB,                    -- NULL for CREATE
    new_state JSONB,                    -- NULL for DELETE
    change_reason TEXT,
    
    -- Who/when
    performed_by_user_id UUID REFERENCES shared.users(id),
    performed_at TIMESTAMP DEFAULT NOW(),
    
    -- Context
    request_id UUID,                    -- Link to approval_request if applicable
    session_id VARCHAR(100),            -- For correlation
    
    CONSTRAINT valid_audit_action CHECK (action IN (
        'CREATE', 'UPDATE', 'DELETE', 
        'APPROVE', 'REJECT', 'ESCALATE', 
        'PROMOTE', 'DEPRECATE'
    ))
);

CREATE INDEX IF NOT EXISTS idx_audit_log_record ON shared.audit_log(table_name, record_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_performed_at ON shared.audit_log(performed_at);

-- =============================================================================
-- PART 3: APPROVAL REQUESTS (ontology.approval_requests) - RFC v2 §10.3
-- =============================================================================

CREATE TABLE IF NOT EXISTS ontology.approval_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- What needs approval
    request_type VARCHAR(50) NOT NULL,    -- TYPE_PROMOTION, TYPE_DEPRECATION, RELATION_PROMOTION
    target_category VARCHAR(30) NOT NULL, -- CONCRETE_TYPE, ABSTRACT_TYPE, RELATION
    target_id UUID NOT NULL,              -- Type/relation being approved
    target_snapshot JSONB NOT NULL,       -- Full state at request time
    
    -- Routing (per RFC v2 §10.1 decision matrix)
    assigned_level INTEGER NOT NULL,      -- 0=auto, 1=Domain Lead, 2=Architecture Team, 3=Head of QData
    assigned_to_user_id UUID REFERENCES shared.users(id),
    assigned_to_role VARCHAR(50),
    
    -- Context for reviewer
    confidence_score DECIMAL(3,2),
    evidence_summary TEXT,
    validation_results JSONB,             -- Output from validation agents
    llm_recommendation VARCHAR(20),       -- APPROVE, REJECT, NEEDS_INFO
    llm_reasoning TEXT,
    
    -- Lifecycle
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT NOW(),
    sla_deadline TIMESTAMP NOT NULL,
    
    -- Decision
    decision VARCHAR(20),                 -- APPROVED, REJECTED, ESCALATED
    decision_at TIMESTAMP,
    decision_by_user_id UUID REFERENCES shared.users(id),
    decision_notes TEXT,
    
    CONSTRAINT valid_request_type CHECK (request_type IN (
        'TYPE_PROMOTION', 'TYPE_DEPRECATION', 
        'RELATION_PROMOTION', 'RELATION_DEPRECATION'
    )),
    CONSTRAINT valid_target_category CHECK (target_category IN (
        'CONCRETE_TYPE', 'ABSTRACT_TYPE', 'RELATION'
    )),
    CONSTRAINT valid_request_status CHECK (status IN (
        'PENDING', 'APPROVED', 'REJECTED', 'ESCALATED', 'EXPIRED'
    )),
    CONSTRAINT valid_assigned_level CHECK (assigned_level BETWEEN 0 AND 3)
);

CREATE INDEX IF NOT EXISTS idx_approval_requests_status ON ontology.approval_requests(status);
CREATE INDEX IF NOT EXISTS idx_approval_requests_sla ON ontology.approval_requests(sla_deadline) WHERE status = 'PENDING';
CREATE INDEX IF NOT EXISTS idx_approval_requests_assigned ON ontology.approval_requests(assigned_to_user_id) WHERE status = 'PENDING';

-- =============================================================================
-- VERIFICATION
-- =============================================================================

DO $$
BEGIN
    RAISE NOTICE 'Migration 008 complete: Approval workflow tables created';
    RAISE NOTICE '  - shared.users (authorization with Azure AD support)';
    RAISE NOTICE '  - shared.audit_log (governance decision tracking)';
    RAISE NOTICE '  - ontology.approval_requests (human-in-the-loop queue)';
END $$;
