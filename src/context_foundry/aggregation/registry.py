"""
AggDefinitionRegistry - CRUD for semantic contract definitions.

Per v1.3 spec §4.1, this manages the agg_definitions table that maps
natural language concepts to executable aggregation candidates.
"""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from .models import IntentKind

logger = logging.getLogger(__name__)


class AggDefinitionRegistry:
    """
    Registry for aggregation definitions (semantic contracts).
    
    Provides CRUD operations for the agg_definitions table and
    caches tenant definitions for performance.
    """
    
    def __init__(self, session: Session, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
        self._cache: Dict[str, List[Dict[str, Any]]] = {}
    
    def get_candidates(
        self,
        concept_key: str,
        intent_kind: Optional[IntentKind] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get candidate definitions for a concept.
        
        Args:
            concept_key: The concept name (e.g., "job", "incident")
            intent_kind: Optional filter for specific intent kind
            
        Returns:
            List of candidate definitions (ordered by priority)
        """
        # Check cache
        cache_key = f"{concept_key}:{intent_kind.value if intent_kind else 'all'}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Query database
        query = text("""
            SELECT concept_key, synonyms, candidates, status
            FROM agg_definitions
            WHERE tenant_id = :tenant_id
              AND status = 'active'
              AND (concept_key = :concept_key 
                   OR :concept_key = ANY(synonyms))
            ORDER BY version DESC
            LIMIT 1
        """)
        
        result = self.session.execute(
            query,
            {"tenant_id": str(self.tenant_id), "concept_key": concept_key.lower()},
        ).fetchone()
        
        if result is None:
            # Try fuzzy match on synonyms
            return self._fuzzy_match(concept_key, intent_kind)
        
        candidates = result.candidates
        if isinstance(candidates, str):
            candidates = json.loads(candidates)
        
        # Filter by intent kind if specified
        if intent_kind:
            candidates = [
                c for c in candidates
                if intent_kind.value in c.get("intent_kinds", [])
            ]
        
        # Cache and return
        self._cache[cache_key] = candidates
        return candidates
    
    def _fuzzy_match(
        self,
        concept_key: str,
        intent_kind: Optional[IntentKind],
    ) -> List[Dict[str, Any]]:
        """Fuzzy match on synonyms using trigram similarity."""
        # This would use pg_trgm in production
        # For now, return empty list
        logger.debug(f"No exact match for '{concept_key}'; fuzzy match not implemented")
        return []
    
    def register_definition(
        self,
        concept_key: str,
        candidates: List[Dict[str, Any]],
        synonyms: Optional[List[str]] = None,
    ) -> bool:
        """
        Register a new aggregation definition.
        
        Args:
            concept_key: The canonical concept name
            candidates: List of candidate definitions
            synonyms: Alternative names for this concept
            
        Returns:
            True if successful
        """
        query = text("""
            INSERT INTO agg_definitions (tenant_id, concept_key, synonyms, candidates)
            VALUES (:tenant_id, :concept_key, :synonyms, :candidates)
            ON CONFLICT (tenant_id, concept_key, version) 
            DO UPDATE SET 
                candidates = :candidates,
                synonyms = :synonyms,
                updated_at = now()
        """)
        
        self.session.execute(query, {
            "tenant_id": str(self.tenant_id),
            "concept_key": concept_key.lower(),
            "synonyms": synonyms or [],
            "candidates": json.dumps(candidates),
        })
        
        # Invalidate cache
        self._cache = {}
        
        return True
    
    def clear_cache(self) -> None:
        """Clear the definition cache."""
        self._cache = {}
