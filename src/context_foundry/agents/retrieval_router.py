"""
Retrieval Router

Routes queries to the optimal retrieval strategy based on classification:
- GRAPH_ONLY: Use knowledge graph for relationships
- DOCS_ONLY: Use document search for specific values
- HYBRID: Use both in parallel
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import text
import concurrent.futures
import re

from src.context_foundry.agents.query_classifier import QueryClassification, classify_query_type
from src.context_foundry.agents.role_resolver import RoleResolution
from src.context_foundry.agents.query_intent_detector import (
    QueryIntent,
    QueryIntentDetector,
    DirectedRelationshipRetriever,
    DirectedAttributeRetriever
)
from src.context_foundry.agents.tools.wrappers import extract_person_names
from src.context_foundry.query.intent_classifier import (
    QueryIntentClassifier,
    ClassifiedQuery,
    QueryIntent as NewQueryIntent,
    classify_query,
)
from src.context_foundry.query.entity_router import (
    EntityTypeRouter,
    EntityTypeFilter,
    get_entity_router,
)
from src.context_foundry.utils.logger import logger

# Query-time blacklist for metadata entities that should never appear in results
# These are document metadata fields that were incorrectly extracted as entities
RETRIEVAL_BLACKLIST = {
    'document owner',
    'document author',
    'author',
    'owner',
    'classification',
    'confidential',
    'internal use only',
    'board only',
}


def _is_blacklisted_entity(name: str) -> bool:
    """Check if an entity name should be filtered from retrieval results."""
    if not name:
        return True
    name_lower = name.lower().strip()
    if name_lower in RETRIEVAL_BLACKLIST:
        return True
    for blacklisted in RETRIEVAL_BLACKLIST:
        if name_lower.startswith(f"{blacklisted}:") or name_lower.startswith(f"{blacklisted} "):
            return True
    return False


# DISABLED FOR RLM TEST - was: metric-specific reranking rules
# To restore: see git history for METRIC_RERANK_RULES
METRIC_RERANK_RULES = {}


def rerank_chunks_by_metric(chunks: List[Dict], query: str) -> List[Dict]:
    """Rerank chunks to prefer those containing the correct metric type.
    
    Uses aggressive scoring to ensure correct metric type appears first.
    """
    if not chunks:
        return chunks
    
    query_lower = query.lower()
    rules_to_apply = []
    for metric, r in METRIC_RERANK_RULES.items():
        if metric in query_lower:
            rules_to_apply.append((metric, r))
    
    if not rules_to_apply:
        return chunks
    
    for metric, _ in rules_to_apply:
        logger.info(f"[CHUNK_RERANK] Applying rule for metric: {metric}")
    
    def score_chunk(chunk: Dict) -> float:
        text = (chunk.get('text', '') or '').lower()
        base_score = chunk.get('similarity', 0.5)
        adjustment = 0.0
        
        for metric, rule in rules_to_apply:
            must_contain = rule.get('must_contain', [])
            has_required = any(term in text for term in must_contain) if must_contain else True
            
            if has_required:
                for term in rule['prefer']:
                    if term in text:
                        adjustment += 0.5
            
            boost_patterns = rule.get('boost_patterns', [])
            for pattern in boost_patterns:
                if pattern in text:
                    adjustment += 1.0
                    logger.debug(f"[CHUNK_RERANK] Boosted for pattern '{pattern}'")
            
            has_preferred = any(term in text for term in rule['prefer'])
            for term in rule['demote']:
                if term in text and not has_preferred:
                    adjustment -= 1.0
        
        return base_score + adjustment
    
    scored = [(chunk, score_chunk(chunk)) for chunk in chunks]
    scored.sort(key=lambda x: x[1], reverse=True)
    
    for i, (chunk, score) in enumerate(scored[:3]):
        text_preview = (chunk.get('text', '') or '')[:80]
        logger.info(f"[CHUNK_RERANK] #{i+1} score={score:.2f}: {text_preview}...")
    
    reranked = [chunk for chunk, _ in scored]
    return reranked


@dataclass
class AmbiguityResult:
    """
    Generalized ambiguity result for queries that match multiple entities.
    
    Extensible pattern for:
    - Role queries: "Who is the CEO?" → Multiple CEOs
    - Entity queries: "Tell me about Sarah" → Multiple Sarahs
    - Department queries: "Engineering team status" → Multiple eng teams
    - Project queries: "Expansion status" → Multiple expansions
    - Location queries: "Austin office" → Multiple Austin locations
    
    This structure allows the ToolAgent to handle any type of ambiguity
    with a single response formatter.
    """
    ambiguity_type: str  # "role", "entity", "department", "project", "location", "metric"
    query_term: str  # The ambiguous term from the query
    matches: List[Dict[str, Any]] = field(default_factory=list)  # All matching items
    
    @property
    def has_multiple_matches(self) -> bool:
        return len(self.matches) > 1
    
    @property
    def single_match(self) -> Optional[Dict[str, Any]]:
        """Return the single match if only one exists."""
        return self.matches[0] if len(self.matches) == 1 else None
    
    def to_dict(self) -> dict:
        return {
            "ambiguity_type": self.ambiguity_type,
            "query_term": self.query_term,
            "matches": self.matches,
            "has_multiple_matches": self.has_multiple_matches,
            "match_count": len(self.matches)
        }


@dataclass
class RetrievalResult:
    """Combined result from retrieval operations."""
    entities: List[Dict[str, Any]] = field(default_factory=list)
    relationships: List[Dict[str, Any]] = field(default_factory=list)
    chunks: List[Dict[str, Any]] = field(default_factory=list)
    strategy_used: str = "HYBRID"
    role_resolution: Optional[RoleResolution] = None
    classification: Optional[QueryClassification] = None
    expanded_query: Optional[str] = None
    query: Optional[str] = None
    intent: Optional[Any] = None
    ambiguity: Optional[AmbiguityResult] = None
    classified_query: Optional[ClassifiedQuery] = None
    
    def to_dict(self) -> dict:
        return {
            "entities": self.entities,
            "relationships": self.relationships,
            "chunks": self.chunks,
            "strategy_used": self.strategy_used,
            "role_resolution": self.role_resolution.to_dict() if self.role_resolution else None,
            "classification": self.classification.to_dict() if self.classification else None,
            "expanded_query": self.expanded_query,
            "query": self.query,
            "ambiguity": self.ambiguity.to_dict() if self.ambiguity else None
        }
    
    @property
    def needs_disambiguation(self) -> bool:
        """Check if the result requires user disambiguation."""
        return self.ambiguity is not None and self.ambiguity.has_multiple_matches
    
    @property
    def has_data(self) -> bool:
        return bool(self.entities or self.relationships or self.chunks)


class RetrievalRouter:
    """Routes queries to optimal retrieval strategy."""
    
    DEFAULT_LIMIT = 5
    LIST_QUERY_LIMIT = 15
    
    ABBREVIATION_EXPANSIONS = {
        'ceo': 'chief executive officer',
        'cto': 'chief technology officer',
        'cfo': 'chief financial officer',
        'coo': 'chief operating officer',
        'cdo': 'chief data officer',
        'vp': 'vice president',
        'svp': 'senior vice president',
        'evp': 'executive vice president',
    }
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
    
    def _get_limit(self, classification: QueryClassification) -> int:
        """Get retrieval limit based on classification."""
        if classification.expects_list:
            return self.LIST_QUERY_LIMIT
        return self.DEFAULT_LIMIT
    
    def _resolve_person_entities(
        self,
        person_names: List[str],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Directly query the entities table for PERSON entities matching given names.
        
        This is a fallback for "graph-only" entities that exist in the database
        (e.g., extracted from spreadsheets) but have no document chunks mentioning them.
        
        Args:
            person_names: List of person names to search for
            limit: Maximum entities to return per name
            
        Returns:
            List of entity dicts with id, name, type, confidence, and properties
        """
        if not person_names:
            return []
        
        # Set RLS context for tenant isolation
        from src.context_foundry.models.schema import set_tenant_context
        set_tenant_context(self.session, self.tenant_id)
        
        entities = []
        seen_ids = set()
        
        for person_name in person_names:
            try:
                sql = text("""
                    SELECT id, name, entity_type, confidence, lifecycle_state, properties
                    FROM entities
                    WHERE tenant_id = :tenant_id
                      AND name ILIKE :name_pattern
                      AND lifecycle_state = 'TRUSTED'
                    ORDER BY confidence DESC
                    LIMIT :limit
                """)
                results = self.session.execute(sql, {
                    "tenant_id": self.tenant_id,
                    "name_pattern": f"%{person_name}%",
                    "limit": limit
                }).fetchall()
                
                for r in results:
                    entity_id = str(r.id)
                    if entity_id in seen_ids:
                        continue
                    if _is_blacklisted_entity(r.name):
                        continue
                    
                    seen_ids.add(entity_id)
                    entity_dict = {
                        "id": entity_id,
                        "name": r.name,
                        "type": r.entity_type,
                        "confidence": r.confidence,
                        "source": "direct_entity_lookup"
                    }
                    
                    # Include properties (critical for spreadsheet-extracted entities)
                    if r.properties:
                        props = r.properties
                        if isinstance(props, str):
                            import json
                            try:
                                props = json.loads(props)
                            except:
                                props = {}
                        entity_dict["properties"] = props
                    
                    entities.append(entity_dict)
                    logger.info(f"[ROUTER] Direct entity lookup found: {r.name} (type={r.entity_type}, props={bool(r.properties)})")
                    
            except Exception as e:
                logger.warning(f"[ROUTER] Direct entity lookup failed for '{person_name}': {e}")
        
        return entities
    
    def _lookup_person_role(
        self,
        person_names: List[str]
    ) -> tuple:
        """
        Directly query HOLDS_POSITION relationships for given person names.
        
        This is a specialized lookup for person-role queries like "What is Sarah Chen's role?"
        that bypasses the generic graph search which may fail due to query text matching.
        
        Args:
            person_names: List of person names to lookup roles for
            
        Returns:
            Tuple of (entities, relationships) where relationships contain HOLDS_POSITION data
        """
        if not person_names:
            return [], []
        
        from src.context_foundry.models.schema import set_tenant_context
        set_tenant_context(self.session, self.tenant_id)
        
        entities = []
        relationships = []
        seen_entity_ids = set()
        
        for person_name in person_names:
            try:
                # Find person entity
                entity_sql = text("""
                    SELECT id, name, entity_type, confidence, properties
                    FROM entities
                    WHERE tenant_id = :tenant_id
                      AND name ILIKE :name_pattern
                      AND lifecycle_state = 'TRUSTED'
                    ORDER BY confidence DESC
                    LIMIT 3
                """)
                entity_results = self.session.execute(entity_sql, {
                    "tenant_id": self.tenant_id,
                    "name_pattern": f"%{person_name}%"
                }).fetchall()
                
                for entity in entity_results:
                    entity_id = str(entity.id)
                    if entity_id in seen_entity_ids:
                        continue
                    seen_entity_ids.add(entity_id)
                    
                    # Add entity to results
                    props = entity.properties if entity.properties else {}
                    if isinstance(props, str):
                        import json
                        try:
                            props = json.loads(props)
                        except:
                            props = {}
                    
                    entities.append({
                        "id": entity_id,
                        "name": entity.name,
                        "type": entity.entity_type,
                        "confidence": entity.confidence,
                        "properties": props,
                        "source": "person_role_lookup"
                    })
                    
                    # Look for HOLDS_POSITION or similar role relationships
                    rel_sql = text("""
                        SELECT r.id, r.relationship_type, r.source_id, r.target_id,
                               r.confidence, r.provenance_text,
                               se.name as source_name, se.entity_type as source_type,
                               te.name as target_name, te.entity_type as target_type
                        FROM relationships r
                        JOIN entities se ON r.source_id = se.id
                        JOIN entities te ON r.target_id = te.id
                        WHERE r.tenant_id = :tenant_id
                          AND r.source_id = :entity_id
                          AND r.relationship_type IN ('HOLDS_POSITION', 'HAS_ROLE', 'WORKS_AS', 'IS_A')
                          AND r.lifecycle_state = 'TRUSTED'
                        ORDER BY r.confidence DESC
                        LIMIT 5
                    """)
                    rel_results = self.session.execute(rel_sql, {
                        "tenant_id": self.tenant_id,
                        "entity_id": entity_id
                    }).fetchall()
                    
                    for r in rel_results:
                        relationships.append({
                            "id": str(r.id),
                            "type": r.relationship_type,
                            "source": r.source_name,
                            "source_type": r.source_type,
                            "target": r.target_name,
                            "target_type": r.target_type,
                            "confidence": r.confidence,
                            "provenance": r.provenance_text
                        })
                        logger.info(f"[ROUTER] Person-role lookup found: {r.source_name} --[{r.relationship_type}]--> {r.target_name}")
                
            except Exception as e:
                logger.warning(f"[ROUTER] Person-role lookup failed for '{person_name}': {e}")
        
        return entities, relationships
    
    def _search_graph(
        self,
        query: str,
        classification: QueryClassification,
        role_resolution: Optional[RoleResolution] = None,
        limit: int = 5,
        classified_query: Optional[ClassifiedQuery] = None
    ) -> tuple:
        """Search knowledge graph for entities and relationships with intent-based filtering."""
        entities = []
        relationships = []
        
        search_terms = [query.lower()]
        if role_resolution and role_resolution.is_resolved:
            search_terms.append(role_resolution.resolved_name.lower())
        if classification.target_entity:
            search_terms.append(classification.target_entity.lower())
        
        entity_router = get_entity_router()
        type_filter: Optional[EntityTypeFilter] = None
        if classified_query:
            type_filter = entity_router.get_filter(classified_query)
            logger.info(f"[ROUTER] Intent-based filtering: {classified_query.primary_intent.value}")
        
        try:
            like_clauses = " OR ".join([f"LOWER(e.name) LIKE :term{i}" for i in range(len(search_terms))])
            
            type_filter_clause = ""
            if type_filter and type_filter.exclude:
                exclude_list = ", ".join([f"'{t}'" for t in type_filter.exclude])
                type_filter_clause = f" AND e.entity_type NOT IN ({exclude_list})"
            
            entity_query = text(f"""
                SELECT e.id, e.name, e.entity_type, e.confidence, e.properties
                FROM entities e
                WHERE e.tenant_id = :tenant_id
                AND ({like_clauses})
                {type_filter_clause}
                ORDER BY e.confidence DESC
                LIMIT :limit
            """)
            
            params = {"tenant_id": self.tenant_id, "limit": limit}
            for i, term in enumerate(search_terms):
                params[f"term{i}"] = f"%{term}%"
            
            entity_results = self.session.execute(entity_query, params).fetchall()
            entities = []
            for r in entity_results:
                if _is_blacklisted_entity(r.name):
                    continue
                entity_dict = {
                    "id": str(r.id),
                    "name": r.name,
                    "type": r.entity_type,
                    "confidence": r.confidence
                }
                # Include properties if available
                if r.properties:
                    props = r.properties
                    if isinstance(props, str):
                        import json
                        try:
                            props = json.loads(props)
                        except:
                            props = {}
                    entity_dict["properties"] = props
                entities.append(entity_dict)
            
            if entities:
                entity_ids = [e["id"] for e in entities]
                placeholders = ", ".join([f":eid{i}" for i in range(len(entity_ids))])
                
                rel_query = text(f"""
                    SELECT 
                        r.id, r.relationship_type, r.confidence,
                        r.provenance_text,
                        src.name as source_name, src.entity_type as source_type,
                        tgt.name as target_name, tgt.entity_type as target_type
                    FROM relationships r
                    JOIN entities src ON r.source_id = src.id
                    JOIN entities tgt ON r.target_id = tgt.id
                    WHERE r.tenant_id = :tenant_id
                    AND (r.source_id IN ({placeholders}) OR r.target_id IN ({placeholders}))
                    ORDER BY r.confidence DESC
                    LIMIT :limit
                """)
                
                rel_params = {"tenant_id": self.tenant_id, "limit": limit * 2}
                for i, eid in enumerate(entity_ids):
                    rel_params[f"eid{i}"] = eid
                
                rel_results = self.session.execute(rel_query, rel_params).fetchall()
                relationships = [
                    {
                        "id": str(r.id),
                        "type": r.relationship_type,
                        "source": r.source_name,
                        "source_type": r.source_type,
                        "target": r.target_name,
                        "target_type": r.target_type,
                        "confidence": r.confidence,
                        "provenance": r.provenance_text
                    }
                    for r in rel_results
                    if not _is_blacklisted_entity(r.source_name) and not _is_blacklisted_entity(r.target_name)
                ]
            
            logger.info(f"[ROUTER] Graph search found {len(entities)} entities, {len(relationships)} relationships")
            
        except Exception as e:
            logger.error(f"[ROUTER] Graph search failed: {e}")
        
        return entities, relationships
    
    def _search_documents(
        self,
        query: str,
        classification: QueryClassification,
        role_resolution: Optional[RoleResolution] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search document chunks using unified DocumentSearcher with hybrid keyword fallback."""
        from src.context_foundry.search.document_searcher import DocumentSearcher
        from sqlalchemy import text as sql_text
        
        search_query = query
        if role_resolution and role_resolution.is_resolved:
            search_query = f"{query} {role_resolution.resolved_name}"
        
        searcher = DocumentSearcher(self.session, self.tenant_id)
        # Fetch more results for reranking
        results = searcher.search(search_query, limit=limit * 2, use_vector=True)
        
        chunks = [
            {
                "id": r.get("id", ""),
                "text": r.get("text", ""),
                "document": r.get("document_name", "Unknown document"),
                "similarity": r.get("similarity", 0.6)
            }
            for r in results
        ]
        
        # DISABLED FOR RLM TEST - was: hybrid keyword search for specific metric queries
        # To restore: see git history for keyword_patterns logic
        keyword_patterns = []  # Disabled - RLM should handle without hardcoded patterns
        
        if False and keyword_patterns:  # Disabled
            try:
                seen_ids = {c.get("id") for c in chunks}
                for pattern in keyword_patterns:
                    sql = sql_text("""
                        SELECT id, text, 'keyword_match' as doc_name
                        FROM document_chunks
                        WHERE tenant_id = :tid AND text ILIKE :pattern
                        LIMIT 3
                    """)
                    keyword_results = self.session.execute(sql, {
                        "tid": self.tenant_id, "pattern": f"%{pattern}%"
                    }).fetchall()
                    for r in keyword_results:
                        if str(r.id) not in seen_ids:
                            seen_ids.add(str(r.id))
                            chunks.append({
                                "id": str(r.id),
                                "text": r.text or "",
                                "document": "keyword_match",
                                "similarity": 0.7
                            })
                logger.info(f"[ROUTER] Hybrid search added keyword matches for patterns: {keyword_patterns}")
            except Exception as e:
                logger.warning(f"[ROUTER] Keyword search failed: {e}")
        
        chunks = rerank_chunks_by_metric(chunks, query)
        
        logger.info(f"[ROUTER] Document search found {len(chunks)} chunks")
        return chunks[:limit]
    
    def _search_documents_for_attribute(
        self,
        intent: QueryIntent,
        resolved_name: Optional[str],
        original_role: Optional[str] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search document chunks for specific attribute using intent's search terms.
        
        Searches with both resolved_name (e.g., "Robert Thompson") AND original_role (e.g., "CIO")
        to improve recall when vector embeddings don't match person names well.
        """
        from src.context_foundry.search.document_searcher import DocumentSearcher
        
        entity_name = resolved_name or intent.target_entity
        if not entity_name:
            return []
        
        search_terms = intent.search_terms
        if not search_terms:
            search_terms = [intent.attribute_type.lower()] if intent.attribute_type else []
        
        search_entities = [entity_name]
        if original_role and original_role.lower() != entity_name.lower():
            search_entities.append(original_role)
        
        searcher = DocumentSearcher(self.session, self.tenant_id)
        all_chunks = []
        seen_ids = set()
        
        for entity in search_entities:
            for term in search_terms[:2]:
                search_query = f"{entity} {term}"
                results = searcher.search(search_query, limit=limit, use_vector=True)
                
                for r in results:
                    chunk_id = r.get("id", "")
                    if chunk_id and chunk_id not in seen_ids:
                        seen_ids.add(chunk_id)
                        all_chunks.append({
                            "id": chunk_id,
                            "text": r.get("text", ""),
                            "document": r.get("document_name", "Unknown"),
                            "similarity": r.get("similarity", 0.6)
                        })
                
                if len(all_chunks) >= limit * 2:
                    break
            if len(all_chunks) >= limit * 2:
                break
        
        # Apply metric-based reranking
        original_query = f"{entity_name} {' '.join(search_terms)}"
        all_chunks = rerank_chunks_by_metric(all_chunks, original_query)
        
        logger.info(f"[ROUTER] Attribute search found {len(all_chunks)} chunks for {entity_name}/{original_role}")
        return all_chunks[:limit]
    
    def route(
        self,
        query: str,
        classification: QueryClassification,
        role_resolution: Optional[RoleResolution] = None,
        intent: Optional[QueryIntent] = None,
        classified_query: Optional[ClassifiedQuery] = None
    ) -> RetrievalResult:
        """
        Route query to optimal retrieval strategy with intent-based entity filtering.
        
        Enhanced with query type classification for person/relationship routing:
        - 'person' queries: Call _lookup_person_role() FIRST to get KG relationships
        - 'relationship' queries: Use directed KG traversal
        - Always include KG results in the answer synthesis context
        
        Args:
            query: The user's query
            classification: Query classification result
            role_resolution: Optional resolved role info
            intent: Optional QueryIntent for directed retrieval
            classified_query: Optional ClassifiedQuery for intent-based filtering
            
        Returns:
            RetrievalResult with combined data
        """
        limit = self._get_limit(classification)
        strategy = classification.retrieval_strategy
        
        expanded_query = query
        if role_resolution and role_resolution.is_resolved:
            expanded_query = f"{query} (Note: {role_resolution.role} = {role_resolution.resolved_name})"
        
        # Enhanced query type classification for person/relationship routing
        query_type = classify_query_type(query)
        logger.info(f"[ROUTER] Query type classification: {query_type}")
        
        # Early extraction: detect person names for graph-only entity fallback
        # This handles entities from spreadsheets that have no document chunks
        detected_person_names = extract_person_names(query)
        if detected_person_names:
            logger.info(f"[ROUTER] Detected person names in query: {detected_person_names}")
        
        if classified_query:
            logger.info(f"[ROUTER] Routing with strategy={strategy}, intent={classified_query.primary_intent.value}, limit={limit}")
        else:
            logger.info(f"[ROUTER] Routing with strategy={strategy}, limit={limit}, expects_list={classification.expects_list}")
        
        result = RetrievalResult(
            strategy_used=strategy,
            role_resolution=role_resolution,
            classification=classification,
            expanded_query=expanded_query,
            classified_query=classified_query
        )
        
        # PERSON QUERY ROUTING: For person/role queries, call _lookup_person_role() FIRST
        # This ensures KG relationships (HOLDS_POSITION) are retrieved before document search
        if query_type == 'person' and detected_person_names:
            logger.info(f"[ROUTER] Person query detected - prioritizing KG person-role lookup for: {detected_person_names}")
            person_entities, role_relationships = self._lookup_person_role(detected_person_names)
            
            if person_entities or role_relationships:
                result.entities = person_entities
                result.relationships = role_relationships
                logger.info(f"[ROUTER] Person-role KG lookup: {len(person_entities)} entities, {len(role_relationships)} relationships")
                
                # Also fetch document chunks for additional context
                chunks = self._search_documents(query, classification, role_resolution, limit)
                result.chunks = chunks
                result.strategy_used = "PERSON_KG_FIRST"
                
                logger.info(f"[ROUTER] Person query complete: {len(result.entities)} entities, {len(result.relationships)} rels, {len(result.chunks)} chunks")
                return result
        
        # Handle role-title queries (e.g., "Who is the CEO?") where no person name detected
        # but role_resolution succeeded
        if query_type == 'person' and not detected_person_names:
            if classification.has_role_reference and role_resolution and role_resolution.is_resolved and role_resolution.resolved_name:
                resolved_names = [role_resolution.resolved_name]
                role_entities, role_relationships = self._lookup_person_role(resolved_names)
                if role_entities or role_relationships:
                    result.entities = role_entities
                    result.relationships = role_relationships
                    result.strategy_used = "ROLE_KG_FIRST"
                    logger.info(f"[ROUTER] Role-title KG lookup: resolved {role_resolution.role} to {role_resolution.resolved_name}")
                    
                    # Also fetch document chunks for additional context
                    chunks = self._search_documents(query, classification, role_resolution, limit)
                    result.chunks = chunks
                    
                    logger.info(f"[ROUTER] Role-title query complete: {len(result.entities)} entities, {len(result.relationships)} rels, {len(result.chunks)} chunks")
                    return result
        
        # RELATIONSHIP QUERY ROUTING: For ownership/structure queries, use directed KG traversal
        if query_type == 'relationship':
            logger.info(f"[ROUTER] Relationship query detected - using directed KG traversal")
            
            # Extract subject entity from query for directed traversal
            subject_patterns = [
                r"(?:owns|handles|manages)\s+(.+?)(?:\?|$)",
                r"(.+?)\s+(?:belongs to|reports to)",
                r"(?:which|what)\s+(?:business unit|team|department|group)\s+(?:owns|handles|manages)\s+(.+?)(?:\?|$)",
            ]
            subject = None
            for pattern in subject_patterns:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    subject = match.group(1).strip()
                    break
            
            if subject:
                logger.info(f"[ROUTER] Extracted subject entity for directed traversal: '{subject}'")
                # Direct SQL query for ownership/structure relationships
                rel_types = ('OWNS', 'OWNED_BY', 'BELONGS_TO', 'MANAGES', 'HANDLES', 'PART_OF', 'HAS_UNIT', 'CONTAINS')
                
                try:
                    from src.context_foundry.models.schema import set_tenant_context
                    set_tenant_context(self.session, self.tenant_id)
                    
                    # Query for relationships where subject is the target
                    # Use = ANY() for Postgres array binding instead of IN
                    rel_sql = text("""
                        SELECT 
                            r.id, r.relationship_type, r.confidence, r.provenance_text,
                            src.name as source_name, src.entity_type as source_type,
                            tgt.name as target_name, tgt.entity_type as target_type
                        FROM relationships r
                        JOIN entities src ON r.source_id = src.id
                        JOIN entities tgt ON r.target_id = tgt.id
                        WHERE r.tenant_id = :tenant_id
                        AND r.relationship_type = ANY(:rel_types)
                        AND LOWER(tgt.name) LIKE :subject_pattern
                        AND r.lifecycle_state = 'TRUSTED'
                        ORDER BY r.confidence DESC
                        LIMIT :limit
                    """)
                    
                    rel_results = self.session.execute(rel_sql, {
                        "tenant_id": self.tenant_id,
                        "rel_types": list(rel_types),
                        "subject_pattern": f"%{subject.lower()}%",
                        "limit": limit
                    }).fetchall()
                    
                    directed_relationships = [
                        {
                            "id": str(r.id),
                            "type": r.relationship_type,
                            "source": r.source_name,
                            "source_type": r.source_type,
                            "target": r.target_name,
                            "target_type": r.target_type,
                            "confidence": r.confidence,
                            "provenance": r.provenance_text
                        }
                        for r in rel_results
                        if not _is_blacklisted_entity(r.source_name) and not _is_blacklisted_entity(r.target_name)
                    ]
                    
                    if directed_relationships:
                        result.relationships = directed_relationships
                        logger.info(f"[ROUTER] Directed relationship retrieval found {len(directed_relationships)} matches")
                        
                        # Also get entities and chunks
                        entities, _ = self._search_graph(query, classification, role_resolution, limit, classified_query)
                        chunks = self._search_documents(query, classification, role_resolution, limit)
                        
                        result.entities = entities
                        result.chunks = chunks
                        result.strategy_used = "DIRECTED_RELATIONSHIP_TRAVERSAL"
                        
                        logger.info(f"[ROUTER] Relationship query: {len(entities)} entities, {len(directed_relationships)} rels, {len(chunks)} chunks")
                        return result
                        
                except Exception as e:
                    logger.warning(f"[ROUTER] Directed relationship query failed: {e}")
            
            # Fallback to standard graph search if directed retrieval didn't find anything
            entities, relationships = self._search_graph(query, classification, role_resolution, limit, classified_query)
            chunks = self._search_documents(query, classification, role_resolution, limit)
            
            result.entities = entities
            result.relationships = relationships
            result.chunks = chunks
            result.strategy_used = "RELATIONSHIP_KG_TRAVERSAL"
            
            logger.info(f"[ROUTER] Relationship query: {len(entities)} entities, {len(relationships)} rels, {len(chunks)} chunks")
            return result
        
        if intent and intent.intent_type == "relationship" and intent.relationship_type:
            directed_retriever = DirectedRelationshipRetriever(self.session, self.tenant_id)
            relationships = directed_retriever.retrieve(intent, limit=limit)
            
            if relationships:
                result.relationships = relationships
                logger.info(f"[ROUTER] Directed relationship retrieval found {len(relationships)} matches")
                
                entities, _ = self._search_graph(query, classification, role_resolution, limit, classified_query)
                result.entities = entities
                
                result.strategy_used = "DIRECTED_RELATIONSHIP"
                return result
            else:
                logger.info("[ROUTER] Directed retrieval empty, falling back to standard")
        
        if intent and intent.intent_type == "attribute" and intent.attribute_type:
            resolved_name = role_resolution.resolved_name if role_resolution and role_resolution.is_resolved else None
            original_role = role_resolution.role if role_resolution and role_resolution.is_resolved else None
            chunks = self._search_documents_for_attribute(intent, resolved_name, original_role, limit)
            
            if chunks:
                result.chunks = chunks
                
                entities, relationships = self._search_graph(query, classification, role_resolution, limit, classified_query)
                result.entities = entities
                result.relationships = relationships
                
                logger.info(f"[ROUTER] Directed attribute retrieval found {len(chunks)} chunks")
                result.strategy_used = "DIRECTED_ATTRIBUTE"
                return result
            else:
                logger.info("[ROUTER] Directed attribute retrieval empty, falling back to standard")
        
        if strategy == "GRAPH_ONLY":
            entities, relationships = self._search_graph(query, classification, role_resolution, limit, classified_query)
            result.entities = entities
            result.relationships = relationships
            
            kg_has_data = len(entities) > 0 or len(relationships) > 0
            if not kg_has_data or (classification.expects_list and len(relationships) < 3):
                logger.info(f"[ROUTER] GRAPH_ONLY returned insufficient data (entities={len(entities)}, rels={len(relationships)}), falling back to HYBRID")
                chunks = self._search_documents(query, classification, role_resolution, limit)
                result.chunks = chunks
                result.strategy_used = "HYBRID_FALLBACK"
            
        elif strategy == "DOCS_ONLY":
            chunks = self._search_documents(query, classification, role_resolution, limit)
            result.chunks = chunks
            
            # Also search graph to include entity properties (e.g., spreadsheet-extracted data)
            entities, relationships = self._search_graph(query, classification, role_resolution, limit, classified_query)
            if entities:
                result.entities = entities
                result.relationships = relationships
                logger.info(f"[ROUTER] DOCS_ONLY also found {len(entities)} entities from graph")
            
        else:  # HYBRID
            entities, relationships = self._search_graph(query, classification, role_resolution, limit, classified_query)
            chunks = self._search_documents(query, classification, role_resolution, limit)
            
            result.entities = entities
            result.relationships = relationships
            result.chunks = chunks
        
        # Graph-first entity resolution fallback for "graph-only" entities
        # This handles entities extracted from spreadsheets that have properties but no document chunks
        # Triggers when: person names detected AND (no entities found OR chunks don't mention the person)
        
        def chunks_mention_person(chunks: List[Dict], person_names: List[str]) -> bool:
            """Check if any chunk actually mentions any of the detected person names."""
            for chunk in chunks:
                chunk_text = (chunk.get("text") or chunk.get("content") or "").lower()
                for name in person_names:
                    if name.lower() in chunk_text:
                        return True
            return False
        
        entities_are_sparse = len(result.entities) == 0
        has_person_query = bool(detected_person_names)
        chunks_mention_target = chunks_mention_person(result.chunks, detected_person_names) if detected_person_names else True
        
        # Fallback triggers when:
        # 1. Person names detected in query, AND
        # 2. Entities are empty OR chunks don't mention the person
        should_fallback = has_person_query and (entities_are_sparse or not chunks_mention_target)
        
        if should_fallback:
            logger.info(f"[ROUTER] Triggering graph-first entity fallback: chunks={len(result.chunks)}, chunks_mention_target={chunks_mention_target}, entities={len(result.entities)}, names={detected_person_names}")
            
            # Use person-role lookup to get both entities AND relationships (e.g., HOLDS_POSITION)
            direct_entities, role_relationships = self._lookup_person_role(detected_person_names)
            
            if direct_entities:
                # Merge with existing entities (avoid duplicates)
                existing_ids = {e.get("id") for e in result.entities}
                new_entities = [e for e in direct_entities if e.get("id") not in existing_ids]
                
                if new_entities:
                    result.entities = list(result.entities) + new_entities
                    logger.info(f"[ROUTER] Graph-first fallback added {len(new_entities)} entities with properties")
                    result.strategy_used = f"{result.strategy_used}+ENTITY_FALLBACK"
            
            if role_relationships:
                # Merge relationships (avoid duplicates)
                existing_rel_ids = {r.get("id") for r in result.relationships}
                new_relationships = [r for r in role_relationships if r.get("id") not in existing_rel_ids]
                
                if new_relationships:
                    result.relationships = list(result.relationships) + new_relationships
                    logger.info(f"[ROUTER] Graph-first fallback added {len(new_relationships)} role relationships")
        
        logger.info(f"[ROUTER] Retrieved: {len(result.entities)} entities, {len(result.relationships)} rels, {len(result.chunks)} chunks")
        
        return result


class QueryPipeline:
    """
    Complete query pre-processing pipeline.
    
    Runs: Classification → Role Resolution → Intent Detection → Retrieval Routing
    
    Supports role→attribute chaining: "What is the CEO's salary?" becomes
    "What is Sarah Chen's compensation?" when CEO resolves to Sarah Chen.
    """
    
    def __init__(self, session: Session, tenant_id: str):
        self.session = session
        self.tenant_id = tenant_id
        
        from src.context_foundry.agents.query_classifier import QueryClassifier
        from src.context_foundry.agents.role_resolver import RoleResolver
        
        self.classifier = QueryClassifier()
        self.role_resolver = RoleResolver(session, tenant_id)
        self.intent_detector = QueryIntentDetector(session, tenant_id)
        self.router = RetrievalRouter(session, tenant_id)
        self.new_intent_classifier = QueryIntentClassifier()
    
    def _rewrite_query_with_person(
        self,
        original_query: str,
        person_name: Optional[str],
        intent_key: Optional[str],
        direction: Optional[str] = None
    ) -> str:
        """
        Rewrite a role-based query to use the resolved person's name.
        Uses direction field when available for relationship queries.
        
        "What is the CEO's salary?" → "What is Sarah Chen's compensation?"
        "Who reports to the CFO?" → "Who reports to James O'Brien?" (inbound)
        "Who does the CFO report to?" → "Who does James O'Brien report to?" (outbound)
        """
        key_upper = (intent_key or "").upper()
        query_lower = original_query.lower()
        
        if key_upper == "COMPENSATION" or "salary" in query_lower or "pay" in query_lower or "make" in query_lower:
            return f"What is {person_name}'s compensation?"
        
        elif key_upper in ("REPORTS", "REPORTS_TO"):
            if direction == "outbound":
                return f"Who does {person_name} report to?"
            else:
                return f"Who reports to {person_name}?"
        
        elif key_upper == "MANAGES":
            if direction == "inbound":
                return f"Who does {person_name} manage?"
            else:
                return f"Who manages {person_name}?"
        
        elif key_upper == "OWNS":
            if direction == "inbound":
                return f"What does {person_name} own?"
            else:
                return f"Who owns {person_name}?"
        
        elif key_upper == "INVESTED_IN":
            if direction == "inbound":
                return f"Who invested in {person_name}?"
            else:
                return f"What has {person_name} invested in?"
        
        elif key_upper == "DEPARTMENT":
            return f"What department is {person_name} in?"
        
        else:
            return f"Tell me about {person_name}"
    
    def process(self, query: str, vault_context: str = None) -> RetrievalResult:
        """
        Process a query through the full pipeline.
        
        1. Classify the query
        2. Detect intent early (for role→attribute chaining)
        3. Resolve any role references (using vault_context if no explicit entity)
        4. Chain attribute queries if role resolves to single person
        5. Route to optimal retrieval strategy
        
        Args:
            query: User's query
            vault_context: Name of the current vault for entity resolution
            
        Returns:
            RetrievalResult with all retrieved data
        """
        logger.info(f"[PIPELINE] Processing query: '{query}' (vault_context={vault_context})")
        
        classified_query = self.new_intent_classifier.classify(query)
        logger.info(f"[PIPELINE] Intent classification: {classified_query.primary_intent.value} (confidence={classified_query.confidence:.2f})")
        
        classification = self.classifier.classify(query)
        
        intent = self.intent_detector.detect(query, resolved_entity=None)
        
        skip_role_resolution = classified_query.primary_intent in (
            NewQueryIntent.POLICY,
            NewQueryIntent.METRIC,
            NewQueryIntent.TEMPORAL,
        )
        if skip_role_resolution:
            logger.info(f"[PIPELINE] Skipping role resolution for {classified_query.primary_intent.value} intent")
        
        role_resolution = None
        if classification.has_role_reference and classification.role_referenced and not skip_role_resolution:
            role_resolution = self.role_resolver.resolve_all(classification.role_referenced, vault_context=vault_context)
            
            should_chain = (
                intent 
                and intent.intent_type in ("attribute", "relationship")
                and role_resolution.is_resolved 
                and not role_resolution.has_multiple_matches
            )
            
            if should_chain:
                person_name = role_resolution.resolved_name
                intent_key = intent.attribute_type or intent.relationship_type
                rewritten_query = self._rewrite_query_with_person(
                    query, person_name, intent_key, direction=intent.direction
                )
                
                logger.info(f"[PIPELINE] Chaining role→{intent.intent_type} (dir={intent.direction}): '{query}' → '{rewritten_query}'")
                return self.process(rewritten_query, vault_context)
            
            if role_resolution.has_multiple_matches:
                if intent and intent.intent_type in ("attribute", "relationship") and vault_context:
                    primary_match = role_resolution.all_matches[0] if role_resolution.all_matches else None
                    if primary_match:
                        orgs = primary_match.get("organizations", [])
                        vault_lower = vault_context.lower() if vault_context else ""
                        has_vault_match = any(
                            org and vault_lower in org.lower() 
                            for org in orgs
                        )
                        
                        if has_vault_match:
                            person_name = primary_match.get("name")
                            if person_name:
                                intent_key = intent.attribute_type or intent.relationship_type
                                rewritten_query = self._rewrite_query_with_person(
                                    query, person_name, intent_key, direction=intent.direction
                                )
                                logger.info(f"[PIPELINE] Chaining role→{intent.intent_type} (dir={intent.direction}, vault match): '{query}' → '{rewritten_query}'")
                                return self.process(rewritten_query, vault_context)
                
                logger.info(f"[PIPELINE] Multiple matches for role '{classification.role_referenced}': {len(role_resolution.all_matches)} - disambiguation required")
                
                ambiguity = AmbiguityResult(
                    ambiguity_type="role",
                    query_term=classification.role_referenced,
                    matches=role_resolution.all_matches
                )
                
                result = RetrievalResult(
                    entities=[],
                    relationships=[],
                    chunks=[],
                    strategy_used="DISAMBIGUATION",
                    query=query,
                    classification=classification,
                    role_resolution=role_resolution,
                    intent=intent,
                    ambiguity=ambiguity
                )
                return result
        
        if not classification.target_entity and vault_context:
            if not role_resolution or not role_resolution.is_resolved:
                logger.info(f"[PIPELINE] Injected vault context as target_entity: {vault_context}")
                classification.target_entity = vault_context
            else:
                logger.info(f"[PIPELINE] Skipping vault context injection - role already resolved")
        
        resolved_entity = role_resolution.resolved_name if role_resolution and role_resolution.is_resolved else None
        intent = self.intent_detector.detect(query, resolved_entity)
        
        if intent.intent_type != "general":
            logger.info(f"[PIPELINE] Detected intent: {intent.intent_type}={intent.relationship_type or intent.attribute_type}")
        
        result = self.router.route(query, classification, role_resolution, intent, classified_query)
        
        logger.info(f"[PIPELINE] Complete: strategy={result.strategy_used}, has_data={result.has_data}")
        
        return result
