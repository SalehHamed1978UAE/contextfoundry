# DOCUMENT STATUS UI — COMPLETE IMPLEMENTATION SPEC

## Overview

Add visual status indicators and action buttons to the document list so users can see extraction status and take action on failed/stuck extractions.

**Problem:** Backend job tracking is complete, but users have no way to see or act on extraction status.

**Solution:** Add status colors, progress indicators, and Refresh/Retry/Replace/Cancel buttons to the document list UI.

---

## PHASE 1: BACKEND — ADD CANCEL AND REPLACE ENDPOINTS

### File: Add to your extraction API routes

```python
from flask import Blueprint, request, jsonify
from sqlalchemy import text
from uuid import uuid4
from context_foundry.database import get_db_session
from context_foundry.extraction.job_tracker import get_job_tracker

# If you already have an extraction blueprint, add these routes to it
# Otherwise create: extraction_bp = Blueprint('extraction', __name__)


@extraction_bp.route('/api/document/<document_id>/cancel', methods=['POST'])
def cancel_extraction(document_id):
    """Cancel a running extraction job"""
    db = get_db_session()
    
    result = db.execute(text("""
        UPDATE extraction_jobs 
        SET status = 'FAILED', 
            completed_at = NOW(),
            error_message = 'Cancelled by user'
        WHERE document_id = :doc_id 
          AND status IN ('PENDING', 'RUNNING')
        RETURNING id
    """), {"doc_id": document_id})
    
    cancelled = result.fetchone()
    db.commit()
    
    if cancelled:
        return jsonify({"cancelled": True, "job_id": str(cancelled.id)})
    else:
        return jsonify({"cancelled": False, "reason": "No active job found"})


@extraction_bp.route('/api/document/<document_id>/replace', methods=['POST'])
def replace_document(document_id):
    """
    Replace a document with a new file.
    
    Flow:
    1. Receive new file
    2. Delete old document (cascades to chunks, entities, relationships)
    3. Create new document record (same name, new content)
    4. Trigger extraction on new document
    """
    db = get_db_session()
    
    # Get old document info
    old_doc = db.execute(text("""
        SELECT id, tenant_id, name FROM platform.documents 
        WHERE id = :doc_id
    """), {"doc_id": document_id}).fetchone()
    
    if not old_doc:
        return jsonify({"error": "Document not found"}), 404
    
    # Get new file from request
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    new_content = file.read().decode('utf-8')
    
    # Use original name or new filename
    new_name = request.form.get('name', old_doc.name)
    
    try:
        # 1. Cancel any active extraction jobs for old document
        db.execute(text("""
            UPDATE extraction_jobs 
            SET status = 'FAILED', 
                completed_at = NOW(),
                error_message = 'Document replaced'
            WHERE document_id = :doc_id 
              AND status IN ('PENDING', 'RUNNING')
        """), {"doc_id": document_id})
        
        # 2. Delete old document (CASCADE handles chunks, relationships)
        db.execute(text("""
            DELETE FROM platform.documents WHERE id = :doc_id
        """), {"doc_id": document_id})
        
        # 3. Create new document record
        new_doc_id = str(uuid4())
        db.execute(text("""
            INSERT INTO platform.documents (id, tenant_id, name, content, created_at)
            VALUES (:id, :tenant_id, :name, :content, NOW())
        """), {
            "id": new_doc_id,
            "tenant_id": old_doc.tenant_id,
            "name": new_name,
            "content": new_content
        })
        
        db.commit()
        
        # 4. Trigger extraction on new document
        tracker = get_job_tracker(db)
        content_hash = tracker.compute_content_hash(new_content)
        job_id = tracker.create_job(
            tenant_id=old_doc.tenant_id,
            document_id=new_doc_id,
            content_hash=content_hash
        )
        
        # Queue extraction (implement based on your extraction queue)
        # queue_extraction(new_doc_id, old_doc.tenant_id)
        
        return jsonify({
            "replaced": True,
            "old_document_id": document_id,
            "new_document_id": new_doc_id,
            "job_id": str(job_id),
            "status": "extraction_queued"
        })
        
    except Exception as e:
        db.rollback()
        return jsonify({"error": str(e)}), 500


@extraction_bp.route('/api/vault/<vault_id>/documents', methods=['GET'])
def get_vault_documents(vault_id):
    """Get all documents with extraction status for a vault"""
    db = get_db_session()
    
    results = db.execute(text("""
        SELECT * FROM document_extraction_status
        WHERE tenant_id = :vault_id
        ORDER BY document_name
    """), {"vault_id": vault_id}).fetchall()
    
    return jsonify([dict(r._mapping) for r in results])
```

