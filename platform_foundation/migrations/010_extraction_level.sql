-- Migration: Add extraction_level column to platform.documents
-- This distinguishes between single-model (OntologyCentricPipeline) and multi-model extraction

ALTER TABLE platform.documents 
ADD COLUMN IF NOT EXISTS extraction_level TEXT;

ALTER TABLE platform.documents 
ADD CONSTRAINT documents_extraction_level_check 
CHECK (extraction_level IS NULL OR extraction_level IN ('single', 'multi'));

COMMENT ON COLUMN platform.documents.extraction_level IS 'Extraction type: single = OntologyCentricPipeline, multi = MultiModelExtractor';
