"""
Ontology Foundry API Endpoints (Flask)

Phase 1: Read-only endpoints for candidates
"""

from flask import Blueprint, request, jsonify, g
from uuid import UUID

from src.context_foundry.models.schema import get_session
from src.context_foundry.ontology.candidate_store import CandidateStore
from src.context_foundry.utils.logger import logger

ontology_bp = Blueprint('ontology', __name__, url_prefix='/api/ontology')


@ontology_bp.route('/candidates', methods=['GET'])
def get_candidates():
    """
    Get ontology candidates for review.
    Returns candidates sorted by confidence descending.
    
    Query params:
    - type: Filter by RELATIONSHIP, ENTITY, or ATTRIBUTE
    - min_confidence: Minimum confidence threshold (default 0.0)
    """
    if not g.tenant_id:
        return jsonify({"error": "No vault selected"}), 400
    
    candidate_type = request.args.get('type')
    min_confidence = request.args.get('min_confidence', type=float, default=0.0)
    
    db_session = get_session()
    try:
        store = CandidateStore(db_session, UUID(g.tenant_id))
        candidates = store.get_pending_candidates(
            candidate_type=candidate_type,
            min_confidence=min_confidence
        )
        
        logger.info(f"[OntologyAPI] Retrieved {len(candidates)} candidates")
        
        return jsonify({
            "candidates": candidates,
            "count": len(candidates)
        })
    finally:
        db_session.close()


@ontology_bp.route('/candidates/<candidate_id>', methods=['GET'])
def get_candidate(candidate_id):
    """
    Get a single candidate with its pending extractions.
    """
    if not g.tenant_id:
        return jsonify({"error": "No vault selected"}), 400
    
    db_session = get_session()
    try:
        store = CandidateStore(db_session, UUID(g.tenant_id))
        
        try:
            candidate = store.get_candidate_by_id(UUID(candidate_id))
        except ValueError:
            return jsonify({"error": "Invalid candidate ID"}), 400
        
        if not candidate:
            return jsonify({"error": "Candidate not found"}), 404
        
        extractions = store.get_pending_extractions(UUID(candidate_id))
        
        return jsonify({
            "candidate": candidate,
            "pending_extractions": extractions,
            "extraction_count": len(extractions)
        })
    finally:
        db_session.close()


@ontology_bp.route('/stats', methods=['GET'])
def get_stats():
    """
    Get candidate counts by type and status.
    """
    if not g.tenant_id:
        return jsonify({"error": "No vault selected"}), 400
    
    db_session = get_session()
    try:
        store = CandidateStore(db_session, UUID(g.tenant_id))
        stats = store.get_stats()
        
        return jsonify({
            "stats": stats,
            "total_pending": sum(s.get("PENDING", 0) for s in stats.values())
        })
    finally:
        db_session.close()
