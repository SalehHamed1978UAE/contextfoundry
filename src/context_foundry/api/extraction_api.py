"""
Extraction Job Tracking API

Endpoints for monitoring and managing extraction jobs.

Endpoints:
- GET /api/extraction/jobs/<job_id> - Get job details
- GET /api/extraction/jobs/<job_id>/verify - Verify job results
- POST /api/extraction/jobs/<job_id>/retry - Queue job for retry
- GET /api/vault/<vault_id>/extraction/status - Get vault extraction status
- GET /api/extraction/health - Get system extraction health
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