---

## PHASE 2: VERIFY CASCADE DELETES

Run this query to check if CASCADE is set up:

```sql
SELECT
    tc.table_name, 
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    rc.delete_rule
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
    ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
    ON ccu.constraint_name = tc.constraint_name
JOIN information_schema.referential_constraints AS rc
    ON rc.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
    AND ccu.table_name = 'documents';
```

If CASCADE is not set, add it:

```sql
-- For document_chunks
ALTER TABLE document_chunks 
DROP CONSTRAINT IF EXISTS document_chunks_document_id_fkey;

ALTER TABLE document_chunks
ADD CONSTRAINT document_chunks_document_id_fkey 
    FOREIGN KEY (document_id) 
    REFERENCES platform.documents(id) 
    ON DELETE CASCADE;

-- For extraction_jobs
ALTER TABLE extraction_jobs 
DROP CONSTRAINT IF EXISTS extraction_jobs_document_id_fkey;

ALTER TABLE extraction_jobs
ADD CONSTRAINT extraction_jobs_document_id_fkey 
    FOREIGN KEY (document_id) 
    REFERENCES platform.documents(id) 
    ON DELETE CASCADE;
```

---

## PHASE 3: FRONTEND — DOCUMENT ROW COMPONENT

Create file: `components/DocumentRow.jsx` (or equivalent in your framework)

```jsx
import React from 'react';

const STATUS_CONFIG = {
  COMPLETE: { color: 'green', icon: '✓', label: 'Complete' },
  RUNNING: { color: 'orange', icon: '⏳', label: 'Running' },
  PENDING: { color: 'orange', icon: '⏳', label: 'Pending' },
  PARTIAL: { color: 'orange', icon: '⚠️', label: 'Partial' },
  FAILED: { color: 'red', icon: '✗', label: 'Failed' },
  TIMEOUT: { color: 'red', icon: '⏱', label: 'Timeout' },
  null: { color: 'gray', icon: '—', label: 'Not Started' }
};

export function DocumentRow({ document, onRefresh, onCancel, onDelete, onReplace }) {
  const status = STATUS_CONFIG[document.status] || STATUS_CONFIG[null];
  const isActive = ['RUNNING', 'PENDING'].includes(document.status);
  const isFailed = ['FAILED', 'TIMEOUT'].includes(document.status);
  
  return (
    <div className="document-row">
      {/* Document Info */}
      <div className="document-info">
        <span className="document-icon">📄</span>
        <span className="document-name">{document.document_name}</span>
      </div>
      
      {/* Status Indicator */}
      <div className={`status-indicator status-${status.color}`}>
        <span className="status-icon">{status.icon}</span>
        <span className="status-label">{status.label}</span>
        {document.progress_pct > 0 && document.progress_pct < 100 && (
          <span className="progress">{document.progress_pct}%</span>
        )}
      </div>
      
      {/* Entity Count */}
      <div className="entity-count">
        {document.entities_extracted > 0 && (
          <span>{document.entities_extracted} entities</span>
        )}
      </div>
      
      {/* Actions */}
      <div className="document-actions">
        {isActive ? (
          <button 
            className="btn-cancel" 
            onClick={() => onCancel(document.document_id)}
            title="Cancel extraction"
          >
            ✗ Cancel
          </button>
        ) : (
          <>
            {isFailed && (
              <button 
                className="btn-replace" 
                onClick={() => onReplace(document.document_id)}
                title="Replace file"
              >
                📎 Replace
              </button>
            )}
            <button 
              className="btn-refresh" 
              onClick={() => onRefresh(document.document_id, isFailed)}
              title={isFailed ? "Retry extraction" : "Re-extract"}
            >
              ↻ {isFailed ? 'Retry' : 'Refresh'}
            </button>
            <button 
              className="btn-delete" 
              onClick={() => onDelete(document.document_id)}
              title="Delete document"
            >
              🗑
            </button>
          </>
        )}
      </div>
    </div>
  );
}
```

