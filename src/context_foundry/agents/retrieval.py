"""
Retrieval Agent - Builds ContextBundles by querying all three memory layers.
The core of the tri-memory query system.
"""
from typing import List, Dict, Optional, Set
from sqlalchemy.orm import Session
import uuid
import re

from ..models.schema import EntityType, RelationshipType, get_session
from ..models.context_bundle import ContextBundle, create_bundle
from ..memory.semantic import SemanticMemory
from ..memory.episodic import EpisodicMemory
from ..memory.symbolic import SymbolicMemory
from ..utils.logger import logger, QueryLogger


class RetrievalAgent:
    """
    Agent that retrieves relevant context from all three memory layers
    and assembles a ContextBundle for reasoning.
    """
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()
        self.semantic = SemanticMemory(self.session)
        self.episodic = EpisodicMemory(self.session)
        self.symbolic = SymbolicMemory(self.session)
        
        logger.info("RetrievalAgent initialized")
    
    def build_context_bundle(
        self,
        query_text: str,
        query_logger: Optional[QueryLogger] = None,
        max_entities: int = 20,
        max_documents: int = 5,
        max_rules: int = 10,
        traverse_depth: int = 2
    ) -> ContextBundle:
        """
        Build a ContextBundle by querying all memory layers.
        
        This is the main entry point for context retrieval.
        """
        bundle = create_bundle(query_text)
        
        keywords = self._extract_keywords(query_text)
        entity_types = self._infer_entity_types(query_text)
        
        if query_logger:
            query_logger.log_event("RETRIEVAL_START", {
                "keywords": keywords,
                "inferred_entity_types": [t.value for t in entity_types]
            })
        
        semantic_results = self._query_semantic_memory(
            keywords, entity_types, traverse_depth, max_entities, query_logger
        )
        bundle.semantic_entities = semantic_results["entities"]
        bundle.semantic_relationships = semantic_results["relationships"]
        
        episodic_results = self._query_episodic_memory(
            query_text, keywords, max_documents, query_logger
        )
        bundle.episodic_documents = episodic_results
        
        relationship_types = [r.get("relationship_type") for r in bundle.semantic_relationships]
        entity_type_strs = [e.get("entity_type") for e in bundle.semantic_entities]
        
        symbolic_results = self._query_symbolic_memory(
            query_text, keywords, entity_type_strs, relationship_types, max_rules, query_logger
        )
        bundle.symbolic_rules = symbolic_results
        
        bundle.calculate_uncertainty()
        
        bundle.retrieval_metadata = {
            "keywords": keywords,
            "entity_types_searched": [t.value for t in entity_types],
            "traverse_depth": traverse_depth
        }
        
        if query_logger:
            query_logger.log_context_bundle({
                "query_id": bundle.query_id,
                "semantic_count": len(bundle.semantic_entities) + len(bundle.semantic_relationships),
                "episodic_count": len(bundle.episodic_documents),
                "rules_count": len(bundle.symbolic_rules),
                "confidence": bundle.confidence
            })
        
        return bundle
    
    def _extract_keywords(self, query_text: str) -> List[str]:
        """Extract meaningful keywords from the query."""
        stop_words = {
            'what', 'who', 'which', 'when', 'where', 'how', 'why',
            'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did',
            'will', 'would', 'could', 'should', 'may', 'might',
            'the', 'a', 'an', 'this', 'that', 'these', 'those',
            'i', 'you', 'he', 'she', 'it', 'we', 'they',
            'and', 'or', 'but', 'if', 'for', 'to', 'of', 'in', 'on', 'at',
            'by', 'with', 'about', 'as', 'from'
        }
        
        words = re.findall(r'\b[a-zA-Z][\w-]*\b', query_text)
        
        keywords = [w for w in words if w.lower() not in stop_words and len(w) > 2]
        
        return keywords
    
    def _infer_entity_types(self, query_text: str) -> List[EntityType]:
        """Infer which entity types are relevant based on query content."""
        query_lower = query_text.lower()
        types = []
        
        if any(w in query_lower for w in ['database', 'db', 'postgres', 'mysql', 'redis']):
            types.append(EntityType.DATABASE)
        if any(w in query_lower for w in ['service', 'api', 'endpoint']):
            types.append(EntityType.SERVICE)
        if any(w in query_lower for w in ['team', 'group', 'department']):
            types.append(EntityType.TEAM)
        if any(w in query_lower for w in ['person', 'who', 'engineer', 'lead', 'escalat', 'contact']):
            types.append(EntityType.PERSON)
        if any(w in query_lower for w in ['incident', 'outage', 'failure', 'sev1', 'sev2']):
            types.append(EntityType.INCIDENT)
        if any(w in query_lower for w in ['runbook', 'procedure', 'playbook', 'how to']):
            types.append(EntityType.RUNBOOK)
        if any(w in query_lower for w in ['component', 'cache', 'queue']):
            types.append(EntityType.COMPONENT)
        
        return types if types else list(EntityType)
    
    def _query_semantic_memory(
        self,
        keywords: List[str],
        entity_types: List[EntityType],
        traverse_depth: int,
        max_entities: int,
        query_logger: Optional[QueryLogger]
    ) -> Dict:
        """Query semantic memory (knowledge graph) for relevant entities and relationships."""
        entities = []
        relationships = []
        seen_entity_ids: Set[str] = set()
        
        for keyword in keywords:
            found = self.semantic.search_entities(
                keyword,
                entity_types=entity_types if entity_types else None,
                trusted_only=True,
                limit=5
            )
            
            for entity in found:
                entity_dict = entity.to_dict()
                if entity_dict["id"] not in seen_entity_ids:
                    seen_entity_ids.add(entity_dict["id"])
                    entities.append(entity_dict)
        
        entities_to_traverse = list(entities)[:10]
        
        for entity in entities_to_traverse:
            entity_id = uuid.UUID(entity["id"])
            
            rels = self.semantic.get_entity_relationships(
                entity_id,
                direction="both",
                trusted_only=True
            )
            
            for rel_info in rels:
                rel_dict = rel_info["relationship"]
                if rel_dict not in relationships:
                    relationships.append(rel_dict)
                
                connected = rel_info["connected_entity"]
                if connected["id"] not in seen_entity_ids:
                    seen_entity_ids.add(connected["id"])
                    entities.append(connected)
        
        entities = entities[:max_entities]
        
        if query_logger:
            avg_conf = sum(e.get("confidence", 0) for e in entities) / len(entities) if entities else 0
            query_logger.log_semantic_retrieval(entities, relationships, avg_conf)
        
        logger.debug(f"Semantic query: {len(entities)} entities, {len(relationships)} relationships")
        
        return {
            "entities": entities,
            "relationships": relationships
        }
    
    def _query_episodic_memory(
        self,
        query_text: str,
        keywords: List[str],
        max_documents: int,
        query_logger: Optional[QueryLogger]
    ) -> List[Dict]:
        """Query episodic memory (vector store) for similar documents."""
        documents = self.episodic.search_similar(
            query_text,
            limit=max_documents,
            min_similarity=0.0
        )
        
        if len(documents) < max_documents and keywords:
            keyword_docs = self.episodic.search_by_keywords(
                keywords,
                limit=max_documents - len(documents)
            )
            
            seen_ids = {d["id"] for d in documents}
            for doc in keyword_docs:
                if doc["id"] not in seen_ids:
                    documents.append(doc)
        
        if query_logger:
            similarities = [d.get("similarity", 0) for d in documents]
            query_logger.log_episodic_retrieval(documents, similarities)
        
        logger.debug(f"Episodic query: {len(documents)} documents")
        
        return documents
    
    def _query_symbolic_memory(
        self,
        query_text: str,
        keywords: List[str],
        entity_types: List[str],
        relationship_types: List[str],
        max_rules: int,
        query_logger: Optional[QueryLogger]
    ) -> List[Dict]:
        """Query symbolic memory for applicable rules."""
        rules = self.symbolic.find_applicable_rules(
            entity_types=entity_types,
            relationship_types=relationship_types,
            query_keywords=keywords
        )
        
        rules = rules[:max_rules]
        
        if query_logger:
            query_logger.log_event("SYMBOLIC_QUERY", {
                "rules_found": len(rules),
                "rule_names": [r["name"] for r in rules]
            })
        
        logger.debug(f"Symbolic query: {len(rules)} applicable rules")
        
        return rules
    
    def get_impact_analysis(self, entity_name: str) -> Dict:
        """
        Special retrieval for impact analysis queries.
        "What services are affected if X goes down?"
        """
        impact = self.semantic.find_impact_chain(entity_name)
        
        if impact.get("impacted"):
            affected_names = [i["entity"]["name"] for i in impact["impacted"]]
            docs = self.episodic.search_by_keywords(
                affected_names[:5],
                doc_types=["RUNBOOK"],
                limit=3
            )
            impact["related_runbooks"] = docs
        
        return impact
    
    def get_escalation_path(self, start_point: str) -> Dict:
        """
        Special retrieval for escalation queries.
        "Who should I escalate to for X?"
        """
        entity = self.semantic.find_entity_by_name(start_point)
        if not entity:
            return {"error": f"Entity not found: {start_point}", "path": []}
        
        path = self.semantic.find_escalation_path(start_point)
        
        escalation_rules = self.symbolic.get_escalation_rules()
        
        return {
            "start_point": entity.to_dict(),
            "escalation_path": path,
            "applicable_rules": [r.to_dict() for r in escalation_rules]
        }
