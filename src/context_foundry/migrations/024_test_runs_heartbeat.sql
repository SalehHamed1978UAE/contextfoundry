-- Migration 024: Add heartbeat_at column to test_runs for crash detection
-- If a test is "running" but heartbeat_at is > 30 seconds old, it's interrupted

ALTER TABLE test_runs ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMP WITH TIME ZONE;

-- Update status check constraint to include 'interrupted'
-- (Already exists in 021 but ensure constraint is correct)

-- Index for finding stale running tests
CREATE INDEX IF NOT EXISTS idx_test_runs_heartbeat ON test_runs(heartbeat_at) WHERE status = 'running';