---

## PHASE 4: FRONTEND — DOCUMENT LIST COMPONENT

Create file: `components/DocumentList.jsx`

```jsx
import React, { useState, useEffect, useCallback } from 'react';
import { DocumentRow } from './DocumentRow';

export function DocumentList({ vaultId }) {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  
  // Fetch documents with status
  const fetchDocuments = useCallback(async () => {
    try {
      const response = await fetch(`/api/vault/${vaultId}/documents`);
      if (!response.ok) throw new Error('Failed to fetch documents');
      const data = await response.json();
      setDocuments(data);
      setError(null);
    } catch (err) {
      console.error('Failed to fetch documents:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [vaultId]);
  
  // Initial fetch
  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);
  
  // Poll for updates while any document is running
  useEffect(() => {
    const hasRunning = documents.some(d => 
      ['RUNNING', 'PENDING'].includes(d.status)
    );
    
    if (hasRunning) {
      const interval = setInterval(fetchDocuments, 3000); // Poll every 3s
      return () => clearInterval(interval);
    }
  }, [documents, fetchDocuments]);
  
  // Action handlers
  const handleRefresh = async (documentId, force = false) => {
    try {
      await fetch(`/api/document/${documentId}/refresh?force=${force}`, {
        method: 'POST'
      });
      fetchDocuments();
    } catch (err) {
      alert(`Refresh failed: ${err.message}`);
    }
  };
  
  const handleCancel = async (documentId) => {
    try {
      await fetch(`/api/document/${documentId}/cancel`, {
        method: 'POST'
      });
      fetchDocuments();
    } catch (err) {
      alert(`Cancel failed: ${err.message}`);
    }
  };
  
  const handleDelete = async (documentId) => {
    if (!confirm('Delete this document? This cannot be undone.')) return;
    
    try {
      await fetch(`/api/document/${documentId}`, {
        method: 'DELETE'
      });
      fetchDocuments();
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    }
  };
  
  const handleReplace = async (documentId) => {
    // Create hidden file input
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.txt,.pdf,.docx,.md';
    
    fileInput.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      
      // Confirm replacement
      if (!confirm(`Replace document with "${file.name}"?`)) return;
      
      // Create form data
      const formData = new FormData();
      formData.append('file', file);
      
      try {
        const response = await fetch(`/api/document/${documentId}/replace`, {
          method: 'POST',
          body: formData
        });
        
        const result = await response.json();
        
        if (result.replaced) {
          fetchDocuments();
          alert('Document replaced. Extraction started.');
        } else {
          alert(`Replace failed: ${result.error}`);
        }
      } catch (err) {
        alert(`Replace failed: ${err.message}`);
      }
    };
    
    // Trigger file picker
    fileInput.click();
  };
  
  const handleRetryAllFailed = async () => {
    try {
      const response = await fetch(`/api/vault/${vaultId}/refresh-failed`, {
        method: 'POST'
      });
      const result = await response.json();
      alert(`Queued ${result.queued} documents for retry.`);
      fetchDocuments();
    } catch (err) {
      alert(`Retry all failed: ${err.message}`);
    }
  };
  
  // Summary counts
  const summary = {
    total: documents.length,
    complete: documents.filter(d => d.status === 'COMPLETE').length,
    running: documents.filter(d => ['RUNNING', 'PENDING'].includes(d.status)).length,
    failed: documents.filter(d => ['FAILED', 'TIMEOUT'].includes(d.status)).length,
    notStarted: documents.filter(d => !d.status).length
  };
  
  if (loading) {
    return <div className="document-list-loading">Loading documents...</div>;
  }
  
  if (error) {
    return (
      <div className="document-list-error">
        <p>Error loading documents: {error}</p>
        <button onClick={fetchDocuments}>Retry</button>
      </div>
    );
  }
  
  if (documents.length === 0) {
    return (
      <div className="document-list-empty">
        <p>No documents in this vault.</p>
        <p>Upload documents to get started.</p>
      </div>
    );
  }
  
  return (
    <div className="document-list">
      {/* Summary Header */}
      <div className="document-summary">
        <span className="summary-total">{summary.total} documents</span>
        {summary.complete > 0 && (
          <span className="summary-complete">🟢 {summary.complete} complete</span>
        )}
        {summary.running > 0 && (
          <span className="summary-running">🟡 {summary.running} running</span>
        )}
        {summary.failed > 0 && (
          <span className="summary-failed">🔴 {summary.failed} failed</span>
        )}
        {summary.notStarted > 0 && (
          <span className="summary-not-started">⚪ {summary.notStarted} not started</span>
        )}
      </div>
      
      {/* Document Rows */}
      <div className="document-rows">
        {documents.map(doc => (
          <DocumentRow
            key={doc.document_id}
            document={doc}
            onRefresh={handleRefresh}
            onCancel={handleCancel}
            onDelete={handleDelete}
            onReplace={handleReplace}
          />
        ))}
      </div>
      
      {/* Retry All Failed Button */}
      {summary.failed > 0 && (
        <div className="document-list-actions">
          <button 
            className="btn-retry-all"
            onClick={handleRetryAllFailed}
          >
            ↻ Retry All Failed ({summary.failed})
          </button>
        </div>
      )}
    </div>
  );
}
```

