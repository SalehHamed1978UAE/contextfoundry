-- =============================================================================
-- Migration 022: Vault-Scoped Question Sets
-- =============================================================================
-- Purpose: Link question sets to specific vaults instead of being global
-- Date: 2026-01-20
-- Note: No FK constraint because vaults are managed as tenants, not in a vaults table
-- =============================================================================

-- Add vault_id column to question_sets (nullable first for migration)
ALTER TABLE question_sets ADD COLUMN IF NOT EXISTS vault_id UUID;

-- Add index for vault-based lookups
CREATE INDEX IF NOT EXISTS idx_question_sets_vault ON question_sets(vault_id, uploaded_at DESC);

-- Drop the unique constraint on name since different vaults can have same-named question sets
ALTER TABLE question_sets DROP CONSTRAINT IF EXISTS question_sets_name_key;

-- Delete any existing global question sets (they have no vault association)
DELETE FROM question_sets WHERE vault_id IS NULL;

-- Make vault_id NOT NULL going forward
ALTER TABLE question_sets ALTER COLUMN vault_id SET NOT NULL;

-- Add unique constraint on vault_id + name (same vault can't have duplicate names)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'question_sets_vault_name_unique'
    ) THEN
        ALTER TABLE question_sets ADD CONSTRAINT question_sets_vault_name_unique UNIQUE (vault_id, name);
    END IF;
END $$;
