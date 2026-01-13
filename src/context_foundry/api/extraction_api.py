"""
Extraction Job Tracking API

Endpoints for monitoring and managing extraction jobs.

Endpoints:
- GET /api/extraction/jobs/<job_id> - Get job details
- GET /api/extraction/jobs/<job_id>/verify - Verify job results
- POST /api/extraction/jobs/<job_id>/retry - Queue job for retry
- GET /api/vault/<vault_id>/extraction/status - Get vault extraction status
- GET /api/vault/<vault_id>/documents - Get documents with extraction status
- GET /api/extraction/health - Get system extraction health
- GET /api/extraction/circuit-breaker - Get circuit breaker status
- POST /api/extraction/circuit-breaker/reset - Reset circuit breaker
- GET /api/document/<document_id>/extraction/status - Get document extraction status
- POST /api/document/<document_id>/cancel - Cancel running extraction
- POST /api/document/<document_id>/replace - Replace document (handles PDF, DOCX, TXT, MD)
"""

import os
import logging
from uuid import UUID

from flask import Blueprint, request, jsonify
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ..extraction.job_tracker import get_job_tracker
from ..extraction.extraction_monitor import get_extraction_monitor
from ..extraction.circuit_breaker import get_circuit_breaker

logger = logging.getLogger(__name__)

extraction_api = Blueprint('extraction_api', __name__)


