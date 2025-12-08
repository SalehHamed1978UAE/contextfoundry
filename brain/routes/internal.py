import os
import time
import logging
from flask import Blueprint, request, jsonify
from sqlalchemy import text

logger = logging.getLogger(__name__)

internal_bp = Blueprint('internal', __name__, url_prefix='/internal/v1')


def get_db_session():
    from src.context_foundry.models.schema import get_session
    return get_session()


def get_context_foundry():
    from src.context_foundry.core import ContextFoundry
    return ContextFoundry()


@internal_bp.route('/health')
def health():
    start_time = time.time()
    components = {}
    overall_healthy = True
    
    try:
        session = get_db_session()
        session.execute(text("SELECT 1"))
        components['database'] = {'status': 'healthy', 'latency_ms': int((time.time() - start_time) * 1000)}
        session.close()
    except Exception as e:
        components['database'] = {'status': 'unhealthy', 'error': str(e)}
        overall_healthy = False
    
    try:
        foundry = get_context_foundry()
        components['core'] = {'status': 'healthy' if foundry else 'unhealthy'}
        if not foundry:
            overall_healthy = False
    except Exception as e:
        components['core'] = {'status': 'unhealthy', 'error': str(e)}
        overall_healthy = False
    
    try:
        session = get_db_session()
        
        stuck_result = session.execute(text("""
            SELECT COUNT(*) FROM platform.extraction_requests 
            WHERE status = 'pending' 
            AND created_at < NOW() - INTERVAL '5 minutes'
        """))
        stuck_count = stuck_result.scalar()
        
        recent_result = session.execute(text("""
            SELECT COUNT(*) FROM platform.extraction_requests 
            WHERE status = 'completed' 
            AND completed_at > NOW() - INTERVAL '10 minutes'
        """))
        recent_completed = recent_result.scalar()
        
        processing_result = session.execute(text("""
            SELECT COUNT(*) FROM platform.extraction_requests 
            WHERE status = 'processing' 
            AND claimed_at < NOW() - INTERVAL '5 minutes'
        """))
        stale_processing = processing_result.scalar()
        
        session.close()
        
        if stuck_count > 5 or stale_processing > 2:
            components['extraction_worker'] = {
                'status': 'degraded',
                'reason': f'{stuck_count} stuck, {stale_processing} stale processing',
                'recent_completed': recent_completed
            }
        else:
            components['extraction_worker'] = {
                'status': 'healthy',
                'pending_count': stuck_count,
                'recent_completed': recent_completed
            }
    except Exception as e:
        components['extraction_worker'] = {'status': 'unknown', 'error': str(e)}
    
    components['query_endpoint'] = {'status': 'healthy'}
    
    return jsonify({
        'status': 'healthy' if overall_healthy else 'degraded',
        'version': '1.0.0',
        'components': components,
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    }), 200 if overall_healthy else 503


