"""
Role Resolver

Resolves job titles/roles to actual people via knowledge graph.
CEO → Sarah Chen
CTO → Marcus Williams
"""

from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.context_foundry.utils.logger import logger


class RoleResolution:
    """Result of role resolution."""
    
    def __init__(
        self,
        role: str,
        resolved_name: Optional[str] = None,
        resolved_entity_id: Optional[str] = None,
        confidence: float = 0.0,
        alternatives: Optional[List[Dict[str, Any]]] = None
    ):
        self.role = role
        self.resolved_name = resolved_name
        self.resolved_entity_id = resolved_entity_id
        self.confidence = confidence
        self.alternatives = alternatives or []
    
    @property
    def is_resolved(self) -> bool:
        return self.resolved_name is not None
    
    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "resolved_name": self.resolved_name,
            "resolved_entity_id": self.resolved_entity_id,
            "confidence": self.confidence,
            "is_resolved": self.is_resolved,
            "alternatives": self.alternatives
        }


class RoleResolver:
    """Resolves role references to actual person entities."""
    
    ROLE_EXPANSIONS = {
        'ceo': ['chief executive officer', 'ceo'],
        'cto': ['chief technology officer', 'cto'],
        'cfo': ['chief financial officer', 'cfo'],
        'coo': ['chief operating officer', 'coo'],
        'cdo': ['chief data officer', 'cdo'],
        'cmo': ['chief marketing officer', 'cmo'],
        'cio': ['chief information officer', 'cio'],
        'ciso': ['chief information security officer', 'ciso'],
        'vp': ['vice president', 'vp'],
        'svp': ['senior vice president', 'svp'],
        'evp': ['executive vice president', 'evp'],
        'president': ['president'],
        'general counsel': ['general counsel'],
        'controller': ['controller'],
        'treasurer': ['treasurer'],
        'director': ['director'],
    }
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def _normalize_role(self, role: str) -> List[str]:
        """Get all variations of a role for matching."""
        role_lower = role.lower().strip()
        
        for abbrev, expansions in self.ROLE_EXPANSIONS.items():
            if role_lower == abbrev or role_lower in expansions:
                return expansions
        
        return [role_lower]
    
    def resolve(self, role: str, organization: Optional[str] = None) -> RoleResolution:
        """
        Resolve a role to the person who holds it.
        
        Args:
            role: The role to resolve (e.g., "CEO", "Chief Technology Officer")
            organization: Optional organization context
            
        Returns:
            RoleResolution with resolved person info
        """
        role_variations = self._normalize_role(role)
        
        like_clauses = " OR ".join([f"LOWER(target.name) LIKE :role{i}" for i in range(len(role_variations))])
        
        query = text(f"""
            SELECT 
                source.id as person_id,
                source.name as person_name,
                target.name as role_name,
                r.confidence as relationship_confidence
            FROM relationships r
            JOIN entities source ON r.source_id = source.id
            JOIN entities target ON r.target_id = target.id
            WHERE r.tenant_id = :tenant_id
            AND r.relationship_type = 'HELD_POSITION'
            AND ({like_clauses})
            ORDER BY r.confidence DESC, r.created_at DESC
            LIMIT 5
        """)
        
        params = {"tenant_id": self.tenant_id}
        for i, variation in enumerate(role_variations):
            params[f"role{i}"] = f"%{variation}%"
        
        try:
            results = self.session.execute(query, params).fetchall()
            
            if not results:
                logger.info(f"[ROLE_RESOLVER] No resolution found for role: {role}")
                return RoleResolution(role=role)
            
            best_match = results[0]
            alternatives = [
                {
                    "name": r.person_name,
                    "role": r.role_name,
                    "confidence": r.relationship_confidence
                }
                for r in results[1:]
            ]
            
            resolution = RoleResolution(
                role=role,
                resolved_name=best_match.person_name,
                resolved_entity_id=str(best_match.person_id),
                confidence=best_match.relationship_confidence or 0.9,
                alternatives=alternatives
            )
            
            logger.info(f"[ROLE_RESOLVER] Resolved '{role}' → '{resolution.resolved_name}' (conf: {resolution.confidence})")
            
            return resolution
            
        except Exception as e:
            logger.error(f"[ROLE_RESOLVER] Resolution failed for '{role}': {e}")
            return RoleResolution(role=role)
    
    def expand_query(self, query: str, resolution: RoleResolution) -> str:
        """
        Expand a query by adding the resolved person's name.
        
        "CEO's salary" + Sarah Chen → "CEO (Sarah Chen) salary"
        """
        if not resolution.is_resolved:
            return query
        
        role_lower = resolution.role.lower()
        query_lower = query.lower()
        
        if role_lower in query_lower:
            idx = query_lower.find(role_lower)
            end_idx = idx + len(role_lower)
            
            before = query[:end_idx]
            after = query[end_idx:]
            
            expanded = f"{before} ({resolution.resolved_name}){after}"
            
            logger.info(f"[ROLE_RESOLVER] Expanded query: '{query}' → '{expanded}'")
            return expanded
        
        return f"{query} (Note: {resolution.role} = {resolution.resolved_name})"
