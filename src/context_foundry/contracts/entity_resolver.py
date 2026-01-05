"""
EntityResolver Contract - Defines the interface for entity resolution.

The EntityResolver implements a 3-stage pipeline:
1. Exact match (case-insensitive, fast path)
2. Semantic search (embedding similarity > 0.75)
3. Fuzzy match (Levenshtein ratio > 0.70)

With disambiguation when multiple candidates score within 0.1 of each other.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class MatchStage(str, Enum):
    """The stage at which a match was found."""
    EXACT = "exact"
    SEMANTIC = "semantic"
    FUZZY = "fuzzy"
    NOT_FOUND = "not_found"
    EMPTY_QUERY = "empty_query"


@dataclass
class EntityCandidate:
    """
    A candidate entity match with scoring details.
    
    Invariants:
    1. score is in range [0, 1]
    2. confidence is in range [0, 1]
    3. entity_id is a valid UUID string
    4. match_stage indicates which resolution stage found this candidate
    """
    entity_id: str
    name: str
    entity_type: str
    description: Optional[str]
    score: float
    match_stage: str
    confidence: float = 0.0
    
    def __post_init__(self):
        if not 0.0 <= self.score <= 1.0:
            raise ValueError(f"score must be in [0, 1], got {self.score}")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "score": round(self.score, 4),
            "match_stage": self.match_stage,
            "confidence": round(self.confidence, 4)
        }


@dataclass
class ResolveResult:
    """
    Result of entity resolution.
    
    Invariants:
    1. If entity is not None, confidence > 0
    2. If needs_disambiguation is True, len(candidates) >= 2
    3. match_stage is never empty
    """
    entity: Optional[EntityCandidate] = None
    confidence: float = 0.0
    needs_disambiguation: bool = False
    candidates: List[EntityCandidate] = field(default_factory=list)
    match_stage: str = "none"
    
    def __post_init__(self):
        if self.entity and self.confidence <= 0:
            raise ValueError("If entity is matched, confidence must be > 0")
        if self.needs_disambiguation and len(self.candidates) < 2:
            raise ValueError("Disambiguation requires at least 2 candidates")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity.to_dict() if self.entity else None,
            "confidence": round(self.confidence, 4),
            "needs_disambiguation": self.needs_disambiguation,
            "candidates": [c.to_dict() for c in self.candidates],
            "match_stage": self.match_stage
        }
    
    @property
    def is_found(self) -> bool:
        """Returns True if an entity was resolved."""
        return self.entity is not None
    
    @property
    def is_high_confidence(self) -> bool:
        """Returns True if match confidence is above 0.8."""
        return self.confidence >= 0.8


class EntityResolverContract(ABC):
    """
    Abstract contract for entity resolution.
    
    Implementations must provide a 3-stage resolution pipeline:
    1. Exact match (fast path, case-insensitive)
    2. Semantic search (embedding similarity)
    3. Fuzzy match (string similarity)
    
    With configurable thresholds and disambiguation support.
    """
    
    EXACT_MATCH_THRESHOLD: float = 0.95
    SEMANTIC_THRESHOLD: float = 0.75
    FUZZY_THRESHOLD: float = 0.70
    DISAMBIGUATION_DELTA: float = 0.1
    
    @abstractmethod
    def resolve(
        self,
        query: str,
        entity_type_hint: Optional[str] = None,
        top_k: int = 20
    ) -> ResolveResult:
        """
        Resolve a query string to the best matching entity.
        
        Args:
            query: The search query (entity name or description)
            entity_type_hint: Optional type filter (e.g., 'SERVICE', 'PERSON')
            top_k: Maximum candidates to consider in semantic search
            
        Returns:
            ResolveResult with matched entity or disambiguation candidates
            
        Contract:
            - Must return ResolveResult (never None)
            - Empty query returns match_stage="empty_query"
            - Must try stages in order: exact -> semantic -> fuzzy
            - Must populate needs_disambiguation when candidates are close
        """
        pass
    
    @abstractmethod
    def _exact_match(
        self,
        query: str,
        entity_type_hint: Optional[str] = None
    ) -> ResolveResult:
        """
        Stage 1: Case-insensitive exact match.
        
        This is the fast path that handles ~60% of queries.
        
        Args:
            query: Entity name to match exactly
            entity_type_hint: Optional type filter
            
        Returns:
            ResolveResult with match_stage="exact"
        """
        pass
    
    @abstractmethod
    def _semantic_search(
        self,
        query: str,
        entity_type_hint: Optional[str] = None,
        top_k: int = 20
    ) -> ResolveResult:
        """
        Stage 2: Semantic search using embeddings.
        
        Uses OpenAI embeddings with cosine similarity.
        
        Args:
            query: Query text to embed and search
            entity_type_hint: Optional type filter
            top_k: Maximum candidates to retrieve
            
        Returns:
            ResolveResult with match_stage="semantic"
        """
        pass
    
    @abstractmethod
    def _fuzzy_match(
        self,
        query: str,
        entity_type_hint: Optional[str] = None
    ) -> ResolveResult:
        """
        Stage 3: Fuzzy string matching.
        
        Uses Levenshtein ratio for typo tolerance.
        
        Args:
            query: Query text to fuzzy match
            entity_type_hint: Optional type filter
            
        Returns:
            ResolveResult with match_stage="fuzzy"
        """
        pass
    
    def _check_disambiguation(
        self,
        candidates: List[EntityCandidate],
        delta: float = None
    ) -> bool:
        """
        Check if top candidates need disambiguation.
        
        Returns True if top 2+ candidates are within delta of each other.
        """
        if delta is None:
            delta = self.DISAMBIGUATION_DELTA
        
        if len(candidates) < 2:
            return False
        
        sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)
        top_score = sorted_candidates[0].score
        
        close_candidates = [c for c in sorted_candidates[1:] 
                          if top_score - c.score <= delta]
        
        return len(close_candidates) >= 1
