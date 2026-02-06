"""
Tree-Based Retrieval

Hierarchical entity retrieval via graph traversal from anchor organization.
Prioritizes graph proximity over flat semantic similarity.
"""

from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import text
import numpy as np
import time

from src.context_foundry.utils.logger import logger
from src.context_foundry.retrieval.anchor_resolver import AnchorResolver
from src.context_foundry.retrieval.intent_extractor import IntentExtractor, QueryIntent


@dataclass
class RetrievalResult:
    """Result from tree-based retrieval."""
    entities: List[Dict[str, Any]]
    relationships: List[Dict[str, Any]]
    confidence: str  # 'high', 'medium', 'low', 'none'
    method: str  # 'tree_traversal', 'semantic_fallback'
    anchor: Optional[Dict[str, Any]] = None
    max_depth_reached: int = 0
    total_traversed: int = 0


class TreeBasedRetriever:
    """
    Hierarchical entity retrieval via graph traversal.

    Core principle: Answers are ranked by graph distance from anchor,
    not just semantic similarity. Extends relationship-first retrieval
    (currently role-only) to ALL query types.

    Retrieval tiers (in priority order):
    1. GRAPH_TIER: Entities reachable from anchor (depth 1-3)
    2. HYBRID_TIER: Graph + semantic fusion for complex queries
    3. FALLBACK_TIER: Pure semantic search with low confidence marker
    """

    # Maximum traversal depth (prevents infinite loops)
    DEFAULT_MAX_DEPTH = 3

    # Relationship types that typically connect important entities
    CORE_RELATIONSHIP_TYPES = [
        # Organization to people
        'LEADS', 'MANAGES', 'HAS_EXECUTIVE', 'HAS_OFFICER', 'EMPLOYS', 'HAS_EMPLOYEE',
        'HAS_ROLE', 'HOLDS_POSITION', 'WORKS_FOR', 'WORKS_AT', 'EMPLOYED_BY',

        # Organization to projects/products
        'HAS_PROJECT', 'HAS_PRODUCT', 'HAS_INITIATIVE', 'HAS_PROGRAM',
        'WORKS_ON', 'MANAGES', 'DIRECTS',

        # Organization to divisions/units
        'HAS_DIVISION', 'HAS_DEPARTMENT', 'HAS_UNIT', 'PART_OF',

        # Organization to partners/customers
        'PARTNERED_WITH', 'CUSTOMER_OF', 'SUPPLIER_OF', 'SUPPLIES_TO',

        # Entity to specifications/metrics
        'HAS_SPEC', 'HAS_METRIC', 'HAS_REVENUE', 'HAS_BUDGET', 'HAS_CAPACITY',
        'HAS_VALUE', 'HAS_COST', 'HAS_AGREEMENT',

        # Temporal relationships
        'STARTED_ON', 'ENDED_ON', 'SCHEDULED_FOR', 'EXPECTED_ON',

        # Role relationships
        'CEO_OF', 'CFO_OF', 'CTO_OF', 'PROJECT_DIRECTOR_OF', 'CHAIRS',
    ]

    # Relationship types that imply specific roles (for ROLE queries)
    RELATIONSHIP_TO_ROLE = {
        'LEADS': ['CEO', 'CHIEF EXECUTIVE OFFICER', 'PRESIDENT'],
        'CEO_OF': ['CEO', 'CHIEF EXECUTIVE OFFICER'],
        'CFO_OF': ['CFO', 'CHIEF FINANCIAL OFFICER'],
        'CTO_OF': ['CTO', 'CHIEF TECHNOLOGY OFFICER'],
        'COO_OF': ['COO', 'CHIEF OPERATING OFFICER'],
        'CHAIRS': ['CHAIR', 'CHAIRPERSON'],
        'PROJECT_DIRECTOR_OF': ['DIRECTOR', 'PROJECT DIRECTOR'],
    }

    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        self.anchor_resolver = AnchorResolver(session, tenant_id)
        self.intent_extractor = IntentExtractor()
        self.timeout_seconds: Optional[float] = None
        self._start_time: Optional[float] = None

    def retrieve(
        self,
        query: str,
        query_type: str = "UNKNOWN",
        max_depth: int = None
    ) -> RetrievalResult:
        """
        Main retrieval method for all query types.

        Args:
            query: User question
            query_type: Pre-classified query type (ROLE, METRIC, etc.)
            max_depth: Maximum graph traversal depth (default 3)

        Returns:
            RetrievalResult with entities, relationships, confidence
        """
        if max_depth is None:
            max_depth = self.DEFAULT_MAX_DEPTH

        self._start_time = time.monotonic()

        logger.info(f"[TREE] Retrieving for query: {query}")
        logger.info(f"[TREE] Query type: {query_type}, max_depth: {max_depth}, timeout: {self.timeout_seconds}s")

        # Step 1: Identify anchor
        anchor = self.anchor_resolver.identify_anchor(query)
        if not anchor:
            logger.warning(f"[TREE] No anchor found, falling back to semantic search")
            return self._fallback_semantic_search(query)

        logger.info(f"[TREE] Anchor: {anchor['name']} (id={anchor['id']})")
        logger.info(f"[TREE] Anchor full ID: {anchor['id']}")

        # Step 2: Extract query intent
        intent = self.intent_extractor.extract(query, query_type)

        # Step 3: Traverse graph from anchor
        traversal_results = self._traverse_from_anchor(
            anchor=anchor,
            intent=intent,
            max_depth=max_depth
        )

        logger.info(f"[TREE] Traversal found {len(traversal_results)} results")

        # Step 4: Rank by graph proximity + semantic relevance
        ranked = self._rank_results(traversal_results, query, intent)

        # Step 5: Return with confidence
        if ranked:
            max_depth_reached = max([r['depth'] for r in ranked]) if ranked else 0
            confidence = self._compute_confidence(ranked, max_depth_reached)

            # Extract relationships for these entities
            relationships = self._get_relationships_for_entities(
                [r['entity']['id'] for r in ranked[:10]]  # Top 10 entities
            )

            return RetrievalResult(
                entities=[r['entity'] for r in ranked],
                relationships=relationships,
                confidence=confidence,
                method="tree_traversal",
                anchor=anchor,
                max_depth_reached=max_depth_reached,
                total_traversed=len(traversal_results)
            )

        # Fallback to semantic search
        logger.info(f"[TREE] No graph results, falling back to semantic search")
        return self._fallback_semantic_search(query)

    def _traverse_from_anchor(
        self,
        anchor: Dict[str, Any],
        intent: QueryIntent,
        max_depth: int
    ) -> List[Dict[str, Any]]:
        """
        BFS traversal from anchor entity.

        Returns all entities reachable within max_depth hops,
        filtered by intent (entity type, relationship type, properties).
        """
        visited: Set[str] = set()
        queue: List[Tuple[str, int, Optional[str]]] = [(anchor['id'], 0, None)]  # (entity_id, depth, edge_type)
        results: List[Dict[str, Any]] = []

        logger.info(f"[TREE] Starting BFS from anchor: {anchor['name']}")
        logger.info(f"[TREE] Target entity types: {intent.target_entity_types}")
        logger.info(f"[TREE] Relationship types: {intent.relationship_types[:5]}...")

        while queue:
            if self.timeout_seconds and self._start_time:
                elapsed = time.monotonic() - self._start_time
                if elapsed > self.timeout_seconds:
                    logger.warning(f"[TREE] BFS timeout after {elapsed:.1f}s (limit={self.timeout_seconds}s), "
                                   f"visited {len(visited)} entities, returning {len(results)} partial matches")
                    break

            entity_id, depth, edge_type = queue.pop(0)

            if entity_id in visited or depth > max_depth:
                continue

            visited.add(entity_id)

            # Get entity details (allow ARCHIVED anchor at depth 0 for traversal bootstrap)
            entity = self._get_entity_details(entity_id, allow_archived=(depth == 0))
            if not entity:
                continue

            # Check if entity matches intent
            if self._matches_intent(entity, intent, depth, edge_type=edge_type):
                results.append({
                    'entity': entity,
                    'depth': depth,
                    'anchor_path': []  # TODO: track path for provenance
                })
                logger.debug(f"[TREE] Match at depth {depth}: {entity['name']} ({entity['entity_type']})")

            # Get connected entities (only if depth < max_depth)
            if depth < max_depth:
                # Use intent relationship types if specified, otherwise use all core types
                rel_types = intent.relationship_types if intent.relationship_types != ['*'] else self.CORE_RELATIONSHIP_TYPES

                connected = self._get_connected_entities(entity_id, rel_types)
                logger.info(f"[TREE] Depth {depth}: entity_id={entity_id[:8]}..., found {len(connected)} connected entities")
                if len(connected) > 0:
                    logger.info(f"[TREE] First 3 connections: {[c['name'] for c in connected[:3]]}")
                else:
                    logger.info(f"[TREE] Zero connections found - checking if this entity ID exists in relationships")
                for conn in connected:
                    if conn['id'] not in visited:
                        queue.append((conn['id'], depth + 1, conn.get('edge_type')))

        logger.info(f"[TREE] BFS complete: visited {len(visited)} entities, found {len(results)} matches")
        return results

    def _get_entity_details(self, entity_id: str, allow_archived: bool = False) -> Optional[Dict[str, Any]]:
        """Get full entity details including properties and embedding."""
        try:
            lifecycle_filter = "('TRUSTED', 'STAGING', 'ARCHIVED')" if allow_archived else "('TRUSTED', 'STAGING')"
            result = self.session.execute(text("""
                SELECT
                    id, name, entity_type,
                    properties::jsonb as properties,
                    name_embedding,
                    confidence,
                    lifecycle_state
                FROM entities
                WHERE id = :entity_id
                AND tenant_id = :tenant_id
                AND lifecycle_state IN """ + lifecycle_filter + """
            """), {
                "entity_id": entity_id,
                "tenant_id": self.tenant_id
            }).fetchone()

            if not result:
                return None

            return {
                'id': str(result.id),
                'name': result.name,
                'entity_type': result.entity_type,
                'properties': result.properties or {},
                'embedding': result.name_embedding,
                'confidence': result.confidence,
                'lifecycle_state': result.lifecycle_state
            }
        except Exception as e:
            logger.error(f"[TREE] Error getting entity details: {e}")
            return None

    def _get_connected_entities(
        self,
        entity_id: str,
        relationship_types: List[str]
    ) -> List[Dict[str, str]]:
        """
        Get all entities connected to this entity via specified relationships.

        Returns list of {id, name, entity_type, edge_type, direction}.
        """
        if not relationship_types:
            return []

        # Build relationship type filter
        if relationship_types == ['*']:
            rel_filter = ""
        else:
            rel_types_str = ", ".join([f"'{t}'" for t in relationship_types])
            rel_filter = f"AND r.relationship_type IN ({rel_types_str})"

        query = text(f"""
            WITH connected AS (
                -- Outgoing edges (this entity → other)
                SELECT
                    target.id as connected_id,
                    target.name as connected_name,
                    target.entity_type as connected_type,
                    r.relationship_type as edge_type,
                    'outgoing' as direction
                FROM relationships r
                JOIN entities target ON r.target_id = target.id
                WHERE r.source_id = :entity_id
                AND r.tenant_id = :tenant_id
                AND r.lifecycle_state IN ('TRUSTED', 'STAGING')
                AND target.lifecycle_state IN ('TRUSTED', 'STAGING')
                {rel_filter}

                UNION ALL

                -- Incoming edges (other → this entity)
                SELECT
                    source.id as connected_id,
                    source.name as connected_name,
                    source.entity_type as connected_type,
                    r.relationship_type as edge_type,
                    'incoming' as direction
                FROM relationships r
                JOIN entities source ON r.source_id = source.id
                WHERE r.target_id = :entity_id
                AND r.tenant_id = :tenant_id
                AND r.lifecycle_state IN ('TRUSTED', 'STAGING')
                AND source.lifecycle_state IN ('TRUSTED', 'STAGING')
                {rel_filter}
            )
            SELECT DISTINCT connected_id, connected_name, connected_type, edge_type, direction
            FROM connected
        """)

        try:
            results = self.session.execute(query, {
                "entity_id": entity_id,
                "tenant_id": self.tenant_id
            }).fetchall()

            connected_list = [{
                'id': str(r.connected_id),
                'name': r.connected_name,
                'entity_type': r.connected_type,
                'edge_type': r.edge_type,
                'direction': r.direction
            } for r in results]

            logger.debug(f"[TREE] Entity {entity_id[:8]} has {len(connected_list)} connected entities " +
                        f"(filtering for: {relationship_types[:3] if len(relationship_types) > 3 else relationship_types}...)")

            return connected_list

        except Exception as e:
            logger.error(f"[TREE] Error getting connected entities: {e}")
            return []

    def _matches_intent(
        self,
        entity: Dict[str, Any],
        intent: QueryIntent,
        depth: int,
        edge_type: Optional[str] = None
    ) -> bool:
        """
        Check if entity matches the query intent.

        Matches on:
        1. Entity type (if specified)
        2. Property filters (fiscal_year, role, etc.)
        3. Keywords in name or properties
        """
        # Skip anchor itself (depth 0) unless it's the only result
        if depth == 0 and intent.target_entity_types != ['ORGANIZATION']:
            return False

        # Check entity type match
        if intent.target_entity_types != ['*']:
            if entity['entity_type'] not in intent.target_entity_types:
                return False

        # ROLE queries: use relationship semantics instead of entity properties
        if intent.query_type == 'ROLE' and intent.property_filters:
            role_value = intent.property_filters.get('role')
            if role_value and not self._relationship_implies_role(edge_type, role_value):
                return False
        else:
            # Check property filters (fiscal_year, etc.)
            if intent.property_filters:
                props = entity.get('properties', {})
                for key, value in intent.property_filters.items():
                    prop_value = props.get(key, '')
                    if isinstance(prop_value, str):
                        if value.lower() not in prop_value.lower():
                            return False
                    elif str(value).lower() not in str(prop_value).lower():
                        return False

        # Check semantic keywords (soft match)
        if intent.semantic_keywords:
            entity_text = f"{entity['name']} {entity.get('properties', {})}"
            entity_text_lower = entity_text.lower()

            # At least one keyword should match
            keyword_match = any(kw in entity_text_lower for kw in intent.semantic_keywords)
            if not keyword_match and depth > 1:  # Be strict for deep results
                return False

        return True

    def _relationship_implies_role(self, edge_type: Optional[str], role_value: str) -> bool:
        """Check if a relationship type implies the requested role."""
        if not edge_type or not role_value:
            return False
        roles = self.RELATIONSHIP_TO_ROLE.get(edge_type.upper())
        if not roles:
            return False
        return role_value.strip().upper() in roles

    def _rank_results(
        self,
        results: List[Dict[str, Any]],
        query: str,
        intent: QueryIntent
    ) -> List[Dict[str, Any]]:
        """
        Rank results by graph proximity and semantic relevance.

        Score = (graph_score * 0.7) + (semantic_score * 0.3)

        Graph Score:
        - Depth 0 (anchor): 0.5 (only if anchor is the answer)
        - Depth 1: 1.0
        - Depth 2: 0.75
        - Depth 3: 0.5

        Semantic Score:
        - Cosine similarity of entity embedding vs query embedding
        """
        if not results:
            return []

        # Get query embedding for semantic scoring
        query_embedding = self._get_query_embedding(query)

        for result in results:
            entity = result['entity']
            depth = result['depth']

            # Graph proximity score (higher is better, closer to anchor)
            if depth == 0:
                graph_score = 0.5  # Anchor itself (low priority unless it's the answer)
            elif depth == 1:
                graph_score = 1.0
            elif depth == 2:
                graph_score = 0.75
            else:
                graph_score = 0.5

            # Semantic similarity score
            entity_embedding = entity.get('embedding')
            if entity_embedding and query_embedding is not None:
                semantic_score = self._cosine_similarity(query_embedding, entity_embedding)
            else:
                # Fallback to keyword matching
                semantic_score = self._keyword_similarity(entity, intent.semantic_keywords)

            # Combined score (graph weighted higher)
            combined_score = (graph_score * 0.7) + (semantic_score * 0.3)

            result['graph_score'] = graph_score
            result['semantic_score'] = semantic_score
            result['combined_score'] = combined_score

        # Sort by combined score (descending)
        results.sort(key=lambda x: x['combined_score'], reverse=True)

        logger.info(f"[TREE] Top result: {results[0]['entity']['name']} "
                   f"(score={results[0]['combined_score']:.3f}, depth={results[0]['depth']})")

        return results

    def _get_query_embedding(self, query: str) -> Optional[np.ndarray]:
        """Get embedding for query (placeholder - integrate with embedding service)."""
        # TODO: Integrate with actual embedding service
        # For now, return None and fall back to keyword matching
        return None

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        try:
            if vec1 is None or vec2 is None:
                return 0.0

            # Convert to numpy arrays if needed
            if not isinstance(vec1, np.ndarray):
                vec1 = np.array(vec1)
            if not isinstance(vec2, np.ndarray):
                vec2 = np.array(vec2)

            # Compute cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return float(dot_product / (norm1 * norm2))

        except Exception as e:
            logger.error(f"[TREE] Error computing cosine similarity: {e}")
            return 0.0

    def _keyword_similarity(self, entity: Dict[str, Any], keywords: List[str]) -> float:
        """
        Compute keyword-based similarity score.

        Returns 0.0-1.0 based on keyword overlap.
        """
        if not keywords:
            return 0.5  # Neutral score

        entity_text = f"{entity['name']} {entity.get('properties', {})}"
        entity_text_lower = entity_text.lower()

        matches = sum(1 for kw in keywords if kw in entity_text_lower)
        return min(1.0, matches / len(keywords))

    def _compute_confidence(self, results: List[Dict[str, Any]], max_depth: int) -> str:
        """
        Compute confidence level based on results quality.

        high: Depth 1-2 results with good scores
        medium: Depth 3 or lower scores
        low: Only deep results or poor scores
        none: No results
        """
        if not results:
            return 'none'

        top_score = results[0]['combined_score']
        top_depth = results[0]['depth']

        if top_depth <= 2 and top_score >= 0.7:
            return 'high'
        elif top_depth <= 3 and top_score >= 0.5:
            return 'medium'
        else:
            return 'low'

    def _get_relationships_for_entities(self, entity_ids: List[str]) -> List[Dict[str, Any]]:
        """Get all relationships between the provided entities."""
        if not entity_ids:
            return []

        entity_ids_str = ", ".join([f"'{eid}'" for eid in entity_ids])

        query = text(f"""
            SELECT
                r.id,
                r.source_id,
                r.target_id,
                r.relationship_type,
                r.metadata::jsonb as metadata,
                r.confidence,
                source.name as source_name,
                target.name as target_name
            FROM relationships r
            JOIN entities source ON r.source_id = source.id
            JOIN entities target ON r.target_id = target.id
            WHERE r.tenant_id = :tenant_id
            AND (r.source_id::text IN ({entity_ids_str}) OR r.target_id::text IN ({entity_ids_str}))
            AND r.lifecycle_state IN ('TRUSTED', 'STAGING')
            ORDER BY r.confidence DESC
            LIMIT 50
        """)

        try:
            results = self.session.execute(query, {"tenant_id": self.tenant_id}).fetchall()

            return [{
                'id': str(r.id),
                'source_id': str(r.source_id),
                'target_id': str(r.target_id),
                'relationship_type': r.relationship_type,
                'metadata': r.metadata or {},
                'confidence': r.confidence,
                'source_name': r.source_name,
                'target_name': r.target_name
            } for r in results]

        except Exception as e:
            logger.error(f"[TREE] Error getting relationships: {e}")
            return []

    def _fallback_semantic_search(self, query: str) -> RetrievalResult:
        """
        Fallback to semantic search when graph traversal fails.

        Returns low confidence result.
        """
        logger.info(f"[TREE] Using semantic search fallback")

        # TODO: Integrate with actual semantic search
        # For now, return empty result

        return RetrievalResult(
            entities=[],
            relationships=[],
            confidence='none',
            method='semantic_fallback',
            anchor=None
        )