---

## PHASE 5: CSS STYLES

Create file: `styles/document-list.css` (or add to existing stylesheet)

```css
/* =============================================================================
   Document List Styles
   ============================================================================= */

.document-list {
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  overflow: hidden;
}

.document-list-loading,
.document-list-error,
.document-list-empty {
  padding: 40px;
  text-align: center;
  color: #666;
}

.document-list-error {
  color: #c62828;
}

.document-list-error button {
  margin-top: 16px;
  padding: 8px 16px;
  cursor: pointer;
}

/* -----------------------------------------------------------------------------
   Summary Header
   ----------------------------------------------------------------------------- */

.document-summary {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #e0e0e0;
  font-size: 14px;
}

.summary-total {
  font-weight: 600;
}

.summary-complete { color: #2e7d32; }
.summary-running { color: #ef6c00; }
.summary-failed { color: #c62828; }
.summary-not-started { color: #757575; }

/* -----------------------------------------------------------------------------
   Document Row
   ----------------------------------------------------------------------------- */

.document-row {
  display: flex;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e0e0e0;
  gap: 16px;
}

.document-row:last-child {
  border-bottom: none;
}

.document-row:hover {
  background: #f5f5f5;
}

.document-info {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0; /* Allow text truncation */
}

.document-icon {
  flex-shrink: 0;
}

.document-name {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* -----------------------------------------------------------------------------
   Status Indicator
   ----------------------------------------------------------------------------- */

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: 16px;
  font-size: 14px;
  white-space: nowrap;
}

.status-green {
  background: #e8f5e9;
  color: #2e7d32;
}

.status-orange {
  background: #fff3e0;
  color: #ef6c00;
}

.status-red {
  background: #ffebee;
  color: #c62828;
}

.status-gray {
  background: #f5f5f5;
  color: #757575;
}

.status-icon {
  font-size: 12px;
}

.progress {
  font-size: 12px;
  opacity: 0.8;
}

/* -----------------------------------------------------------------------------
   Entity Count
   ----------------------------------------------------------------------------- */

.entity-count {
  min-width: 100px;
  color: #666;
  font-size: 14px;
  text-align: right;
}

/* -----------------------------------------------------------------------------
   Action Buttons
   ----------------------------------------------------------------------------- */

.document-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.document-actions button {
  padding: 6px 12px;
  border-radius: 4px;
  border: 1px solid #ddd;
  background: white;
  cursor: pointer;
  font-size: 14px;
  white-space: nowrap;
  transition: background 0.2s, border-color 0.2s;
}

.document-actions button:hover {
  background: #f0f0f0;
}

.document-actions button:active {
  background: #e0e0e0;
}

.btn-refresh {
  color: #1976d2;
  border-color: #1976d2;
}

.btn-refresh:hover {
  background: #e3f2fd;
}

.btn-cancel {
  color: #ef6c00;
  border-color: #ef6c00;
}

.btn-cancel:hover {
  background: #fff3e0;
}

.btn-delete {
  color: #c62828;
  border-color: #c62828;
}

.btn-delete:hover {
  background: #ffebee;
}

.btn-replace {
  color: #7b1fa2;
  border-color: #7b1fa2;
}

.btn-replace:hover {
  background: #f3e5f5;
}

/* -----------------------------------------------------------------------------
   List Actions (Retry All)
   ----------------------------------------------------------------------------- */

.document-list-actions {
  padding: 16px;
  background: #fafafa;
  border-top: 1px solid #e0e0e0;
}

.btn-retry-all {
  padding: 10px 20px;
  background: #fff3e0;
  color: #ef6c00;
  border: 1px solid #ef6c00;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.btn-retry-all:hover {
  background: #ffe0b2;
}

/* -----------------------------------------------------------------------------
   Responsive
   ----------------------------------------------------------------------------- */

@media (max-width: 768px) {
  .document-row {
    flex-wrap: wrap;
  }
  
  .document-info {
    width: 100%;
  }
  
  .status-indicator {
    order: 1;
  }
  
  .entity-count {
    order: 2;
    min-width: auto;
  }
  
  .document-actions {
    order: 3;
    width: 100%;
    justify-content: flex-end;
    margin-top: 8px;
  }
}
```