@internal_bp.route('/query', methods=['POST'])
def query():
    from packages.interface_types.src import QueryRequest, QueryType
    
    start_time = time.time()
    data = request.get_json() or {}
    
    try:
        query_request = QueryRequest(**data)
    except Exception as e:
        return jsonify({
            'success': False,
            'results': [],
            'total_count': 0,
            'tokens_consumed': {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0},
            'duration_ms': int((time.time() - start_time) * 1000),
            'error': {'code': 'INVALID_QUERY', 'message': str(e)}
        }), 400
    
    try:
        foundry = get_context_foundry()
        
        if query_request.query_type == QueryType.SEMANTIC_SEARCH:
            result = foundry.query(query_request.query_text or "")
            
            entities = result.get('context_bundle', {}).get('blast_radius_entities', [])
            results = [
                {
                    'entity_id': e.get('id', ''),
                    'entity_type': e.get('type', ''),
                    'content': e,
                    'similarity_score': 0.8,
                    'source_document_id': e.get('source_document_id')
                }
                for e in entities[:query_request.max_results or 10]
            ]
            
            input_tokens = 100
            output_tokens = 50
            
        elif query_request.query_type == QueryType.VERIFY_STATEMENT:
            result = foundry.query(query_request.statement or "")
            
            verified = result.get('confidence', 0) > 0.7
            results = [{
                'verified': verified,
                'confidence': result.get('confidence', 0),
                'supporting_entities': [],
                'contradicting_entities': [],
                'explanation': result.get('answer', '')
            }]
            
            input_tokens = 150
            output_tokens = 100
            
        elif query_request.query_type == QueryType.GET_SCHEMA:
            from src.context_foundry.models.schema import OntologyType
            session = get_db_session()
            types = session.query(OntologyType).filter(
                OntologyType.state == 'ACTIVE'
            ).limit(50).all()
            
            results = [
                {
                    'entity_type': t.name,
                    'properties': [],
                    'relationships': []
                }
                for t in types
            ]
            session.close()
            
            input_tokens = 50
            output_tokens = 30
            
        else:
            results = []
            input_tokens = 20
            output_tokens = 10
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return jsonify({
            'success': True,
            'results': results,
            'total_count': len(results),
            'tokens_consumed': {
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'total_tokens': input_tokens + output_tokens
            },
            'duration_ms': duration_ms
        })
        
    except Exception as e:
        logger.error(f"Query error: {e}")
        return jsonify({
            'success': False,
            'results': [],
            'total_count': 0,
            'tokens_consumed': {'input_tokens': 0, 'output_tokens': 0, 'total_tokens': 0},
            'duration_ms': int((time.time() - start_time) * 1000),
            'error': {'code': 'INTERNAL_ERROR', 'message': str(e)}
        }), 500


