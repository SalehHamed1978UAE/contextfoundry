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

from src.context_foundry.agents.query_classifier import QueryClassification
from src.context_foundry.agents.role_resolver import RoleResolution
from src.context_foundry.agents.query_intent_detector import (
    QueryIntent,
    QueryIntentDetector,
    DirectedRelationshipRetriever,
    DirectedAttributeRetriever
)
from src.context_foundry.utils.logger import logger


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
    
    def _search_graph(
        self,
        query: str,
        classification: QueryClassification,
        role_resolution: Optional[RoleResolution] = None,
        limit: int = 5
    ) -> tuple:
        """Search knowledge graph for entities and relationships."""
        entities = []
        relationships = []
        
        search_terms = [query.lower()]
        if role_resolution and role_resolution.is_resolved:
            search_terms.append(role_resolution.resolved_name.lower())
        if classification.target_entity:
            search_terms.append(classification.target_entity.lower())
        
        try:
            like_clauses = " OR ".join([f"LOWER(e.name) LIKE :term{i}" for i in range(len(search_terms))])
            
            entity_query = text(f"""
                SELECT e.id, e.name, e.entity_type, e.confidence
                FROM entities e
                WHERE e.tenant_id = :tenant_id
                AND ({like_clauses})
                ORDER BY e.confidence DESC
                LIMIT :limit
            """)
            
            params = {"tenant_id": self.tenant_id, "limit": limit}
            for i, term in enumerate(search_terms):
                params[f"term{i}"] = f"%{term}%"
            
            entity_results = self.session.execute(entity_query, params).fetchall()
            entities = [
                {
                    "id": str(r.id),
                    "name": r.name,
                    "type": r.entity_type,
                    "confidence": r.confidence
                }
                for r in entity_results
            ]
            
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
        """Search document chunks using unified DocumentSearcher."""
        from src.context_foundry.search.document_searcher import DocumentSearcher
        
        search_query = query
        if role_resolution and role_resolution.is_resolved:
            search_query = f"{query} {role_resolution.resolved_name}"
        
        searcher = DocumentSearcher(self.session, self.tenant_id)
        results = searcher.search(search_query, limit=limit, use_vector=True)
        
        chunks = [
            {
                "id": r.get("id", ""),
                "text": r.get("text", ""),
                "document": r.get("document_name", "Unknown document"),
                "similarity": r.get("similarity", 0.6)
            }
            for r in results
        ]
        
        logger.info(f"[ROUTER] Document search found {len(chunks)} chunks")
        return chunks
    
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
        
        logger.info(f"[ROUTER] Attribute search found {len(all_chunks)} chunks for {entity_name}/{original_role}")
        return all_chunks[:limit]
    
    def route(
        self,
        query: str,
        classification: QueryClassification,
        role_resolution: Optional[RoleResolution] = None,
        intent: Optional[QueryIntent] = None
    ) -> RetrievalResult:
        """
        Route query to optimal retrieval strategy.
        
        Args:
            query: The user's query
            classification: Query classification result
            role_resolution: Optional resolved role info
            intent: Optional QueryIntent for directed retrieval
            
        Returns:
            RetrievalResult with combined data
        """
        limit = self._get_limit(classification)
        strategy = classification.retrieval_strategy
        
        expanded_query = query
        if role_resolution and role_resolution.is_resolved:
            expanded_query = f"{query} (Note: {role_resolution.role} = {role_resolution.resolved_name})"
        
        logger.info(f"[ROUTER] Routing with strategy={strategy}, limit={limit}, expects_list={classification.expects_list}")
        
        result = RetrievalResult(
            strategy_used=strategy,
            role_resolution=role_resolution,
            classification=classification,
            expanded_query=expanded_query
        )
        
        if intent and intent.intent_type == "relationship" and intent.relationship_type:
            directed_retriever = DirectedRelationshipRetriever(self.session, self.tenant_id)
            relationships = directed_retriever.retrieve(intent, limit=limit)
            
            if relationships:
                result.relationships = relationships
                logger.info(f"[ROUTER] Directed relationship retrieval found {len(relationships)} matches")
                
                entities, _ = self._search_graph(query, classification, role_resolution, limit)
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
                
                entities, relationships = self._search_graph(query, classification, role_resolution, limit)
                result.entities = entities
                result.relationships = relationships
                
                logger.info(f"[ROUTER] Directed attribute retrieval found {len(chunks)} chunks")
                result.strategy_used = "DIRECTED_ATTRIBUTE"
                return result
            else:
                logger.info("[ROUTER] Directed attribute retrieval empty, falling back to standard")
        
        if strategy == "GRAPH_ONLY":
            entities, relationships = self._search_graph(query, classification, role_resolution, limit)
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
            
        else:  # HYBRID
            entities, relationships = self._search_graph(query, classification, role_resolution, limit)
            chunks = self._search_documents(query, classification, role_resolution, limit)
            
            result.entities = entities
            result.relationships = relationships
            result.chunks = chunks
        
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
    
    def _rewrite_query_with_person(
        self,
        original_query: str,
        person_name: Optional[str],
        attribute_type: Optional[str]
    ) -> str:
        """
        Rewrite a role-based query to use the resolved person's name.
        
        "What is the CEO's salary?" → "What is Sarah Chen's compensation?"
        "Who reports to the CFO?" → "Who reports to James O'Brien?"
        """
        attr_upper = (attribute_type or "").upper()
        query_lower = original_query.lower()
        
        if attr_upper == "COMPENSATION" or "salary" in query_lower or "pay" in query_lower or "make" in query_lower:
            return f"What is {person_name}'s compensation?"
        
        elif attr_upper == "REPORTS" or "report" in query_lower:
            if "reports to" in query_lower or "report to" in query_lower:
                return f"Who does {person_name} report to?"
            else:
                return f"Who reports to {person_name}?"
        
        elif attr_upper == "DEPARTMENT":
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
        
        classification = self.classifier.classify(query)
        
        intent = self.intent_detector.detect(query, resolved_entity=None)
        
        role_resolution = None
        if classification.has_role_reference and classification.role_referenced:
            role_resolution = self.role_resolver.resolve_all(classification.role_referenced, vault_context=vault_context)
            
            if (intent 
                and intent.intent_type == "attribute" 
                and role_resolution.is_resolved 
                and not role_resolution.has_multiple_matches):
                
                person_name = role_resolution.resolved_name
                rewritten_query = self._rewrite_query_with_person(
                    query, person_name, intent.attribute_type
                )
                
                logger.info(f"[PIPELINE] Chaining role→attribute: '{query}' → '{rewritten_query}'")
                return self.process(rewritten_query, vault_context)
            
            if role_resolution.has_multiple_matches:
                if intent and intent.intent_type == "attribute" and vault_context:
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
                                rewritten_query = self._rewrite_query_with_person(
                                    query, person_name, intent.attribute_type
                                )
                                logger.info(f"[PIPELINE] Chaining role→attribute (vault match): '{query}' → '{rewritten_query}'")
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
        
        result = self.router.route(query, classification, role_resolution, intent)
        
        logger.info(f"[PIPELINE] Complete: strategy={result.strategy_used}, has_data={result.has_data}")
        
        return result
