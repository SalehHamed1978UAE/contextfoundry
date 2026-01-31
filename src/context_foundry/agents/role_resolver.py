"""
Role Resolver - Enhanced 3-Stage Resolution

Resolves job titles/roles to actual people via:
1. Stage 1: Exact relationship lookup (HOLDS_POSITION)
2. Stage 2: Fuzzy ILIKE matching on role names
3. Stage 3: Document search fallback for patterns like "Sarah Chen, CEO"

CEO → Sarah Chen
CTO → Marcus Williams
"""

import re
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
    Enhanced 3-stage role resolution.
    
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

    # Patterns to detect scoped role queries like "Who is the CEO of NextGen Battery?"
    SCOPED_ROLE_PATTERNS = [
        # "Who is the CEO of NextGen Battery?"
        re.compile(r"(?:who is|who's|name of)\s+(?:the\s+)?(.+?)\s+(?:of|for|at)\s+(.+?)[\?\.]?$", re.IGNORECASE),
        # "CEO of NextGen Battery" - direct pattern
        re.compile(r"^(?:the\s+)?(.+?)\s+(?:of|for|at)\s+(.+?)[\?\.]?$", re.IGNORECASE),
    ]

    def extract_scoped_query(self, query: str) -> Optional[Dict[str, str]]:
        """
        Detect if query asks for a role at a specific entity.

        Examples:
            "Who is the CEO of NextGen Battery?" → {"role": "CEO", "entity": "NextGen Battery"}
            "Who will be the CEO of the Toyota JV?" → {"role": "CEO", "entity": "Toyota JV"}

        Returns:
            Dict with 'role' and 'entity' if scoped query detected, None otherwise
        """
        logger.info(f"[SCOPED_EXTRACT] Input query: {query}")

        for pattern in self.SCOPED_ROLE_PATTERNS:
            match = pattern.search(query.strip())
            if match:
                role = match.group(1).strip()
                entity = match.group(2).strip()

                logger.info(f"[SCOPED_EXTRACT] Pattern matched: role='{role}', entity='{entity}'")

                # Skip if "role" is actually a common question word
                if role.lower() in ('who', 'what', 'the', 'name', 'a'):
                    logger.info(f"[SCOPED_EXTRACT] Skipping - role is question word: '{role}'")
                    continue

                # Check if the role is actually a known role type
                normalized_role = self._normalize_role(role)
                role_keywords = ['ceo', 'cto', 'cfo', 'coo', 'cmo', 'cio', 'cdo', 'president',
                                'director', 'manager', 'head', 'lead', 'vp', 'svp', 'evp',
                                'chief', 'officer', 'engineer', 'project']

                is_role = (
                    normalized_role in self.ROLE_NORMALIZATIONS.values() or
                    role.lower() in self.ROLE_EXPANSIONS or
                    any(kw in role.lower() for kw in role_keywords)
                )

                if is_role:
                    logger.info(f"[SCOPED_EXTRACT] SUCCESS - Detected scoped query: role='{role}' entity='{entity}'")
                    return {"role": role, "entity": entity}
                else:
                    logger.info(f"[SCOPED_EXTRACT] Not a recognized role: '{role}'")

        logger.info(f"[SCOPED_EXTRACT] No scoped pattern matched for query")
        return None

    def resolve_for_entity(self, role: str, entity_name: str) -> RoleResolution:
        """
        Resolve a role specifically for a given entity.

        This is used for scoped queries like "Who is the CEO of NextGen Battery?"
        Unlike resolve_all, this ONLY searches for the role at the specified entity.

        Args:
            role: The role to find (e.g., "CEO", "Director")
            entity_name: The entity to search within (e.g., "NextGen Battery Technologies")

        Returns:
            RoleResolution - if not found, resolution_method will be "scoped_entity_not_found"
        """
        logger.info(f"[SCOPED_RESOLVE] Resolving '{role}' specifically for entity '{entity_name}'")

        role_variations = self._get_role_variations(role)
        logger.info(f"[SCOPED_RESOLVE] Role variations: {role_variations}")

        # Step 1: Find the entity by name (fuzzy match)
        entity_query = text("""
            SELECT id, name, entity_type
            FROM entities
            WHERE tenant_id = :tenant_id
            AND lifecycle_state IN ('TRUSTED', 'STAGING')
            AND (
                LOWER(name) LIKE LOWER(:entity_pattern)
                OR name ILIKE :entity_pattern
            )
            ORDER BY
                CASE WHEN LOWER(name) = LOWER(:exact_name) THEN 0 ELSE 1 END,
                confidence DESC
            LIMIT 5
        """)

        try:
            entity_results = self.session.execute(entity_query, {
                "tenant_id": self.tenant_id,
                "entity_pattern": f"%{entity_name}%",
                "exact_name": entity_name
            }).fetchall()

            if not entity_results:
                logger.info(f"[SCOPED_RESOLVE] Entity '{entity_name}' not found in KG")
                return RoleResolution(
                    role=role,
                    resolution_method="scoped_entity_not_found"
                )

            entity_ids = [str(r.id) for r in entity_results]
            entity_names = [r.name for r in entity_results]
            logger.info(f"[SCOPED_RESOLVE] Found entity candidates: {entity_names}")

            # Step 2: Find person with role who has relationship to this entity
            role_edge_types = ['HOLDS_POSITION', 'MANAGES', 'LEADS', 'DIRECTS', 'CHAIRS',
                              'CEO_OF', 'CTO_OF', 'CFO_OF', 'HEAD_OF', 'WORKS_AT', 'EMPLOYED_BY']

            role_clauses, role_params = self._build_role_field_clauses(role_variations, "person")
            type_placeholders = ", ".join([f":edge_type{i}" for i in range(len(role_edge_types))])
            entity_placeholders = ", ".join([f":entity_id{i}" for i in range(len(entity_ids))])

            person_query = text(f"""
                SELECT DISTINCT
                    person.id as person_id,
                    person.name as person_name,
                    person.properties as props,
                    r.relationship_type,
                    target.name as target_name
                FROM entities person
                JOIN relationships r ON (r.source_id = person.id OR r.target_id = person.id)
                JOIN entities target ON (
                    CASE WHEN r.source_id = person.id THEN r.target_id ELSE r.source_id END = target.id
                )
                WHERE person.tenant_id = :tenant_id
                AND person.entity_type = 'PERSON'
                AND person.lifecycle_state IN ('TRUSTED', 'STAGING')
                AND r.lifecycle_state IN ('TRUSTED', 'STAGING')
                AND target.id IN ({entity_placeholders})
                AND (
                    r.relationship_type IN ({type_placeholders})
                    OR ({role_clauses})
                )
                ORDER BY person.confidence DESC
                LIMIT 10
            """)

            params = {
                "tenant_id": self.tenant_id,
                **role_params
            }
            for i, eid in enumerate(entity_ids):
                params[f"entity_id{i}"] = eid
            for i, edge_type in enumerate(role_edge_types):
                params[f"edge_type{i}"] = edge_type

            person_results = self.session.execute(person_query, params).fetchall()
            logger.info(f"[SCOPED_RESOLVE] Found {len(person_results)} person candidates")

            if person_results:
                for row in person_results:
                    props = row.props or {}
                    person_role = (props.get('position') or props.get('role') or
                                   props.get('title') or '').lower()

                    logger.info(f"[SCOPED_RESOLVE] Checking {row.person_name}: role='{person_role}', rel_type='{row.relationship_type}'")

                    # Check if person's role matches any variation
                    role_match = any(var in person_role for var in role_variations)

                    if role_match:
                        logger.info(f"[SCOPED_RESOLVE] SUCCESS - Found '{role}' of '{entity_name}': {row.person_name}")
                        return RoleResolution(
                            role=role,
                            resolved_name=row.person_name,
                            resolved_entity_id=str(row.person_id),
                            confidence=0.85,
                            resolution_method="scoped_entity_match"
                        )

                # Check relationship type as fallback
                for row in person_results:
                    rel_type = row.relationship_type.upper() if row.relationship_type else ''
                    normalized = self._normalize_role(role)

                    if normalized in rel_type or role.upper() in rel_type:
                        logger.info(f"[SCOPED_RESOLVE] SUCCESS via relationship type - Found '{role}' of '{entity_name}': {row.person_name}")
                        return RoleResolution(
                            role=role,
                            resolved_name=row.person_name,
                            resolved_entity_id=str(row.person_id),
                            confidence=0.80,
                            resolution_method="scoped_relationship_match"
                        )

            # Not found - return explicit "not found for this entity" status
            logger.info(f"[SCOPED_RESOLVE] FAILED - Could not find '{role}' for entity '{entity_name}'")
            return RoleResolution(
                role=role,
                resolution_method="scoped_entity_not_found"
            )

        except Exception as e:
            logger.error(f"[SCOPED_RESOLVE] Exception: {e}")
            return RoleResolution(
                role=role,
                resolution_method="scoped_entity_not_found"
            )

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
    
    def resolve(self, role: str, organization: Optional[str] = None) -> RoleResolution:
        """
        Resolve a role to the person who holds it using 3-stage lookup.
        
        Now checks both Stage 1 (relationships) and Stage 2 (properties) to find
        the best match based on organization context, rather than stopping at
        Stage 1 if any result is found.
        
        Args:
            role: The role to resolve (e.g., "CEO", "Chief Technology Officer")
            organization: Optional organization context
            
        Returns:
            RoleResolution with resolved person info
        """
        logger.info(f"[ROLE_RESOLVER] Resolving role: '{role}' (org={organization})")
        
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
                    
                    all_matches.append({
                        "name": row.person_name,
                        "entity_id": str(row.person_id),
                        "role": role_value,
                        "organizations": orgs_list,
                        "organization": orgs_list[0] if orgs_list else None
                    })
            
            rel_results = self.session.execute(relationship_query, rel_params).fetchall()
            for row in rel_results:
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
                    
                    all_matches.append({
                        "name": row.person_name,
                        "entity_id": str(row.person_id),
                        "role": role_value,
                        "organizations": orgs_list,
                        "organization": orgs_list[0] if orgs_list else None,
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
