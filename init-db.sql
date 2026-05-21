-- Initialize Apache AGE extension
CREATE EXTENSION IF NOT EXISTS age;
CREATE EXTENSION IF NOT EXISTS vector;

-- Load AGE into search path
SET search_path = ag_catalog, "$user", public;

-- Create graph for Context Foundry
SELECT create_graph('cf_knowledge');

-- Enable vector operations
ALTER DATABASE context_foundry SET search_path TO ag_catalog, "$user", public;

-- Note: Full schema will be loaded separately via schema.sql
-- This file only handles extensions and graph creation
