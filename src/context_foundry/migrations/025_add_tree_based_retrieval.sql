-- =============================================================================
-- Migration 025: Add tree_based_retrieval column to test_runs
-- =============================================================================
-- Purpose: Support tree-based retrieval toggle in Test Runner Dashboard
-- Date: 2026-02-08
-- =============================================================================

-- Add tree_based_retrieval column to test_runs table
-- This column tracks whether tree-based retrieval was enabled for a test run
ALTER TABLE test_runs
ADD COLUMN IF NOT EXISTS tree_based_retrieval BOOLEAN DEFAULT false;

-- Create index for filtering by tree_based_retrieval
CREATE INDEX IF NOT EXISTS idx_test_runs_tree_flag
ON test_runs(tree_based_retrieval);

-- Update any existing test runs to have tree_based_retrieval = false
-- (safe default for historical runs)
UPDATE test_runs
SET tree_based_retrieval = false
WHERE tree_based_retrieval IS NULL;
