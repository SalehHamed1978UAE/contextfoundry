"""
Role Resolver - Enhanced 3-Stage Resolution

Resolves job titles/roles to actual people via:
1. Stage 1: Exact relationship lookup (HOLDS_POSITION)
2. Stage 2: Fuzzy ILIKE matching on role names
3. Stage 3: Document search fallback for patterns like "Sarah Chen, CEO"

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
        alternatives: Optional[List[Dict[str, Any]]] = None,
        resolution_method: str = "none"
    ):
        self.role = role
        self.resolved_name = resolved_name
        self.resolved_entity_id = resolved_entity_id
        self.confidence = confidence
        self.alternatives = alternatives or []
        self.resolution_method = resolution_method
    
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
            "alternatives": self.alternatives,
            "resolution_method": self.resolution_method
        }


class RoleResolver:
    """
    Enhanced 3-stage role resolution.
    
    Handles role variations and multiple relationship type names.
    """
    
    POSITION_RELATIONSHIP_TYPES = [
        'HOLDS_POSITION',
        'HELD_POSITION', 
        'HOLD_POSITION',
        'HAS_ROLE',
        'HAS_TITLE'
    ]
    
    ROLE_NORMALIZATIONS = {
        'chief executive officer': 'CEO',
        'chief technology officer': 'CTO',
        'chief financial officer': 'CFO',
        'chief operating officer': 'COO',
        'chief data officer': 'CDO',
        'chief marketing officer': 'CMO',
        'chief information officer': 'CIO',
        'chief information security officer': 'CISO',
        'chief product officer': 'CPO',
        'chief revenue officer': 'CRO',
        'vice president': 'VP',
        'senior vice president': 'SVP',
        'executive vice president': 'EVP',
        'ceo': 'CEO',
        'cto': 'CTO',
        'cfo': 'CFO',
        'coo': 'COO',
        'cdo': 'CDO',
        'cmo': 'CMO',
        'cio': 'CIO',
        'ciso': 'CISO',
        'cpo': 'CPO',
        'cro': 'CRO',
        'vp': 'VP',
        'svp': 'SVP',
        'evp': 'EVP',
    }
    
    ROLE_EXPANSIONS = {
        'ceo': ['chief executive officer', 'ceo', 'chief exec'],
        'cto': ['chief technology officer', 'cto', 'chief tech'],
        'cfo': ['chief financial officer', 'cfo', 'chief finance'],
        'coo': ['chief operating officer', 'coo', 'chief ops'],
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
    
    def _normalize_role(self, role: str) -> str:
        """Normalize role to standard form (CEO, CTO, etc.)."""
        role_lower = role.lower().strip()
        return self.ROLE_NORMALIZATIONS.get(role_lower, role.upper())
    
    def _get_role_variations(self, role: str) -> List[str]:
        """Get all variations of a role for matching."""
        role_lower = role.lower().strip()
        normalized = self._normalize_role(role)
        
        variations = [role_lower, normalized.lower()]
        
        for abbrev, expansions in self.ROLE_EXPANSIONS.items():
            if role_lower == abbrev or role_lower in expansions:
                variations.extend(expansions)
                variations.append(abbrev)
                break
        
        return list(set(variations))
    
    def resolve(self, role: str, organization: Optional[str] = None) -> RoleResolution:
        """
        Resolve a role to the person who holds it using 3-stage lookup.
        
        Args:
            role: The role to resolve (e.g., "CEO", "Chief Technology Officer")
            organization: Optional organization context
            
        Returns:
            RoleResolution with resolved person info
        """
        logger.info(f"[ROLE_RESOLVER] Resolving role: '{role}'")
        
        result = self._stage1_exact_relationship(role)
        if result.is_resolved:
            logger.info(f"[ROLE_RESOLVER] Stage 1 (exact): '{role}' → '{result.resolved_name}'")
            return result
        
        result = self._stage2_fuzzy_relationship(role)
        if result.is_resolved:
            logger.info(f"[ROLE_RESOLVER] Stage 2 (fuzzy): '{role}' → '{result.resolved_name}'")
            return result
        
        result = self._stage3_document_search(role)
        if result.is_resolved:
            logger.info(f"[ROLE_RESOLVER] Stage 3 (docs): '{role}' → '{result.resolved_name}'")
            return result
        
        logger.info(f"[ROLE_RESOLVER] No resolution found for role: '{role}'")
        return RoleResolution(role=role)
    
    def _stage1_exact_relationship(self, role: str) -> RoleResolution:
        """Stage 1: Exact relationship lookup with multiple type names."""
        role_variations = self._get_role_variations(role)
        
        type_placeholders = ", ".join([f":type{i}" for i in range(len(self.POSITION_RELATIONSHIP_TYPES))])
        like_clauses = " OR ".join([f"LOWER(target.name) LIKE :role{i}" for i in range(len(role_variations))])
        
        query = text(f"""
            SELECT 
                source.id as person_id,
                source.name as person_name,
                target.name as role_name,
                r.relationship_type,
                r.confidence as relationship_confidence
            FROM relationships r
            JOIN entities source ON r.source_id = source.id
            JOIN entities target ON r.target_id = target.id
            WHERE r.tenant_id = :tenant_id
            AND r.relationship_type IN ({type_placeholders})
            AND ({like_clauses})
            ORDER BY r.confidence DESC, r.created_at DESC
            LIMIT 5
        """)
        
        params = {"tenant_id": self.tenant_id}
        for i, rel_type in enumerate(self.POSITION_RELATIONSHIP_TYPES):
            params[f"type{i}"] = rel_type
        for i, variation in enumerate(role_variations):
            params[f"role{i}"] = f"%{variation}%"
        
        try:
            results = self.session.execute(query, params).fetchall()
            
            if results:
                best = results[0]
                return RoleResolution(
                    role=role,
                    resolved_name=best.person_name,
                    resolved_entity_id=str(best.person_id),
                    confidence=best.relationship_confidence or 0.9,
                    resolution_method="stage1_exact_relationship",
                    alternatives=[
                        {"name": r.person_name, "role": r.role_name, "confidence": r.relationship_confidence}
                        for r in results[1:]
                    ]
                )
        except Exception as e:
            logger.error(f"[ROLE_RESOLVER] Stage 1 failed: {e}")
        
        return RoleResolution(role=role)
    
    def _stage2_fuzzy_relationship(self, role: str) -> RoleResolution:
        """Stage 2: Fuzzy ILIKE matching on entity properties."""
        normalized = self._normalize_role(role)
        
        query = text("""
            SELECT 
                e.id as person_id,
                e.name as person_name,
                e.properties
            FROM entities e
            WHERE e.tenant_id = :tenant_id
            AND e.entity_type = 'PERSON'
            AND (
                e.properties::text ILIKE :role_pattern1
                OR e.properties::text ILIKE :role_pattern2
            )
            LIMIT 5
        """)
        
        try:
            results = self.session.execute(query, {
                "tenant_id": self.tenant_id,
                "role_pattern1": f"%{normalized}%",
                "role_pattern2": f"%{role}%"
            }).fetchall()
            
            if results:
                best = results[0]
                return RoleResolution(
                    role=role,
                    resolved_name=best.person_name,
                    resolved_entity_id=str(best.person_id),
                    confidence=0.8,
                    resolution_method="stage2_fuzzy_properties"
                )
        except Exception as e:
            logger.debug(f"[ROLE_RESOLVER] Stage 2 properties search failed: {e}")
        
        return RoleResolution(role=role)
    
    def _stage3_document_search(self, role: str) -> RoleResolution:
        """Stage 3: Search document chunks for role patterns."""
        normalized = self._normalize_role(role)
        role_variations = self._get_role_variations(role)
        
        patterns = []
        for var in role_variations[:3]:
            patterns.append(f"%{var}%")
        
        or_clauses = " OR ".join([f"LOWER(dc.text) LIKE :pattern{i}" for i in range(len(patterns))])
        
        query = text(f"""
            SELECT dc.text
            FROM document_chunks dc
            WHERE dc.tenant_id = :tenant_id
            AND ({or_clauses})
            LIMIT 10
        """)
        
        params = {"tenant_id": self.tenant_id}
        for i, pattern in enumerate(patterns):
            params[f"pattern{i}"] = pattern.lower()
        
        try:
            results = self.session.execute(query, params).fetchall()
            
            if results:
                for row in results:
                    text_content = row.text
                    person_name = self._extract_person_from_role_pattern(text_content, role, normalized)
                    if person_name:
                        return RoleResolution(
                            role=role,
                            resolved_name=person_name,
                            confidence=0.75,
                            resolution_method="stage3_document_search"
                        )
        except Exception as e:
            logger.debug(f"[ROLE_RESOLVER] Stage 3 document search failed: {e}")
        
        return RoleResolution(role=role)
    
    def _extract_person_from_role_pattern(self, text: str, role: str, normalized: str) -> Optional[str]:
        """Extract person name from text patterns like 'Sarah Chen, CEO' or 'CEO Sarah Chen'."""
        import re
        
        text_lower = text.lower()
        role_lower = role.lower()
        normalized_lower = normalized.lower()
        
        patterns = [
            rf"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+),?\s*(?:{re.escape(role_lower)}|{re.escape(normalized_lower)})",
            rf"(?:{re.escape(role_lower)}|{re.escape(normalized_lower)})\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            rf"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:is|serves as|as)\s+(?:the\s+)?(?:{re.escape(role_lower)}|{re.escape(normalized_lower)})",
            rf"([A-Z][a-z]+(?:\s+[A-Z]\.?\s+)?[A-Z][a-z]+)\s*[-–]\s*(?:{re.escape(role_lower)}|{re.escape(normalized_lower)})",
            rf"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–]\s*Chief\s+\w+\s+Officer",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                name = re.sub(r'\s+', ' ', name)
                if len(name) > 3 and len(name) < 50:
                    return name
        
        return None
    
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
