-- ============================================================
-- Migration 006: Extraction Queue
-- Platform Foundation - Queue for Platform → Brain communication
-- ============================================================

CREATE TABLE platform.extraction_requests (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id UUID NOT NULL UNIQUE,
  document_id UUID NOT NULL REFERENCES platform.documents(id),
  tenant_id UUID NOT NULL REFERENCES platform.tenants(id),
  
  file_path TEXT NOT NULL,
  file_name TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  file_size_bytes BIGINT NOT NULL,
  
  ontology_hints TEXT[],
  extraction_mode TEXT NOT NULL DEFAULT 'full' CHECK (extraction_mode IN ('full', 'incremental')),
  priority TEXT NOT NULL DEFAULT 'normal' CHECK (priority IN ('low', 'normal', 'high')),
  
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'claimed', 'processing', 'completed', 'failed')),
  claimed_by TEXT,
  claimed_at TIMESTAMPTZ,
  
  submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at TIMESTAMPTZ,
  
  retry_count INTEGER NOT NULL DEFAULT 0,
  max_retries INTEGER NOT NULL DEFAULT 3,
  next_retry_at TIMESTAMPTZ,
  
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE platform.extraction_results (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id UUID NOT NULL REFERENCES platform.extraction_requests(request_id),
  document_id UUID NOT NULL,
  tenant_id UUID NOT NULL,
  
  status TEXT NOT NULL CHECK (status IN ('success', 'partial', 'failed')),
  entities_extracted INTEGER NOT NULL DEFAULT 0,
  relationships_extracted INTEGER NOT NULL DEFAULT 0,
  
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  
  started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ NOT NULL,
  duration_ms INTEGER NOT NULL DEFAULT 0,
  
  error_code TEXT,
  error_message TEXT,
  error_recoverable BOOLEAN DEFAULT false,
  
  extraction_version TEXT NOT NULL DEFAULT '1.0.0',
  model_used TEXT NOT NULL DEFAULT 'gpt-4o-mini',
  
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_extraction_requests_status ON platform.extraction_requests(status);
CREATE INDEX idx_extraction_requests_tenant ON platform.extraction_requests(tenant_id);
CREATE INDEX idx_extraction_requests_priority ON platform.extraction_requests(priority, submitted_at);
CREATE INDEX idx_extraction_results_request ON platform.extraction_results(request_id);
CREATE INDEX idx_extraction_results_tenant ON platform.extraction_results(tenant_id);

-- Function to claim next extraction request (atomic)
CREATE OR REPLACE FUNCTION platform.claim_extraction_request(p_worker_id TEXT)
RETURNS platform.extraction_requests AS $$
DECLARE
  v_request platform.extraction_requests;
BEGIN
  UPDATE platform.extraction_requests
  SET 
    status = 'claimed',
    claimed_by = p_worker_id,
    claimed_at = NOW()
  WHERE id = (
    SELECT id 
    FROM platform.extraction_requests 
    WHERE status = 'pending' 
      AND (next_retry_at IS NULL OR next_retry_at <= NOW())
    ORDER BY 
      CASE priority 
        WHEN 'high' THEN 1 
        WHEN 'normal' THEN 2 
        WHEN 'low' THEN 3 
      END,
      submitted_at
    LIMIT 1
    FOR UPDATE SKIP LOCKED
  )
  RETURNING * INTO v_request;
  
  RETURN v_request;
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE platform.extraction_requests IS 'Extraction queue - Platform submits, Brain consumes';
COMMENT ON TABLE platform.extraction_results IS 'Extraction results - Brain writes, Platform reads for metering';
COMMENT ON FUNCTION platform.claim_extraction_request IS 'Atomic claim function for extraction workers - priority ordered';
