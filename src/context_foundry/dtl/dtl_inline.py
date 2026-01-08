"""
DTL Inline Adapter

Thin in-process adapter for precedent search.
NO retrieval logic - only:
1. Accept AuthContext (derived from internal CF request context)
2. Call core
3. Return PrecedentResult list

This adapter bypasses HTTP transport for agents/orchestrator running
in the same process, eliminating ~490ms network overhead.
"""

import time
import logging
from dataclasses import dataclass
from typing import List, Optional

from src.context_foundry.models.schema import get_session
from .core import AuthContext, PrecedentResult, search_precedents

logger = logging.getLogger(__name__)


@dataclass
class InlineSearchResult:
    """Result wrapper with timing metadata for inline searches"""
    precedents: List[PrecedentResult]
    latency_ms: float
    used_precomputed_embedding: bool


def inline_search_precedents(
    ctx: AuthContext,
    query_text: str,
    query_embedding: Optional[List[float]] = None,
    decision_type_hint: Optional[str] = None,
    required_entity_ids: Optional[List[str]] = None,
    limit: int = 10,
    min_confidence: float = 0.0,
    include_negative_outcomes: bool = True
) -> InlineSearchResult:
    """
    In-process precedent search for agents/orchestrator.
    
    THIN ADAPTER - No scoring/ranking logic here.
    Accepts AuthContext -> calls core -> returns PrecedentResult list.
    
    This function is called directly by PrecedentMiddleware and other
    in-process callers, bypassing HTTP transport entirely.
    
    Args:
        ctx: AuthContext with tenant_id, user_id, role (REQUIRED)
        query_text: Natural language query
        query_embedding: Pre-computed embedding (recommended)
        decision_type_hint: Optional category hint
        required_entity_ids: Optional entity UUIDs for overlap scoring
        limit: Maximum results
        min_confidence: Minimum confidence threshold
        include_negative_outcomes: Include negative outcomes
        
    Returns:
        InlineSearchResult with precedents list and timing
    """
    t_start = time.time()
    
    session = None
    try:
        session = get_session(use_rls_role=True)
        
        precedents = search_precedents(
            ctx=ctx,
            session=session,
            query_text=query_text,
            query_embedding=query_embedding,
            decision_type_hint=decision_type_hint,
            required_entity_ids=required_entity_ids,
            limit=limit,
            min_confidence=min_confidence,
            include_negative_outcomes=include_negative_outcomes
        )
        
        latency_ms = (time.time() - t_start) * 1000
        logger.debug(f"[DTL Inline] Search completed: {len(precedents)} results in {latency_ms:.1f}ms")
        
        return InlineSearchResult(
            precedents=precedents,
            latency_ms=latency_ms,
            used_precomputed_embedding=query_embedding is not None
        )
        
    except Exception as e:
        logger.error(f"[DTL Inline] Search failed: {e}")
        latency_ms = (time.time() - t_start) * 1000
        return InlineSearchResult(
            precedents=[],
            latency_ms=latency_ms,
            used_precomputed_embedding=query_embedding is not None
        )
    finally:
        if session:
            session.close()


def derive_auth_context_from_cf_request(
    tenant_id: str,
    user_id: str,
    role: str = 'user'
) -> AuthContext:
    """
    Create AuthContext from internal CF request context.
    
    Use this when you have tenant/user/role from the existing CF
    request context (e.g., from Flask g object, middleware state,
    or agent initialization).
    
    Args:
        tenant_id: Tenant UUID from CF request context
        user_id: User UUID from CF request context  
        role: User role, defaults to 'user'
        
    Returns:
        AuthContext for use with inline_search_precedents
    """
    return AuthContext(
        tenant_id=tenant_id,
        user_id=user_id,
        role=role
    )
