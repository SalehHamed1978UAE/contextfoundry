import logging
from flask import Blueprint, request, jsonify, g
from sqlalchemy import text
from platform_service.brain_client import call_brain

logger = logging.getLogger(__name__)

knowledge_bp = Blueprint('knowledge', __name__, url_prefix='/api/knowledge')


def login_required(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'tenant_id') or not g.tenant_id:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function


@knowledge_bp.route('/entities')
@login_required
def list_entities():
    params = {
        'page': request.args.get('page', 1),
        'per_page': request.args.get('per_page', 50),
        'type': request.args.get('type'),
        'document_id': request.args.get('document_id')
    }
    params = {k: v for k, v in params.items() if v}
    data, status = call_brain('/internal/v1/entities', params)
    return jsonify(data), status


@knowledge_bp.route('/entities/<entity_id>')
@login_required
def get_entity(entity_id):
    data, status = call_brain(f'/internal/v1/entities/{entity_id}')
    return jsonify(data), status


@knowledge_bp.route('/relationships')
@login_required
def list_relationships():
    params = {
        'page': request.args.get('page', 1),
        'per_page': request.args.get('per_page', 50)
    }
    data, status = call_brain('/internal/v1/relationships', params)
    return jsonify(data), status


@knowledge_bp.route('/graph')
@login_required
def get_graph():
    params = {'document_id': request.args.get('document_id')}
    params = {k: v for k, v in params.items() if v}
    data, status = call_brain('/internal/v1/graph', params)
    return jsonify(data), status


@knowledge_bp.route('/stats')
@login_required
def get_stats():
    data, status = call_brain('/internal/v1/stats')
    
    if status == 200 and hasattr(g, 'tenant_id'):
        try:
            from src.context_foundry.models.schema import get_session
            session = get_session()
            doc_result = session.execute(
                text("SELECT COUNT(*) FROM platform.documents WHERE tenant_id = :tenant_id AND status = 'extracted'"),
                {'tenant_id': str(g.tenant_id)}
            )
            doc_count = doc_result.scalar() or 0
            session.close()
            data['documents'] = doc_count
        except Exception as e:
            logger.warning(f"Could not get document count: {e}")
            data['documents'] = 0
    
    return jsonify(data), status
