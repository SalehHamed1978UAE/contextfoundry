-- =============================================================================
-- Migration 021: Test Runner Dashboard
-- =============================================================================
-- Purpose: Support the Test Runner Dashboard UI with question sets and test tracking
-- Date: 2026-01-20
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Question Sets: Store uploadable question sets for testing
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS question_sets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    question_count INTEGER NOT NULL,
    questions JSONB NOT NULL,
    uploaded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    uploaded_by VARCHAR(100)
);

CREATE INDEX IF NOT EXISTS idx_question_sets_name ON question_sets(name);
CREATE INDEX IF NOT EXISTS idx_question_sets_uploaded ON question_sets(uploaded_at DESC);

-- -----------------------------------------------------------------------------
-- Test Runs: Track test execution history
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS test_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    vault_id UUID NOT NULL,
    vault_name VARCHAR(255) NOT NULL,
    question_set_id UUID REFERENCES question_sets(id) ON DELETE SET NULL,
    question_set_name VARCHAR(255) NOT NULL,
    mode VARCHAR(20) NOT NULL CHECK (mode IN ('auto', 'fresh')),
    corpus_folder VARCHAR(255),
    
    status VARCHAR(20) NOT NULL DEFAULT 'running' 
        CHECK (status IN ('running', 'complete', 'interrupted', 'failed')),
    stage VARCHAR(20) 
        CHECK (stage IN ('delete', 'create', 'upload', 'extract', 'qa', 'complete')),
    
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    
    questions_total INTEGER,
    questions_answered INTEGER DEFAULT 0,
    questions_passed INTEGER DEFAULT 0,
    questions_failed INTEGER DEFAULT 0,
    
    checkpoint JSONB,
    error_message TEXT,
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_test_runs_status ON test_runs(status);
CREATE INDEX IF NOT EXISTS idx_test_runs_vault ON test_runs(vault_id);
CREATE INDEX IF NOT EXISTS idx_test_runs_started ON test_runs(started_at DESC);

-- -----------------------------------------------------------------------------
-- Test Results: Individual question results for each test run
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS test_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_run_id UUID REFERENCES test_runs(id) ON DELETE CASCADE,
    
    question_id VARCHAR(50) NOT NULL,
    question_text TEXT NOT NULL,
    expected_answer TEXT NOT NULL,
    actual_answer TEXT,
    category VARCHAR(100),
    
    passed BOOLEAN NOT NULL,
    failure_reason TEXT,
    duration_ms INTEGER,
    
    answered_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    
    CONSTRAINT unique_test_question UNIQUE (test_run_id, question_id)
);

CREATE INDEX IF NOT EXISTS idx_test_results_run ON test_results(test_run_id);
CREATE INDEX IF NOT EXISTS idx_test_results_passed ON test_results(test_run_id, passed);