def get_db_session():
    """Get database session."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


@extraction_api.route('/api/extraction/jobs/<job_id>', methods=['GET'])
def get_extraction_job(job_id: str):
    """Get extraction job details."""
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        return jsonify({'error': 'Invalid job ID format'}), 400
    
    session = get_db_session()
    try:
        tracker = get_job_tracker(session)
        job = tracker.get_job(job_uuid)
        
        if not job:
            return jsonify({'error': 'Job not found'}), 404
        
        for key, val in job.items():
            if isinstance(val, UUID):
                job[key] = str(val)
            elif hasattr(val, 'isoformat'):
                job[key] = val.isoformat()
        
        return jsonify(job)
    finally:
        session.close()


@extraction_api.route('/api/extraction/jobs/<job_id>/verify', methods=['GET'])
def verify_extraction_job(job_id: str):
    """Verify extraction job results against actual database state."""
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        return jsonify({'error': 'Invalid job ID format'}), 400
    
    session = get_db_session()
    try:
        tracker = get_job_tracker(session)
        verification = tracker.verify_job(job_uuid)
        
        return jsonify(verification)
    finally:
        session.close()


@extraction_api.route('/api/extraction/jobs/<job_id>/retry', methods=['POST'])
def retry_extraction_job(job_id: str):
    """Queue job for retry."""
    try:
        job_uuid = UUID(job_id)
    except ValueError:
        return jsonify({'error': 'Invalid job ID format'}), 400
    
    session = get_db_session()
    try:
        monitor = get_extraction_monitor(session)
        
        if not monitor.circuit_breaker.can_retry():
            status = monitor.circuit_breaker.get_status()
            return jsonify({
                'error': 'Circuit breaker open - retries blocked',
                'circuit_breaker': status
            }), 503
        
        success = monitor.queue_retry(job_uuid)
        
        if success:
            return jsonify({'status': 'queued', 'job_id': job_id})
        else:
            return jsonify({'error': 'Failed to queue retry - check max retries'}), 400
    finally:
        session.close()


@extraction_api.route('/api/vault/<vault_id>/extraction/status', methods=['GET'])
def get_vault_extraction_status(vault_id: str):
    """Get extraction status summary for a vault."""
    try:
        tenant_uuid = UUID(vault_id)
    except ValueError:
        return jsonify({'error': 'Invalid vault ID format'}), 400
    
    session = get_db_session()
    try:
        tracker = get_job_tracker(session)
        status = tracker.get_vault_status(tenant_uuid)
        
        return jsonify({
            'vault_id': vault_id,
            **status
        })
    finally:
        session.close()


@extraction_api.route('/api/vault/<vault_id>/extraction/verify', methods=['GET'])
def verify_vault_extractions(vault_id: str):
    """Verify all extractions in a vault."""
    try:
        tenant_uuid = UUID(vault_id)
    except ValueError:
        return jsonify({'error': 'Invalid vault ID format'}), 400
    
    session = get_db_session()
    try:
        tracker = get_job_tracker(session)
        verification = tracker.verify_vault(tenant_uuid)
        
        return jsonify(verification)
    finally:
        session.close()


@extraction_api.route('/api/extraction/health', methods=['GET'])
def get_extraction_health():
    """Get overall extraction system health."""
    session = get_db_session()
    try:
        monitor = get_extraction_monitor(session)
        health = monitor.get_health_summary()
        
        return jsonify(health)
    finally:
        session.close()


@extraction_api.route('/api/extraction/circuit-breaker', methods=['GET'])
def get_circuit_breaker_status():
    """Get circuit breaker status."""
    session = get_db_session()
    try:
        cb = get_circuit_breaker(session)
        return jsonify(cb.get_status())
    finally:
        session.close()


@extraction_api.route('/api/extraction/circuit-breaker/reset', methods=['POST'])
def reset_circuit_breaker():
    """Manually reset the circuit breaker."""
    session = get_db_session()
    try:
        cb = get_circuit_breaker(session)
        cb.reset()
        return jsonify({'status': 'reset', 'state': cb.state.value})
    finally:
        session.close()


@extraction_api.route('/api/document/<document_id>/extraction/status', methods=['GET'])
def get_document_extraction_status(document_id: str):
    """Get extraction status for a specific document."""
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        return jsonify({'error': 'Invalid document ID format'}), 400
    
    session = get_db_session()
    try:
        tracker = get_job_tracker(session)
        status = tracker.get_document_status(doc_uuid)
        
        if not status:
            return jsonify({'error': 'Document not found or no extraction job'}), 404
        
        for key, val in status.items():
            if isinstance(val, UUID):
                status[key] = str(val)
            elif hasattr(val, 'isoformat'):
                status[key] = val.isoformat()
        
        return jsonify(status)
    finally:
        session.close()


@extraction_api.route('/api/document/<document_id>/cancel', methods=['POST'])
def cancel_document_extraction(document_id: str):
    """Cancel a running extraction job for a document."""
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        return jsonify({'error': 'Invalid document ID format'}), 400
    
    session = get_db_session()
    try:
        from sqlalchemy import text
        result = session.execute(text("""
            UPDATE extraction_jobs 
            SET status = 'FAILED', 
                completed_at = NOW(),
                error_message = 'Cancelled by user'
            WHERE document_id = :doc_id 
              AND status IN ('PENDING', 'RUNNING')
            RETURNING id
        """), {"doc_id": str(doc_uuid)})
        
        cancelled = result.fetchone()
        session.commit()
        
        if cancelled:
            logger.info(f"Cancelled extraction job for document {document_id}")
            return jsonify({"cancelled": True, "job_id": str(cancelled.id)})
        else:
            return jsonify({"cancelled": False, "reason": "No active job found"})
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to cancel extraction for {document_id}: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@extraction_api.route('/api/document/<document_id>/replace', methods=['POST'])
def replace_document(document_id: str):
    """
    Replace a document with a new file.
    Handles binary files (PDF, DOCX) as well as text files.
    """
    import tempfile
    from pathlib import Path
    from uuid import uuid4
    from sqlalchemy import text
    from ..ingestion.document_loader import DocumentLoader
    
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        return jsonify({'error': 'Invalid document ID format'}), 400
    
    session = get_db_session()
    try:
        old_doc = session.execute(text("""
            SELECT id, tenant_id, name FROM platform.documents 
            WHERE id = :doc_id
        """), {"doc_id": str(doc_uuid)}).fetchone()
        
        if not old_doc:
            return jsonify({"error": "Document not found"}), 404
        
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if not file.filename:
            return jsonify({"error": "No filename provided"}), 400
        
        filename = file.filename
        file_ext = Path(filename).suffix.lower()
        
        loader = DocumentLoader()
        if file_ext not in loader.SUPPORTED_EXTENSIONS:
            return jsonify({
                "error": f"Unsupported file type: {file_ext}",
                "supported": list(loader.SUPPORTED_EXTENSIONS)
            }), 400
        
        with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
            file.save(tmp.name)
            tmp_path = tmp.name
        
        try:
            loaded_doc = loader.load(tmp_path)
            new_content = loaded_doc.content
        finally:
            os.unlink(tmp_path)
        
        new_name = request.form.get('name', old_doc.name)
        
        session.execute(text("""
            UPDATE extraction_jobs 
            SET status = 'FAILED', 
                completed_at = NOW(),
                error_message = 'Document replaced'
            WHERE document_id = :doc_id 
              AND status IN ('PENDING', 'RUNNING')
        """), {"doc_id": str(doc_uuid)})
        
        session.execute(text("""
            DELETE FROM platform.documents WHERE id = :doc_id
        """), {"doc_id": str(doc_uuid)})
        
        new_doc_uuid = uuid4()
        new_doc_id = str(new_doc_uuid)
        session.execute(text("""
            INSERT INTO platform.documents (id, tenant_id, name, content, created_at)
            VALUES (:id, :tenant_id, :name, :content, NOW())
        """), {
            "id": new_doc_id,
            "tenant_id": old_doc.tenant_id,
            "name": new_name,
            "content": new_content
        })
        
        session.commit()
        
        tracker = get_job_tracker(session)
        content_hash = tracker.compute_content_hash(new_content)
        job_id = tracker.create_job(
            tenant_id=old_doc.tenant_id,
            document_id=new_doc_uuid,
            content_hash=content_hash
        )
        
        logger.info(f"Replaced document {document_id} with new document {new_doc_id}")
        
        return jsonify({
            "replaced": True,
            "old_document_id": document_id,
            "new_document_id": new_doc_id,
            "job_id": str(job_id),
            "file_type": loaded_doc.file_type,
            "status": "extraction_queued"
        })
        
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to replace document {document_id}: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        session.close()


@extraction_api.route('/api/vault/<vault_id>/documents', methods=['GET'])
def get_vault_documents_with_status(vault_id: str):
    """Get all documents with extraction status for a vault."""
    try:
        tenant_uuid = UUID(vault_id)
    except ValueError:
        return jsonify({'error': 'Invalid vault ID format'}), 400
    
    session = get_db_session()
    try:
        from sqlalchemy import text
        results = session.execute(text("""
            SELECT * FROM document_extraction_status
            WHERE tenant_id = :vault_id
            ORDER BY document_name
        """), {"vault_id": str(tenant_uuid)}).fetchall()
        
        docs = []
        for r in results:
            doc = dict(r._mapping)
            for key, val in doc.items():
                if isinstance(val, UUID):
                    doc[key] = str(val)
                elif hasattr(val, 'isoformat'):
                    doc[key] = val.isoformat()
            docs.append(doc)
        
        return jsonify(docs)
    finally:
        session.close()
