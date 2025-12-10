"""
Context Bundle API for External Applications.

This module provides the public API for external applications (like Premisia)
to query the Context Foundry knowledge graph.

Endpoints:
- POST /api/v1/query - Natural language query with GROUNDED/GAP/INFERRED response
- POST /api/v1/context - Get structured context bundle for an entity
- GET /api/v1/entities/{name} - Get entity details + relationships
- GET /api/v1/health - System health check

Authentication:
- API key required in X-CF-API-Key header
- Keys managed via api_keys table
"""

import os
import hashlib
import secrets
from datetime import datetime
from functools import wraps
from typing import Optional, Dict, Any, List

from flask import Blueprint, request, jsonify, g

from sqlalchemy import Column, String, Boolean, DateTime, Text, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class APIKey(Base):
    """API key model for external application authentication."""
    __tablename__ = 'api_keys'
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True)
    key_prefix = Column(String(8), nullable=False)
    tenant_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime)
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    scopes = Column(Text)
    created_by = Column(String(36))


def get_db_session():
    """Get database session."""
    database_url = os.environ.get('DATABASE_URL')
    if not database_url:
        raise RuntimeError("DATABASE_URL not configured")
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    return Session()


def hash_api_key(key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> tuple:
    """Generate a new API key. Returns (full_key, prefix, hash)."""
    key = f"cf_{secrets.token_urlsafe(32)}"
    prefix = key[:8]
    key_hash = hash_api_key(key)
    return key, prefix, key_hash


def validate_api_key(key: str) -> Optional[Dict[str, Any]]:
    """Validate an API key and return key info if valid."""
    if not key:
        return None
    
    key_hash = hash_api_key(key)
    
    try:
        session = get_db_session()
        api_key = session.query(APIKey).filter_by(
            key_hash=key_hash,
            is_active=True
        ).first()
        
        if not api_key:
            session.close()
            return None
        
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            session.close()
            return None
        
        api_key.last_used_at = datetime.utcnow()
        session.commit()
        
        result = {
            'id': api_key.id,
            'name': api_key.name,
            'tenant_id': api_key.tenant_id,
            'scopes': api_key.scopes.split(',') if api_key.scopes else ['read']
        }
        
        session.close()
        return result
        
    except Exception as e:
        return None


def require_api_key(f):
    """Decorator to require valid API key for endpoint."""
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-CF-API-Key')
        
        if not api_key:
            return jsonify({
                'error': 'Missing API key',
                'message': 'Provide API key in X-CF-API-Key header'
            }), 401
        
        key_info = validate_api_key(api_key)
        
        if not key_info:
            return jsonify({
                'error': 'Invalid API key',
                'message': 'API key is invalid, expired, or revoked'
            }), 401
        
        g.api_key_info = key_info
        g.tenant_id = key_info['tenant_id']
        
        return f(*args, **kwargs)
    
    return decorated


external_api = Blueprint('external_api', __name__, url_prefix='/api/v1')


@external_api.route('/health', methods=['GET'])
def health_check():
    """
    System health check endpoint.
    
    No authentication required.
    
    Returns:
        {
            "status": "healthy",
            "version": "1.0.0",
            "timestamp": "2025-12-10T04:30:00Z"
        }
    """
    try:
        from sqlalchemy import text
        session = get_db_session()
        session.execute(text("SELECT 1"))
        session.close()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    
    return jsonify({
        'status': 'healthy' if db_status == 'connected' else 'degraded',
        'version': '1.0.0',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'components': {
            'database': db_status,
            'api': 'operational'
        }
    })


@external_api.route('/query', methods=['POST'])
@require_api_key
def query_knowledge():
    """
    Natural language query endpoint.
    
    Input:
        {
            "query": "What is the blast radius if API Gateway fails?",
            "options": {
                "include_inferred": true,
                "max_depth": 3,
                "confidence_threshold": 0.7
            }
        }
    
    Output:
        {
            "answer": "...",
            "confidence": 0.85,
            "grounded": [{"fact": "...", "source": "..."}],
            "inferred": [{"fact": "...", "reasoning": "..."}],
            "gaps": [{"topic": "...", "suggestion": "..."}]
        }
    """
    data = request.get_json()
    
    if not data or not data.get('query'):
        return jsonify({
            'error': 'No query provided',
            'message': 'Request body must contain a "query" field'
        }), 400
    
    query_text = data['query'].strip()
    options = data.get('options', {})
    
    try:
        from ..agents.reasoning import ReasoningAgent
        
        agent = ReasoningAgent(tenant_id=g.tenant_id)
        result = agent.process_query(query_text)
        
        grounded = []
        inferred = []
        gaps = []
        
        answer = result.get('answer', '')
        
        if 'GROUNDED:' in answer:
            parts = answer.split('GROUNDED:')
            if len(parts) > 1:
                grounded_text = parts[1].split('GAP')[0].split('INFERRED')[0]
                for line in grounded_text.strip().split('\n'):
                    if line.strip().startswith('-'):
                        grounded.append({'fact': line.strip()[1:].strip(), 'source': 'knowledge_graph'})
        
        if 'GAP' in answer:
            parts = answer.split('GAP')
            if len(parts) > 1:
                gap_text = parts[1].split('INFERRED')[0]
                for line in gap_text.strip().split('\n'):
                    if line.strip().startswith('-') or line.strip():
                        gaps.append({'topic': line.strip().lstrip('-').strip(), 'suggestion': 'Document this relationship'})
        
        if 'INFERRED' in answer:
            parts = answer.split('INFERRED')
            if len(parts) > 1:
                inferred_text = parts[1]
                for line in inferred_text.strip().split('\n'):
                    if line.strip().startswith('-'):
                        inferred.append({'fact': line.strip()[1:].strip(), 'reasoning': 'Derived from graph structure'})
        
        return jsonify({
            'answer': answer,
            'confidence': result.get('confidence', 0.5),
            'grounded': grounded,
            'inferred': inferred,
            'gaps': gaps,
            'query_type': result.get('query_type', 'unknown'),
            'entities_found': result.get('entities_found', [])
        })
        
    except Exception as e:
        return jsonify({
            'error': 'Query processing failed',
            'message': str(e)
        }), 500


@external_api.route('/context', methods=['POST'])
@require_api_key
def get_context_bundle():
    """
    Get structured context bundle for an entity.
    
    Input:
        {
            "entity": "API Gateway",
            "depth": 2,
            "include": ["relationships", "properties", "sources"]
        }
    
    Output:
        {
            "entity": {...},
            "relationships": [...],
            "related_entities": [...],
            "sources": [...],
            "rules": [...]
        }
    """
    data = request.get_json()
    
    if not data or not data.get('entity'):
        return jsonify({
            'error': 'No entity specified',
            'message': 'Request body must contain an "entity" field'
        }), 400
    
    entity_name = data['entity'].strip()
    depth = min(data.get('depth', 1), 5)
    include = data.get('include', ['relationships', 'properties'])
    
    try:
        from ..api.context_bundle import ContextBundleBuilder
        
        builder = ContextBundleBuilder(tenant_id=g.tenant_id)
        bundle = builder.build_for_entity(
            entity_name=entity_name,
            depth=depth,
            include_relationships='relationships' in include,
            include_properties='properties' in include,
            include_sources='sources' in include
        )
        
        if not bundle:
            return jsonify({
                'error': 'Entity not found',
                'message': f'No entity named "{entity_name}" found in knowledge graph',
                'suggestion': 'Check entity name spelling or search for similar entities'
            }), 404
        
        return jsonify(bundle)
        
    except Exception as e:
        return jsonify({
            'error': 'Context retrieval failed',
            'message': str(e)
        }), 500


@external_api.route('/entities/<path:name>', methods=['GET'])
@require_api_key
def get_entity(name: str):
    """
    Get entity details by name.
    
    URL Parameters:
        name: Entity name (URL encoded)
    
    Query Parameters:
        include_relationships: bool (default: true)
        include_properties: bool (default: true)
    
    Output:
        {
            "id": "...",
            "name": "API Gateway",
            "type": "SERVICE",
            "properties": {...},
            "relationships": {
                "incoming": [...],
                "outgoing": [...]
            }
        }
    """
    include_rels = request.args.get('include_relationships', 'true').lower() == 'true'
    include_props = request.args.get('include_properties', 'true').lower() == 'true'
    
    try:
        from ..memory.semantic import SemanticMemory
        
        memory = SemanticMemory(tenant_id=g.tenant_id)
        
        entities = memory.search_entities(name, limit=1, threshold=0.9)
        
        if not entities:
            entities = memory.search_entities(name, limit=5, threshold=0.5)
            if entities:
                suggestions = [e.get('canonical_name', e.get('name', '')) for e in entities[:3]]
                return jsonify({
                    'error': 'Entity not found',
                    'message': f'No exact match for "{name}"',
                    'suggestions': suggestions
                }), 404
            else:
                return jsonify({
                    'error': 'Entity not found',
                    'message': f'No entity named "{name}" found'
                }), 404
        
        entity = entities[0]
        
        result = {
            'id': entity.get('id'),
            'name': entity.get('canonical_name', entity.get('name')),
            'type': entity.get('entity_type'),
            'confidence': entity.get('confidence'),
            'lifecycle_state': entity.get('lifecycle_state')
        }
        
        if include_props:
            result['properties'] = entity.get('properties', {})
            result['description'] = entity.get('description')
        
        if include_rels:
            relationships = memory.get_entity_relationships(entity.get('id'))
            result['relationships'] = {
                'incoming': relationships.get('incoming', []),
                'outgoing': relationships.get('outgoing', [])
            }
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            'error': 'Entity retrieval failed',
            'message': str(e)
        }), 500


