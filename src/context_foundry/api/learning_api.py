"""
Learning Flow API Endpoints

REST API for managing learning flow operations.

Endpoints:
- GET /api/learning/status/<vault_id> - Get learning status for a vault
- GET /api/learning/gaps/<vault_id> - Get open gaps for a vault
- GET /api/learning/gaps/<vault_id>/summary - Get gap summary
- POST /api/learning/feedback - Submit user feedback/correction
- POST /api/learning/trigger/<vault_id> - Manually trigger learning
- POST /api/learning/process - Process pending learning tasks
- GET /api/learning/queue/<vault_id> - Get queue status
- GET /api/learning/dashboard - Get learning dashboard
- POST /api/learning/gaps/<gap_id>/resolve - Resolve a gap
- POST /api/learning/gaps/<gap_id>/ignore - Ignore a gap
"""

import os
import logging
from uuid import UUID

from flask import Blueprint, request, jsonify
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from ..learning.orchestrator import get_orchestrator

logger = logging.getLogger(__name__)


def get_db_session():
    """Get database session."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()

learning_bp = Blueprint('learning', __name__)


@learning_bp.route('/api/learning/status/<vault_id>', methods=['GET'])
def get_learning_status(vault_id):
    """Get learning flow status for a vault"""
    try:
        db = get_db_session()
        orchestrator = get_orchestrator(db)
        
        status = orchestrator.get_learning_status(UUID(vault_id))
        return jsonify({"success": True, **status})
    except Exception as e:
        logger.error(f"Error getting learning status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@learning_bp.route('/api/learning/gaps/<vault_id>', methods=['GET'])
def get_gaps(vault_id):
    """Get open gaps for a vault"""
    try:
        db = get_db_session()
        orchestrator = get_orchestrator(db)
        
        limit = request.args.get('limit', 20, type=int)
        gaps = orchestrator.gap_detector.get_open_gaps(UUID(vault_id), limit=limit)
        
        for gap in gaps:
            gap['id'] = str(gap['id'])
            gap['tenant_id'] = str(gap['tenant_id'])
            if gap.get('created_at'):
                gap['created_at'] = gap['created_at'].isoformat()
        
        return jsonify({"success": True, "gaps": gaps, "count": len(gaps)})
    except Exception as e:
        logger.error(f"Error getting gaps: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@learning_bp.route('/api/learning/gaps/<vault_id>/summary', methods=['GET'])
def get_gap_summary(vault_id):
    """Get gap summary for a vault"""
    try:
        db = get_db_session()
        orchestrator = get_orchestrator(db)
        
        summary = orchestrator.get_gap_summary(UUID(vault_id))
        return jsonify({"success": True, **summary})
    except Exception as e:
        logger.error(f"Error getting gap summary: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@learning_bp.route('/api/learning/feedback', methods=['POST'])
def submit_feedback():
    """Submit user feedback/correction"""
    try:
        data = request.json
        
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400
        
        required_fields = ['vault_id', 'original_value', 'corrected_value', 'correction_field']
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "error": f"Missing required field: {field}"}), 400
        
        db = get_db_session()
        orchestrator = get_orchestrator(db)
        
        result = orchestrator.on_user_feedback(
            tenant_id=UUID(data['vault_id']),
            original_value=data['original_value'],
            corrected_value=data['corrected_value'],
            correction_field=data['correction_field'],
            feedback_text=data.get('feedback_text'),
            query_gap_id=UUID(data['query_gap_id']) if data.get('query_gap_id') else None,
            entity_id=UUID(data['entity_id']) if data.get('entity_id') else None,
            relationship_id=UUID(data['relationship_id']) if data.get('relationship_id') else None
        )
        
        return jsonify({"success": True, **result})
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@learning_bp.route('/api/learning/trigger/<vault_id>', methods=['POST'])
def trigger_learning(vault_id):
    """Manually trigger learning for a vault"""
    try:
        data = request.json or {}
        limit = data.get('limit', 10)
        
        db = get_db_session()
        orchestrator = get_orchestrator(db)
        
        result = orchestrator.trigger_learning(UUID(vault_id), limit=limit)
        return jsonify({"success": True, **result})
    except Exception as e:
        logger.error(f"Error triggering learning: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@learning_bp.route('/api/learning/process', methods=['POST'])
def process_queue():
    """Process pending learning tasks"""
    try:
        data = request.json or {}
        limit = data.get('limit', 5)
        vault_id = data.get('vault_id')
        
        db = get_db_session()
        orchestrator = get_orchestrator(db)
        
        tenant_uuid = UUID(vault_id) if vault_id else None
        result = orchestrator.process_learning_queue(limit=limit, tenant_id=tenant_uuid)
        return jsonify({"success": True, **result})
    except Exception as e:
        logger.error(f"Error processing queue: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@learning_bp.route('/api/learning/queue/<vault_id>', methods=['GET'])
def get_queue_status(vault_id):
    """Get learning queue status for a vault"""
    try:
        db = get_db_session()
        orchestrator = get_orchestrator(db)
        
        stats = orchestrator.queue_manager.get_queue_stats(UUID(vault_id))
        tasks = orchestrator.queue_manager.get_next_tasks(limit=10, tenant_id=UUID(vault_id))
        
        for task in tasks:
            task['id'] = str(task['id'])
            task['tenant_id'] = str(task['tenant_id'])
            if task.get('created_at'):
                task['created_at'] = task['created_at'].isoformat()
        
        return jsonify({
            "success": True,
            "stats": stats,
            "pending_tasks": tasks
        })
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@learning_bp.route('/api/learning/dashboard', methods=['GET'])
def get_dashboard():
    """Get learning dashboard for all vaults"""
    try:
        db = get_db_session()
        
        result = db.execute(text("SELECT * FROM learning_dashboard")).fetchall()
        
        data = []
        for row in result:
            row_dict = dict(row._mapping)
            row_dict['tenant_id'] = str(row_dict['tenant_id'])
            data.append(row_dict)
        
        return jsonify({"success": True, "vaults": data})
    except Exception as e:
        logger.error(f"Error getting dashboard: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@learning_bp.route('/api/learning/gaps/<gap_id>/resolve', methods=['POST'])
def resolve_gap(gap_id):
    """Manually resolve a gap"""
    try:
        data = request.json or {}
        notes = data.get('notes', 'Manually resolved')
        
        db = get_db_session()
        
        db.execute(text("""
            UPDATE query_gaps 
            SET status = 'RESOLVED', 
                resolved_at = NOW(),
                resolution_notes = :notes
            WHERE id = :gap_id
        """), {"gap_id": UUID(gap_id), "notes": notes})
        db.commit()
        
        return jsonify({"success": True, "message": "Gap resolved"})
    except Exception as e:
        logger.error(f"Error resolving gap: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@learning_bp.route('/api/learning/gaps/<gap_id>/ignore', methods=['POST'])
def ignore_gap(gap_id):
    """Ignore a gap (mark as not relevant)"""
    try:
        data = request.json or {}
        notes = data.get('notes', 'Manually ignored')
        
        db = get_db_session()
        
        db.execute(text("""
            UPDATE query_gaps 
            SET status = 'IGNORED',
                resolution_notes = :notes
            WHERE id = :gap_id
        """), {"gap_id": UUID(gap_id), "notes": notes})
        db.commit()
        
        return jsonify({"success": True, "message": "Gap ignored"})
    except Exception as e:
        logger.error(f"Error ignoring gap: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
