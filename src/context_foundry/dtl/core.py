"""
DTL Core - Single Source of Truth for Precedent Retrieval

This module contains ALL precedent retrieval logic. No retrieval logic
may live in adapters - they only handle auth + request/response formatting.

SECURITY:
- Core accepts ONLY AuthContext (no raw tenant_id/user_id parameters)
- Core sets DB session vars before query for RLS enforcement:
  - app.current_tenant_id
  - app.current_user_id
  - app.current_user_role

EMBEDDING POLICY:
- Default: caller supplies query_embedding (fast path)
- Fallback: core computes embedding if missing (slow path, marked in logs)
"""

import os
import time
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple

import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


EMBEDDING_CACHE: Dict[str, Tuple[List[float], float]] = {}
EMBEDDING_CACHE_TTL = 3600  # 1 hour
EMBEDDING_CACHE_MAX_SIZE = 1000


@dataclass(frozen=True)
class AuthContext:
    """
    Authentication context for precedent searches.
    
    This is the ONLY way to pass identity to core functions.
    Never accept raw tenant_id/user_id as function parameters.
    
    Attributes:
        tenant_id: UUID string of the authenticated tenant
        user_id: UUID string of the authenticated user
        role: User role ('user', 'admin', etc.)
    """
    tenant_id: str
    user_id: str
    role: str = 'user'
    
    def __post_init__(self):
        if not self.tenant_id:
            raise ValueError("AuthContext requires tenant_id")
        if not self.user_id:
            raise ValueError("AuthContext requires user_id")


@dataclass
class PrecedentResult:
    """A single precedent search result with explainability signals"""
    decision_id: str
    decision_human_id: str
    summary: str
    decision_type: Optional[str]
    rationale_summary: Optional[str]
    choice: Dict[str, Any]
    decision_timestamp: datetime
    decision_maker_id: str
    outcome_status: Optional[str]
    
    semantic_rank: Optional[int]
    fulltext_rank: Optional[int]
    entity_rank: Optional[int]
    semantic_score: float
    fulltext_score: float
    entity_overlap_score: float
    recency_score: float
    outcome_score: float
    category_bonus: float
    rrf_score: float
    
    @property
    def relevance_explanation(self) -> Dict[str, Any]:
        """Generate relevance explanation as a dict with consistent keys"""
        factors = []
        if self.semantic_score > 0.7:
            factors.append(f"highly similar reasoning ({self.semantic_score:.0%})")
        if self.fulltext_score > 0.3:
            factors.append("matching keywords")
        if self.entity_overlap_score > 0.5:
            factors.append(f"related entities ({self.entity_overlap_score:.0%})")
        if self.recency_score > 0.8:
            factors.append("recent")
        if self.outcome_status == 'positive':
            factors.append("positive outcome")
        elif self.outcome_status == 'negative':
            factors.append("negative outcome")
        
        return {
            "summary": "Relevant: " + ", ".join(factors) if factors else "General similarity",
            "factors": factors,
            "semantic_score": self.semantic_score,
            "fulltext_score": self.fulltext_score,
            "entity_overlap_score": self.entity_overlap_score,
            "recency_score": self.recency_score,
            "outcome_score": self.outcome_score,
            "category_bonus": self.category_bonus,
            "rrf_score": self.rrf_score
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "decision_id": self.decision_id,
            "decision_human_id": self.decision_human_id,
            "summary": self.summary,
            "decision_type": self.decision_type,
            "rationale_summary": self.rationale_summary,
            "choice": self.choice,
            "decision_timestamp": self.decision_timestamp.isoformat() if self.decision_timestamp else None,
            "decision_maker_id": self.decision_maker_id,
            "outcome_status": self.outcome_status,
            "semantic_rank": self.semantic_rank,
            "fulltext_rank": self.fulltext_rank,
            "entity_rank": self.entity_rank,
            "semantic_score": self.semantic_score,
            "fulltext_score": self.fulltext_score,
            "entity_overlap_score": self.entity_overlap_score,
            "recency_score": self.recency_score,
            "outcome_score": self.outcome_score,
            "category_bonus": self.category_bonus,
            "rrf_score": self.rrf_score,
            "relevance_explanation": self.relevance_explanation
        }