@external_api.route('/entities', methods=['GET'])
@require_api_key
def search_entities():
    """
    Search entities by query.
    
    Query Parameters:
        q: Search query (required)
        type: Filter by entity type
        limit: Max results (default: 10, max: 100)
        offset: Pagination offset
    
    Output:
        {
            "entities": [...],
            "total": 42,
            "limit": 10,
            "offset": 0
        }
    """
    query = request.args.get('q', '').strip()
    entity_type = request.args.get('type')
    limit = min(int(request.args.get('limit', 10)), 100)
    offset = int(request.args.get('offset', 0))
    
    if not query:
        return jsonify({
            'error': 'No search query',
            'message': 'Provide search query in "q" parameter'
        }), 400
    
    try:
        from ..memory.semantic import SemanticMemory
        
        memory = SemanticMemory(tenant_id=g.tenant_id)
        
        entities = memory.search_entities(
            query, 
            limit=limit + offset,
            entity_type=entity_type
        )
        
        paginated = entities[offset:offset + limit]
        
        results = []
        for e in paginated:
            results.append({
                'id': e.get('id'),
                'name': e.get('canonical_name', e.get('name')),
                'type': e.get('entity_type'),
                'confidence': e.get('confidence'),
                'similarity': e.get('similarity')
            })
        
        return jsonify({
            'entities': results,
            'total': len(entities),
            'limit': limit,
            'offset': offset
        })
        
    except Exception as e:
        return jsonify({
            'error': 'Search failed',
            'message': str(e)
        }), 500


def register_external_api(app):
    """Register the external API blueprint with a Flask app."""
    app.register_blueprint(external_api)