---

## PHASE 6: INTEGRATE INTO YOUR APP

Wherever you display the vault/document view, add the DocumentList component:

```jsx
import { DocumentList } from './components/DocumentList';

function VaultView({ vaultId }) {
  return (
    <div className="vault-view">
      <h1>Documents</h1>
      
      {/* Upload button - your existing upload UI */}
      <UploadButton vaultId={vaultId} />
      
      {/* Document list with status */}
      <DocumentList vaultId={vaultId} />
    </div>
  );
}
```

---

## VERIFICATION CHECKLIST

### Backend Endpoints

```bash
# Test cancel endpoint
curl -X POST http://localhost:8000/api/document/{document_id}/cancel

# Test replace endpoint
curl -X POST http://localhost:8000/api/document/{document_id}/replace \
  -F "file=@new_document.txt"

# Test get documents with status
curl http://localhost:8000/api/vault/{vault_id}/documents

# Test retry all failed
curl -X POST http://localhost:8000/api/vault/{vault_id}/refresh-failed
```

### UI Verification

1. [ ] Document list shows all documents
2. [ ] Status indicators show correct colors:
   - 🟢 Green for COMPLETE
   - 🟡 Orange for RUNNING/PENDING
   - 🔴 Red for FAILED/TIMEOUT
   - ⚪ Gray for not started
3. [ ] Progress percentage shows for running documents
4. [ ] Entity count shows for completed documents
5. [ ] Refresh button works on completed documents
6. [ ] Retry button works on failed documents
7. [ ] Replace button opens file picker and replaces document
8. [ ] Cancel button cancels running extraction
9. [ ] Delete button deletes document (with confirmation)
10. [ ] "Retry All Failed" button appears when there are failed documents
11. [ ] List auto-refreshes while documents are running (3s polling)

### End-to-End Test

1. Upload a document → Status should show 🟡 Running
2. Wait for extraction → Status should change to 🟢 Complete
3. Click Refresh → Should re-extract (status goes to Running then Complete)
4. Manually fail an extraction in DB → Status should show 🔴 Failed
5. Click Retry → Should re-extract
6. Click Replace → Should upload new file and extract

---

## REPORT BACK

After implementation, confirm:

1. Cancel endpoint added and working?
2. Replace endpoint added and working?
3. CASCADE deletes verified/configured?
4. DocumentRow component created?
5. DocumentList component created?
6. CSS styles added?
7. UI displays correct status colors?
8. All action buttons work?
9. Polling updates status while running?
10. End-to-end flow tested?
