# Context Foundry: Decision Trace Layer v1.0
## Final Canonical Specification

**Version**: 1.0 (Patched)  
**Date**: January 7, 2026  
**Status**: Production-Ready  
**Platform**: Replit (Neon Postgres + pgvector)  
**Reviewed By**: Claude + ChatGPT collaborative review  

---

## Document History

| Version | Date | Changes |
|---------|------|---------|
| 1.0-draft | Jan 7, 2026 | Initial synthesis from 4-model research |
| 1.0-patched | Jan 7, 2026 | Applied ChatGPT's 6 structural fixes |
| 1.0-final | Jan 7, 2026 | Applied ChatGPT's 4 production hardening fixes |
| 1.0-ship | Jan 7, 2026 | Applied ChatGPT's 3 final nits + 2 optional tweaks |

### Fixes Applied (Round 1 — Structural)

1. **Removed `approver_ids UUID[]`** — Uses `decision_entity_links` with `entity_role='approver'`
2. **Sensitivity as column** — Security metadata is NOT in JSONB
3. **Split outcomes** — Three tables: `decision_executions`, `decision_results`, `decision_assessments`
4. **Category as ranking bonus** — `search_precedents` uses soft ranking, not hard filter
5. **Evidence required** — Deferrable constraint trigger blocks enacted decisions without evidence
6. **HNSW index** — Replaced IVFFLAT with HNSW for vector search

### Fixes Applied (Round 2 — Production Hardening)

A. **Agent entity requirement** — Agents must have entity IDs; `decision_maker_id` is never NULL
B. **RLS on child tables** — Evidence, exceptions, results, assessments all have RLS policies
C. **Evidence quality gate** — CHECK constraint requires substantive content (not just "ok")
D. **Stable API wrapper** — `search_precedents_api()` isolates API from internal tuning changes

### Fixes Applied (Round 3 — Final Nits)

A. **Explicit tenant_id in child RLS** — Child table policies now explicitly check `tenant_id` to prevent RLS bypass
B. **decision_maker_id required in API** — `DecisionCreate` model now requires `decision_maker_id` (matches DDL)
C. **PrecedentSearchClient uses wrapper** — All code paths now call `search_precedents_api()`

### Optional Tweaks (Recommended)

