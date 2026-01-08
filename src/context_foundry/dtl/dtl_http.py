"""
DTL HTTP Adapter

Thin HTTP adapter for precedent search.
NO retrieval logic - only:
1. Authenticate via existing API key auth
2. Build AuthContext from auth
3. Call core
4. Serialize JSON response
"""

import time
import logging
from typing import Dict, Any, List, Optional

from flask import Blueprint, request, jsonify, g

from src.context_foundry.api.external import require_api_key
from src.context_foundry.models.schema import get_session
from .core import AuthContext, search_precedents

logger = logging.getLogger(__name__)


dtl_core_bp = Blueprint('dtl_core', __name__, url_prefix='/api/v1/dtl')


def _derive_auth_context_from_api_key() -> AuthContext:
    """
    Derive AuthContext from existing API key authentication.
    
    Uses g.api_key_info and g.tenant_id set by @require_api_key decorator.
    """
    api_key_info = getattr(g, 'api_key_info', {})
    
    return AuthContext(
        tenant_id=g.tenant_id,
        user_id=api_key_info.get('id', 'api_user'),
        role='user'
    )


@dtl_core_bp.route('/core/precedents/search', methods=['POST'])
@require_api_key
def http_search_precedents():
    """
    HTTP endpoint for precedent search.
    
    THIN ADAPTER - No scoring/ranking logic here.
    Derives AuthContext from API key -> calls core -> returns JSON.
    
    Request:
        {
            "query": "How should we handle X?",
            "embedding": [...],  // Optional pre-computed embedding
            "decision_type_hint": "routing",  // Optional
            "entity_ids": ["uuid1", "uuid2"],  // Optional
            "limit": 10,  // Optional, default 10
            "min_confidence": 0.0,  // Optional
            "include_negative_outcomes": true  // Optional
        }
    
    Response:
        {
            "query": "...",
            "count": 5,
            "precedents": [...],
            "_timing": {...}
        }
    
    SECURITY:
    - tenant_id comes from authenticated API key, NOT request body
    - Any tenant_id in request body is IGNORED
    """
    t_start = time.time()
    
    data = request.get_json() or {}
    
    if 'query' not in data:
        return jsonify({"error": "Missing required field: query"}), 400
    
    ctx = _derive_auth_context_from_api_key()
    
    session = None
    try:
        session = get_session(use_rls_role=True)
        
        t_core_start = time.time()
        precedents = search_precedents(
            ctx=ctx,
            session=session,
            query_text=data['query'],
            query_embedding=data.get('embedding'),
            decision_type_hint=data.get('decision_type_hint'),
            required_entity_ids=data.get('entity_ids'),
            limit=data.get('limit', 10),
            min_confidence=data.get('min_confidence', 0.0),
            include_negative_outcomes=data.get('include_negative_outcomes', True)
        )
        t_core_end = time.time()
        
        response_data = {
            "query": data['query'],
            "count": len(precedents),
            "precedents": [p.to_dict() for p in precedents],
            "_timing": {
                "t_core_ms": (t_core_end - t_core_start) * 1000,
                "t_total_ms": (time.time() - t_start) * 1000,
                "used_precomputed_embedding": bool(data.get('embedding'))
            }
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"[DTL HTTP] Search failed: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if session:
            session.close()
