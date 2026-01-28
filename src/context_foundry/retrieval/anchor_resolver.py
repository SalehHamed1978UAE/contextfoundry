"""
Anchor Resolver - Vault Primary Organization Detection and Query Anchoring

This module provides:
1. Auto-detection of a vault's primary organization via graph centrality
2. Query-time anchor identification (explicit from query OR vault default)
3. Relationship-first role resolution (traverse from anchor, then filter by role)

The key insight: treat the KG as a graph, not a flat property store.
Every answer must be reachable via relationship traversal from the anchor entity.
"""

import re
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.context_foundry.utils.logger import logger


class AnchorResolver:
    """
    Resolves and manages vault anchor organizations.
    
    The anchor is the primary organization entity that queries are scoped to.
    For "Who is the CFO?" in a Nexus vault, the anchor is Nexus Industries.
    """
    
    ORGANIZATION_ENTITY_TYPES = ['ORGANIZATION', 'COMPANY', 'BUSINESS_UNIT', 'CORPORATION']
    
    ROLE_RELATIONSHIP_TYPES = [
        'LEADS',
        'HAS_EXECUTIVE', 
        'HAS_OFFICER',
        'EMPLOYS',
        'HAS_EMPLOYEE',
        'HAS_ROLE',
        'WORKS_FOR',
        'WORKS_AT',
        'EMPLOYED_BY',
        'MEMBER_OF'
    ]
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def determine_primary_organization(self) -> Optional[Dict[str, Any]]:
        """
        Auto-detect the vault's primary organization via graph centrality.
        
        Returns the ORGANIZATION entity with the most relationship connections,
        making it the natural anchor for role queries.
        
        Returns:
            Dict with 'id' and 'name' of primary org, or None if not found
        """
        logger.info(f"[ANCHOR] Determining primary organization for tenant {self.tenant_id}")
        
        type_placeholders = ", ".join([f":type{i}" for i in range(len(self.ORGANIZATION_ENTITY_TYPES))])
        
        query = text(f"""
            SELECT 
                e.id,
                e.name,
                COUNT(DISTINCT r.id) as connection_count,
                COUNT(DISTINCT CASE WHEN r.source_id = e.id THEN r.id END) as outgoing,
                COUNT(DISTINCT CASE WHEN r.target_id = e.id THEN r.id END) as incoming
            FROM entities e
            LEFT JOIN relationships r ON (e.id = r.source_id OR e.id = r.target_id)
                AND r.tenant_id = :tenant_id
            WHERE e.tenant_id = :tenant_id
            AND e.entity_type IN ({type_placeholders})
            GROUP BY e.id, e.name
            ORDER BY connection_count DESC, incoming DESC
            LIMIT 5
        """)
        
        params = {"tenant_id": self.tenant_id}
        for i, etype in enumerate(self.ORGANIZATION_ENTITY_TYPES):
            params[f"type{i}"] = etype
        
        try:
            results = self.session.execute(query, params).fetchall()
            
            if results:
                top = results[0]
                logger.info(f"[ANCHOR] Primary org detected: {top.name} (id={top.id}, connections={top.connection_count})")
                
                for r in results:
                    logger.debug(f"[ANCHOR]   Candidate: {r.name} - {r.connection_count} connections (in={r.incoming}, out={r.outgoing})")
                
                return {
                    "id": str(top.id),
                    "name": top.name,
                    "connection_count": top.connection_count
                }
            
            logger.warning(f"[ANCHOR] No organization entities found for tenant {self.tenant_id}")
            return None
            
        except Exception as e:
            logger.error(f"[ANCHOR] determine_primary_organization failed: {e}")
            return None
    
    def set_primary_organization(self, org_id: str, org_name: str) -> bool:
        """
        Store the primary organization in the tenant record.
        
        Args:
            org_id: Entity ID of the primary organization
            org_name: Name of the organization
            
        Returns:
            True if successfully updated
        """
        try:
            self.session.execute(text("""
                UPDATE platform.tenants
                SET primary_organization_id = :org_id,
                    primary_organization_name = :org_name
                WHERE id = :tenant_id
            """), {
                "org_id": org_id,
                "org_name": org_name,
                "tenant_id": self.tenant_id
            })
            self.session.commit()
            logger.info(f"[ANCHOR] Set primary org for tenant {self.tenant_id}: {org_name} ({org_id})")
            return True
        except Exception as e:
            logger.error(f"[ANCHOR] set_primary_organization failed: {e}")
            self.session.rollback()
            return False
    
    def get_primary_organization(self) -> Optional[Dict[str, Any]]:
        """
        Get the stored primary organization for this tenant.
        
        Priority:
        1. Look up primary_organization_name within this vault's entities
        2. Fall back to stored primary_organization_id (may not exist in this vault)
        
        Returns:
            Dict with 'id' and 'name', or None if not set
        """
        try:
            result = self.session.execute(text("""
                SELECT primary_organization_id, primary_organization_name,
                       COALESCE(settings->>'anchor_organization', primary_organization_name) as anchor_name
                FROM platform.tenants
                WHERE id = :tenant_id
            """), {"tenant_id": self.tenant_id}).fetchone()
            
            if result and result.anchor_name:
                # Look up entity by name within this vault (more reliable than stored ID)
                entity = self._find_entity_by_name(result.anchor_name)
                if entity:
                    logger.info(f"[ANCHOR] Found primary org by name lookup: {entity['name']} ({entity['id']})")
                    return entity
                
                # Fall back to stored ID if entity lookup fails
                if result.primary_organization_id:
                    logger.info(f"[ANCHOR] Using stored primary org ID: {result.primary_organization_id}")
                    return {
                        "id": str(result.primary_organization_id),
                        "name": result.primary_organization_name
                    }
            
            return None
        except Exception as e:
            logger.error(f"[ANCHOR] get_primary_organization failed: {e}")
            return None
    
    def identify_anchor(self, query: str) -> Optional[Dict[str, Any]]:
        """
        Identify the anchor entity for a query.
        
        Priority:
        1. Explicit mention in query ("CFO of Nexus", "Toyota's CEO")  
        2. Vault's primary organization (default)
        
        Args:
            query: The user's question
            
        Returns:
            Dict with anchor entity info, or None if no anchor found
        """
        explicit_org = self._extract_organization_from_query(query)
        if explicit_org:
            entity = self._find_entity_by_name(explicit_org)
            if entity:
                logger.info(f"[ANCHOR] Explicit anchor from query: {entity['name']}")
                return entity
        
        primary = self.get_primary_organization()
        if primary:
            logger.info(f"[ANCHOR] Using vault's primary org as anchor: {primary['name']}")
            return primary
        
        detected = self.determine_primary_organization()
        if detected:
            self.set_primary_organization(detected['id'], detected['name'])
            logger.info(f"[ANCHOR] Auto-detected and cached anchor: {detected['name']}")
            return detected
        
        logger.warning(f"[ANCHOR] No anchor available for query: {query[:50]}...")
        return None
    
    def _extract_organization_from_query(self, query: str) -> Optional[str]:
        """
        Extract explicit organization mention from query.
        
        Patterns matched:
        - "CEO of Nexus Industries"
        - "Nexus's CFO"  
        - "Who leads Toyota?"
        """
        patterns = [
            r"(?:of|at|for)\s+([A-Z][A-Za-z\s]+?)(?:\?|$|,|\s+(?:and|or|who|what|which))",
            r"([A-Z][A-Za-z\s]+?)'s\s+(?:CEO|CFO|CTO|COO|President|Director|VP|Chief)",
            r"(?:leads?|heads?|runs?)\s+([A-Z][A-Za-z\s]+?)(?:\?|$|,)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                org_name = match.group(1).strip()
                if len(org_name) > 2 and org_name.lower() not in ['the', 'this', 'that', 'our']:
                    return org_name
        
        return None
    
    def _find_entity_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find an organization entity by name (fuzzy match)."""
        try:
            result = self.session.execute(text("""
                SELECT id, name, entity_type
                FROM entities
                WHERE tenant_id = :tenant_id
                AND LOWER(name) LIKE :pattern
                AND entity_type IN ('ORGANIZATION', 'COMPANY', 'BUSINESS_UNIT', 'CORPORATION')
                ORDER BY 
                    CASE WHEN LOWER(name) = :exact THEN 0 ELSE 1 END,
                    LENGTH(name)
                LIMIT 1
            """), {
                "tenant_id": self.tenant_id,
                "pattern": f"%{name.lower()}%",
                "exact": name.lower()
            }).fetchone()
            
            if result:
                return {
                    "id": str(result.id),
                    "name": result.name,
                    "entity_type": result.entity_type
                }
            return None
        except Exception as e:
            logger.error(f"[ANCHOR] _find_entity_by_name failed: {e}")
            return None


class RelationshipFirstRetriever:
    """
    Retrieves entities via relationship traversal from an anchor.
    
    The key principle: start from the anchor org and traverse outward
    via relationship edges, then filter by properties. This ensures
    answers are always connected to the query context.
    """
    
    ROLE_EDGE_TYPES = [
        'LEADS',
        'HAS_EXECUTIVE',
        'HAS_OFFICER', 
        'EMPLOYS',
        'HAS_EMPLOYEE',
        'HAS_ROLE',
    ]
    
    REVERSE_EDGE_TYPES = [
        'WORKS_FOR',
        'WORKS_AT',
        'EMPLOYED_BY',
        'LEADS',
        'MEMBER_OF',
        'HOLDS_POSITION',  # Person HOLDS_POSITION at Organization
    ]
    
    ROLE_NORMALIZATIONS = {
        'chief executive officer': 'CEO',
        'chief technology officer': 'CTO',
        'chief financial officer': 'CFO',
        'chief operating officer': 'COO',
        'ceo': 'CEO',
        'cto': 'CTO',
        'cfo': 'CFO',
        'coo': 'COO',
        'vp': 'VP',
        'vice president': 'VP',
        'president': 'President',
        'director': 'Director',
    }
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def resolve_role_from_anchor(
        self, 
        role: str, 
        anchor_id: str,
        anchor_name: str
    ) -> Dict[str, Any]:
        """
        Find entities with a given role by traversing from anchor.
        
        This is the core of relationship-first retrieval:
        1. Get all people connected to anchor via role-related edges
        2. Filter those people by role properties
        3. Return high-confidence results
        
        Args:
            role: The role to find (e.g., "CFO", "Chief Engineer")
            anchor_id: Entity ID of the anchor organization
            anchor_name: Name of the anchor org (for logging)
            
        Returns:
            Dict with 'entities', 'confidence', 'method'
        """
        logger.info(f"[REL_FIRST] Resolving '{role}' from anchor: {anchor_name}")
        
        connected_people = self._get_connected_people(anchor_id)
        logger.info(f"[REL_FIRST] Found {len(connected_people)} people connected to {anchor_name}")
        
        matches = []
        for person in connected_people:
            if self._matches_role(person, role):
                matches.append(person)
                edge_info = f"[edge_rank={person.get('edge_rank', 9)}, {person.get('edge_type', 'unknown')}]"
                logger.info(f"[REL_FIRST] Role match: {person['name']} - {person.get('role_from_props', 'via relationship')} {edge_info}")
        
        if matches:
            # Sort by edge_rank (HOLDS_POSITION=1 > LEADS=2 > WORKS_FOR=3)
            matches.sort(key=lambda x: x.get('edge_rank', 9))
            logger.info(f"[REL_FIRST] Sorted {len(matches)} matches by edge_rank, best: {matches[0]['name']} (rank={matches[0].get('edge_rank', 9)})")
            
            return {
                "entities": matches,
                "confidence": "high",
                "method": "graph_traversal",
                "anchor": anchor_name
            }
        
        logger.info(f"[REL_FIRST] No direct role matches for '{role}' from anchor {anchor_name}")
        return {
            "entities": [],
            "confidence": "none",
            "method": "graph_traversal",
            "anchor": anchor_name
        }
    
    def _get_connected_people(self, anchor_id: str) -> List[Dict[str, Any]]:
        """
        Get all PERSON entities connected to the anchor via role-related edges.
        
        Traverses both directions:
        - Outgoing: anchor -> LEADS -> person
        - Incoming: person -> WORKS_AT -> anchor
        """
        outgoing_types = ", ".join([f"'{t}'" for t in self.ROLE_EDGE_TYPES])
        incoming_types = ", ".join([f"'{t}'" for t in self.REVERSE_EDGE_TYPES])
        
        # Rank edge types by quality: HOLDS_POSITION (1) > LEADS (2) > WORKS_FOR (3) > others (4)
        query = text(f"""
            WITH connected AS (
                -- Outgoing from anchor (e.g., Nexus LEADS person)
                SELECT 
                    target.id as person_id,
                    target.name as person_name,
                    target.properties::jsonb as props,
                    r.relationship_type as edge_type,
                    'outgoing' as direction,
                    CASE 
                        WHEN r.relationship_type = 'HOLDS_POSITION' THEN 1
                        WHEN r.relationship_type = 'LEADS' THEN 2
                        WHEN r.relationship_type IN ('HAS_EXECUTIVE', 'HAS_OFFICER') THEN 2
                        WHEN r.relationship_type = 'WORKS_FOR' THEN 3
                        ELSE 4
                    END as edge_rank
                FROM relationships r
                JOIN entities target ON r.target_id = target.id
                WHERE r.source_id = :anchor_id
                AND r.tenant_id = :tenant_id
                AND target.entity_type = 'PERSON'
                AND r.relationship_type IN ({outgoing_types})
                
                UNION ALL
                
                -- Incoming to anchor (e.g., person WORKS_AT Nexus)
                SELECT 
                    source.id as person_id,
                    source.name as person_name,
                    source.properties::jsonb as props,
                    r.relationship_type as edge_type,
                    'incoming' as direction,
                    CASE 
                        WHEN r.relationship_type = 'HOLDS_POSITION' THEN 1
                        WHEN r.relationship_type = 'LEADS' THEN 2
                        WHEN r.relationship_type IN ('HAS_EXECUTIVE', 'HAS_OFFICER') THEN 2
                        WHEN r.relationship_type = 'WORKS_FOR' THEN 3
                        ELSE 4
                    END as edge_rank
                FROM relationships r
                JOIN entities source ON r.source_id = source.id
                WHERE r.target_id = :anchor_id
                AND r.tenant_id = :tenant_id
                AND source.entity_type = 'PERSON'
                AND r.relationship_type IN ({incoming_types})
            )
            SELECT DISTINCT ON (person_id)
                person_id,
                person_name,
                props,
                edge_type,
                direction,
                edge_rank
            FROM connected
            ORDER BY person_id, edge_rank ASC
        """)
        
        try:
            results = self.session.execute(query, {
                "anchor_id": anchor_id,
                "tenant_id": self.tenant_id
            }).fetchall()
            
            people = []
            for row in results:
                props = row.props or {}
                role_from_props = (
                    props.get('position') or 
                    props.get('role') or 
                    props.get('title') or 
                    props.get('job_title')
                )
                
                people.append({
                    "id": str(row.person_id),
                    "name": row.person_name,
                    "properties": props,
                    "edge_type": row.edge_type,
                    "direction": row.direction,
                    "edge_rank": row.edge_rank,
                    "role_from_props": role_from_props
                })
            
            return people
            
        except Exception as e:
            logger.error(f"[REL_FIRST] _get_connected_people failed: {e}")
            return []
    
    def _matches_role(self, person: Dict[str, Any], target_role: str) -> bool:
        """
        Check if a person matches the target role.
        
        Checks:
        1. Properties: position, role, title, job_title
        2. Normalized role matching (CFO = Chief Financial Officer)
        
        Does NOT match if person has no role information.
        """
        target_lower = target_role.lower().strip()
        target_normalized = self.ROLE_NORMALIZATIONS.get(target_lower, target_lower)
        
        targets = {target_lower, target_normalized.lower()}
        if target_lower in self.ROLE_NORMALIZATIONS:
            full_title = [k for k, v in self.ROLE_NORMALIZATIONS.items() if v.lower() == target_normalized.lower()]
            targets.update(full_title)
        for k, v in self.ROLE_NORMALIZATIONS.items():
            if k == target_lower:
                targets.add(v.lower())
        
        props = person.get('properties', {})
        if not props:
            props = {}
        
        for field in ['position', 'role', 'title', 'job_title']:
            value = props.get(field)
            if value and isinstance(value, str) and value.strip():
                value_lower = value.lower()
                for target in targets:
                    if target in value_lower or value_lower in target:
                        return True
        
        return False


def auto_detect_and_set_anchor(session: Session, tenant_id: str) -> Optional[Dict[str, Any]]:
    """
    Convenience function to auto-detect and store a vault's primary organization.
    
    Call this after extraction completes to ensure every vault has an anchor.
    
    Args:
        session: Database session
        tenant_id: The vault/tenant ID
        
    Returns:
        Dict with anchor info, or None if detection failed
    """
    resolver = AnchorResolver(session, tenant_id)
    
    existing = resolver.get_primary_organization()
    if existing:
        logger.info(f"[ANCHOR] Vault {tenant_id} already has primary org: {existing['name']}")
        return existing
    
    detected = resolver.determine_primary_organization()
    if detected:
        resolver.set_primary_organization(detected['id'], detected['name'])
        return detected
    
    return None