1. **Unique entity role index** — Prevents duplicate approver/subject links per decision
2. **Evidence deletion guard** — Prevents deleting last evidence from enacted decisions

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture](#2-architecture)
3. [Database Schema (Patched DDL)](#3-database-schema-patched-ddl)
4. [Precedent Search](#4-precedent-search)
5. [Agent Integration](#5-agent-integration)
6. [Schema Evolution](#6-schema-evolution)
7. [API Layer](#7-api-layer)
8. [Replit Deployment](#8-replit-deployment)
9. [Implementation Plan](#9-implementation-plan)

---

## 1. Executive Summary

### What This Is

The **Decision Trace Layer (DTL)** extends Context Foundry's Knowledge Graph with a **precedent-aware decision memory**. While CF captures *what exists* (entities, relationships), DTL captures *why decisions were made* (rationale, precedents, exceptions, outcomes).

### Core Principle

> **Context Foundry refuses to hallucinate and admits uncertainty. The Decision Trace Layer extends this by grounding agent reasoning in actual organizational precedent — not invented rationale.**

### What This Enables

1. **Precedent-Aware Agents**: "Have we approved a 25% discount before? Under what circumstances?"
2. **Reduced Hallucination**: Agents cite real decisions, not fabricated justifications
3. **Knowledge Retention**: Decision rationale persists when decision-makers leave
4. **Policy Drift Detection**: System detects when "exceptions" have become the actual rule
5. **Compliance & Audit**: Complete decision chain visible for regulatory review

### Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| Bi-temporal modeling | Required for "what was known when" queries |
| Choice ≠ Execution ≠ Outcome ≠ Assessment | Agents must learn that good decisions can fail |
| Categories are nullable | Types emerge from patterns, not predefined |
| Evidence is required | Decisions without receipts cannot be enacted |
| Category is ranking signal, not filter | Avoids premature taxonomy lock-in |
| HNSW over IVFFLAT | More forgiving for evolving datasets |

---

## 2. Architecture

### 2.1 The Four-Layer Model

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  LAYER 4: META-LEARNING (Emergent)                                          │
│  • Category proposals & lifecycle (proposed → active → deprecated → merged) │
│  • Policy drift detection ("exception rate rising")                         │
│  • Exception inversion alerts ("80% exception = new rule")                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  LAYER 3: EXECUTION & OUTCOME (Temporal)                                    │
│  • decision_executions: What actions were taken                             │
│  • decision_results: What happened (metrics, success/failure)               │
│  • decision_assessments: Was this a good decision? (retrospective)          │
├─────────────────────────────────────────────────────────────────────────────┤
│  LAYER 2: RATIONALE GRAPH (Expandable)                                      │
│  • Stated rationale + inferred factors                                      │
│  • Evidence links (source messages, documents)                              │
│  • Precedents cited (with follow/deviate reasoning)                         │
│  • Exceptions invoked (policy waivers)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│  LAYER 1: DECISION EVENT (Immutable)                                        │
│  • What was decided (decision_choice JSONB)                                 │
│  • Who decided (decision_maker_id + approvers via entity_links)             │
│  • When (bi-temporal: valid_time + transaction_time)                        │
│  • Context snapshot (state of world at decision time)                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Agent Memory Model (MemGPT Pattern)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  WORKING CONTEXT (Agent's Active Memory)                                    │
│  • Current conversation state                                               │
│  • Loaded precedents (retrieved from DTL)                                   │
│  • Active policy constraints                                                │
│  • Observations made during this session                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│  EPISODIC MEMORY (Decision Trace Layer)                                     │
│  • Historical decision traces                                               │
│  • Precedent links & similarity scores                                      │
│  • Outcome history & success rates                                          │
└─────────────────────────────────────────────────────────────────────────────┘

Agent Decision Cycle:
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│   LOAD   │────►│  REASON  │────►│   ACT    │────►│  FLUSH   │
│ Query    │     │ Apply    │     │ Execute  │     │ Write    │
│ precedent│     │ precedent│     │ decision │     │ trace    │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

### 2.3 Case-Based Reasoning (CBR) Cycle

| Phase | Action | System Interaction |
|-------|--------|-------------------|
| **RETRIEVE** | Find similar past decisions | `search_precedents()` → top-k matches |
| **REUSE** | Propose solution from best precedent | Adapt precedent to current case |
| **REVISE** | Adapt solution with human input | Modifications + rationale |
| **RETAIN** | Store new decision as future precedent | New trace with precedent links |

---

## 3. Database Schema (Patched DDL)

This is the **canonical, production-ready DDL** with all 6 fixes applied.

```sql
/* ============================================================================
   Context Foundry — Decision Trace Layer (DTL) v1.0 PATCHED DDL
   
   Fixes Applied:
   1. Removes approver_ids array; uses decision_entity_links (entity_role='approver')
   2. Adds sensitivity column (NOT inside JSONB)
   3. Splits outcomes into executions/results/assessments
   4. search_precedents uses decision_type as RANKING BONUS, not a hard filter
   5. Enforces evidence required for enacted decisions via DEFERRABLE constraint trigger
   6. Switches vector index from IVFFLAT to HNSW
   ============================================================================ */

BEGIN;

-- ----------------------------------------------------------------------------
-- EXTENSIONS
-- ----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "btree_gist";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ----------------------------------------------------------------------------
-- TYPES / ENUMS
-- ----------------------------------------------------------------------------
DO $$ BEGIN
  CREATE TYPE decision_lifecycle AS ENUM (
    'draft','proposed','approved','enacted','superseded','expired','revoked'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE category_lifecycle AS ENUM ('proposed','active','deprecated','merged');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE sensitivity_level AS ENUM ('public','internal','confidential','restricted');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE evidence_type AS ENUM (
    'slack_msg','email','meeting_segment','jira','doc','pr_comment','code_review','manual_note','agent_log'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE decision_entity_role AS ENUM (
    'subject','affected_party','decision_maker','approver','advisor','implementer',
    'policy','system_consulted','context'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE result_status AS ENUM ('positive','neutral','negative','unknown');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ----------------------------------------------------------------------------
-- CORE TABLE: decision_traces (L1 Decision Event)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_traces (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id VARCHAR(50) NOT NULL UNIQUE,              -- human-readable id e.g. DEC-2026-00001234

  -- Bi-temporal
  valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  valid_until TIMESTAMPTZ NOT NULL DEFAULT 'infinity',
  sys_period TSTZRANGE NOT NULL DEFAULT tstzrange(NOW(), NULL, '[)'),

  -- Core metadata
  decision_timestamp TIMESTAMPTZ NOT NULL,
  decision_summary TEXT NOT NULL,

  -- Decision choice (fast path)
  decision_choice JSONB NOT NULL DEFAULT '{}'::jsonb,

  -- Decision maker (single)
  decision_maker_id UUID NOT NULL,                      -- references CF entities.id logically

  -- Category is a hypothesis (nullable)
  decision_type TEXT NULL,
  decision_type_confidence NUMERIC(3,2) NULL,

  -- Rationale (kept here for simplicity + search)
  rationale_summary TEXT NULL,
  rationale_structured JSONB NOT NULL DEFAULT '{}'::jsonb,

  -- Semantic search vector (use same dimension as your embedder)
  rationale_embedding VECTOR(1536),

  -- Context snapshot at time of decision
  context_snapshot JSONB NOT NULL DEFAULT '{}'::jsonb,

  -- Lifecycle
  lifecycle_state decision_lifecycle NOT NULL DEFAULT 'draft',

  -- Source tracking
  source_system TEXT NOT NULL,                           -- slack/email/agent/manual/etc.
  source_reference TEXT NULL,
  extraction_confidence NUMERIC(3,2) NULL,

  -- ✅ FIX 2: security classification is a column, not JSON
  sensitivity sensitivity_level NOT NULL DEFAULT 'internal',

  -- Audit / tenancy
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by VARCHAR(255) NOT NULL,
  tenant_id UUID NOT NULL,

  CONSTRAINT valid_time_range CHECK (valid_from < valid_until)
);

-- ----------------------------------------------------------------------------
-- L2: decision_entity_links (replaces approver_ids array)
-- ✅ FIX 1: Approvers are linked via entity_role='approver'
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_entity_links (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  entity_id UUID NOT NULL,                               -- CF entities.id
  entity_role decision_entity_role NOT NULL,

  -- optional: when this entity acted (approval time, implementation time, etc.)
  acted_at TIMESTAMPTZ NULL,

  -- resolution metadata (for extracted decisions)
  resolution_method VARCHAR(50) NULL,                    -- exact_match/fuzzy/llm_inferred/manual
  resolution_confidence NUMERIC(3,2) NULL,

  -- optional snapshot of entity state at decision time
  entity_state_at_decision JSONB NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- ✅ FIX 5: decision_evidence (receipts / provenance)
-- Evidence MUST exist for enacted decisions (enforced by trigger below)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_evidence (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  evidence_type evidence_type NOT NULL,
  source_uri TEXT NULL,                                  -- permalink / URL (if available)
  source_id TEXT NULL,                                   -- slack msg id, email msg id, jira id, etc.
  excerpt TEXT NULL,                                     -- short excerpt for grounding
  excerpt_hash TEXT NULL,                                -- dedupe
  event_timestamp TIMESTAMPTZ NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- L2: decision_precedent_links
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_precedent_links (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,
  precedent_decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  link_type VARCHAR(50) NOT NULL,                         -- cited/distinguished/overruled/extended/conflicts_with
  similarity_score NUMERIC(4,3) NULL,
  match_reasoning TEXT NULL,

  precedent_applied BOOLEAN NOT NULL DEFAULT TRUE,
  deviation_reason TEXT NULL,

  discovered_by VARCHAR(50) NOT NULL,                     -- system_auto/user_manual/agent
  discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT no_self_reference CHECK (decision_id != precedent_decision_id),
  CONSTRAINT valid_link_type CHECK (
    link_type IN ('cited','distinguished','overruled','extended','conflicts_with')
  )
);

-- ----------------------------------------------------------------------------
-- L2: decision_exceptions
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_exceptions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  policy_id UUID NULL,
  policy_name VARCHAR(255) NOT NULL,
  policy_version VARCHAR(50) NULL,

  exception_type VARCHAR(100) NOT NULL,
  exception_aspect TEXT NOT NULL,

  policy_limit JSONB NULL,
  actual_value JSONB NULL,
  deviation_magnitude JSONB NULL,

  exception_justification TEXT NOT NULL,

  exception_requested_by UUID NULL,
  exception_approved_by UUID NULL,

  risk_acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
  risk_notes TEXT NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- L2: decision_confidence_scores
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_confidence_scores (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  overall_confidence NUMERIC(4,3) NOT NULL,

  extraction_accuracy NUMERIC(4,3) NULL,
  source_reliability NUMERIC(4,3) NULL,
  temporal_certainty NUMERIC(4,3) NULL,
  rationale_completeness NUMERIC(4,3) NULL,
  entity_resolution_confidence NUMERIC(4,3) NULL,

  scoring_model_version VARCHAR(50) NOT NULL,
  human_reviewed BOOLEAN NOT NULL DEFAULT FALSE,
  reviewer_id UUID NULL,
  reviewed_at TIMESTAMPTZ NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- ✅ FIX 3: Split outcomes into executions/results/assessments
-- This separation is CRITICAL for agent learning:
--   - A good decision can have a bad outcome (bad luck)
--   - A bad decision can have a good outcome (good luck)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_executions (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  expected_outcome JSONB NULL,

  execution_result JSONB NULL,                            -- what actions were taken / tool calls / change ids
  executed_at TIMESTAMPTZ NULL,
  executed_by_entity_id UUID NULL,                        -- CF entity (agent or human)

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decision_results (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  outcome_status result_status NOT NULL DEFAULT 'unknown',
  outcome_metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
  observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  result_notes TEXT NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decision_assessments (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,

  -- "good decision" quality score (not the same as outcome)
  decision_quality_score NUMERIC(4,3) NULL,
  assessment_notes TEXT NULL,
  assessment_confidence NUMERIC(3,2) NULL,

  assessed_at TIMESTAMPTZ NULL,
  assessed_by_entity_id UUID NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- L4: decision_categories
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_categories (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL,

  name TEXT NOT NULL,
  description TEXT NULL,

  emerged_from_clustering BOOLEAN NOT NULL DEFAULT TRUE,
  cluster_id VARCHAR(100) NULL,

  human_validated BOOLEAN NOT NULL DEFAULT FALSE,
  validated_by UUID NULL,
  validated_at TIMESTAMPTZ NULL,

  prototype_embedding VECTOR(1536) NULL,
  typical_attributes JSONB NOT NULL DEFAULT '{}'::jsonb,

  lifecycle category_lifecycle NOT NULL DEFAULT 'proposed',
  merged_into_id UUID NULL REFERENCES decision_categories(id),

  usage_count INTEGER NOT NULL DEFAULT 0,
  last_used_at TIMESTAMPTZ NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Schema evolution proposals
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS schema_evolution_proposals (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL,

  proposal_type VARCHAR(50) NOT NULL,                    -- new_category/merge_categories/policy_update/exception_promotion/promote_attribute/category_deprecation
  detection_method VARCHAR(50) NULL,

  supporting_decision_count INTEGER NOT NULL,
  supporting_decision_ids UUID[] NULL,
  detection_confidence NUMERIC(3,2) NOT NULL,

  proposal_summary TEXT NOT NULL,
  proposal_details JSONB NOT NULL DEFAULT '{}'::jsonb,
  recommendation TEXT NULL,

  status VARCHAR(20) NOT NULL DEFAULT 'pending',         -- pending/under_review/approved/rejected/implemented
  reviewed_by UUID NULL,
  reviewed_at TIMESTAMPTZ NULL,
  review_notes TEXT NULL,

  implemented_at TIMESTAMPTZ NULL,
  implementation_notes TEXT NULL,

  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- Access grants + audit
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS decision_access_grants (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL,
  decision_id UUID NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,
  grantee_id UUID NOT NULL,                               -- CF entity id
  granted_by UUID NULL,
  granted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decision_access_audit (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  tenant_id UUID NOT NULL,

  accessor_id UUID NOT NULL,
  accessor_role VARCHAR(100) NULL,

  decision_id UUID NULL REFERENCES decision_traces(id),
  access_type VARCHAR(20) NOT NULL,                       -- read/search/export
  access_granted BOOLEAN NOT NULL,
  denial_reason TEXT NULL,

  access_reason TEXT NULL,
  client_ip VARCHAR(45) NULL,
  user_agent TEXT NULL,

  accessed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------------------
-- INDEXES
-- ----------------------------------------------------------------------------

-- Core decision queries
CREATE INDEX IF NOT EXISTS idx_decisions_org_date ON decision_traces(tenant_id, decision_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_decisions_lifecycle ON decision_traces(lifecycle_state);
CREATE INDEX IF NOT EXISTS idx_decisions_maker ON decision_traces(decision_maker_id);
CREATE INDEX IF NOT EXISTS idx_decisions_type ON decision_traces(decision_type) WHERE decision_type IS NOT NULL;

-- Bi-temporal
CREATE INDEX IF NOT EXISTS idx_decisions_valid_time ON decision_traces USING GIST (tstzrange(valid_from, valid_until, '[)'));
CREATE INDEX IF NOT EXISTS idx_decisions_sys_period ON decision_traces USING GIST (sys_period);

-- Full-text search (rationale + summary)
CREATE INDEX IF NOT EXISTS idx_decisions_rationale_fts
ON decision_traces USING GIN (
  to_tsvector('english', COALESCE(decision_summary,'') || ' ' || COALESCE(rationale_summary,''))
);

-- ✅ FIX 6: HNSW vector index (preferred over IVFFLAT)
CREATE INDEX IF NOT EXISTS idx_decisions_rationale_hnsw
ON decision_traces USING hnsw (rationale_embedding vector_cosine_ops);

-- Links
CREATE INDEX IF NOT EXISTS idx_entity_links_decision ON decision_entity_links(decision_id);
CREATE INDEX IF NOT EXISTS idx_entity_links_entity ON decision_entity_links(entity_id);
CREATE INDEX IF NOT EXISTS idx_entity_links_role ON decision_entity_links(entity_role);

CREATE INDEX IF NOT EXISTS idx_evidence_decision ON decision_evidence(decision_id);
CREATE INDEX IF NOT EXISTS idx_evidence_type ON decision_evidence(evidence_type);

CREATE INDEX IF NOT EXISTS idx_precedent_links_decision ON decision_precedent_links(decision_id);
CREATE INDEX IF NOT EXISTS idx_precedent_links_precedent ON decision_precedent_links(precedent_decision_id);

CREATE INDEX IF NOT EXISTS idx_exceptions_decision ON decision_exceptions(decision_id);
CREATE INDEX IF NOT EXISTS idx_exceptions_policy_name ON decision_exceptions(policy_name);

CREATE INDEX IF NOT EXISTS idx_confidence_decision ON decision_confidence_scores(decision_id);

CREATE INDEX IF NOT EXISTS idx_exec_decision ON decision_executions(decision_id);
CREATE INDEX IF NOT EXISTS idx_results_decision ON decision_results(decision_id);
CREATE INDEX IF NOT EXISTS idx_results_status ON decision_results(outcome_status);
CREATE INDEX IF NOT EXISTS idx_assess_decision ON decision_assessments(decision_id);

CREATE INDEX IF NOT EXISTS idx_categories_org ON decision_categories(tenant_id);
CREATE INDEX IF NOT EXISTS idx_categories_lifecycle ON decision_categories(lifecycle);

CREATE INDEX IF NOT EXISTS idx_access_grants_decision ON decision_access_grants(decision_id);
CREATE INDEX IF NOT EXISTS idx_access_grants_grantee ON decision_access_grants(grantee_id);

CREATE INDEX IF NOT EXISTS idx_audit_decision ON decision_access_audit(decision_id);
CREATE INDEX IF NOT EXISTS idx_audit_accessor ON decision_access_audit(accessor_id);
CREATE INDEX IF NOT EXISTS idx_audit_time ON decision_access_audit(accessed_at DESC);

-- ----------------------------------------------------------------------------
-- ✅ FIX 5: Evidence must exist for enacted decisions (DEFERRABLE constraint)
-- ----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION dtl_enforce_evidence_for_enacted()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF NEW.lifecycle_state = 'enacted' THEN
    IF NOT EXISTS (
      SELECT 1 FROM decision_evidence de WHERE de.decision_id = NEW.id
    ) THEN
      RAISE EXCEPTION 'Decision % is enacted but has no evidence. Add at least one decision_evidence row before COMMIT.', NEW.id;
    END IF;
  END IF;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_decision_requires_evidence ON decision_traces;

CREATE CONSTRAINT TRIGGER trg_decision_requires_evidence
AFTER INSERT OR UPDATE OF lifecycle_state ON decision_traces
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW
EXECUTE FUNCTION dtl_enforce_evidence_for_enacted();

-- ----------------------------------------------------------------------------
-- ROW LEVEL SECURITY (RLS) — patched to use sensitivity column (not JSON)
-- ----------------------------------------------------------------------------
ALTER TABLE decision_traces ENABLE ROW LEVEL SECURITY;

-- Org isolation (assumes app sets: app.current_tenant_id)
DROP POLICY IF EXISTS org_isolation ON decision_traces;
CREATE POLICY org_isolation ON decision_traces
  FOR ALL
  USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Read policy (assumes app sets: app.current_user_id, app.current_user_role)
DROP POLICY IF EXISTS decision_read_policy ON decision_traces;
CREATE POLICY decision_read_policy ON decision_traces
  FOR SELECT
  USING (
    tenant_id = current_setting('app.current_tenant_id')::uuid
    AND (
      sensitivity = 'public'
      OR sensitivity = 'internal'
      OR (
        sensitivity = 'confidential' AND (
          current_setting('app.current_user_role', true) IN ('admin','compliance','leadership')
          OR EXISTS (
            SELECT 1
            FROM decision_entity_links del
            WHERE del.decision_id = decision_traces.id
              AND del.entity_id = current_setting('app.current_user_id')::uuid
          )
        )
      )
      OR (
        sensitivity = 'restricted' AND (
          decision_maker_id = current_setting('app.current_user_id')::uuid
          OR EXISTS (
            SELECT 1 FROM decision_access_grants dag
            WHERE dag.decision_id = decision_traces.id
              AND dag.grantee_id = current_setting('app.current_user_id')::uuid
          )
        )
      )
    )
  );

-- ✅ FIX B: RLS on child tables (evidence, exceptions, results, assessments)
-- Child tables inherit access through their parent decision_traces row
-- ✅ FIX NIT A: Explicitly check tenant_id to avoid RLS bypass via query shape

ALTER TABLE decision_evidence ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS evidence_via_decision ON decision_evidence;
CREATE POLICY evidence_via_decision ON decision_evidence
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM decision_traces dt
      WHERE dt.id = decision_evidence.decision_id
        AND dt.tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

ALTER TABLE decision_exceptions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS exceptions_via_decision ON decision_exceptions;
CREATE POLICY exceptions_via_decision ON decision_exceptions
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM decision_traces dt
      WHERE dt.id = decision_exceptions.decision_id
        AND dt.tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

ALTER TABLE decision_results ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS results_via_decision ON decision_results;
CREATE POLICY results_via_decision ON decision_results
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM decision_traces dt
      WHERE dt.id = decision_results.decision_id
        AND dt.tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

ALTER TABLE decision_assessments ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS assessments_via_decision ON decision_assessments;
CREATE POLICY assessments_via_decision ON decision_assessments
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM decision_traces dt
      WHERE dt.id = decision_assessments.decision_id
        AND dt.tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

ALTER TABLE decision_executions ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS executions_via_decision ON decision_executions;
CREATE POLICY executions_via_decision ON decision_executions
  FOR ALL
  USING (
    EXISTS (
      SELECT 1 FROM decision_traces dt
      WHERE dt.id = decision_executions.decision_id
        AND dt.tenant_id = current_setting('app.current_tenant_id')::uuid
    )
  );

-- ✅ FIX C: Evidence quality gate (at least one substantive field required)
ALTER TABLE decision_evidence DROP CONSTRAINT IF EXISTS evidence_has_substance;
ALTER TABLE decision_evidence ADD CONSTRAINT evidence_has_substance CHECK (
  source_uri IS NOT NULL 
  OR source_id IS NOT NULL 
  OR (excerpt IS NOT NULL AND LENGTH(excerpt) >= 10)
);

-- ✅ OPTIONAL TWEAK 1: Prevent duplicate entity roles per decision
-- (e.g., same person listed as approver twice)
CREATE UNIQUE INDEX IF NOT EXISTS uq_decision_entity_role
ON decision_entity_links(decision_id, entity_id, entity_role);

-- ✅ OPTIONAL TWEAK 2: Prevent evidence deletion when decision is enacted
CREATE OR REPLACE FUNCTION dtl_prevent_evidence_deletion_when_enacted()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM decision_traces dt 
    WHERE dt.id = OLD.decision_id 
      AND dt.lifecycle_state = 'enacted'
  ) THEN
    -- Check if this is the last evidence row
    IF NOT EXISTS (
      SELECT 1 FROM decision_evidence de 
      WHERE de.decision_id = OLD.decision_id 
        AND de.id != OLD.id
    ) THEN
      RAISE EXCEPTION 'Cannot delete last evidence row for enacted decision %', OLD.decision_id;
    END IF;
  END IF;
  RETURN OLD;
END;
$$;

DROP TRIGGER IF EXISTS trg_prevent_evidence_deletion ON decision_evidence;
CREATE TRIGGER trg_prevent_evidence_deletion
BEFORE DELETE ON decision_evidence
FOR EACH ROW
EXECUTE FUNCTION dtl_prevent_evidence_deletion_when_enacted();

COMMIT;
```

---

## 4. Precedent Search

### 4.1 search_precedents Function

This is the **canonical search function** with Fix #4 applied: category is a **ranking bonus**, not a hard filter.

```sql
-- ✅ FIX 4: search_precedents — category is a ranking bonus, not a filter
-- Also adds entity overlap signal + confidence gate + optional negative-outcome filtering

DROP FUNCTION IF EXISTS search_precedents(
  TEXT, VECTOR(1536), UUID, TEXT, UUID[], FLOAT, INT, BOOLEAN, INT, FLOAT, FLOAT, FLOAT, FLOAT
);

CREATE OR REPLACE FUNCTION search_precedents(
  p_query_text TEXT,
  p_query_embedding VECTOR(1536),
  p_tenant_id UUID,
  p_decision_type_hint TEXT DEFAULT NULL,     -- soft hint (RANKING BONUS only)
  p_required_entity_ids UUID[] DEFAULT NULL,  -- optional constraint signal
  p_min_overall_confidence FLOAT DEFAULT 0.0,
  p_limit INT DEFAULT 10,
  p_include_negative_outcomes BOOLEAN DEFAULT TRUE,

  -- scoring knobs
  p_rrf_k INT DEFAULT 60,
  p_recency_half_life_days INT DEFAULT 180,
  p_recency_weight FLOAT DEFAULT 0.30,
  p_outcome_weight FLOAT DEFAULT 0.15,
  p_category_bonus_weight FLOAT DEFAULT 0.05,
  p_entity_bonus_weight FLOAT DEFAULT 0.05
)
RETURNS TABLE (
  decision_id UUID,
  decision_human_id VARCHAR,
  summary TEXT,
  decision_type TEXT,
  rationale_summary TEXT,
  choice JSONB,
  decision_timestamp TIMESTAMPTZ,
  decision_maker_id UUID,
  outcome_status result_status,

  -- explainability signals
  semantic_rank INT,
  fulltext_rank INT,
  entity_rank INT,

  semantic_score FLOAT,
  fulltext_score FLOAT,
  entity_overlap_score FLOAT,
  recency_score FLOAT,
  outcome_score FLOAT,
  category_bonus FLOAT,

  rrf_score FLOAT
)
LANGUAGE plpgsql
AS $$
DECLARE
  k INT := p_rrf_k;
BEGIN
  RETURN QUERY
  WITH base AS (
    SELECT
      dt.*,
      COALESCE(dcs.overall_confidence::float, 0.5) AS overall_conf
    FROM decision_traces dt
    LEFT JOIN LATERAL (
      SELECT overall_confidence
      FROM decision_confidence_scores
      WHERE decision_id = dt.id
      ORDER BY created_at DESC
      LIMIT 1
    ) dcs ON TRUE
    WHERE dt.tenant_id = p_tenant_id
      AND dt.lifecycle_state = 'enacted'
      AND COALESCE(dcs.overall_confidence::float, 0.5) >= p_min_overall_confidence
  ),

  -- Semantic candidates (vector)
  semantic_search AS (
    SELECT
      b.id,
      ROW_NUMBER() OVER (ORDER BY b.rationale_embedding <=> p_query_embedding) AS r,
      (1.0 - (b.rationale_embedding <=> p_query_embedding))::float AS s
    FROM base b
    WHERE b.rationale_embedding IS NOT NULL
    ORDER BY b.rationale_embedding <=> p_query_embedding
    LIMIT k
  ),

  -- Full-text candidates
  fulltext_search AS (
    SELECT
      b.id,
      ROW_NUMBER() OVER (
        ORDER BY ts_rank_cd(
          to_tsvector('english', COALESCE(b.decision_summary,'') || ' ' || COALESCE(b.rationale_summary,'')),
          plainto_tsquery('english', p_query_text)
        ) DESC
      ) AS r,
      ts_rank_cd(
        to_tsvector('english', COALESCE(b.decision_summary,'') || ' ' || COALESCE(b.rationale_summary,'')),
        plainto_tsquery('english', p_query_text)
      )::float AS s
    FROM base b
    WHERE to_tsvector('english', COALESCE(b.decision_summary,'') || ' ' || COALESCE(b.rationale_summary,'')) @@ plainto_tsquery('english', p_query_text)
    LIMIT k
  ),

  -- Entity overlap candidates (signal, not hard constraint)
  entity_overlap AS (
    SELECT
      del.decision_id AS id,
      COUNT(*)::float AS overlap_count
    FROM decision_entity_links del
    WHERE p_required_entity_ids IS NOT NULL
      AND del.entity_id = ANY(p_required_entity_ids)
    GROUP BY del.decision_id
  ),

  entity_search AS (
    SELECT
      eo.id,
      ROW_NUMBER() OVER (ORDER BY eo.overlap_count DESC) AS r,
      (eo.overlap_count / NULLIF(array_length(p_required_entity_ids, 1), 0))::float AS s
    FROM entity_overlap eo
    ORDER BY eo.overlap_count DESC
    LIMIT k
  ),

  -- Combine ranks with Reciprocal Rank Fusion
  rrf_combined AS (
    SELECT id, 0.40 / (k + r) AS score, r AS sem_rank, NULL::INT AS ft_rank, NULL::INT AS ent_rank
    FROM semantic_search
    UNION ALL
    SELECT id, 0.35 / (k + r) AS score, NULL::INT, r, NULL::INT
    FROM fulltext_search
    UNION ALL
    SELECT id, 0.25 / (k + r) AS score, NULL::INT, NULL::INT, r
    FROM entity_search
  ),

  rrf_aggregated AS (
    SELECT
      id,
      SUM(score)::float AS base_rrf_score,
      MIN(sem_rank) AS semantic_rank,
      MIN(ft_rank) AS fulltext_rank,
      MIN(ent_rank) AS entity_rank
    FROM rrf_combined
    GROUP BY id
  ),

  joined AS (
    SELECT
      b.id AS decision_id,
      b.decision_id AS decision_human_id,
      b.decision_summary AS summary,
      b.decision_type,
      b.rationale_summary,
      b.decision_choice AS choice,
      b.decision_timestamp,
      b.decision_maker_id,

      ra.semantic_rank,
      ra.fulltext_rank,
      ra.entity_rank,

      COALESCE(ss.s, 0.0)::float AS semantic_score,
      COALESCE(fs.s, 0.0)::float AS fulltext_score,
      COALESCE(es.s, 0.0)::float AS entity_overlap_score,

      -- Recency score (exp decay, 0..1)
      (EXP(
        -0.693 * EXTRACT(EPOCH FROM (NOW() - b.decision_timestamp)) / 86400.0 / p_recency_half_life_days
      ))::float AS recency_score,

      -- Outcome score (from most recent result)
      COALESCE(dr.outcome_status, 'unknown'::result_status) AS outcome_status,
      CASE COALESCE(dr.outcome_status, 'unknown'::result_status)
        WHEN 'positive' THEN 1.0
        WHEN 'neutral'  THEN 0.5
        WHEN 'negative' THEN 0.1
        ELSE 0.5
      END::float AS outcome_score,

      -- Category match bonus (NO FILTER - just ranking boost)
      CASE
        WHEN p_decision_type_hint IS NOT NULL AND b.decision_type = p_decision_type_hint THEN 1.0
        ELSE 0.0
      END::float AS category_bonus,

      ra.base_rrf_score
    FROM rrf_aggregated ra
    JOIN base b ON b.id = ra.id
    LEFT JOIN semantic_search ss ON ss.id = b.id
    LEFT JOIN fulltext_search fs ON fs.id = b.id
    LEFT JOIN entity_search es ON es.id = b.id

    LEFT JOIN LATERAL (
      SELECT outcome_status
      FROM decision_results
      WHERE decision_id = b.id
      ORDER BY observed_at DESC
      LIMIT 1
    ) dr ON TRUE
  )

  SELECT
    j.decision_id,
    j.decision_human_id,
    j.summary,
    j.decision_type,
    j.rationale_summary,
    j.choice,
    j.decision_timestamp,
    j.decision_maker_id,
    j.outcome_status,

    j.semantic_rank,
    j.fulltext_rank,
    j.entity_rank,

    j.semantic_score,
    j.fulltext_score,
    j.entity_overlap_score,
    j.recency_score,
    j.outcome_score,
    j.category_bonus,

    (
      j.base_rrf_score
      + p_recency_weight * j.recency_score
      + p_outcome_weight * j.outcome_score
      + p_category_bonus_weight * j.category_bonus
      + p_entity_bonus_weight * COALESCE(j.entity_overlap_score, 0.0)
    )::float AS rrf_score

  FROM joined j
  WHERE (p_include_negative_outcomes OR j.outcome_status != 'negative'::result_status)
  ORDER BY rrf_score DESC
  LIMIT p_limit;

END;
$$;
```

### 4.2 Stable API Wrapper Function

To prevent signature drift between the full `search_precedents` function and API calls, use this wrapper with a fixed 8-parameter signature:

```sql
-- ✅ FIX D: Stable wrapper function with fixed signature for API
-- This prevents breaking changes when the main function evolves

CREATE OR REPLACE FUNCTION search_precedents_api(
  p_query_text TEXT,
  p_query_embedding VECTOR(1536),
  p_tenant_id UUID,
  p_decision_type_hint TEXT DEFAULT NULL,
  p_entity_ids UUID[] DEFAULT NULL,
  p_min_confidence FLOAT DEFAULT 0.0,
  p_limit INT DEFAULT 10,
  p_include_negative_outcomes BOOLEAN DEFAULT TRUE
)
RETURNS TABLE (
  decision_id UUID,
  decision_human_id VARCHAR,
  summary TEXT,
  decision_type TEXT,
  rationale_summary TEXT,
  choice JSONB,
  decision_timestamp TIMESTAMPTZ,
  decision_maker_id UUID,
  outcome_status result_status,
  semantic_rank INT,
  fulltext_rank INT,
  entity_rank INT,
  semantic_score FLOAT,
  fulltext_score FLOAT,
  entity_overlap_score FLOAT,
  recency_score FLOAT,
  outcome_score FLOAT,
  category_bonus FLOAT,
  rrf_score FLOAT
)
LANGUAGE sql
AS $$
  SELECT * FROM search_precedents(
    p_query_text,
    p_query_embedding,
    p_tenant_id,
    p_decision_type_hint,
    p_entity_ids,
    p_min_confidence,
    p_limit,
    p_include_negative_outcomes,
    60,    -- p_rrf_k (default)
    180,   -- p_recency_half_life_days (default)
    0.30,  -- p_recency_weight (default)
    0.15,  -- p_outcome_weight (default)
    0.05,  -- p_category_bonus_weight (default)
    0.05   -- p_entity_bonus_weight (default)
  );
$$;
```

**API should call `search_precedents_api`**, not the full function. This isolates the API from internal tuning changes.

### 4.3 Scoring Weights

| Signal | Default Weight | Purpose |
|--------|---------------|---------|
| Semantic similarity | 0.40 (in RRF) | Core relevance |
| Full-text match | 0.35 (in RRF) | Keyword relevance |
| Entity overlap | 0.25 (in RRF) + 0.05 bonus | Related entities |
| Recency | 0.30 | Prefer recent decisions |
| Outcome quality | 0.15 | Prefer successful precedents |
| Category match | 0.05 | Soft type alignment |

### 4.3 Python Client

```python
"""
precedent_search.py - Client for search_precedents function
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional, Any
import asyncpg
import httpx


@dataclass
class PrecedentResult:
    """A single precedent search result"""
    decision_id: str
    decision_human_id: str
    summary: str
    decision_type: Optional[str]
    rationale_summary: Optional[str]
    choice: Dict[str, Any]
    decision_timestamp: datetime
    outcome_status: Optional[str]
    
    # Explainability
    semantic_rank: Optional[int]
    fulltext_rank: Optional[int]
    entity_rank: Optional[int]
    semantic_score: float
    fulltext_score: float
    entity_overlap_score: float
    recency_score: float
    outcome_score: float
    category_bonus: float
    rrf_score: float
    
    @property
    def relevance_explanation(self) -> str:
        """Generate human-readable relevance explanation"""
        factors = []
        if self.semantic_score > 0.7:
            factors.append(f"highly similar reasoning ({self.semantic_score:.0%})")
        if self.fulltext_score > 0.3:
            factors.append("matching keywords")
        if self.entity_overlap_score > 0.5:
            factors.append(f"related entities ({self.entity_overlap_score:.0%})")
        if self.recency_score > 0.8:
            factors.append("recent")
        if self.outcome_status == 'positive':
            factors.append("positive outcome")
        elif self.outcome_status == 'negative':
            factors.append("⚠️ negative outcome")
        return "Relevant: " + ", ".join(factors) if factors else "General similarity"


class PrecedentSearchClient:
    """Client for searching precedents"""
    
    def __init__(
        self,
        db_pool: asyncpg.Pool,
        openai_api_key: str,
        tenant_id: str
    ):
        self.db = db_pool
        self.openai_key = openai_api_key
        self.tenant_id = tenant_id
    
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding from OpenAI text-embedding-3-small"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={
                    "Authorization": f"Bearer {self.openai_key}",
                    "Content-Type": "application/json"
                },
                json={"model": "text-embedding-3-small", "input": text},
                timeout=30.0
            )
            response.raise_for_status()
            return response.json()["data"][0]["embedding"]
    
    async def search(
        self,
        query: str,
        decision_type_hint: Optional[str] = None,
        entity_ids: Optional[List[str]] = None,
        min_confidence: float = 0.0,
        limit: int = 10,
        include_negative_outcomes: bool = True
    ) -> List[PrecedentResult]:
        """Search for relevant precedents"""
        
        embedding = await self.get_embedding(query)
        
        async with self.db.acquire() as conn:
            # ✅ FIX NIT C: Use stable wrapper function (not the full function)
            rows = await conn.fetch(
                """
                SELECT * FROM search_precedents_api(
                    $1, $2::vector, $3, $4, $5, $6, $7, $8
                )
                """,
                query,
                embedding,
                self.tenant_id,
                decision_type_hint,
                entity_ids,
                min_confidence,
                limit,
                include_negative_outcomes
            )
        
        return [
            PrecedentResult(
                decision_id=str(row['decision_id']),
                decision_human_id=row['decision_human_id'],
                summary=row['summary'],
                decision_type=row['decision_type'],
                rationale_summary=row['rationale_summary'],
                choice=row['choice'],
                decision_timestamp=row['decision_timestamp'],
                outcome_status=str(row['outcome_status']) if row['outcome_status'] else None,
                semantic_rank=row['semantic_rank'],
                fulltext_rank=row['fulltext_rank'],
                entity_rank=row['entity_rank'],
                semantic_score=row['semantic_score'],
                fulltext_score=row['fulltext_score'],
                entity_overlap_score=row['entity_overlap_score'],
                recency_score=row['recency_score'],
                outcome_score=row['outcome_score'],
                category_bonus=row['category_bonus'],
                rrf_score=row['rrf_score']
            )
            for row in rows
        ]
```

---

## 5. Agent Integration

### 5.1 Agent Decision Logger

```python
"""
agent_logger.py - Non-blocking decision logging for CF agents
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from enum import Enum
import uuid


@dataclass
class Observation:
    """An observation made during decision process"""
    timestamp: datetime
    action: str
    result: Dict[str, Any]
    source: str = 'api_call'


@dataclass
class DecisionSession:
    """Tracks a decision-making session"""
    session_id: str
    started_at: datetime
    tenant_id: str
    agent_id: str
    decision_type: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    entity_ids: List[str] = field(default_factory=list)
    observations: List[Observation] = field(default_factory=list)
    precedents_queried: List[Dict] = field(default_factory=list)
    precedents_cited: List[str] = field(default_factory=list)
    choice: Optional[Dict] = None
    rationale: Optional[str] = None
    evidence: List[Dict] = field(default_factory=list)


class AgentDecisionLogger:
    """
    Agent-native decision logging.
    
    Key features:
    - Non-blocking async logging
    - Automatic observation capture
    - Precedent query integration
    - Evidence tracking (required for enacted decisions)
    - Anti-annoyance "why?" prompting (max 1/hour)
    
    IMPORTANT: Each agent MUST have a corresponding entity in CF's entities table.
    Create the agent entity once during agent registration:
    
        INSERT INTO entities (id, name, entity_type, tenant_id)
        VALUES ('agent-uuid-here', 'discount_agent', 'agent', 'org-uuid');
    
    Then pass that UUID as agent_entity_id when constructing the logger.
    """
    
    MAX_WHY_PROMPTS_PER_HOUR = 1
    
    def __init__(
        self,
        db_pool,
        precedent_client: 'PrecedentSearchClient',
        tenant_id: str,
        agent_id: str,
        agent_entity_id: str  # REQUIRED: UUID of agent's entity in CF entities table
    ):
        self.db = db_pool
        self.precedents = precedent_client
        self.tenant_id = tenant_id
        self.agent_id = agent_id
        self.agent_entity_id = agent_entity_id  # This satisfies decision_maker_id NOT NULL
        self.session: Optional[DecisionSession] = None
        self._why_prompt_times: List[datetime] = []
    
    async def start(self, decision_type: str) -> str:
        """Start a new decision session"""
        session_id = str(uuid.uuid4())
        self.session = DecisionSession(
            session_id=session_id,
            started_at=datetime.now(),
            tenant_id=self.tenant_id,
            agent_id=self.agent_id,
            decision_type=decision_type
        )
        return session_id
    
    def add_context(self, context: Dict[str, Any]):
        """Add context information"""
        self.session.context.update(context)
    
    def add_entity(self, entity_id: str):
        """Add an entity involved in this decision"""
        if entity_id not in self.session.entity_ids:
            self.session.entity_ids.append(entity_id)
    
    def observe(self, action: str, result: Dict[str, Any], source: str = 'api_call'):
        """Log an observation during decision process"""
        self.session.observations.append(Observation(
            timestamp=datetime.now(),
            action=action,
            result=result,
            source=source
        ))
    
    def add_evidence(
        self,
        evidence_type: str,
        excerpt: str,
        source_uri: Optional[str] = None,
        source_id: Optional[str] = None
    ):
        """Add evidence for this decision (REQUIRED before enacting)"""
        self.session.evidence.append({
            'evidence_type': evidence_type,
            'excerpt': excerpt,
            'source_uri': source_uri,
            'source_id': source_id,
            'event_timestamp': datetime.now()
        })
    
    async def find_precedents(self, situation: str, limit: int = 5) -> List['PrecedentResult']:
        """Find relevant precedents before making a decision"""
        precedents = await self.precedents.search(
            query=situation,
            decision_type_hint=self.session.decision_type,
            entity_ids=self.session.entity_ids,
            limit=limit
        )
        
        self.session.precedents_queried = [
            {
                'decision_id': p.decision_id,
                'summary': p.summary,
                'score': p.rrf_score,
                'outcome': p.outcome_status
            }
            for p in precedents
        ]
        
        return precedents
    
    async def decide(
        self,
        choice: Dict[str, Any],
        rationale: str,
        cited_precedents: Optional[List[str]] = None
    ):
        """Record the decision"""
        self.session.choice = choice
        self.session.rationale = rationale
        self.session.precedents_cited = cited_precedents or []
    
    async def finalize(self, enact: bool = True) -> str:
        """
        Write decision trace to database.
        
        Args:
            enact: If True, set lifecycle_state='enacted' (requires evidence)
        
        Returns:
            Decision ID
        """
        if not self.session.choice:
            raise RuntimeError("No decision made. Call decide() first.")
        
        if enact and not self.session.evidence:
            raise RuntimeError(
                "Cannot enact decision without evidence. "
                "Call add_evidence() first, or set enact=False."
            )
        
        # Get embedding for rationale
        embedding = await self.precedents.get_embedding(self.session.rationale)
        
        # Generate human-readable ID
        decision_id = str(uuid.uuid4())
        human_id = f"DEC-{datetime.now().strftime('%Y')}-{decision_id[:8].upper()}"
        
        lifecycle = 'enacted' if enact else 'draft'
        
        async with self.db.acquire() as conn:
            async with conn.transaction():
                # Insert decision trace
                await conn.execute(
                    """
                    INSERT INTO decision_traces (
                        id, decision_id, decision_timestamp, decision_summary,
                        decision_choice, decision_maker_id, decision_type,
                        rationale_summary, rationale_embedding, context_snapshot,
                        lifecycle_state, source_system, created_by, tenant_id, sensitivity
                    ) VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9::vector, $10, $11, 
                        'agent', $12, $13, 'internal'
                    )
                    """,
                    decision_id,
                    human_id,
                    datetime.now(),
                    self._generate_summary(),
                    self.session.choice,
                    self.agent_entity_id,  # ✅ FIX A: Use agent's entity ID (NOT NULL satisfied)
                    self.session.decision_type,
                    self.session.rationale,
                    embedding,
                    {
                        **self.session.context,
                        'observations': [
                            {'action': o.action, 'result': o.result}
                            for o in self.session.observations
                        ],
                        'agent_id': self.agent_id
                    },
                    lifecycle,
                    f"agent_{self.agent_id}",
                    self.tenant_id
                )
                
                # Insert evidence (required for enacted)
                for ev in self.session.evidence:
                    await conn.execute(
                        """
                        INSERT INTO decision_evidence (
                            decision_id, evidence_type, source_uri, source_id,
                            excerpt, event_timestamp
                        ) VALUES ($1, $2, $3, $4, $5, $6)
                        """,
                        decision_id,
                        ev['evidence_type'],
                        ev.get('source_uri'),
                        ev.get('source_id'),
                        ev['excerpt'],
                        ev.get('event_timestamp')
                    )
                
                # Link entities
                for entity_id in self.session.entity_ids:
                    await conn.execute(
                        """
                        INSERT INTO decision_entity_links (
                            decision_id, entity_id, entity_role, resolution_method
                        ) VALUES ($1, $2, 'subject', 'agent_provided')
                        """,
                        decision_id,
                        entity_id
                    )
                
                # Link precedents
                for prec_id in self.session.precedents_cited:
                    await conn.execute(
                        """
                        INSERT INTO decision_precedent_links (
                            decision_id, precedent_decision_id, link_type,
                            precedent_applied, discovered_by
                        ) VALUES ($1, $2, 'cited', true, 'agent')
                        """,
                        decision_id,
                        prec_id
                    )
                
                # Insert confidence scores
                await conn.execute(
                    """
                    INSERT INTO decision_confidence_scores (
                        decision_id, overall_confidence, rationale_completeness,
                        scoring_model_version
                    ) VALUES ($1, $2, $3, 'agent_logger_v1')
                    """,
                    decision_id,
                    0.8 if self.session.evidence else 0.5,
                    1.0 if self.session.rationale else 0.5
                )
        
        # Clear session
        self.session = None
        
        return human_id
    
    def _generate_summary(self) -> str:
        """Generate a summary from choice"""
        choice = self.session.choice or {}
        decision = choice.get('decision', 'made')
        dtype = self.session.decision_type or 'decision'
        return f"Agent {decision} ({dtype})"
```

### 5.2 Usage Example

```python
async def handle_discount_request(customer_id: str, requested_discount: int):
    """Example: Agent handling a discount approval request"""
    
    # IMPORTANT: agent_entity_id must be created once during agent registration:
    # INSERT INTO entities (id, name, entity_type, tenant_id)
    # VALUES ('550e8400-e29b-41d4-a716-446655440000', 'discount_agent', 'agent', tenant_id);
    
    AGENT_ENTITY_ID = "550e8400-e29b-41d4-a716-446655440000"  # Pre-registered agent entity
    
    logger = AgentDecisionLogger(
        db_pool, 
        precedent_client, 
        tenant_id, 
        "discount_agent",
        agent_entity_id=AGENT_ENTITY_ID  # ✅ Required for decision_maker_id
    )
    
    # Start decision session
    await logger.start("discount_approval")
    
    # Add context
    logger.add_context({
        "customer_id": customer_id,
        "requested_discount": requested_discount
    })
    logger.add_entity(customer_id)
    
    # Make observations
    logger.observe("check_customer_tier", {"tier": "enterprise"})
    logger.observe("check_churn_risk", {"risk_score": 0.72, "risk_level": "high"})
    
    # Find precedents BEFORE deciding
    precedents = await logger.find_precedents(
        f"Customer requesting {requested_discount}% discount due to churn risk"
    )
    
    # Add evidence (REQUIRED for enacted decisions)
    logger.add_evidence(
        evidence_type="agent_log",
        excerpt=f"Customer {customer_id} has churn risk score 0.72, tier: enterprise",
        source_id=f"obs_{logger.session.session_id}"
    )
    
    # Make decision based on precedents
    if precedents and precedents[0].rrf_score > 0.7:
        # Follow precedent
        prior_choice = precedents[0].choice
        await logger.decide(
            choice={"decision": "approved", "discount_percent": requested_discount},
            rationale=f"Following precedent: {precedents[0].summary}",
            cited_precedents=[precedents[0].decision_id]
        )
    else:
        # Apply default policy
        approved = requested_discount <= 20
        await logger.decide(
            choice={"decision": "approved" if approved else "needs_review", 
                    "discount_percent": requested_discount},
            rationale="No strong precedent found, applying default policy"
        )
    
    # Finalize (writes to database)
    decision_id = await logger.finalize(enact=True)
    
    return {"decision_id": decision_id}
```

---

## 6. Schema Evolution

### 6.1 Detection Engine

```python
"""
schema_evolution.py - Detect emergent patterns and propose schema updates
"""

from dataclasses import dataclass
from typing import List, Dict, Any
from enum import Enum


class ProposalType(Enum):
    NEW_CATEGORY = "new_category"
    EXCEPTION_PROMOTION = "exception_promotion"
    POLICY_DRIFT = "policy_drift"
    CATEGORY_DEPRECATION = "category_deprecation"


@dataclass
class SchemaEvolutionProposal:
    proposal_type: ProposalType
    summary: str
    evidence: Dict[str, Any]
    confidence: float
    recommendation: str
    affected_decision_count: int


class SchemaEvolutionEngine:
    """
    Detect emergent patterns:
    1. Exception → Rule: When exceptions happen >50% of the time
    2. Emergent Categories: Clusters of uncategorized decisions
    3. Policy Drift: Behavior diverging from stated policy
    4. Category Decay: Unused categories
    """
    
    def __init__(self, db_pool, tenant_id: str):
        self.db = db_pool
        self.tenant_id = tenant_id
    
    async def detect_exception_promotion(self, lookback_days: int = 180) -> List[SchemaEvolutionProposal]:
        """Detect when exceptions have become the norm (>50%)"""
        
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH exception_stats AS (
                    SELECT 
                        de.policy_name,
                        COUNT(DISTINCT dt.id) as total_decisions,
                        COUNT(DISTINCT de.id) as exception_count
                    FROM decision_traces dt
                    LEFT JOIN decision_exceptions de ON de.decision_id = dt.id
                    WHERE 
                        dt.tenant_id = $1
                        AND dt.lifecycle_state = 'enacted'
                        AND dt.decision_timestamp > NOW() - INTERVAL '1 day' * $2
                        AND de.id IS NOT NULL
                    GROUP BY de.policy_name
                    HAVING COUNT(DISTINCT de.id) >= 5
                )
                SELECT *,
                    exception_count::float / NULLIF(total_decisions, 0) as exception_rate
                FROM exception_stats
                WHERE exception_count::float / NULLIF(total_decisions, 0) > 0.5
                ORDER BY exception_rate DESC
                """,
                self.tenant_id,
                lookback_days
            )
        
        return [
            SchemaEvolutionProposal(
                proposal_type=ProposalType.EXCEPTION_PROMOTION,
                summary=f"Exception to '{row['policy_name']}' is now the norm ({row['exception_rate']:.0%})",
                evidence={
                    'policy_name': row['policy_name'],
                    'exception_rate': float(row['exception_rate']),
                    'exception_count': row['exception_count'],
                    'total_decisions': row['total_decisions']
                },
                confidence=min(0.95, float(row['exception_rate'])),
                recommendation=f"Update policy '{row['policy_name']}' to reflect actual practice",
                affected_decision_count=row['exception_count']
            )
            for row in rows
        ]
    
    async def detect_category_decay(self, days_unused: int = 90) -> List[SchemaEvolutionProposal]:
        """Detect categories that should be deprecated"""
        
        async with self.db.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    id, name, usage_count,
                    EXTRACT(DAY FROM NOW() - last_used_at) as days_since_use
                FROM decision_categories
                WHERE 
                    tenant_id = $1
                    AND lifecycle = 'active'
                    AND (last_used_at < NOW() - INTERVAL '1 day' * $2 OR usage_count < 3)
                """,
                self.tenant_id,
                days_unused
            )
        
        return [
            SchemaEvolutionProposal(
                proposal_type=ProposalType.CATEGORY_DEPRECATION,
                summary=f"Category '{row['name']}' has low usage",
                evidence={
                    'category_name': row['name'],
                    'usage_count': row['usage_count'],
                    'days_since_use': float(row['days_since_use']) if row['days_since_use'] else None
                },
                confidence=0.8 if row['days_since_use'] and row['days_since_use'] > 180 else 0.6,
                recommendation=f"Deprecate category '{row['name']}'",
                affected_decision_count=row['usage_count']
            )
            for row in rows
        ]
    
    async def run_full_analysis(self, lookback_days: int = 180) -> List[SchemaEvolutionProposal]:
        """Run all detection analyses"""
        proposals = []
        proposals.extend(await self.detect_exception_promotion(lookback_days))
        proposals.extend(await self.detect_category_decay())
        return proposals
```

---

## 7. API Layer

### 7.1 FastAPI Application

```python
"""
api.py - FastAPI application for Decision Trace Layer
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import os
import asyncpg
import httpx

app = FastAPI(title="Context Foundry Decision Trace Layer", version="1.0")

DATABASE_URL = os.environ["DATABASE_URL"]
OPENAI_API_KEY = os.environ["OPENAI_API_KEY"]

db_pool: Optional[asyncpg.Pool] = None


@app.on_event("startup")
async def startup():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)


@app.on_event("shutdown")
async def shutdown():
    if db_pool:
        await db_pool.close()


# --- Models ---

class DecisionCreate(BaseModel):
    summary: str
    choice: Dict[str, Any]
    choice_type: str = "approval"
    rationale: str
    decision_type: Optional[str] = None
    decision_maker_id: str  # ✅ FIX NIT B: REQUIRED (matches DDL NOT NULL constraint)
    entity_ids: Optional[List[str]] = []
    context: Optional[Dict[str, Any]] = {}
    evidence: List[Dict[str, Any]]  # REQUIRED
    sensitivity: str = "internal"
    tenant_id: str


class PrecedentSearchRequest(BaseModel):
    query: str
    tenant_id: str
    decision_type_hint: Optional[str] = None
    entity_ids: Optional[List[str]] = None
    min_confidence: float = 0.0
    limit: int = 10
    include_negative_outcomes: bool = True


class OutcomeCreate(BaseModel):
    outcome_status: str
    metrics: Optional[Dict[str, Any]] = {}
    notes: Optional[str] = None


# --- Helpers ---

async def get_embedding(text: str) -> List[float]:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/embeddings",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={"model": "text-embedding-3-small", "input": text},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]


# --- Endpoints ---

@app.post("/api/v1/decisions")
async def create_decision(decision: DecisionCreate):
    """Create a new decision trace"""
    
    if not decision.evidence:
        raise HTTPException(400, "Evidence is required for decisions")
    
    embedding = await get_embedding(f"{decision.summary}. {decision.rationale}")
    
    import uuid
    decision_uuid = str(uuid.uuid4())
    human_id = f"DEC-{datetime.now().strftime('%Y')}-{decision_uuid[:8].upper()}"
    
    async with db_pool.acquire() as conn:
        async with conn.transaction():
            # Insert decision
            await conn.execute(
                """
                INSERT INTO decision_traces (
                    id, decision_id, decision_timestamp, decision_summary,
                    decision_choice, decision_maker_id, decision_type,
                    rationale_summary, rationale_embedding, context_snapshot,
                    lifecycle_state, source_system, created_by, tenant_id, sensitivity
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9::vector, $10,
                    'enacted', 'api', 'api_user', $11, $12
                )
                """,
                decision_uuid, human_id, datetime.now(), decision.summary,
                decision.choice, decision.decision_maker_id, decision.decision_type,
                decision.rationale, embedding, decision.context,
                decision.tenant_id, decision.sensitivity
            )
            
            # Insert evidence
            for ev in decision.evidence:
                await conn.execute(
                    """
                    INSERT INTO decision_evidence (
                        decision_id, evidence_type, source_uri, source_id, excerpt
                    ) VALUES ($1, $2, $3, $4, $5)
                    """,
                    decision_uuid, ev.get('evidence_type', 'manual_note'),
                    ev.get('source_uri'), ev.get('source_id'), ev.get('excerpt')
                )
            
            # Insert entity links
            for entity_id in decision.entity_ids:
                await conn.execute(
                    """
                    INSERT INTO decision_entity_links (
                        decision_id, entity_id, entity_role, resolution_method
                    ) VALUES ($1, $2, 'subject', 'manual')
                    """,
                    decision_uuid, entity_id
                )
            
            # Insert confidence
            await conn.execute(
                """
                INSERT INTO decision_confidence_scores (
                    decision_id, overall_confidence, rationale_completeness,
                    scoring_model_version
                ) VALUES ($1, 1.0, 1.0, 'manual_entry')
                """,
                decision_uuid
            )
    
    return {"decision_id": human_id, "id": decision_uuid}


@app.post("/api/v1/precedents/search")
async def search_precedents(request: PrecedentSearchRequest):
    """Search for relevant precedents"""
    
    embedding = await get_embedding(request.query)
    
    async with db_pool.acquire() as conn:
        # ✅ FIX D: Use stable wrapper function (not the full function)
        rows = await conn.fetch(
            """
            SELECT * FROM search_precedents_api($1, $2::vector, $3, $4, $5, $6, $7, $8)
            """,
            request.query, embedding, request.tenant_id,
            request.decision_type_hint, request.entity_ids,
            request.min_confidence, request.limit,
            request.include_negative_outcomes
        )
    
    return [dict(row) for row in rows]


@app.get("/api/v1/decisions/{decision_id}")
async def get_decision(decision_id: str):
    """Get a decision with all related data"""
    
    async with db_pool.acquire() as conn:
        decision = await conn.fetchrow(
            "SELECT * FROM decision_traces WHERE id = $1 OR decision_id = $1",
            decision_id
        )
        
        if not decision:
            raise HTTPException(404, "Decision not found")
        
        result = dict(decision)
        
        # Get evidence
        evidence = await conn.fetch(
            "SELECT * FROM decision_evidence WHERE decision_id = $1",
            decision['id']
        )
        result['evidence'] = [dict(e) for e in evidence]
        
        # Get precedents
        precedents = await conn.fetch(
            """
            SELECT dpl.*, dt.decision_summary as precedent_summary
            FROM decision_precedent_links dpl
            JOIN decision_traces dt ON dt.id = dpl.precedent_decision_id
            WHERE dpl.decision_id = $1
            """,
            decision['id']
        )
        result['precedents'] = [dict(p) for p in precedents]
        
        # Get outcome
        result_row = await conn.fetchrow(
            "SELECT * FROM decision_results WHERE decision_id = $1 ORDER BY observed_at DESC LIMIT 1",
            decision['id']
        )
        result['outcome'] = dict(result_row) if result_row else None
    
    return result


@app.post("/api/v1/decisions/{decision_id}/outcome")
async def record_outcome(decision_id: str, outcome: OutcomeCreate):
    """Record the outcome of a decision"""
    
    async with db_pool.acquire() as conn:
        decision_uuid = await conn.fetchval(
            "SELECT id FROM decision_traces WHERE id = $1 OR decision_id = $1",
            decision_id
        )
        if not decision_uuid:
            raise HTTPException(404, "Decision not found")
        
        import uuid
        await conn.execute(
            """
            INSERT INTO decision_results (
                id, decision_id, outcome_status, outcome_metrics, result_notes
            ) VALUES ($1, $2, $3, $4, $5)
            """,
            str(uuid.uuid4()), decision_uuid, outcome.outcome_status,
            outcome.metrics, outcome.notes
        )
    
    return {"status": "recorded"}


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "DTL", "version": "1.0"}
```

---

## 8. Replit Deployment

### 8.1 Project Structure

```
context-foundry-dtl/
├── .replit
├── replit.nix
├── pyproject.toml
├── main.py
├── src/
│   ├── __init__.py
│   ├── api.py
│   ├── precedent_search.py
│   ├── agent_logger.py
│   └── schema_evolution.py
└── sql/
    └── schema.sql          # The DDL from Section 3
```

### 8.2 .replit

```toml
run = "python main.py"
entrypoint = "main.py"
modules = ["python-3.11:v18-20230807-322e88b"]

[nix]
channel = "stable-23_11"

[env]
PYTHONPATH = "${PYTHONPATH}:${REPL_HOME}/src"

[deployment]
run = ["sh", "-c", "python main.py"]
deploymentTarget = "cloudrun"

[[ports]]
localPort = 8000
externalPort = 80
```

### 8.3 pyproject.toml

```toml
[project]
name = "context-foundry-dtl"
version = "1.0.0"
requires-python = ">=3.11"

dependencies = [
    "fastapi>=0.104.0",
    "uvicorn[standard]>=0.24.0",
    "asyncpg>=0.29.0",
    "httpx>=0.25.0",
    "pydantic>=2.5.0",
    "python-dotenv>=1.0.0",
]
```

### 8.4 main.py

```python
import os
import uvicorn
from dotenv import load_dotenv

load_dotenv()

required = ["DATABASE_URL", "OPENAI_API_KEY"]
missing = [v for v in required if not os.environ.get(v)]
if missing:
    raise RuntimeError(f"Missing: {missing}")

from src.api import app

if __name__ == "__main__":
    uvicorn.run("src.api:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)), reload=True)
```

### 8.5 Environment Variables (Replit Secrets)

| Secret | Description |
|--------|-------------|
| `DATABASE_URL` | Your CF Neon Postgres connection string |
| `OPENAI_API_KEY` | For `text-embedding-3-small` (direct call) |

### 8.6 Setup Commands

```bash
# Run the DDL against your database
psql $DATABASE_URL -f sql/schema.sql

# Start the server
python main.py
```

---

## 9. Implementation Plan

### 9.1 6-Week Timeline

| Week | Focus | Deliverables |
|------|-------|--------------|
| **1** | Foundation | Schema deployed, basic API working |
| **2** | Agent Integration | Logger + precedent search in agents |
| **3** | Evidence & Outcomes | Full lifecycle working |
| **4** | Schema Evolution | Pattern detection active |
| **5** | Polish | Performance, edge cases |
| **6** | Launch | Documentation, training, production |

### 9.2 Week 1 Checklist

- [ ] Deploy DDL to Neon database
- [ ] Verify HNSW index works
- [ ] Create `/api/v1/decisions` endpoint
- [ ] Create `/api/v1/precedents/search` endpoint
- [ ] Test evidence constraint trigger
- [ ] Seed 10 test decisions

### 9.3 Success Criteria

| Metric | Target |
|--------|--------|
| Precedent search latency | < 500ms p95 |
| Decision create with evidence | Works |
| Enacted without evidence | Blocked by trigger |
| RLS enforcement | Verified |
| Agent can query + log | End-to-end working |

---

## Appendix: Table Summary

| Table | Purpose | Key Constraint |
|-------|---------|----------------|
| `decision_traces` | Core decision events | Bi-temporal, sensitivity column |
| `decision_entity_links` | Who's involved (replaces arrays) | `entity_role` enum |
| `decision_evidence` | Receipts/provenance | Required for enacted |
| `decision_precedent_links` | Precedent relationships | No self-reference |
| `decision_exceptions` | Policy deviations | Justification required |
| `decision_confidence_scores` | Multi-dimensional confidence | — |
| `decision_executions` | What was done | — |
| `decision_results` | What happened | `result_status` enum |
| `decision_assessments` | Was it a good decision? | — |
| `decision_categories` | Emergent types | Lifecycle governance |
| `schema_evolution_proposals` | Pattern-based proposals | Status workflow |
| `decision_access_grants` | Explicit permissions | — |
| `decision_access_audit` | Access logging | — |

---

**End of Specification**

*Version 1.0 (Patched)*  
*January 7, 2026*  
*Reviewed by: Claude + ChatGPT*
