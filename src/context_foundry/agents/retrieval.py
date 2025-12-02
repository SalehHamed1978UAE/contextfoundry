"""
Retrieval Agent - Builds ContextBundles by querying all three memory layers.
The core of the tri-memory query system.

CRITICAL: This agent now tracks "target entity" - the specific entity being queried.
If the target entity doesn't exist in the graph, we flag this explicitly to prevent
the LLM from hallucinating answers about non-existent entities.
"""
from typing import List, Dict, Optional, Set, Tuple
from sqlalchemy.orm import Session
import uuid
import re

from ..models.schema import EntityType, RelationshipType, get_session, Entity
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
        
        CRITICAL: We now track "target entity" - the specific entity being queried.
        If it doesn't exist, we flag this to prevent hallucinations.
        """
        bundle = create_bundle(query_text)
        
        keywords = self._extract_keywords(query_text)
        entity_types = self._infer_entity_types(query_text)
        
        # CRITICAL: Extract and verify target entity FIRST
        target_entity_name = self._extract_target_entity(query_text)
        if target_entity_name:
            found, entity_match = self._verify_target_entity_exists(target_entity_name)
            bundle.target_entity_name = target_entity_name
            bundle.target_entity_found = found
            bundle.target_entity_match = entity_match
            
            if query_logger:
                query_logger.log_event("TARGET_ENTITY_CHECK", {
                    "target_entity": target_entity_name,
                    "found": found,
                    "match": entity_match.get("name") if entity_match else None
                })
            
            if not found:
                logger.warning(f"TARGET ENTITY NOT FOUND: '{target_entity_name}' does not exist in knowledge graph")
        
        if query_logger:
            query_logger.log_event("RETRIEVAL_START", {
                "keywords": keywords,
                "inferred_entity_types": [t.value for t in entity_types],
                "target_entity": target_entity_name,
                "target_entity_found": bundle.target_entity_found
            })
        
        # If we couldn't extract a target entity from patterns, try fallback detection
        # Look for any capitalized multi-word phrases that look like entity names
        if not target_entity_name:
            potential_entities = self._find_potential_entity_names(query_text)
            if potential_entities:
                # Check each potential entity
                for pe in potential_entities:
                    found, entity_match = self._verify_target_entity_exists(pe)
                    if not found:
                        # Found a potential entity that doesn't exist - flag it
                        bundle.target_entity_name = pe
                        bundle.target_entity_found = False
                        bundle.target_entity_match = None
                        logger.warning(f"POTENTIAL ENTITY NOT FOUND: '{pe}' detected in query but not in graph")
                        break
        
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
    
    def _extract_target_entity(self, query_text: str) -> Optional[str]:
        """
        Extract the specific entity the query is asking about.
        
        This is CRITICAL for preventing hallucinations - we need to know if
        the entity being queried actually exists in the graph.
        
        Extended patterns to catch diverse query phrasings:
        - "the X" where X is a named entity
        - "X goes down" / "X fails" 
        - "depends on X" / "depend on X"
        - "owned by X" / "owns X" / "who owns X"
        - "escalate to X for Y" / "X escalation"
        - "incidents for X" / "X incidents"
        - Entity names in quotes
        - Capitalized multi-word entity-like names (fallback)
        
        Now case-insensitive to catch lowercase queries like "search service".
        """
        # Entity type suffixes we look for (case-insensitive)
        ENTITY_SUFFIXES = r'(?:[Ss]ervice|[Dd]atabase|[Tt]eam|[Cc]ache|[Qq]ueue|[Gg]ateway|API|api|[Ss]ystem|[Ee]ngine|[Pp]latform|[Cc]luster)'
        # Entity pattern - now accepts both lower and upper case starting letters
        ENTITY_PATTERN = rf'([A-Za-z][a-zA-Z]*(?:\s+[A-Za-z][a-zA-Z]*)*(?:\s+{ENTITY_SUFFIXES})?)'
        
        # Pattern 1: Quoted entity names (highest priority)
        quoted = re.findall(r'["\']([^"\']+)["\']', query_text)
        if quoted:
            return quoted[0]
        
        # Pattern 2: "the <Entity Name>" - captures multi-word names
        the_pattern = re.search(
            rf'\bthe\s+{ENTITY_PATTERN}\b',
            query_text, re.IGNORECASE
        )
        if the_pattern:
            return self._normalize_entity_name(the_pattern.group(1))
        
        # Pattern 3: "<Entity> goes down" / "<Entity> fails" / "<Entity> is down"
        fails_pattern = re.search(
            rf'\b{ENTITY_PATTERN}\s+(?:goes?\s+down|fails?|is\s+down|crashes?|times?\s+out)\b',
            query_text, re.IGNORECASE
        )
        if fails_pattern:
            return self._normalize_entity_name(fails_pattern.group(1))
        
        # Pattern 4: "depends on <Entity>" / "depend on <Entity>"
        depends_pattern = re.search(
            rf'\bdepends?\s+on\s+(?:the\s+)?{ENTITY_PATTERN}\b',
            query_text, re.IGNORECASE
        )
        if depends_pattern:
            return self._normalize_entity_name(depends_pattern.group(1))
        
        # Pattern 5: "if <Entity>" (impact analysis)
        if_pattern = re.search(
            rf'\bif\s+(?:the\s+)?{ENTITY_PATTERN}\b',
            query_text, re.IGNORECASE
        )
        if if_pattern:
            return self._normalize_entity_name(if_pattern.group(1))
        
        # Pattern 6: "who owns <Entity>" / "owns <Entity>" / "owner of <Entity>"
        owns_pattern = re.search(
            rf'\b(?:who\s+owns?|owns?|owner\s+of)\s+(?:the\s+)?{ENTITY_PATTERN}\b',
            query_text, re.IGNORECASE
        )
        if owns_pattern:
            return self._normalize_entity_name(owns_pattern.group(1))
        
        # Pattern 7: "<Entity> escalation" / "escalate for <Entity>" / "escalation path for <Entity>"
        escalation_pattern = re.search(
            rf'\b(?:{ENTITY_PATTERN}\s+escalation|escalat\w+\s+(?:for|to|path\s+for)\s+(?:the\s+)?{ENTITY_PATTERN})\b',
            query_text, re.IGNORECASE
        )
        if escalation_pattern:
            result = escalation_pattern.group(1) or escalation_pattern.group(2)
            return self._normalize_entity_name(result) if result else None
        
        # Pattern 8: "incidents for <Entity>" / "<Entity> incidents" / "issues with <Entity>"
        incident_pattern = re.search(
            rf'\b(?:incidents?\s+(?:for|on|with|involving)\s+(?:the\s+)?{ENTITY_PATTERN}|{ENTITY_PATTERN}\s+incidents?)\b',
            query_text, re.IGNORECASE
        )
        if incident_pattern:
            result = incident_pattern.group(1) or incident_pattern.group(2)
            return self._normalize_entity_name(result) if result else None
        
        # Pattern 9: "responsible for <Entity>" / "team for <Entity>"
        responsible_pattern = re.search(
            rf'\b(?:responsible\s+for|team\s+for|in\s+charge\s+of)\s+(?:the\s+)?{ENTITY_PATTERN}\b',
            query_text, re.IGNORECASE
        )
        if responsible_pattern:
            return self._normalize_entity_name(responsible_pattern.group(1))
        
        # Pattern 10: "about <Entity>" / "regarding <Entity>"
        about_pattern = re.search(
            rf'\b(?:about|regarding|concerning|for)\s+(?:the\s+)?{ENTITY_PATTERN}\b',
            query_text, re.IGNORECASE
        )
        if about_pattern:
            return self._normalize_entity_name(about_pattern.group(1))
        
        # Pattern 11: FALLBACK - Any multi-word phrase ending with entity suffix (case-insensitive)
        # This catches cases like "search service" at the start or middle of query
        fallback_pattern = re.search(
            rf'\b([A-Za-z][a-zA-Z]*(?:\s+[A-Za-z][a-zA-Z]*)*\s+{ENTITY_SUFFIXES})\b',
            query_text, re.IGNORECASE
        )
        if fallback_pattern:
            return self._normalize_entity_name(fallback_pattern.group(1))
        
        return None
    
    def _normalize_entity_name(self, name: str) -> str:
        """
        Normalize entity name to title case for consistent database lookups.
        Handles special cases like 'API' which should stay uppercase.
        """
        if not name:
            return name
        
        # Special tokens that should stay uppercase
        special_tokens = {'API', 'DB', 'SRE', 'SEV1', 'SEV2', 'SEV3'}
        
        words = name.split()
        normalized = []
        for word in words:
            upper = word.upper()
            if upper in special_tokens:
                normalized.append(upper)
            else:
                normalized.append(word.title())
        
        return ' '.join(normalized)
    
    def _verify_target_entity_exists(self, target_name: str) -> Tuple[bool, Optional[Dict]]:
        """
        Check if the target entity actually exists in the knowledge graph.
        
        Returns (found, entity_dict) tuple.
        """
        if not target_name:
            return False, None
        
        # Search for exact match first
        entity = self.semantic.find_entity_by_name(target_name)
        if entity:
            return True, entity.to_dict()
        
        # Try case-insensitive search
        results = self.session.query(Entity).filter(
            Entity.name.ilike(target_name),
            Entity.lifecycle_state == 'TRUSTED'
        ).first()
        
        if results:
            return True, results.to_dict()
        
        # Try partial match for multi-word names
        words = target_name.split()
        if len(words) > 1:
            # Try searching for the full phrase
            results = self.session.query(Entity).filter(
                Entity.name.ilike(f"%{target_name}%"),
                Entity.lifecycle_state == 'TRUSTED'
            ).first()
            
            if results:
                return True, results.to_dict()
        
        return False, None
    
    def _find_potential_entity_names(self, query_text: str) -> List[str]:
        """
        Find potential entity names in the query that might need verification.
        
        This is a fallback for when pattern-based extraction fails.
        Looks for multi-word phrases that look like entity names (case-insensitive).
        Returns title-cased versions for consistent comparison.
        """
        # Entity type suffixes (case-insensitive)
        ENTITY_SUFFIXES = r'(?:[Ss]ervice|[Dd]atabase|[Tt]eam|[Cc]ache|[Qq]ueue|[Gg]ateway|API|api|[Ss]ystem|[Ee]ngine|[Pp]latform|[Cc]luster)'
        
        # Find all phrases that end with an entity suffix (case-insensitive)
        pattern = rf'\b([A-Za-z][a-zA-Z]*(?:\s+[A-Za-z][a-zA-Z]*)*\s+{ENTITY_SUFFIXES})\b'
        matches = re.findall(pattern, query_text, re.IGNORECASE)
        
        # Also check for phrases that might be entity names without suffix
        # But only if they're 2+ words (e.g., "api gateway", "payment processor")
        alt_pattern = r'\b([A-Za-z][a-zA-Z]+\s+[A-Za-z][a-zA-Z]+(?:\s+[A-Za-z][a-zA-Z]+)?)\b'
        alt_matches = re.findall(alt_pattern, query_text)
        
        # Combine and dedupe, convert to title case for consistent comparison
        all_matches = list(set(matches + alt_matches))
        
        # Filter out common false positives (check lowercase version)
        false_positives = {'what', 'who', 'where', 'when', 'how', 'which', 'the', 'are', 'does', 'can'}
        filtered = [m for m in all_matches if m.split()[0].lower() not in false_positives]
        
        # Convert to title case for consistent database lookups
        title_cased = [m.title() for m in filtered]
        
        # Sort by length (longer matches first) to prefer more specific entities
        return sorted(title_cased, key=len, reverse=True)
    
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