def _compute_embedding_fallback(text_input: str) -> Optional[List[float]]:
    """
    Compute embedding as fallback when caller doesn't supply one.
    
    SLOW PATH - This is marked in logs. Callers should pre-compute embeddings.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.warning("[DTL Core] OPENAI_API_KEY not set, cannot compute embedding")
        return None
    
    normalized = text_input.lower().strip()[:500]
    cache_key = hashlib.md5(normalized.encode()).hexdigest()
    
    if cache_key in EMBEDDING_CACHE:
        embedding, timestamp = EMBEDDING_CACHE[cache_key]
        if time.time() - timestamp < EMBEDDING_CACHE_TTL:
            logger.debug("[DTL Core] Embedding cache hit (fallback path)")
            return embedding
        del EMBEDDING_CACHE[cache_key]
    
    try:
        logger.warning("[DTL Core] SLOW PATH: Computing embedding in core (caller should pre-compute)")
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            },
            json={"model": "text-embedding-3-small", "input": text_input},
            timeout=10.0
        )
        response.raise_for_status()
        embedding = response.json()["data"][0]["embedding"]
        
        if len(EMBEDDING_CACHE) >= EMBEDDING_CACHE_MAX_SIZE:
            oldest_key = min(EMBEDDING_CACHE.keys(), key=lambda k: EMBEDDING_CACHE[k][1])
            del EMBEDDING_CACHE[oldest_key]
        
        EMBEDDING_CACHE[cache_key] = (embedding, time.time())
        return embedding
    except Exception as e:
        logger.error(f"[DTL Core] Embedding fallback failed: {e}")
        return None


def _set_rls_context(session: Session, ctx: AuthContext) -> None:
    """
    Set RLS session variables on the database connection.
    
    MUST be called on the same session/connection used for the query.
    Uses existing set_tenant_context for compatibility with RLS policies.
    """
    from src.context_foundry.models.schema import set_tenant_context
    set_tenant_context(session, ctx.tenant_id, role=ctx.role)
    logger.debug(f"[DTL Core] RLS context set: tenant={ctx.tenant_id}, role={ctx.role}")


def search_precedents(
    ctx: AuthContext,
    session: Session,
    query_text: str,
    query_embedding: Optional[List[float]] = None,
    decision_type_hint: Optional[str] = None,
    required_entity_ids: Optional[List[str]] = None,
    limit: int = 10,
    min_confidence: float = 0.0,
    include_negative_outcomes: bool = True
) -> List[PrecedentResult]:
    """
    Search for relevant precedent decisions.
    
    SINGLE SOURCE OF TRUTH for precedent retrieval logic.
    Both HTTP and inline adapters call this function.
    
    SECURITY:
    - ctx (AuthContext) is the ONLY way to pass identity
    - Sets DB session vars for RLS before query
    
    EMBEDDING POLICY:
    - If query_embedding provided: uses it (fast path)
    - If not provided: computes embedding (slow path, logged as warning)
    
    Args:
        ctx: AuthContext with tenant_id, user_id, role (required)
        session: SQLAlchemy session for database access
        query_text: Natural language query describing the situation
        query_embedding: Pre-computed embedding vector (recommended for performance)
        decision_type_hint: Optional soft hint for category matching (ranking bonus)
        required_entity_ids: Optional list of entity UUIDs for overlap scoring
        limit: Maximum results to return
        min_confidence: Minimum confidence threshold (0.0-1.0)
        include_negative_outcomes: Whether to include decisions with negative outcomes
        
    Returns:
        List of PrecedentResult objects sorted by RRF score (highest first)
    """
    t_start = time.time()
    
    _set_rls_context(session, ctx)
    
    if query_embedding is None:
        query_embedding = _compute_embedding_fallback(query_text)
        if query_embedding is None:
            logger.error("[DTL Core] No embedding available, returning empty results")
            return []
    
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"
    
    sql = text("""
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
    """)
    
    result = session.execute(sql, {
        "query_text": query_text,
        "embedding": embedding_str,
        "tenant_id": ctx.tenant_id,
        "decision_type_hint": decision_type_hint,
        "entity_ids": required_entity_ids,
        "min_confidence": min_confidence,
        "limit": limit,
        "include_negative": include_negative_outcomes
    })
    
    rows = result.fetchall()
    
    precedents = [
        PrecedentResult(
            decision_id=str(row.decision_id),
            decision_human_id=row.decision_human_id,
            summary=row.summary,
            decision_type=row.decision_type,
            rationale_summary=row.rationale_summary,
            choice=row.choice or {},
            decision_timestamp=row.decision_timestamp,
            decision_maker_id=str(row.decision_maker_id),
            outcome_status=str(row.outcome_status) if row.outcome_status else None,
            semantic_rank=row.semantic_rank,
            fulltext_rank=row.fulltext_rank,
            entity_rank=row.entity_rank,
            semantic_score=float(row.semantic_score or 0),
            fulltext_score=float(row.fulltext_score or 0),
            entity_overlap_score=float(row.entity_overlap_score or 0),
            recency_score=float(row.recency_score or 0),
            outcome_score=float(row.outcome_score or 0),
            category_bonus=float(row.category_bonus or 0),
            rrf_score=float(row.rrf_score or 0)
        )
        for row in rows
    ]
    
    t_elapsed = (time.time() - t_start) * 1000
    logger.debug(f"[DTL Core] search_precedents completed: {len(precedents)} results in {t_elapsed:.1f}ms")
    
    return precedents
