"""
Decision Trace Layer API

Flask routes for decision management and precedent search.
Integrates with CF's existing authentication and session patterns.

Security:
- All endpoints (except /health) require API key authentication
- tenant_id comes from the authenticated API key, not from request body
- SQL functions use SECURITY DEFINER to bypass RLS recursion
- All queries explicitly filter by tenant_id
"""
import os
import json
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

from flask import Blueprint, request, jsonify, g
from sqlalchemy import text
import requests

from src.context_foundry.models.schema import get_session, set_tenant_context
from src.context_foundry.api.external import require_api_key

logger = logging.getLogger(__name__)

dtl_bp = Blueprint('dtl', __name__, url_prefix='/api/v1/dtl')


def get_embedding(text_input: str) -> List[float]:
    """Get embedding from OpenAI text-embedding-3-small"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not configured")
    
    response = requests.post(
        "https://api.openai.com/v1/embeddings",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        },
        json={"model": "text-embedding-3-small", "input": text_input},
        timeout=30.0
    )
    response.raise_for_status()
    return response.json()["data"][0]["embedding"]


def validate_uuid(value: str) -> bool:
    """Validate that a string is a valid UUID"""
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError):
        return False


@dtl_bp.route('/health', methods=['GET'])
def health():
    """Health check for DTL (no auth required)"""
    return jsonify({
        "status": "healthy",
        "service": "DTL",
        "version": "1.0"
    })


@dtl_bp.route('/decisions', methods=['POST'])
@require_api_key
def create_decision():
    """
    Create a new decision trace.
    
    Evidence is required and must be submitted in the same transaction.
    If lifecycle_state is 'enacted', the deferrable constraint trigger
    will block commit without evidence.
    
    Tenant_id is derived from the authenticated API key.
    """
    data = request.get_json()
    
    required_fields = ['summary', 'choice', 'rationale', 'decision_maker_id', 'evidence']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    if not data.get('evidence'):
        return jsonify({"error": "Evidence is required for decisions"}), 400
    
    tenant_id = g.tenant_id
    
    if not validate_uuid(data['decision_maker_id']):
        return jsonify({"error": "Invalid decision_maker_id format"}), 400
    
    entity_ids = data.get('entity_ids', [])
    for eid in entity_ids:
        if not validate_uuid(eid):
            return jsonify({"error": f"Invalid entity_id format: {eid}"}), 400
    
    session = None
    try:
        session = get_session(use_rls_role=False)
        set_tenant_context(session, tenant_id)
        
        embedding = get_embedding(f"{data['summary']}. {data['rationale']}")
        
        decision_uuid = str(uuid.uuid4())
        human_id = f"DEC-{datetime.now().strftime('%Y')}-{decision_uuid[:8].upper()}"
        
        lifecycle = data.get('lifecycle_state', 'enacted')
        
        choice_json = json.dumps(data['choice'])
        context_json = json.dumps(data.get('context', {}))
        
        session.execute(text("""
            INSERT INTO decision_traces (
                id, decision_id, decision_timestamp, decision_summary,
                decision_choice, decision_maker_id, decision_type,
                rationale_summary, rationale_embedding, context_snapshot,
                lifecycle_state, source_system, created_by, tenant_id, sensitivity
            ) VALUES (
                CAST(:id AS uuid), :human_id, :timestamp, :summary,
                CAST(:choice AS jsonb), CAST(:maker_id AS uuid), :dtype,
                :rationale, CAST(:embedding AS vector), CAST(:context AS jsonb),
                :lifecycle, :source, :created_by, CAST(:tenant_id AS uuid), :sensitivity
            )
        """), {
            "id": decision_uuid,
            "human_id": human_id,
            "timestamp": datetime.utcnow(),
            "summary": data['summary'],
            "choice": choice_json,
            "maker_id": data['decision_maker_id'],
            "dtype": data.get('decision_type'),
            "rationale": data['rationale'],
            "embedding": str(embedding),
            "context": context_json,
            "lifecycle": lifecycle,
            "source": data.get('source_system', 'api'),
            "created_by": data.get('created_by', 'api_user'),
            "tenant_id": tenant_id,
            "sensitivity": data.get('sensitivity', 'internal')
        })
        
        for ev in data['evidence']:
            session.execute(text("""
                INSERT INTO decision_evidence (
                    decision_id, evidence_type, source_uri, source_id, excerpt
                ) VALUES (CAST(:decision_id AS uuid), :etype, :uri, :source_id, :excerpt)
            """), {
                "decision_id": decision_uuid,
                "etype": ev.get('evidence_type', 'manual_note'),
                "uri": ev.get('source_uri'),
                "source_id": ev.get('source_id'),
                "excerpt": ev.get('excerpt')
            })
        
        for entity_id in entity_ids:
            session.execute(text("""
                INSERT INTO decision_entity_links (
                    decision_id, entity_id, entity_role, resolution_method
                ) VALUES (CAST(:decision_id AS uuid), CAST(:entity_id AS uuid), 'subject', 'manual')
            """), {
                "decision_id": decision_uuid,
                "entity_id": entity_id
            })
        
        session.execute(text("""
            INSERT INTO decision_confidence_scores (
                decision_id, overall_confidence, rationale_completeness,
                scoring_model_version
            ) VALUES (CAST(:decision_id AS uuid), :confidence, :completeness, 'api_v1')
        """), {
            "decision_id": decision_uuid,
            "confidence": 1.0 if data.get('evidence') else 0.5,
            "completeness": 1.0 if data.get('rationale') else 0.5
        })
        
        session.commit()
        
        logger.info(f"Created decision {human_id} for tenant {tenant_id}")
        
        return jsonify({
            "decision_id": human_id,
            "id": decision_uuid,
            "status": "created"
        }), 201
        
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"Failed to create decision: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if session:
            session.close()


@dtl_bp.route('/precedents/search', methods=['POST'])
@require_api_key
def search_precedents():
    """
    Search for relevant precedents.
    
    Uses the search_precedents_api function which combines:
    - Semantic similarity (vector search)
    - Full-text search
    - Entity overlap scoring
    - Recency decay
    - Outcome quality weighting
    - Category matching bonus
    
    Tenant_id is derived from the authenticated API key.
    """
    data = request.get_json()
    
    if 'query' not in data:
        return jsonify({"error": "Missing required field: query"}), 400
    
    tenant_id = g.tenant_id
    
    entity_ids = data.get('entity_ids')
    if entity_ids:
        for eid in entity_ids:
            if not validate_uuid(eid):
                return jsonify({"error": f"Invalid entity_id format: {eid}"}), 400
    
    session = None
    try:
        session = get_session(use_rls_role=False)
        set_tenant_context(session, tenant_id)
        
        embedding = get_embedding(data['query'])
        
        result = session.execute(text("""
            SELECT * FROM search_precedents_api(
                :query_text,
                CAST(:embedding AS vector),
                CAST(:tenant_id AS uuid),
                :decision_type_hint,
                CAST(:entity_ids AS uuid[]),
                :min_confidence,
                :limit,
                :include_negative
            )
        """), {
            "query_text": data['query'],
            "embedding": str(embedding),
            "tenant_id": tenant_id,
            "decision_type_hint": data.get('decision_type_hint'),
            "entity_ids": entity_ids,
            "min_confidence": data.get('min_confidence', 0.0),
            "limit": data.get('limit', 10),
            "include_negative": data.get('include_negative_outcomes', True)
        })
        
        rows = result.fetchall()
        
        precedents = []
        for row in rows:
            precedents.append({
                "decision_id": str(row.decision_id),
                "decision_human_id": row.decision_human_id,
                "summary": row.summary,
                "decision_type": row.decision_type,
                "rationale_summary": row.rationale_summary,
                "choice": row.choice,
                "decision_timestamp": row.decision_timestamp.isoformat() if row.decision_timestamp else None,
                "decision_maker_id": str(row.decision_maker_id),
                "outcome_status": str(row.outcome_status) if row.outcome_status else None,
                "semantic_rank": row.semantic_rank,
                "fulltext_rank": row.fulltext_rank,
                "entity_rank": row.entity_rank,
                "semantic_score": float(row.semantic_score or 0),
                "fulltext_score": float(row.fulltext_score or 0),
                "entity_overlap_score": float(row.entity_overlap_score or 0),
                "recency_score": float(row.recency_score or 0),
                "outcome_score": float(row.outcome_score or 0),
                "category_bonus": float(row.category_bonus or 0),
                "rrf_score": float(row.rrf_score or 0)
            })
        
        return jsonify({
            "query": data['query'],
            "tenant_id": tenant_id,
            "count": len(precedents),
            "precedents": precedents
        })
        
    except Exception as e:
        logger.error(f"Precedent search failed: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if session:
            session.close()


@dtl_bp.route('/decisions/<decision_id>', methods=['GET'])
@require_api_key
def get_decision(decision_id: str):
    """Get a decision with all related data. Tenant_id from authenticated API key."""
    tenant_id = g.tenant_id
    
    session = None
    try:
        session = get_session(use_rls_role=False)
        set_tenant_context(session, tenant_id)
        
        decision = session.execute(text("""
            SELECT * FROM decision_traces 
            WHERE (id::text = :decision_id OR decision_id = :decision_id)
            AND tenant_id = CAST(:tenant_id AS uuid)
        """), {"decision_id": decision_id, "tenant_id": tenant_id}).fetchone()
        
        if not decision:
            return jsonify({"error": "Decision not found"}), 404
        
        decision_uuid = str(decision.id)
        
        result = {
            "id": decision_uuid,
            "decision_id": decision.decision_id,
            "summary": decision.decision_summary,
            "choice": decision.decision_choice,
            "rationale": decision.rationale_summary,
            "decision_type": decision.decision_type,
            "decision_maker_id": str(decision.decision_maker_id),
            "lifecycle_state": decision.lifecycle_state,
            "sensitivity": decision.sensitivity,
            "decision_timestamp": decision.decision_timestamp.isoformat() if decision.decision_timestamp else None,
            "created_at": decision.created_at.isoformat() if decision.created_at else None
        }
        
        evidence = session.execute(text("""
            SELECT * FROM decision_evidence WHERE decision_id = CAST(:decision_id AS uuid)
        """), {"decision_id": decision_uuid}).fetchall()
        result['evidence'] = [
            {
                "id": str(e.id),
                "evidence_type": e.evidence_type,
                "source_uri": e.source_uri,
                "source_id": e.source_id,
                "excerpt": e.excerpt
            }
            for e in evidence
        ]
        
        precedents = session.execute(text("""
            SELECT dpl.*, dt.decision_summary as precedent_summary
            FROM decision_precedent_links dpl
            JOIN decision_traces dt ON dt.id = dpl.precedent_decision_id
            WHERE dpl.decision_id = CAST(:decision_id AS uuid)
        """), {"decision_id": decision_uuid}).fetchall()
        result['precedents'] = [
            {
                "precedent_id": str(p.precedent_decision_id),
                "link_type": p.link_type,
                "similarity_score": float(p.similarity_score) if p.similarity_score else None,
                "precedent_applied": p.precedent_applied,
                "precedent_summary": p.precedent_summary
            }
            for p in precedents
        ]
        
        outcome = session.execute(text("""
            SELECT * FROM decision_results 
            WHERE decision_id = CAST(:decision_id AS uuid)
            ORDER BY observed_at DESC LIMIT 1
        """), {"decision_id": decision_uuid}).fetchone()
        result['outcome'] = {
            "outcome_status": str(outcome.outcome_status) if outcome else None,
            "outcome_metrics": outcome.outcome_metrics if outcome else None,
            "observed_at": outcome.observed_at.isoformat() if outcome and outcome.observed_at else None,
            "notes": outcome.result_notes if outcome else None
        } if outcome else None
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Failed to get decision {decision_id}: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if session:
            session.close()


@dtl_bp.route('/decisions/<decision_id>/outcome', methods=['POST'])
@require_api_key
def record_outcome(decision_id: str):
    """Record the outcome of a decision. Tenant_id from authenticated API key."""
    data = request.get_json()
    
    if 'outcome_status' not in data:
        return jsonify({"error": "Missing required field: outcome_status"}), 400
    
    tenant_id = g.tenant_id
    
    valid_statuses = ['positive', 'neutral', 'negative', 'unknown']
    if data['outcome_status'] not in valid_statuses:
        return jsonify({"error": f"Invalid outcome_status. Must be one of: {valid_statuses}"}), 400
    
    session = None
    try:
        session = get_session(use_rls_role=False)
        set_tenant_context(session, tenant_id)
        
        decision_uuid = session.execute(text("""
            SELECT id FROM decision_traces 
            WHERE (id::text = :decision_id OR decision_id = :decision_id)
            AND tenant_id = CAST(:tenant_id AS uuid)
        """), {"decision_id": decision_id, "tenant_id": tenant_id}).fetchone()
        
        if not decision_uuid:
            return jsonify({"error": "Decision not found"}), 404
        
        result_id = str(uuid.uuid4())
        metrics_json = json.dumps(data.get('metrics', {}))
        
        session.execute(text("""
            INSERT INTO decision_results (
                id, decision_id, outcome_status, outcome_metrics, result_notes
            ) VALUES (CAST(:id AS uuid), CAST(:decision_id AS uuid), :status, CAST(:metrics AS jsonb), :notes)
        """), {
            "id": result_id,
            "decision_id": str(decision_uuid.id),
            "status": data['outcome_status'],
            "metrics": metrics_json,
            "notes": data.get('notes')
        })
        
        session.commit()
        
        return jsonify({
            "status": "recorded",
            "result_id": result_id
        })
        
    except Exception as e:
        if session:
            session.rollback()
        logger.error(f"Failed to record outcome for {decision_id}: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if session:
            session.close()
