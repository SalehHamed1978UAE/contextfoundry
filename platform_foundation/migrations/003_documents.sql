-- ============================================================
-- Migration 003: Documents & Folders
-- Platform Foundation - Document Management
-- ============================================================

CREATE TABLE platform.folders (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES platform.tenants(id),
  parent_id UUID REFERENCES platform.folders(id),
  name TEXT NOT NULL,
  path TEXT NOT NULL,
  created_by UUID REFERENCES platform.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE platform.documents (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id UUID NOT NULL REFERENCES platform.tenants(id),
  folder_id UUID REFERENCES platform.folders(id),
  name TEXT NOT NULL,
  original_filename TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  storage_path TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'uploaded' 
    CHECK (status IN ('uploaded', 'queued', 'processing', 'extracted', 'partial', 'failed')),
  current_version INTEGER NOT NULL DEFAULT 1,
  created_by UUID REFERENCES platform.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE platform.document_versions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id UUID NOT NULL REFERENCES platform.documents(id),
  version_number INTEGER NOT NULL,
  storage_path TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  created_by UUID REFERENCES platform.users(id),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  extraction_request_id UUID,
  UNIQUE(document_id, version_number)
);

CREATE INDEX idx_folders_tenant ON platform.folders(tenant_id);
CREATE INDEX idx_folders_parent ON platform.folders(parent_id);
CREATE INDEX idx_documents_tenant ON platform.documents(tenant_id);
CREATE INDEX idx_documents_folder ON platform.documents(folder_id);
CREATE INDEX idx_documents_status ON platform.documents(status);
CREATE INDEX idx_document_versions_doc ON platform.document_versions(document_id);

COMMENT ON TABLE platform.folders IS 'Folder hierarchy for document organization';
COMMENT ON TABLE platform.documents IS 'Document metadata - storage path references object storage';
COMMENT ON TABLE platform.document_versions IS 'Document version history with extraction linkage';
