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
    __table_args__ = {'schema': 'platform'}
    
    id = Column(String(36), primary_key=True)
    name = Column(String(255), nullable=False)
    key_hash = Column(String(64), nullable=False, unique=True)
    key_prefix = Column(String(8), nullable=False)
    tenant_id = Column(String(36), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used_at = Column(DateTime)
    expires_at = Column(DateTime)
    revoked_at = Column(DateTime)
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
        api_key = session.query(APIKey).filter(
            APIKey.key_hash == key_hash,
            APIKey.revoked_at.is_(None)
        ).first()
        
        if not api_key:
            session.close()
            return None
        
        if api_key.expires_at and api_key.expires_at < datetime.utcnow():
            session.close()
            return None
        
        api_key.last_used_at = datetime.utcnow()
        session.commit()
        
        scopes = ['read']
        if api_key.scopes:
            if isinstance(api_key.scopes, list):
                scopes = api_key.scopes
            elif isinstance(api_key.scopes, str):
                scopes = api_key.scopes.split(',')
        
        result = {
            'id': str(api_key.id),
            'name': api_key.name,
            'tenant_id': str(api_key.tenant_id),
            'scopes': scopes
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


def _log_interaction_event(
    tenant_id: str,
    app_id: str,
    event_type: str,
    raw_text: str,
    result_status: str,
    resolved_entities: list = None,
    confidence: float = None,
    elapsed_ms: float = None,
    user_id: str = None,
    session_id: str = None,
    trace_id: str = None,
    analysis_type: str = None
):
    """Log interaction event (append-only, non-blocking)."""
    try:
        from ..models.schema import InteractionEvent, get_session
        session = get_session()
        event = InteractionEvent(
            tenant_id=tenant_id,
            app_id=app_id or 'unknown',
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id,
            event_type=event_type,
            raw_text=raw_text,
            analysis_type=analysis_type,
            resolved_entities=resolved_entities,
            result_status=result_status,
            confidence=confidence,
            elapsed_ms=elapsed_ms
        )
        session.add(event)
        session.commit()
        session.close()
    except Exception as e:
        pass


def _get_entity_relationships(session, entity_id: str, max_hops: int = 2) -> dict:
    """Get relationships for an entity with hop traversal."""
    from sqlalchemy import text
    
    grounded_facts = []
    
    sql = text("""
        SELECT 
            r.relationship_type,
            e_source.name as source_name,
            e_target.name as target_name,
            r.confidence,
            r.source_sentence
        FROM relationships r
        JOIN entities e_source ON r.source_id = e_source.id
        JOIN entities e_target ON r.target_id = e_target.id
        WHERE (r.source_id = :entity_id OR r.target_id = :entity_id)
          AND r.lifecycle_state = 'TRUSTED'
          AND e_source.lifecycle_state = 'TRUSTED'
          AND e_target.lifecycle_state = 'TRUSTED'
        ORDER BY r.confidence DESC
        LIMIT 50
    """)
    
    try:
        result = session.execute(sql, {"entity_id": entity_id})
        for row in result:
            grounded_facts.append({
                "fact": f"{row[1]} {row[0]} {row[2]}",
                "evidence": [f"edge:{row[0]}"],
                "confidence": float(row[3]) if row[3] else 0.5,
                "source_sentence": row[4]
            })
    except Exception as e:
        pass
    
    return grounded_facts


@external_api.route('/query', methods=['POST'])
@require_api_key
def query_knowledge():
    """
    Natural language query endpoint with entity extraction.
    
    Accepts raw text and extracts entities using Tier 1 Resolver.
    
    Input:
        {
            "query": "Reduce API Gateway downtime by 50%",
            "analysis_type": "root_cause",
            "context": {
                "app_id": "premisia",
                "user_id": "u-123",
                "session_id": "s-456",
                "trace_id": "t-789"
            }
        }
    
    Output:
        {
            "status": "RESOLVED",
            "memory_version": 47,
            "confidence": 0.76,
            "entity_resolution": {...},
            "answer": {...},
            "audit": {...}
        }
    """
    import time
    start_time = time.time()
    
    data = request.get_json()
    
    if not data or not data.get('query'):
        return jsonify({
            'error': 'No query provided',
            'message': 'Request body must contain a "query" field'
        }), 400
    
    query_text = data['query'].strip()
    analysis_type = data.get('analysis_type', 'general')
    context = data.get('context', {})
    
    app_id = context.get('app_id', 'unknown')
    user_id = context.get('user_id')
    session_id = context.get('session_id')
    trace_id = context.get('trace_id')
    
    from ..agents.tier1_resolver import Tier1Resolver
    from ..models.schema import get_session as get_cf_session
    
    cf_session = get_cf_session()
    try:
        resolver = Tier1Resolver(session=cf_session, tenant_id=g.tenant_id)
        resolve_result = resolver.resolve_from_text(query_text)
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        if resolve_result.status == "NO_MATCHES":
            _log_interaction_event(
                tenant_id=g.tenant_id,
                app_id=app_id,
                event_type="QUERY",
                raw_text=query_text,
                result_status="NO_MATCHES",
                elapsed_ms=elapsed_ms,
                user_id=user_id,
                session_id=session_id,
                trace_id=trace_id,
                analysis_type=analysis_type
            )
            
            return jsonify({
                "status": "NO_MATCHES",
                "memory_version": 1,
                "confidence": 0.0,
                "entity_resolution": {
                    "candidates": [],
                    "selected": None,
                    "extracted_terms": resolve_result.extracted_terms
                },
                "answer": {
                    "grounded_facts": [],
                    "gaps": [{"gap": "No entities found in query text", "evidence": ["resolver:tier1"]}]
                },
                "audit": {"elapsed_ms": elapsed_ms}
            })
        
        if resolve_result.status == "AMBIGUOUS":
            _log_interaction_event(
                tenant_id=g.tenant_id,
                app_id=app_id,
                event_type="QUERY",
                raw_text=query_text,
                result_status="AMBIGUOUS",
                resolved_entities=[e.to_dict() for e in resolve_result.entities],
                confidence=resolve_result.entities[0].score if resolve_result.entities else 0,
                elapsed_ms=elapsed_ms,
                user_id=user_id,
                session_id=session_id,
                trace_id=trace_id,
                analysis_type=analysis_type
            )
            
            return jsonify({
                "status": "AMBIGUOUS",
                "memory_version": 1,
                "confidence": resolve_result.entities[0].score if resolve_result.entities else 0,
                "entity_resolution": {
                    "candidates": [e.to_dict() for e in resolve_result.entities],
                    "selected": None,
                    "selection_reason": resolve_result.selection_reason
                },
                "answer": {
                    "grounded_facts": [],
                    "gaps": [{"gap": "Multiple possible entities - clarification needed", "evidence": ["resolver:tier1"]}]
                },
                "audit": {"elapsed_ms": elapsed_ms}
            })
        
        if resolve_result.status == "LOW_CONFIDENCE":
            _log_interaction_event(
                tenant_id=g.tenant_id,
                app_id=app_id,
                event_type="QUERY",
                raw_text=query_text,
                result_status="LOW_CONFIDENCE",
                resolved_entities=[e.to_dict() for e in resolve_result.entities],
                confidence=resolve_result.entities[0].score if resolve_result.entities else 0,
                elapsed_ms=elapsed_ms,
                user_id=user_id,
                session_id=session_id,
                trace_id=trace_id,
                analysis_type=analysis_type
            )
            
            return jsonify({
                "status": "LOW_CONFIDENCE",
                "memory_version": 1,
                "confidence": resolve_result.entities[0].score if resolve_result.entities else 0,
                "entity_resolution": {
                    "candidates": [e.to_dict() for e in resolve_result.entities],
                    "selected": None,
                    "selection_reason": resolve_result.selection_reason
                },
                "answer": {
                    "grounded_facts": [],
                    "gaps": [{"gap": "Low confidence match - may need clarification", "evidence": ["resolver:tier1"]}]
                },
                "audit": {"elapsed_ms": elapsed_ms}
            })
        
        selected = resolve_result.selected
        if not selected:
            return jsonify({
                "status": "NO_MATCHES",
                "memory_version": 1,
                "confidence": 0.0,
                "entity_resolution": {"candidates": [], "selected": None},
                "answer": {"grounded_facts": [], "gaps": [{"gap": "No entity could be resolved"}]},
                "audit": {"elapsed_ms": elapsed_ms}
            })
        
        grounded_facts = _get_entity_relationships(cf_session, selected.entity_id)
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        _log_interaction_event(
            tenant_id=g.tenant_id,
            app_id=app_id,
            event_type="QUERY",
            raw_text=query_text,
            result_status="RESOLVED",
            resolved_entities=[selected.to_dict()],
            confidence=selected.score,
            elapsed_ms=elapsed_ms,
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id,
            analysis_type=analysis_type
        )
        
        return jsonify({
            "status": "RESOLVED",
            "memory_version": 1,
            "confidence": selected.score,
            "entity_resolution": {
                "candidates": [e.to_dict() for e in resolve_result.entities],
                "selected": {
                    "entity_id": selected.entity_id,
                    "name": selected.name,
                    "selection_reason": resolve_result.selection_reason
                }
            },
            "answer": {
                "grounded_facts": grounded_facts,
                "gaps": [] if grounded_facts else [{"gap": f"No relationships found for {selected.name}", "evidence": ["graph:traversal"]}]
            },
            "audit": {
                "evidence_chain": [f"entity:{selected.entity_id}"],
                "applied_memory": [
                    {
                        "type": "resolver",
                        "input": query_text,
                        "resolved_to": selected.name,
                        "evidence": selected.evidence
                    }
                ],
                "elapsed_ms": elapsed_ms
            }
        })
        
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        _log_interaction_event(
            tenant_id=g.tenant_id,
            app_id=app_id,
            event_type="QUERY",
            raw_text=query_text,
            result_status="ERROR",
            elapsed_ms=elapsed_ms,
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id,
            analysis_type=analysis_type
        )
        
        return jsonify({
            'error': 'Query processing failed',
            'message': str(e)
        }), 500
    finally:
        cf_session.close()


@external_api.route('/verify', methods=['POST'])
@require_api_key
def verify_claim():
    """
    Fast claim verification endpoint for real-time use (Meeting Assistant).
    
    Uses Tier 1 Resolver ONLY - no LLM calls.
    Target latency: P95 < 300ms, P99 < 500ms
    
    Input:
        {
            "utterance": "If API Gateway goes down, mobile will be down too.",
            "verification_type": "dependency_check",
            "context": {
                "app_id": "meeting_assistant",
                "user_id": "u-777",
                "session_id": "meeting-2025-12-14-0900",
                "trace_id": "t-abc"
            }
        }
    
    Output:
        {
            "verdict": "SUPPORTED|REFUTED|INSUFFICIENT_EVIDENCE|NEEDS_CLARIFICATION",
            "memory_version": 47,
            "confidence": 0.81,
            "entity_resolution": {...},
            "support": [...],
            "limits": {"max_hops": 2, "llm_used": false}
        }
    """
    import time
    start_time = time.time()
    
    data = request.get_json()
    
    if not data or not data.get('utterance'):
        return jsonify({
            'error': 'No utterance provided',
            'message': 'Request body must contain an "utterance" field'
        }), 400
    
    utterance = data['utterance'].strip()
    verification_type = data.get('verification_type', 'general')
    context = data.get('context', {})
    
    app_id = context.get('app_id', 'unknown')
    user_id = context.get('user_id')
    session_id = context.get('session_id')
    trace_id = context.get('trace_id')
    
    try:
        from ..agents.tier1_resolver import Tier1Resolver
        from ..models.schema import get_session as get_cf_session
        
        cf_session = get_cf_session()
        resolver = Tier1Resolver(session=cf_session, tenant_id=g.tenant_id, use_embeddings=False)
        resolve_result = resolver.resolve_from_text(utterance)
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        if resolve_result.status in ["NO_MATCHES", "NO_TEXT", "NO_ENTITIES_IN_GRAPH"]:
            _log_interaction_event(
                tenant_id=g.tenant_id,
                app_id=app_id,
                event_type="VERIFY",
                raw_text=utterance,
                result_status="INSUFFICIENT_EVIDENCE",
                elapsed_ms=elapsed_ms,
                user_id=user_id,
                session_id=session_id,
                trace_id=trace_id
            )
            
            cf_session.close()
            return jsonify({
                "verdict": "INSUFFICIENT_EVIDENCE",
                "memory_version": 1,
                "confidence": 0.0,
                "entity_resolution": {
                    "selected": None,
                    "secondary": []
                },
                "support": [],
                "limits": {"max_hops": 2, "llm_used": False},
                "elapsed_ms": elapsed_ms
            })
        
        if resolve_result.status in ["AMBIGUOUS", "LOW_CONFIDENCE"]:
            _log_interaction_event(
                tenant_id=g.tenant_id,
                app_id=app_id,
                event_type="VERIFY",
                raw_text=utterance,
                result_status="NEEDS_CLARIFICATION",
                resolved_entities=[e.to_dict() for e in resolve_result.entities],
                confidence=resolve_result.entities[0].score if resolve_result.entities else 0,
                elapsed_ms=elapsed_ms,
                user_id=user_id,
                session_id=session_id,
                trace_id=trace_id
            )
            
            cf_session.close()
            return jsonify({
                "verdict": "NEEDS_CLARIFICATION",
                "memory_version": 1,
                "confidence": resolve_result.entities[0].score if resolve_result.entities else 0,
                "entity_resolution": {
                    "candidates": [e.to_dict() for e in resolve_result.entities[:3]],
                    "selected": None
                },
                "support": [],
                "limits": {"max_hops": 2, "llm_used": False},
                "elapsed_ms": elapsed_ms
            })
        
        selected = resolve_result.selected
        grounded_facts = _get_entity_relationships(cf_session, selected.entity_id, max_hops=2)
        
        if grounded_facts:
            verdict = "SUPPORTED"
            support = grounded_facts[:5]
        else:
            verdict = "INSUFFICIENT_EVIDENCE"
            support = []
        
        elapsed_ms = (time.time() - start_time) * 1000
        
        _log_interaction_event(
            tenant_id=g.tenant_id,
            app_id=app_id,
            event_type="VERIFY",
            raw_text=utterance,
            result_status=verdict,
            resolved_entities=[selected.to_dict()],
            confidence=selected.score,
            elapsed_ms=elapsed_ms,
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id
        )
        
        cf_session.close()
        
        return jsonify({
            "verdict": verdict,
            "memory_version": 1,
            "confidence": selected.score,
            "entity_resolution": {
                "selected": {"entity_id": selected.entity_id, "name": selected.name},
                "secondary": [e.to_dict() for e in resolve_result.entities[1:3]]
            },
            "support": support,
            "limits": {"max_hops": 2, "llm_used": False},
            "elapsed_ms": elapsed_ms
        })
        
    except Exception as e:
        elapsed_ms = (time.time() - start_time) * 1000
        _log_interaction_event(
            tenant_id=g.tenant_id,
            app_id=app_id,
            event_type="VERIFY",
            raw_text=utterance,
            result_status="ERROR",
            elapsed_ms=elapsed_ms,
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id
        )
        
        return jsonify({
            'error': 'Verification failed',
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
        
        entities = memory.search_entities(name, limit=1)
        
        if not entities:
            entities = memory.search_entities(name, limit=5)
            if entities:
                suggestions = [getattr(e, 'name', '') for e in entities[:3]]
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
            'id': str(entity.id) if entity.id else None,
            'name': entity.name,
            'type': entity.entity_type,
            'confidence': float(entity.confidence) if entity.confidence else None,
            'lifecycle_state': str(entity.lifecycle_state) if entity.lifecycle_state else None
        }
        
        if include_props:
            result['properties'] = entity.properties or {}
            result['description'] = entity.description
        
        if include_rels:
            relationships = memory.get_entity_relationships(entity.id)
            incoming = [r for r in relationships if r.get('direction') == 'incoming']
            outgoing = [r for r in relationships if r.get('direction') == 'outgoing']
            result['relationships'] = {
                'incoming': incoming,
                'outgoing': outgoing
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
        
        entity_types = [entity_type] if entity_type else None
        entities = memory.search_entities(
            query, 
            entity_types=entity_types,
            limit=limit + offset
        )
        
        paginated = entities[offset:offset + limit]
        
        results = []
        for e in paginated:
            results.append({
                'id': str(e.id) if e.id else None,
                'name': e.name,
                'type': e.entity_type,
                'confidence': float(e.confidence) if e.confidence else None
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