@internal_bp.route('/entities')
def list_entities():
    tenant_id = request.args.get('tenant_id')
    if not tenant_id:
        return jsonify({'error': 'tenant_id required'}), 400
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    entity_type = request.args.get('type')
    document_id = request.args.get('document_id')
    
    try:
        session = get_db_session()
        
        query = """
            SELECT e.id, e.name, e.entity_type, e.properties, e.confidence,
                   e.source_document_id, e.created_at
            FROM public.entities e
            WHERE e.tenant_id = :tenant_id
        """
        params = {'tenant_id': tenant_id}
        
        if entity_type:
            query += " AND e.entity_type = :entity_type"
            params['entity_type'] = entity_type
        if document_id:
            query += " AND e.source_document_id = :document_id"
            params['document_id'] = document_id
        
        query += " ORDER BY e.created_at DESC LIMIT :limit OFFSET :offset"
        params['limit'] = per_page
        params['offset'] = (page - 1) * per_page
        
        result = session.execute(text(query), params)
        entities = [dict(row._mapping) for row in result]
        
        count_result = session.execute(
            text("SELECT COUNT(*) FROM public.entities WHERE tenant_id = :tenant_id"),
            {'tenant_id': tenant_id}
        )
        total = count_result.scalar()
        
        session.close()
        
        for e in entities:
            e['id'] = str(e['id'])
            e['document_id'] = str(e['source_document_id']) if e.get('source_document_id') else None
            e['created_at'] = e['created_at'].isoformat() if e['created_at'] else None
        
        return jsonify({
            'entities': entities,
            'total': total,
            'page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        logger.error(f"List entities error: {e}")
        return jsonify({'error': str(e)}), 500


@internal_bp.route('/entities/<entity_id>')
def get_entity(entity_id):
    tenant_id = request.args.get('tenant_id')
    if not tenant_id:
        return jsonify({'error': 'tenant_id required'}), 400
    
    try:
        session = get_db_session()
        
        entity_result = session.execute(
            text("""
                SELECT * FROM public.entities
                WHERE id = :entity_id AND tenant_id = :tenant_id
            """),
            {'entity_id': entity_id, 'tenant_id': tenant_id}
        )
        entity = entity_result.fetchone()
        
        if not entity:
            session.close()
            return jsonify({'error': 'Entity not found'}), 404
        
        entity_dict = dict(entity._mapping)
        entity_dict['id'] = str(entity_dict['id'])
        entity_dict['document_id'] = str(entity_dict['document_id']) if entity_dict.get('document_id') else None
        entity_dict['created_at'] = entity_dict['created_at'].isoformat() if entity_dict.get('created_at') else None
        
        rel_result = session.execute(
            text("""
                SELECT r.id, r.relationship_type, r.properties, r.confidence,
                       r.source_id as source_entity_id, r.target_id as target_entity_id,
                       se.name as source_name, se.entity_type as source_type,
                       te.name as target_name, te.entity_type as target_type
                FROM public.relationships r
                JOIN public.entities se ON r.source_id = se.id
                JOIN public.entities te ON r.target_id = te.id
                WHERE (r.source_id = :entity_id OR r.target_id = :entity_id)
                  AND r.tenant_id = :tenant_id
            """),
            {'entity_id': entity_id, 'tenant_id': tenant_id}
        )
        relationships = []
        for r in rel_result:
            rd = dict(r._mapping)
            rd['id'] = str(rd['id'])
            rd['source_entity_id'] = str(rd['source_entity_id'])
            rd['target_entity_id'] = str(rd['target_entity_id'])
            relationships.append(rd)
        
        session.close()
        
        return jsonify({
            'entity': entity_dict,
            'relationships': relationships
        })
        
    except Exception as e:
        logger.error(f"Get entity error: {e}")
        return jsonify({'error': str(e)}), 500


@internal_bp.route('/relationships')
def list_relationships():
    tenant_id = request.args.get('tenant_id')
    if not tenant_id:
        return jsonify({'error': 'tenant_id required'}), 400
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    try:
        session = get_db_session()
        
        result = session.execute(
            text("""
                SELECT r.id, r.relationship_type, r.properties, r.confidence,
                       se.id as source_id, se.name as source_name, se.entity_type as source_type,
                       te.id as target_id, te.name as target_name, te.entity_type as target_type,
                       r.created_at
                FROM public.relationships r
                JOIN public.entities se ON r.source_id = se.id
                JOIN public.entities te ON r.target_id = te.id
                WHERE r.tenant_id = :tenant_id
                ORDER BY r.created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {'tenant_id': tenant_id, 'limit': per_page, 'offset': (page - 1) * per_page}
        )
        
        relationships = []
        for r in result:
            rd = dict(r._mapping)
            rd['id'] = str(rd['id'])
            rd['source_id'] = str(rd['source_id'])
            rd['target_id'] = str(rd['target_id'])
            rd['created_at'] = rd['created_at'].isoformat() if rd.get('created_at') else None
            relationships.append(rd)
        
        count_result = session.execute(
            text("SELECT COUNT(*) FROM public.relationships WHERE tenant_id = :tenant_id"),
            {'tenant_id': tenant_id}
        )
        total = count_result.scalar()
        
        session.close()
        
        return jsonify({
            'relationships': relationships,
            'total': total,
            'page': page,
            'per_page': per_page
        })
        
    except Exception as e:
        logger.error(f"List relationships error: {e}")
        return jsonify({'error': str(e)}), 500


@internal_bp.route('/graph')
def get_graph():
    tenant_id = request.args.get('tenant_id')
    if not tenant_id:
        return jsonify({'error': 'tenant_id required'}), 400
    
    document_id = request.args.get('document_id')
    
    try:
        session = get_db_session()
        
        if document_id:
            entity_result = session.execute(
                text("""
                    SELECT id, name, entity_type, properties
                    FROM public.entities
                    WHERE tenant_id = :tenant_id AND document_id = :document_id
                    LIMIT 500
                """),
                {'tenant_id': tenant_id, 'document_id': document_id}
            )
        else:
            entity_result = session.execute(
                text("""
                    WITH hub_entities AS (
                        SELECT e.id, COUNT(r.id) as connection_count
                        FROM public.entities e
                        LEFT JOIN public.relationships r 
                            ON e.id = r.source_id OR e.id = r.target_id
                        WHERE e.tenant_id = :tenant_id
                        GROUP BY e.id
                        ORDER BY connection_count DESC
                        LIMIT 30
                    ),
                    neighbor_entities AS (
                        SELECT DISTINCT 
                            CASE WHEN r.source_id IN (SELECT id FROM hub_entities) 
                                 THEN r.target_id 
                                 ELSE r.source_id 
                            END as id
                        FROM public.relationships r
                        WHERE r.tenant_id = :tenant_id
                          AND (r.source_id IN (SELECT id FROM hub_entities)
                               OR r.target_id IN (SELECT id FROM hub_entities))
                    ),
                    all_relevant_ids AS (
                        SELECT id FROM hub_entities
                        UNION
                        SELECT id FROM neighbor_entities
                    )
                    SELECT e.id, e.name, e.entity_type, e.properties
                    FROM public.entities e
                    WHERE e.id IN (SELECT id FROM all_relevant_ids)
                    LIMIT 200
                """),
                {'tenant_id': tenant_id}
            )
        
        entities = [dict(row._mapping) for row in entity_result]
        entity_ids = [str(e['id']) for e in entities]
        
        if entity_ids:
            # Build IN clause with explicit UUIDs
            entity_ids_str = ','.join([f"'{eid}'" for eid in entity_ids])
            rel_result = session.execute(
                text(f"""
                    SELECT id, source_id as source_entity_id, target_id as target_entity_id, relationship_type
                    FROM public.relationships
                    WHERE tenant_id = :tenant_id
                      AND source_id::text IN ({entity_ids_str})
                      AND target_id::text IN ({entity_ids_str})
                """),
                {'tenant_id': tenant_id}
            )
            relationships = [dict(row._mapping) for row in rel_result]
        else:
            relationships = []
        
        session.close()
        
        nodes = [{
            'id': str(e['id']),
            'label': e['name'],
            'group': e['entity_type'],
            'title': f"{e['entity_type']}: {e['name']}"
        } for e in entities]
        
        edges = [{
            'id': str(r['id']),
            'from': str(r['source_entity_id']),
            'to': str(r['target_entity_id']),
            'label': r['relationship_type'],
            'arrows': 'to'
        } for r in relationships]
        
        return jsonify({'nodes': nodes, 'edges': edges})
        
    except Exception as e:
        logger.error(f"Get graph error: {e}")
        return jsonify({'error': str(e)}), 500


@internal_bp.route('/stats')
def get_stats():
    tenant_id = request.args.get('tenant_id')
    if not tenant_id:
        return jsonify({'error': 'tenant_id required'}), 400
    
    try:
        session = get_db_session()
        
        stats_result = session.execute(
            text("""
                SELECT 
                    (SELECT COUNT(*) FROM public.entities WHERE tenant_id = :tenant_id) as entity_count,
                    (SELECT COUNT(*) FROM public.relationships WHERE tenant_id = :tenant_id) as relationship_count,
                    (SELECT COUNT(DISTINCT entity_type) FROM public.entities WHERE tenant_id = :tenant_id) as entity_type_count
            """),
            {'tenant_id': tenant_id}
        )
        stats = stats_result.fetchone()
        
        type_result = session.execute(
            text("""
                SELECT entity_type, COUNT(*) as count
                FROM public.entities
                WHERE tenant_id = :tenant_id
                GROUP BY entity_type
                ORDER BY count DESC
            """),
            {'tenant_id': tenant_id}
        )
        type_breakdown = [dict(row._mapping) for row in type_result]
        
        session.close()
        
        return jsonify({
            'entities': stats[0],
            'relationships': stats[1],
            'entity_types': stats[2],
            'type_breakdown': type_breakdown
        })
        
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        return jsonify({'error': str(e)}), 500
