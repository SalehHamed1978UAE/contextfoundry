"""
Precedent Search Client for DTL

Provides semantic + full-text + entity overlap search for finding
relevant precedent decisions using the search_precedents_api function.
"""
import os
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional, Any
import requests
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


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
    def relevance_explanation(self) -> str:
        """Generate human-readable relevance explanation"""
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
        return "Relevant: " + ", ".join(factors) if factors else "General similarity"


class PrecedentSearchClient:
    """
    Client for searching precedents using SQLAlchemy sessions.
    Uses CF's existing OpenAI embedding infrastructure.
    """
    
    def __init__(
        self,
        session: Session,
        tenant_id: str,
        openai_api_key: Optional[str] = None
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.openai_key = openai_api_key or os.environ.get("OPENAI_API_KEY")
    
    def get_embedding(self, text_input: str) -> List[float]:
        """Get embedding from OpenAI text-embedding-3-small"""
        response = requests.post(
            "https://api.openai.com/v1/embeddings",
            headers={
                "Authorization": f"Bearer {self.openai_key}",
                "Content-Type": "application/json"
            },
            json={"model": "text-embedding-3-small", "input": text_input},
            timeout=30.0
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
    
    def search(
        self,
        query: str,
        decision_type_hint: Optional[str] = None,
        entity_ids: Optional[List[str]] = None,
        min_confidence: float = 0.0,
        limit: int = 10,
        include_negative_outcomes: bool = True
    ) -> List[PrecedentResult]:
        """
        Search for relevant precedents.
        
        Args:
            query: Natural language query describing the situation
            decision_type_hint: Optional soft hint for category matching (ranking bonus only)
            entity_ids: Optional list of entity UUIDs for overlap scoring
            min_confidence: Minimum confidence threshold (0.0-1.0)
            limit: Maximum results to return
            include_negative_outcomes: Whether to include decisions with negative outcomes
            
        Returns:
            List of PrecedentResult objects sorted by RRF score
        """
        embedding = self.get_embedding(query)
        
        entity_array = None
        if entity_ids:
            entity_array = entity_ids
        
        sql = text("""
            SELECT * FROM search_precedents_api(
                :query_text,
                :embedding::vector,
                :tenant_id,
                :decision_type_hint,
                :entity_ids,
                :min_confidence,
                :limit,
                :include_negative
            )
        """)
        
        result = self.session.execute(sql, {
            "query_text": query,
            "embedding": str(embedding),
            "tenant_id": self.tenant_id,
            "decision_type_hint": decision_type_hint,
            "entity_ids": entity_array,
            "min_confidence": min_confidence,
            "limit": limit,
            "include_negative": include_negative_outcomes
        })
        
        rows = result.fetchall()
        
        return [
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


def search_precedents(
    session: Session,
    query: str,
    tenant_id: str,
    decision_type_hint: Optional[str] = None,
    entity_ids: Optional[List[str]] = None,
    min_confidence: float = 0.0,
    limit: int = 10,
    include_negative_outcomes: bool = True
) -> List[PrecedentResult]:
    """
    Convenience function for one-off precedent searches.
    
    Args:
        session: SQLAlchemy session
        query: Natural language query
        tenant_id: Tenant UUID
        decision_type_hint: Optional category hint (ranking bonus)
        entity_ids: Optional entity UUIDs for overlap
        min_confidence: Minimum confidence threshold
        limit: Max results
        include_negative_outcomes: Include negative outcome decisions
        
    Returns:
        List of PrecedentResult
    """
    client = PrecedentSearchClient(session=session, tenant_id=tenant_id)
    return client.search(
        query=query,
        decision_type_hint=decision_type_hint,
        entity_ids=entity_ids,
        min_confidence=min_confidence,
        limit=limit,
        include_negative_outcomes=include_negative_outcomes
    )
