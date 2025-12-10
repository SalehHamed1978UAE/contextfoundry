-- Migration 012: Add semantic embeddings to entities for entity resolution
-- Uses OpenAI text-embedding-3-small (1536 dimensions) for consistency with documents

-- Add name_embedding column to entities table
ALTER TABLE entities ADD COLUMN IF NOT EXISTS name_embedding vector(1536);

-- Create index for efficient vector similarity search
CREATE INDEX IF NOT EXISTS idx_entities_name_embedding 
ON entities USING ivfflat (name_embedding vector_cosine_ops)
WITH (lists = 100);

-- Add comment for documentation
COMMENT ON COLUMN entities.name_embedding IS 'OpenAI text-embedding-3-small embedding of entity name + description for semantic search';
