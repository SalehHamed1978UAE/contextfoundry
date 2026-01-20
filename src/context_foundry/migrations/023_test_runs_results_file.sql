-- Migration 023: Add results_file column to test_runs table
-- This stores the path to the JSONL results file for completed tests

ALTER TABLE test_runs ADD COLUMN IF NOT EXISTS results_file TEXT;

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_test_runs_results_file ON test_runs(results_file) WHERE results_file IS NOT NULL;
