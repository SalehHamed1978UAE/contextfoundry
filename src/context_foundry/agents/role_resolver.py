"""
Role Resolver - Enhanced 4-Stage Resolution with Relationship-First Retrieval

Resolves job titles/roles to actual people via:
1. Stage 0: RELATIONSHIP-FIRST - Traverse from anchor org via LEADS/WORKS_AT edges (NEW)
2. Stage 1: Exact relationship lookup (HOLDS_POSITION)
3. Stage 2: Fuzzy ILIKE matching on role names
4. Stage 3: Document search fallback for patterns like "Sarah Chen, CEO"

The key improvement: Stage 0 treats the KG as a graph, not a flat property store.
Every answer must be reachable via relationship traversal from the anchor entity.
This prevents returning Alex Bradley (random CFO) instead of Michael Chang (Nexus CFO).

CEO → Sarah Chen
CTO → Marcus Williams
"""

import re
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text

from src.context_foundry.utils.logger import logger
from src.context_foundry.retrieval.anchor_resolver import AnchorResolver, RelationshipFirstRetriever


# Entity names that should be filtered from role resolution results
# These are document metadata fields that were incorrectly extracted as entities
ROLE_RESOLVER_BLACKLIST = {
    'document owner',
    'document author',
    'author',
    'owner',
    'classification',
    'confidential',
}


def _is_blacklisted_name(name: str) -> bool:
    """Check if an entity name should be filtered from role resolution."""
    if not name:
        return True
    name_lower = name.lower().strip()
    if name_lower in ROLE_RESOLVER_BLACKLIST:
        return True
    for blacklisted in ROLE_RESOLVER_BLACKLIST:
        if name_lower.startswith(f"{blacklisted}:") or name_lower.startswith(f"{blacklisted} "):
            return True
    return False


class RoleResolution:
    """Result of role resolution."""
    
    def __init__(
        self,
        role: str,
        resolved_name: Optional[str] = None,
        resolved_entity_id: Optional[str] = None,
        confidence: float = 0.0,
        alternatives: Optional[List[Dict[str, Any]]] = None,
        resolution_method: str = "none",
        all_matches: Optional[List[Dict[str, Any]]] = None
    ):
        self.role = role
        self.resolved_name = resolved_name
        self.resolved_entity_id = resolved_entity_id
        self.confidence = confidence
        self.alternatives = alternatives or []
        self.resolution_method = resolution_method
        self.all_matches = all_matches or []
    
    @property
    def is_resolved(self) -> bool:
        return self.resolved_name is not None
    
    @property
    def has_multiple_matches(self) -> bool:
        """Returns True if multiple people hold this role."""
        return len(self.all_matches) > 1
    
    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "resolved_name": self.resolved_name,
            "resolved_entity_id": self.resolved_entity_id,
            "confidence": self.confidence,
            "is_resolved": self.is_resolved,
            "alternatives": self.alternatives,
            "resolution_method": self.resolution_method,
            "all_matches": self.all_matches,
            "has_multiple_matches": self.has_multiple_matches
        }


class RoleResolver:
    """
    Enhanced 4-stage role resolution with relationship-first retrieval.
    
    Stage 0 (NEW): Traverse from anchor org via relationship edges
    Stage 1: Exact relationship lookup (HOLDS_POSITION)
    Stage 2: Fuzzy ILIKE matching on role names  
    Stage 3: Document search fallback
    
    Handles role variations and multiple relationship type names.
    """
    
    POSITION_RELATIONSHIP_TYPES = [
        'HOLDS_POSITION',
        'HELD_POSITION', 
        'HOLD_POSITION',
        'HAS_POSITION',
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
        'cmo': ['chief marketing officer', 'chief medical officer', 'cmo'],
        'cio': ['chief information officer', 'cio'],
        'ciso': ['chief information security officer', 'ciso'],
        'cno': ['chief nursing officer', 'cno'],
        'vp': ['vice president', 'vp'],
        'svp': ['senior vice president', 'svp'],
        'evp': ['executive vice president', 'evp'],
        'president': ['president'],
        'general counsel': ['general counsel'],
        'controller': ['controller'],
        'treasurer': ['treasurer'],
        'director': ['director'],
    }
    
    HEALTHCARE_ROLE_ALIASES = {
        'cmo': 'chief medical officer',
        'cno': 'chief nursing officer',
    }
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self._anchor_resolver = None
        self._relationship_retriever = None
        self._anchor_organization = None  # Cached anchor org name for filtering
    
    def _get_anchor_organization(self) -> Optional[str]:
        """Get the anchor organization name for filtering results."""
        if self._anchor_organization is None:
            try:
                from sqlalchemy import text
                result = self.session.execute(text("""
                    SELECT COALESCE(primary_organization_name, settings->>'anchor_organization') as anchor
                    FROM platform.tenants
                    WHERE id = :tenant_id
                """), {"tenant_id": self.tenant_id}).fetchone()
                if result and result.anchor:
                    self._anchor_organization = result.anchor
                    logger.info(f"[ROLE_RESOLVER] Anchor organization: {self._anchor_organization}")
            except Exception as e:
                logger.warning(f"[ROLE_RESOLVER] Could not get anchor organization: {e}")
        return self._anchor_organization
    
    def _filter_by_anchor(self, candidates: list, anchor_name: Optional[str] = None) -> list:
        """Filter candidates to prefer those connected to anchor organization."""
        if not anchor_name:
            anchor_name = self._get_anchor_organization()
        if not anchor_name:
            return candidates
        
        anchor_lower = anchor_name.lower()
        filtered = []
        for c in candidates:
            # Handle both 'organization' (singular) and 'organizations' (plural list)
            orgs = c.get('organizations', [])
            if not orgs:
                org = c.get('organization', '') or ''
                orgs = [org] if org else []
            
            # Keep if: no organization specified, OR any org matches anchor
            if not orgs:
                filtered.append(c)
            else:
                for org in orgs:
                    org_lower = (org or '').lower()
                    if anchor_lower in org_lower or org_lower in anchor_lower:
                        filtered.append(c)
                        break
        
        if filtered:
            logger.info(f"[ROLE_RESOLVER] Anchor filter: {len(candidates)} -> {len(filtered)} candidates (anchor={anchor_name})")
            return filtered
        # If no matches after filtering, return original (don't filter everything out)
        logger.warning(f"[ROLE_RESOLVER] Anchor filter found no matches for anchor={anchor_name}, returning all {len(candidates)}")
        return candidates
    
    def _get_anchor_resolver(self) -> AnchorResolver:
        """Lazy initialization of anchor resolver."""
        if self._anchor_resolver is None:
            self._anchor_resolver = AnchorResolver(self.session, self.tenant_id)
        return self._anchor_resolver
    
    def _get_relationship_retriever(self) -> RelationshipFirstRetriever:
        """Lazy initialization of relationship retriever."""
        if self._relationship_retriever is None:
            self._relationship_retriever = RelationshipFirstRetriever(self.session, self.tenant_id)
        return self._relationship_retriever
    
    def resolve_from_anchor(self, role: str, query: Optional[str] = None) -> RoleResolution:
        """
        Stage 0: Relationship-first retrieval from anchor organization.
        
        This is the primary resolution method that treats the KG as a graph.
        It finds people connected to the anchor org via relationship edges,
        then filters by role properties.
        
        Args:
            role: The role to resolve (e.g., "CFO", "Chief Engineer")
            query: Optional query text to extract explicit org mention
            
        Returns:
            RoleResolution with high confidence if found via graph traversal
        """
        logger.info(f"[ROLE_RESOLVER] Stage 0: Relationship-first for role '{role}'")
        
        try:
            anchor_resolver = self._get_anchor_resolver()
            anchor = anchor_resolver.identify_anchor(query or "")
            
            if not anchor:
                logger.info(f"[ROLE_RESOLVER] Stage 0: No anchor found, skipping relationship-first")
                return RoleResolution(role=role)
            
            logger.info(f"[ROLE_RESOLVER] Stage 0: Using anchor '{anchor['name']}' (id={anchor['id']})")
            
            retriever = self._get_relationship_retriever()
            result = retriever.resolve_role_from_anchor(role, anchor['id'], anchor['name'])
            
            if result['entities']:
                entities = result['entities']
                
                if len(entities) == 1:
                    person = entities[0]
                    person_role = person.get('role_from_props', '')
                    role_lower = role.lower().strip()
                    
                    HIGH_CONFIDENCE_ROLES = {'ceo', 'cfo', 'cto', 'coo', 'cmo', 'ciso', 'chro', 
                                             'president', 'chairman', 'vice president'}
                    is_high_confidence = role_lower in HIGH_CONFIDENCE_ROLES
                    
                    is_exact_match = person_role and person_role.lower().strip() == role_lower
                    
                    if is_high_confidence or is_exact_match:
                        logger.info(f"[ROLE_RESOLVER] Stage 0 SUCCESS: '{role}' → '{person['name']}' via graph_traversal (exact={is_exact_match}, high_conf={is_high_confidence})")
                        return RoleResolution(
                            role=role,
                            resolved_name=person['name'],
                            resolved_entity_id=person['id'],
                            confidence=0.95 if is_exact_match else 0.85,
                            resolution_method="stage0_graph_traversal",
                            all_matches=[{
                                "name": p['name'],
                                "entity_id": p['id'],
                                "role": p.get('role_from_props', role),
                                "organization": anchor['name']
                            } for p in entities]
                        )
                    else:
                        logger.info(f"[ROLE_RESOLVER] Stage 0: Partial match for '{role}' → '{person['name']}' (role='{person_role}'), falling through to validate")
                else:
                    # Multiple matches - check if first match has significantly better edge_rank
                    # Matches are already sorted by edge_rank (HOLDS_POSITION=1 > LEADS=2 > WORKS_FOR=3)
                    best_match = entities[0]
                    best_rank = best_match.get('edge_rank', 9)
                    second_rank = entities[1].get('edge_rank', 9) if len(entities) > 1 else 9
                    
                    # If best match has HOLDS_POSITION (rank=1) and second doesn't, use the best
                    if best_rank == 1 and second_rank > 1:
                        logger.info(f"[ROLE_RESOLVER] Stage 0: Best match '{best_match['name']}' has HOLDS_POSITION (rank=1), second has rank={second_rank} - using best")
                        return RoleResolution(
                            role=role,
                            resolved_name=best_match['name'],
                            resolved_entity_id=best_match['id'],
                            confidence=0.90,  # High confidence - HOLDS_POSITION is definitive
                            resolution_method="stage0_graph_traversal_ranked",
                            all_matches=[{
                                "name": p['name'],
                                "entity_id": p['id'],
                                "role": p.get('role_from_props', role),
                                "organization": anchor['name'],
                                "edge_rank": p.get('edge_rank', 9)
                            } for p in entities]
                        )
                    
                    logger.info(f"[ROLE_RESOLVER] Stage 0: Multiple matches ({len(entities)}) for '{role}' via graph_traversal (ranks: {[e.get('edge_rank', 9) for e in entities]})")
                    return RoleResolution(
                        role=role,
                        resolved_name=None,
                        confidence=0.0,
                        resolution_method="stage0_graph_traversal_multiple",
                        all_matches=[{
                            "name": p['name'],
                            "entity_id": p['id'],
                            "role": p.get('role_from_props', role),
                            "organization": anchor['name'],
                            "edge_rank": p.get('edge_rank', 9)
                        } for p in entities]
                    )
            
            logger.info(f"[ROLE_RESOLVER] Stage 0: No matches for '{role}' from anchor '{anchor['name']}'")
            return RoleResolution(role=role)
            
        except Exception as e:
            logger.error(f"[ROLE_RESOLVER] Stage 0 failed: {e}")
            return RoleResolution(role=role)
    
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
    
    def _build_role_field_clauses(self, role_variations: List[str], entity_alias: str = "e") -> tuple:
        """
        Build SQL clauses for matching roles in specific JSON fields with word boundaries.
        
        Returns:
            tuple: (sql_clause_string, params_dict)
            
        This prevents substring matches like "Director" matching "CTO" by:
        1. Only searching relevant fields (position, role, title, job_title)
        2. Using word boundary regex patterns
        """
        role_field_clauses = []
        params = {}
        
        for i, variation in enumerate(role_variations):
            escaped = re.escape(variation)
            params[f"role{i}"] = f"(^|[^a-zA-Z]){escaped}($|[^a-zA-Z])"
            role_field_clauses.append(f"""(
                {entity_alias}.properties->>'position' ~* :role{i}
                OR {entity_alias}.properties->>'role' ~* :role{i}
                OR {entity_alias}.properties->>'title' ~* :role{i}
                OR {entity_alias}.properties->>'job_title' ~* :role{i}
            )""")
        
        return " OR ".join(role_field_clauses), params
    
    def _check_entity_has_organization(self, entity_id: Optional[str], organization: Optional[str]) -> bool:
        """Check if an entity has a WORKS_AT relationship to the organization."""
        if not entity_id or not organization:
            return False
        try:
            result = self.session.execute(text("""
                SELECT COUNT(*) as cnt
                FROM relationships r
                JOIN entities target ON r.target_id = target.id
                WHERE r.source_id = :entity_id
                AND r.relationship_type = 'WORKS_AT'
                AND LOWER(target.name) LIKE :org_pattern
            """), {"entity_id": entity_id, "org_pattern": f"%{organization.lower()}%"})
            count = result.scalar() or 0
            return count > 0
        except Exception as e:
            logger.error(f"[ROLE_RESOLVER] _check_entity_has_organization failed: {e}")
            return False
    
    def _check_entity_is_main_org_role(self, entity_id: Optional[str]) -> bool:
        """
        Check if an entity is the main org role holder.
        
        Main org role holders typically have:
        - 'position' field (more formal specification)
        - No 'organization' field in properties (portfolio company CEOs have this)
        """
        if not entity_id:
            return False
        try:
            result = self.session.execute(text("""
                SELECT properties::text as props
                FROM entities
                WHERE id = :entity_id
            """), {"entity_id": entity_id})
            row = result.fetchone()
            if row:
                props = row.props or ""
                has_position = '"position"' in props
                has_organization = '"organization"' in props
                return has_position and not has_organization
            return False
        except Exception as e:
            logger.error(f"[ROLE_RESOLVER] _check_entity_is_main_org_role failed: {e}")
            return False
    
    def resolve(self, role: str, organization: Optional[str] = None, query: Optional[str] = None) -> RoleResolution:
        """
        Resolve a role to the person who holds it using 4-stage lookup.
        
        Stage 0: Relationship-first retrieval from anchor org (NEW - highest priority)
        Stage 1: Exact relationship lookup (HOLDS_POSITION)
        Stage 2: Fuzzy ILIKE matching on role properties
        Stage 3: Document search fallback
        
        Args:
            role: The role to resolve (e.g., "CEO", "Chief Technology Officer")
            organization: Optional organization context
            query: Optional query text for anchor detection
            
        Returns:
            RoleResolution with resolved person info
        """
        logger.info(f"[ROLE_RESOLVER] Resolving role: '{role}' (org={organization})")
        
        stage0_result = self.resolve_from_anchor(role, query)
        if stage0_result.is_resolved:
            logger.info(f"[ROLE_RESOLVER] Stage 0 (graph_traversal): '{role}' → '{stage0_result.resolved_name}'")
            return stage0_result
        
        if stage0_result.has_multiple_matches:
            logger.info(f"[ROLE_RESOLVER] Stage 0 has multiple matches, returning for disambiguation")
            return stage0_result
        
        stage1_result = self._stage1_exact_relationship(role, organization)
        stage2_result = self._stage2_fuzzy_relationship(role, organization)
        
        if stage1_result.is_resolved and stage2_result.is_resolved:
            stage1_has_org = self._check_entity_has_organization(stage1_result.resolved_entity_id, organization)
            stage2_has_org = self._check_entity_has_organization(stage2_result.resolved_entity_id, organization)
            stage2_is_main = self._check_entity_is_main_org_role(stage2_result.resolved_entity_id)
            
            if stage2_is_main and not stage1_has_org:
                logger.info(f"[ROLE_RESOLVER] Stage 2 entity is main org role: '{role}' → '{stage2_result.resolved_name}'")
                return stage2_result
            elif stage1_result.confidence >= stage2_result.confidence:
                logger.info(f"[ROLE_RESOLVER] Stage 1 (exact): '{role}' → '{stage1_result.resolved_name}'")
                return stage1_result
            else:
                logger.info(f"[ROLE_RESOLVER] Stage 2 (fuzzy): '{role}' → '{stage2_result.resolved_name}'")
                return stage2_result
        
        if stage1_result.is_resolved:
            logger.info(f"[ROLE_RESOLVER] Stage 1 (exact): '{role}' → '{stage1_result.resolved_name}'")
            return stage1_result
        
        if stage2_result.is_resolved:
            logger.info(f"[ROLE_RESOLVER] Stage 2 (fuzzy): '{role}' → '{stage2_result.resolved_name}'")
            return stage2_result
        
        logger.info(f"[ROLE_RESOLVER] No {role} found in knowledge graph - returning not found (no semantic fallback)")
        return RoleResolution(role=role)
    
    def resolve_all(self, role: str, vault_context: Optional[str] = None) -> RoleResolution:
        """
        Find ALL people who hold a given role across the entire vault.
        
        Returns a RoleResolution with all_matches populated, allowing callers
        to decide how to handle multiple matches (e.g., ask user to clarify).
        
        IMPORTANT: Each match includes ALL organizations the person is connected to,
        not just one. This allows disambiguation to check if ANY organization matches
        the vault context.
        
        Uses TWO sources to find role matches:
        1. Entity properties (position, role, title fields)
        2. HOLDS_POSITION/HOLD_POSITION relationships
        
        Args:
            role: The role to resolve (e.g., "CEO", "Managing Partner")
            vault_context: Optional vault name to prioritize as organization context
            
        Returns:
            RoleResolution with all_matches list containing all people with this role
        """
        logger.info(f"[ROLE_RESOLVER] Finding all matches for role: '{role}' (vault_context={vault_context})")
        
        role_variations = self._get_role_variations(role)
        all_matches = []
        seen_ids = set()
        
        import json as json_module
        
        role_clauses, role_params = self._build_role_field_clauses(role_variations)
        
        property_query = text(f"""
            WITH all_orgs AS (
                SELECT 
                    r.source_id as person_id,
                    json_agg(DISTINCT target.name) as organizations_json
                FROM relationships r
                JOIN entities target ON r.target_id = target.id
                WHERE r.relationship_type IN ('WORKS_AT', 'EMPLOYED_BY', 'MEMBER_OF')
                AND r.tenant_id = :tenant_id
                AND target.entity_type = 'ORGANIZATION'
                GROUP BY r.source_id
            )
            SELECT DISTINCT ON (e.id)
                e.id as person_id,
                e.name as person_name,
                e.properties as props,
                COALESCE(ao.organizations_json::text, '[]') as organizations_json,
                NULL as role_from_relationship
            FROM entities e
            LEFT JOIN all_orgs ao ON ao.person_id = e.id
            WHERE e.tenant_id = :tenant_id
            AND e.entity_type = 'PERSON'
            AND ({role_clauses})
            ORDER BY e.id, e.created_at DESC
        """)
        
        role_like_clauses = " OR ".join([f"LOWER(target.name) LIKE :role_like{i}" for i in range(len(role_variations))])
        type_placeholders = ", ".join([f":rel_type{i}" for i in range(len(self.POSITION_RELATIONSHIP_TYPES))])
        
        relationship_query = text(f"""
            WITH all_orgs AS (
                SELECT 
                    r.source_id as person_id,
                    json_agg(DISTINCT target.name) as organizations_json
                FROM relationships r
                JOIN entities target ON r.target_id = target.id
                WHERE r.relationship_type IN ('WORKS_AT', 'EMPLOYED_BY', 'MEMBER_OF')
                AND r.tenant_id = :tenant_id
                AND target.entity_type = 'ORGANIZATION'
                GROUP BY r.source_id
            )
            SELECT DISTINCT ON (source.id)
                source.id as person_id,
                source.name as person_name,
                source.properties as props,
                COALESCE(ao.organizations_json::text, '[]') as organizations_json,
                target.name as role_from_relationship
            FROM relationships r
            JOIN entities source ON r.source_id = source.id
            JOIN entities target ON r.target_id = target.id
            LEFT JOIN all_orgs ao ON ao.person_id = source.id
            WHERE r.tenant_id = :tenant_id
            AND r.relationship_type IN ({type_placeholders})
            AND source.entity_type = 'PERSON'
            AND ({role_like_clauses})
            ORDER BY source.id, r.confidence DESC, r.created_at DESC
        """)
        
        params = {"tenant_id": self.tenant_id, **role_params}
        
        rel_params = {"tenant_id": self.tenant_id}
        for i, rel_type in enumerate(self.POSITION_RELATIONSHIP_TYPES):
            rel_params[f"rel_type{i}"] = rel_type
        for i, variation in enumerate(role_variations):
            rel_params[f"role_like{i}"] = f"%{variation}%"
        
        try:
            prop_results = self.session.execute(property_query, params).fetchall()
            for row in prop_results:
                # Skip blacklisted entity names (document metadata)
                if _is_blacklisted_name(row.person_name):
                    logger.info(f"[ROLE_RESOLVER] Skipping blacklisted entity: {row.person_name}")
                    continue
                    
                if str(row.person_id) not in seen_ids:
                    seen_ids.add(str(row.person_id))
                    props = row.props or {}
                    role_value = props.get('position') or props.get('role') or props.get('title') or role
                    
                    raw_orgs = row.organizations_json
                    try:
                        orgs_list = json_module.loads(raw_orgs) if raw_orgs else []
                    except (json_module.JSONDecodeError, TypeError):
                        orgs_list = []
                    if not orgs_list and props.get('organization'):
                        orgs_list = [props.get('organization')]
                    
                    # Default to vault_context if no org found
                    org_name = orgs_list[0] if orgs_list else vault_context
                    all_matches.append({
                        "name": row.person_name,
                        "entity_id": str(row.person_id),
                        "role": role_value,
                        "organizations": orgs_list if orgs_list else ([vault_context] if vault_context else []),
                        "organization": org_name
                    })
            
            rel_results = self.session.execute(relationship_query, rel_params).fetchall()
            for row in rel_results:
                # Skip blacklisted entity names (document metadata)
                if _is_blacklisted_name(row.person_name):
                    logger.info(f"[ROLE_RESOLVER] Skipping blacklisted entity: {row.person_name}")
                    continue
                    
                if str(row.person_id) not in seen_ids:
                    seen_ids.add(str(row.person_id))
                    props = row.props or {}
                    role_value = row.role_from_relationship or props.get('position') or role
                    
                    raw_orgs = row.organizations_json
                    try:
                        orgs_list = json_module.loads(raw_orgs) if raw_orgs else []
                    except (json_module.JSONDecodeError, TypeError):
                        orgs_list = []
                    if not orgs_list and props.get('organization'):
                        orgs_list = [props.get('organization')]
                    
                    # Default to vault_context if no org found
                    org_name = orgs_list[0] if orgs_list else vault_context
                    all_matches.append({
                        "name": row.person_name,
                        "entity_id": str(row.person_id),
                        "role": role_value,
                        "organizations": orgs_list if orgs_list else ([vault_context] if vault_context else []),
                        "organization": org_name,
                        "source": "relationship"
                    })
            
            logger.info(f"[ROLE_RESOLVER] Found {len(all_matches)} matches for '{role}'")
            for m in all_matches:
                logger.info(f"[ROLE_RESOLVER]   - {m['name']} ({m['role']}) orgs: {m.get('organizations', [])}")
            
            if vault_context and len(all_matches) > 1:
                def vault_match_score(match):
                    orgs = match.get("organizations", [])
                    vault_lower = vault_context.lower()
                    for org in orgs:
                        if org and vault_lower in org.lower():
                            return 2
                    for org in orgs:
                        if org and any(word in vault_lower for word in org.lower().split()):
                            return 1
                    return 0
                
                all_matches.sort(key=vault_match_score, reverse=True)
                logger.info(f"[ROLE_RESOLVER] Sorted by vault_context='{vault_context}': {[m['name'] for m in all_matches]}")
            
            # Apply anchor organization filter to remove cross-org contamination
            if len(all_matches) > 1:
                all_matches = self._filter_by_anchor(all_matches)
            
            if len(all_matches) == 1:
                match = all_matches[0]
                return RoleResolution(
                    role=role,
                    resolved_name=match["name"],
                    resolved_entity_id=match["entity_id"],
                    confidence=0.9,
                    resolution_method="resolve_all_single",
                    all_matches=all_matches
                )
            elif len(all_matches) > 1:
                return RoleResolution(
                    role=role,
                    resolved_name=None,
                    confidence=0.0,
                    resolution_method="resolve_all_multiple",
                    all_matches=all_matches
                )
            
        except Exception as e:
            logger.error(f"[ROLE_RESOLVER] resolve_all failed: {e}")
        
        return RoleResolution(role=role)
    
    def _stage1_exact_relationship(self, role: str, organization: Optional[str] = None) -> RoleResolution:
        """
        Stage 1: Exact relationship lookup with multiple type names.
        
        Prioritizes entities that:
        1. Have organization matching the vault context
        2. Have 'position' field (more formal, likely main org CEO)
        3. Don't have a different organization specified (portfolio company CEOs)
        """
        role_variations = self._get_role_variations(role)
        org_pattern = f"%{organization}%" if organization else "%NEVER_MATCH_PLACEHOLDER%"
        
        type_placeholders = ", ".join([f":type{i}" for i in range(len(self.POSITION_RELATIONSHIP_TYPES))])
        like_clauses = " OR ".join([f"LOWER(target.name) LIKE :role{i}" for i in range(len(role_variations))])
        
        query = text(f"""
            SELECT 
                source.id as person_id,
                source.name as person_name,
                target.name as role_name,
                r.relationship_type,
                r.confidence as relationship_confidence,
                CASE 
                    WHEN source.properties::text ILIKE :org_pattern THEN 3
                    WHEN source.properties::text ILIKE '%"position"%' 
                         AND source.properties::text NOT ILIKE '%"organization"%' THEN 2
                    WHEN source.properties::text NOT ILIKE '%"organization"%' THEN 1
                    ELSE 0
                END as priority_score
            FROM relationships r
            JOIN entities source ON r.source_id = source.id
            JOIN entities target ON r.target_id = target.id
            WHERE r.tenant_id = :tenant_id
            AND r.relationship_type IN ({type_placeholders})
            AND ({like_clauses})
            ORDER BY priority_score DESC, r.confidence DESC, r.created_at DESC
            LIMIT 5
        """)
        
        params = {"tenant_id": self.tenant_id, "org_pattern": org_pattern}
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
    
    def _stage2_fuzzy_relationship(self, role: str, organization: Optional[str] = None) -> RoleResolution:
        """
        Stage 2: Field-specific matching on entity properties with word boundaries.
        
        Prioritizes entities that:
        1. Have organization matching the vault context
        2. Have 'position' field (more formal, likely main org CEO)
        3. Don't have a different organization specified (portfolio company CEOs)
        
        Uses word boundary regex to prevent substring matches (e.g., "Director" matching "CTO").
        """
        role_variations = self._get_role_variations(role)
        org_pattern = f"%{organization}%" if organization else "%NEVER_MATCH_PLACEHOLDER%"
        
        role_clauses, role_params = self._build_role_field_clauses(role_variations)
        
        first_variation = role_variations[0] if role_variations else role.lower()
        first_escaped = re.escape(first_variation)
        exact_role_pattern = f"(^|[^a-zA-Z]){first_escaped}($|[^a-zA-Z])"
        
        query = text(f"""
            SELECT 
                e.id as person_id,
                e.name as person_name,
                e.properties,
                CASE 
                    WHEN e.properties::text ILIKE :org_pattern THEN 5
                    WHEN (e.properties->>'position' ~* :exact_role OR e.properties->>'role' ~* :exact_role)
                         AND e.properties ? 'position'
                         AND NOT e.properties ? 'organization' THEN 4
                    WHEN e.properties ? 'position'
                         AND NOT e.properties ? 'organization' THEN 2
                    WHEN NOT e.properties ? 'organization' THEN 1
                    ELSE 0
                END as priority_score
            FROM entities e
            WHERE e.tenant_id = :tenant_id
            AND e.entity_type = 'PERSON'
            AND ({role_clauses})
            ORDER BY priority_score DESC, e.created_at DESC
            LIMIT 5
        """)
        
        params = {
            "tenant_id": self.tenant_id, 
            "org_pattern": org_pattern,
            "exact_role": exact_role_pattern,
            **role_params
        }
        
        try:
            results = self.session.execute(query, params).fetchall()
            
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
        """
        Extract person name from text patterns like 'Sarah Chen, CEO' or 'CEO Sarah Chen'.
        
        CRITICAL: Only matches the SPECIFIC role requested, not any C-suite role.
        Uses role expansions to match both abbreviations and full names.
        """
        import re
        
        # Expand abbreviations to ALL variants for matching
        ROLE_EXPANSIONS = {
            'ceo': ['CEO', 'Chief Executive Officer'],
            'cfo': ['CFO', 'Chief Financial Officer'],
            'cto': ['CTO', 'Chief Technology Officer'],
            'cio': ['CIO', 'Chief Information Officer'],
            'coo': ['COO', 'Chief Operating Officer'],
            'cdo': ['CDO', 'Chief Data Officer'],
            'cmo': ['CMO', 'Chief Medical Officer', 'Chief Marketing Officer'],
            'cno': ['CNO', 'Chief Nursing Officer'],
            'cpo': ['CPO', 'Chief Product Officer'],
            'cro': ['CRO', 'Chief Revenue Officer'],
            'ciso': ['CISO', 'Chief Information Security Officer'],
            'managing partner': ['Managing Partner'],
            'senior partner': ['Senior Partner'],
            'partner': ['Partner'],
            'general counsel': ['General Counsel'],
            'vp': ['VP', 'Vice President'],
            'svp': ['SVP', 'Senior Vice President'],
            'evp': ['EVP', 'Executive Vice President'],
        }
        
        # Get all variants for the requested role
        role_lower = role.lower().strip()
        normalized_lower = normalized.lower().strip()
        
        # Build list of all role variants to match
        role_variants = set()
        role_variants.add(role_lower)
        role_variants.add(normalized_lower)
        
        # Add expansions if this is a known abbreviation
        if role_lower in ROLE_EXPANSIONS:
            for expansion in ROLE_EXPANSIONS[role_lower]:
                role_variants.add(expansion.lower())
        
        # Also check if the role matches any expansion (e.g., "chief financial officer" -> add "cfo")
        for abbrev, expansions in ROLE_EXPANSIONS.items():
            for exp in expansions:
                if role_lower == exp.lower() or normalized_lower == exp.lower():
                    role_variants.add(abbrev)
                    for e in expansions:
                        role_variants.add(e.lower())
                    break
        
        # Process text line-by-line to avoid matching across line boundaries
        lines = text.split('\n')
        
        for role_variant in role_variants:
            role_escaped = re.escape(role_variant)
            
            # Patterns for THIS SPECIFIC ROLE only - match within single lines
            patterns = [
                # "Thomas Bradley - Chief Financial Officer" or "Thomas Bradley - CFO"
                rf"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–—:]\s*{role_escaped}",
                # With prefix: "Dr. Margaret Chen - CEO"
                rf"^(?:Dr\.|Mr\.|Ms\.|Mrs\.)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–—:]\s*{role_escaped}",
                # "Chief Financial Officer Thomas Bradley" or "CFO Thomas Bradley"
                rf"^{role_escaped}\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
                # "Thomas Bradley, CFO" or "Thomas Bradley, Chief Financial Officer"
                rf"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+),\s*{role_escaped}",
                # "Thomas Bradley is the CFO"
                rf"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:is|serves as|as)\s+(?:the\s+)?{role_escaped}",
            ]
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                for pattern in patterns:
                    match = re.search(pattern, line, re.IGNORECASE)
                    if match:
                        name = match.group(1).strip()
                        # Clean up extra whitespace
                        name = re.sub(r'\s+', ' ', name)
                        # Validate: reasonable name length (2-3 words typical for names)
                        word_count = len(name.split())
                        if len(name) > 3 and len(name) < 50 and word_count >= 2 and word_count <= 4:
                            logger.debug(f"[ROLE_RESOLVER] Stage 3 matched: '{role_variant}' → '{name}'")
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
