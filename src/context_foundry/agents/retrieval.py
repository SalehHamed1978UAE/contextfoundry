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
import os
import json

from openai import OpenAI

from ..models.schema import LifecycleState, get_session, Entity
from ..models.context_bundle import ContextBundle, create_bundle
from ..memory.semantic import SemanticMemory
from ..memory.episodic import EpisodicMemory
from ..memory.symbolic import SymbolicMemory
from ..utils.logger import logger, QueryLogger
from ..config.domain_schema import get_schema_loader, DomainSchema, TraversalResult
from ..memory.inference import InferenceEngine
from .entity_resolver import EntityResolver, ResolveResult

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")


def _build_property_query_schema(schema: DomainSchema) -> str:
    """
    Build a domain-agnostic property query schema prompt.
    
    Uses the currently loaded schema to determine valid entity types and their fields.
    """
    entity_types_str = ", ".join([f'"{t}"' for t in schema.get_entity_type_names()])
    
    entity_descriptions = []
    for entity_type in schema.get_entity_type_names():
        config = schema.get_entity_type(entity_type)
        if config:
            fields = config.get_all_fields()
            if fields:
                field_desc = "\n".join([f"- {f}" for f in fields])
                entity_descriptions.append(f"{entity_type}:\n{field_desc}")
            else:
                entity_descriptions.append(f"{entity_type}: (properties determined by content)")
    
    entity_properties = "\n\n".join(entity_descriptions) if entity_descriptions else "Entity properties are determined by domain content."
    
    return f"""You are a query analyzer for a knowledge graph system.

CURRENT DOMAIN: {schema.domain}

ENTITY TYPES and their QUERYABLE PROPERTIES:

{entity_properties}

Analyze the query and determine if it's asking for entities filtered by their properties.
Return a JSON object with:
- needs_property_search: boolean - true if this query needs property-based filtering
- entity_type: One of [{entity_types_str}] or null
- filters: array of filter objects, each with:
  - property: the property name
  - contains: value to search for (use for partial matches, lists, or text search)
  - equals: exact value match (use for exact matches)
- intersection_logic: "AND" or "OR" - how multiple filters should be combined

EXAMPLES:
Query: "Which entities have a specific property value?"
{{
  "needs_property_search": true,
  "entity_type": "ENTITY_TYPE",
  "filters": [{{"property": "property_name", "contains": "value"}}],
  "intersection_logic": "AND"
}}

Query: "What depends on X?" or "Who is X?"
{{
  "needs_property_search": false,
  "entity_type": null,
  "filters": [],
  "intersection_logic": "AND"
}}"""


PROPERTY_QUERY_SCHEMA = None


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
        self.entity_resolver = EntityResolver(session=self.session)
        
        self._llm_client = None
        
        logger.info("RetrievalAgent initialized")
    
    @property
    def llm_client(self):
        """Lazy load LLM client for property query analysis."""
        if self._llm_client is None:
            self._llm_client = OpenAI(
                api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
                base_url=AI_INTEGRATIONS_OPENAI_BASE_URL
            )
        return self._llm_client
    
    def analyze_property_query(self, query_text: str) -> Dict:
        """
        Use LLM to analyze if query needs property-based filtering.
        
        DOMAIN-AGNOSTIC: Uses the currently loaded schema to determine
        valid entity types for property filtering.
        
        Returns structured filter specification:
        {
            "needs_property_search": bool,
            "entity_type": str | None (one of current schema's entity types),
            "filters": [{"property": "...", "contains": "..."}],
            "intersection_logic": "AND" | "OR"
        }
        """
        try:
            schema = get_schema_loader().schema
            property_query_prompt = _build_property_query_schema(schema)
            
            response = self.llm_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": property_query_prompt},
                    {"role": "user", "content": f"Analyze this query:\n\n{query_text}"}
                ],
                temperature=0.0,
                max_completion_tokens=500,
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content
            result = json.loads(response_text)
            
            logger.debug(f"Property query analysis: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Property query analysis failed: {e}")
            return {
                "needs_property_search": False,
                "entity_type": None,
                "filters": [],
                "intersection_logic": "AND"
            }
    
    def build_context_bundle(
        self,
        query_text: str,
        query_logger: Optional[QueryLogger] = None,
        max_entities: int = 20,
        max_documents: int = 5,
        max_rules: int = 10,
        traverse_depth: int = 2,
        as_of_date: Optional[str] = None
    ) -> ContextBundle:
        """
        Build a ContextBundle by querying all memory layers.
        
        This is the main entry point for context retrieval.
        
        CRITICAL: We now track "target entity" - the specific entity being queried.
        If it doesn't exist, we flag this to prevent hallucinations.
        
        Args:
            as_of_date: Optional ISO date string for temporal queries.
                        If provided, only returns facts that were valid at this date.
        """
        from datetime import datetime
        
        parsed_as_of_date = None
        if as_of_date:
            try:
                parsed_as_of_date = datetime.fromisoformat(as_of_date.replace('Z', '+00:00'))
            except ValueError:
                try:
                    parsed_as_of_date = datetime.strptime(as_of_date, '%Y-%m-%d')
                except ValueError:
                    logger.warning(f"Invalid as_of_date format: {as_of_date}")
        bundle = create_bundle(query_text)
        bundle.as_of_date = as_of_date
        
        query_type = self._classify_query_type(query_text)
        bundle.query_type = query_type
        
        sequence_intent, sequence_reason = self._detect_sequence_intent(query_text)
        bundle.sequence_intent = sequence_intent
        bundle.sequence_intent_reason = sequence_reason
        
        if query_logger:
            query_logger.log_event("QUERY_CLASSIFICATION", {
                "query_type": query_type,
                "query": query_text[:100],
                "sequence_intent": sequence_intent,
                "sequence_reason": sequence_reason
            })
        
        if query_type == 'rule':
            logger.info(f"RULE QUERY detected: skipping entity extraction")
            keywords = self._extract_rule_context_keywords(query_text)
            entity_types = []
            target_entity_name = None
            bundle.target_entity_found = True
        elif query_type == 'analysis':
            logger.info(f"ANALYSIS QUERY detected: checking for entity listing pattern")
            keywords = []
            entity_types = []
            target_entity_name = None
            bundle.is_analysis_query = True
            
            # Check if this is an entity listing query (e.g., "List all PROCESS entities")
            if self._handle_entity_listing_query(query_text, bundle, query_logger):
                # Entity listing handled - bundle populated with entities
                bundle.target_entity_found = True
            else:
                # General analysis query - no specific entities to list
                bundle.target_entity_found = True
        else:
            keywords = self._extract_keywords(query_text)
            entity_types = self._infer_entity_types(query_text)
            
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
                "inferred_entity_types": entity_types if entity_types else [],
                "target_entity": target_entity_name,
                "target_entity_found": bundle.target_entity_found,
                "query_type": query_type
            })
        
        # NOTE: We deliberately do NOT use _find_potential_entity_names to set 
        # target_entity_name for the hallucination guard. That fallback is too greedy
        # and would incorrectly block general knowledge queries like "What is the 
        # education system in France?" The guard should ONLY trigger when we have
        # explicit entity extraction from deterministic patterns in _extract_target_entity.
        # Log potential entities for debugging, but don't trigger the guard.
        if query_type not in ('rule', 'analysis') and not target_entity_name:
            potential_entities = self._find_potential_entity_names(query_text)
            if potential_entities:
                logger.debug(f"POTENTIAL ENTITIES (informational only): {potential_entities[:3]}")
        
        is_impact = self._is_impact_query(query_text)
        if is_impact and query_logger:
            query_logger.log_event("IMPACT_QUERY_DETECTED", {
                "target_entity": target_entity_name,
                "traversal_direction": "incoming"
            })
        
        property_query_result = self.analyze_property_query(query_text)
        property_entities = []
        
        if property_query_result.get("needs_property_search"):
            entity_type_str = property_query_result.get("entity_type")
            filters = property_query_result.get("filters", [])
            intersection_logic = property_query_result.get("intersection_logic", "AND")
            
            if query_logger:
                query_logger.log_event("PROPERTY_QUERY_DETECTED", {
                    "entity_type": entity_type_str,
                    "filters": filters,
                    "intersection_logic": intersection_logic
                })
            
            entity_type = entity_type_str.upper() if entity_type_str else None
            
            if intersection_logic == "AND" and len(filters) > 1:
                first_results = self.semantic.search_entities_by_properties(
                    entity_type=entity_type,
                    filters=[filters[0]],
                    trusted_only=True,
                    as_of_date=parsed_as_of_date
                )
                
                matching_ids = {str(e.id) for e in first_results}
                
                for f in filters[1:]:
                    next_results = self.semantic.search_entities_by_properties(
                        entity_type=entity_type,
                        filters=[f],
                        trusted_only=True,
                        as_of_date=parsed_as_of_date
                    )
                    next_ids = {str(e.id) for e in next_results}
                    matching_ids = matching_ids.intersection(next_ids)
                
                property_entities = [e for e in first_results if str(e.id) in matching_ids]
            else:
                property_entities = self.semantic.search_entities_by_properties(
                    entity_type=entity_type,
                    filters=filters,
                    trusted_only=True,
                    as_of_date=parsed_as_of_date
                )
            
            if query_logger:
                query_logger.log_event("PROPERTY_SEARCH_RESULTS", {
                    "count": len(property_entities),
                    "entities": [e.name for e in property_entities[:10]]
                })
            
            logger.info(f"Property search found {len(property_entities)} entities matching filters {filters}")
            
            bundle.is_property_query = True
            bundle.property_filters = filters
            # Only set target_entity_found=True if we haven't already verified
            # that the target entity is missing. This prevents hallucination 
            # when queries ask about non-existent entities with property-like syntax.
            if bundle.target_entity_name is None:
                # No specific target entity to verify - property search is valid
                bundle.target_entity_found = True
            # else: preserve the existing value from _verify_target_entity_exists
        
        # Skip semantic memory query for aggregation queries - entities already populated
        if not bundle.is_aggregation_query:
            semantic_results = self._query_semantic_memory(
                keywords, entity_types, traverse_depth, max_entities, query_logger,
                is_impact_query=is_impact,
                target_entity_name=target_entity_name,
                as_of_date=parsed_as_of_date
            )
            bundle.semantic_entities = semantic_results["entities"]
            bundle.semantic_relationships = semantic_results["relationships"]
        else:
            # For aggregation queries, semantic_entities was populated by _handle_entity_listing_query
            semantic_results = {"entities": bundle.semantic_entities, "relationships": []}
        
        # Set blast radius entities for deterministic impact queries
        if "blast_radius_entities" in semantic_results:
            bundle.blast_radius_entities = semantic_results["blast_radius_entities"]
            bundle.blast_radius_complete = semantic_results.get("blast_radius_complete", True)
        
        # Set frontier detection results
        if "frontier" in semantic_results:
            bundle.frontier = semantic_results["frontier"]
        if "gaps_identified" in semantic_results:
            bundle.gaps_identified = semantic_results["gaps_identified"]
        if "traversal_result" in semantic_results:
            bundle.traversal_result = semantic_results["traversal_result"]
        
        # Run speculative inference on frontier nodes
        if bundle.frontier:
            try:
                inference_engine = InferenceEngine(self.semantic.session)
                
                # Get entity IDs from semantic entities for neighbors context
                neighbor_ids = [e.get("id") for e in bundle.semantic_entities if e.get("id")]
                
                # Run inference for each frontier node
                all_inferences = []
                for frontier_node in bundle.frontier:
                    entity_name = frontier_node.get("entity_name")
                    if entity_name:
                        frontier_entity = self.semantic.find_entity_by_name(entity_name)
                        if frontier_entity:
                            inferences = inference_engine.run_all_rules(
                                entity_id=str(frontier_entity.id),
                                neighbor_ids=neighbor_ids
                            )
                            all_inferences.extend(inferences)
                
                # Deduplicate by (source, target, rule_name)
                seen_keys = set()
                unique_inferences = []
                for inf in all_inferences:
                    key = (inf.get("source_entity_id"), inf.get("target_entity_id"), inf.get("rule_name"))
                    if key not in seen_keys:
                        seen_keys.add(key)
                        unique_inferences.append(inf)
                
                bundle.speculative_inferences = unique_inferences
                
                if query_logger and unique_inferences:
                    query_logger.log_event("SPECULATIVE_INFERENCES", {
                        "count": len(unique_inferences),
                        "frontier_nodes": len(bundle.frontier),
                        "inferences": [f"{i.get('source_entity_name')} -> {i.get('target_entity_name')}" for i in unique_inferences[:5]]
                    })
            except Exception as e:
                logger.warning(f"Speculative inference failed: {e}")
        
        if property_entities:
            seen_ids = {e.get("id") for e in bundle.semantic_entities}
            for entity in property_entities:
                entity_dict = entity.to_dict()
                entity_dict["matched_via_property_search"] = True
                if entity_dict["id"] not in seen_ids:
                    bundle.semantic_entities.insert(0, entity_dict)
                    seen_ids.add(entity_dict["id"])
        
        if query_type == 'rule':
            rule_keywords = self._get_rule_document_keywords(query_text)
            episodic_results = self._query_episodic_memory_for_rules(
                query_text, rule_keywords, max_documents, query_logger
            )
        else:
            episodic_results = self._query_episodic_memory(
                query_text, keywords, max_documents, query_logger
            )
        bundle.episodic_documents = episodic_results
        
        relationship_types = [r.get("relationship_type") for r in bundle.semantic_relationships]
        entity_type_strs = [e.get("entity_type") for e in bundle.semantic_entities]
        
        if query_type == 'rule':
            symbolic_results = self._query_symbolic_memory_for_rules(
                query_text, keywords, max_rules * 2, query_logger
            )
            
            person_refs = self._extract_person_references_from_rules(symbolic_results)
            if person_refs:
                enriched_people = self._resolve_person_references(person_refs, query_logger)
                bundle.semantic_entities.extend(enriched_people)
                if query_logger:
                    query_logger.log_event("PERSON_REFERENCES_RESOLVED", {
                        "references": person_refs,
                        "resolved_count": len(enriched_people)
                    })
        else:
            symbolic_results = self._query_symbolic_memory(
                query_text, keywords, entity_type_strs, relationship_types, max_rules, query_logger
            )
        bundle.symbolic_rules = symbolic_results
        
        if sequence_intent:
            bundle.has_multi_step_evidence = self._check_multi_step_evidence(
                bundle.episodic_documents, bundle.symbolic_rules, keywords
            )
            if query_logger:
                query_logger.log_event("SEQUENCE_EVIDENCE_CHECK", {
                    "sequence_intent": True,
                    "has_multi_step_evidence": bundle.has_multi_step_evidence,
                    "keywords_used": keywords
                })
        
        bundle.calculate_uncertainty()
        
        bundle.retrieval_metadata = {
            "keywords": keywords,
            "entity_types_searched": entity_types,
            "traverse_depth": traverse_depth,
            "sequence_intent": sequence_intent,
            "sequence_reason": sequence_reason
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
    
    def _infer_entity_types(self, query_text: str) -> List[str]:
        """
        Infer which entity types are relevant based on query content.
        
        DOMAIN-AGNOSTIC: Uses the currently loaded schema's entity types
        instead of hardcoded IT Operations types.
        
        IMPORTANT: Always returns ALL schema types to avoid missing entities.
        For example, "What does Alice possess?" should search CHARACTER for Alice
        even though 'possess' matches OBJECT type. The relationship filtering
        happens later in the pipeline.
        """
        schema = get_schema_loader().schema
        return schema.get_entity_type_names()
    
    def _build_entity_type_keywords(self, schema: DomainSchema) -> Dict[str, List[str]]:
        """
        Build keyword mapping for entity type inference.
        
        Uses schema descriptions and names to generate relevant keywords.
        Falls back to name-based inference for unknown types.
        """
        keyword_map = {}
        
        common_keywords = {
            'DATABASE': ['database', 'db', 'postgres', 'mysql', 'redis', 'data store'],
            'SERVICE': ['service', 'api', 'endpoint', 'microservice'],
            'TEAM': ['team', 'group', 'department', 'squad'],
            'PERSON': ['person', 'who', 'engineer', 'lead', 'manager', 'contact', 'owner'],
            'INCIDENT': ['incident', 'outage', 'failure', 'sev1', 'sev2', 'alert'],
            'RUNBOOK': ['runbook', 'procedure', 'playbook', 'how to', 'guide'],
            'COMPONENT': ['component', 'cache', 'queue', 'module'],
            'CHARACTER': ['character', 'protagonist', 'hero', 'villain', 'who', 'person'],
            'CREATURE': ['creature', 'animal', 'beast', 'monster', 'being'],
            'LOCATION': ['location', 'place', 'where', 'setting', 'land', 'world'],
            'OBJECT': ['object', 'item', 'thing', 'artifact', 'possess', 'has', 'owns'],
            'EVENT': ['event', 'happened', 'occurs', 'when', 'incident', 'happening'],
        }
        
        for entity_type in schema.get_entity_type_names():
            if entity_type in common_keywords:
                keyword_map[entity_type] = common_keywords[entity_type]
            else:
                keyword_map[entity_type] = [entity_type.lower(), entity_type.lower().replace('_', ' ')]
                entity_config = schema.get_entity_type(entity_type)
                if entity_config and entity_config.description:
                    desc_words = entity_config.description.lower().split()
                    keyword_map[entity_type].extend([w for w in desc_words if len(w) > 3][:3])
        
        return keyword_map
    
    def _is_impact_query(self, query_text: str) -> bool:
        """
        Detect if this is a blast radius / impact analysis query.
        
        These queries ask "if X breaks, what else breaks?" which means we need
        to find entities that DEPEND ON X (incoming DEPENDS_ON), not what X depends on.
        
        Also includes notification-style queries like "which services need to be notified"
        when combined with failure/causal context, as these imply full impact chain.
        """
        query_lower = query_text.lower()
        
        impact_keywords = [
            'blast radius', 'impact', 'impacted', 'impacts',
            'affected', 'affects', 
            'goes down', 'becomes unavailable', 'fails', 'failure',
            'breaks', 'crashes', 'is down', 'is corrupted', 'is unavailable',
            'what services', 'which services', 'what depends', 'what breaks',
            'downstream', 'cascade', 'ripple effect'
        ]
        
        if any(kw in query_lower for kw in impact_keywords):
            return True
        
        notification_keywords = ['notified', 'notify', 'alerted', 'paged', 'alert']
        failure_cues = [
            'corrupted', 'fails', 'failure', 'failing',
            'down', 'goes down', 'is down', 'unavailable', 'outage',
            'breaks', 'broken', 'crashes', 'crashed', 'incident'
        ]
        
        has_notification = any(kw in query_lower for kw in notification_keywords)
        has_failure_cue = any(kw in query_lower for kw in failure_cues)
        
        if has_notification and has_failure_cue:
            return True
        
        return False
    
    def _is_analysis_query(self, query_text: str) -> bool:
        """
        Detect if this is an analysis/aggregation query that requires statistical
        capabilities beyond simple retrieval.
        
        These queries ask for patterns, trends, summaries across data - not specific
        facts about entities. CF cannot reliably answer these without aggregation.
        """
        query_lower = query_text.lower()
        
        analysis_patterns = [
            r'\bwhat patterns\b',
            r'\bany patterns\b',
            r'\bany trends\b',
            r'\b(common|frequent|recurring) (issues?|problems?|causes?|errors?|incidents?)\b',
            r'\bmost (common|frequent)\b',
            r'\bhow many (incidents?|outages?|failures?|issues?)\b',
            r'\bwhich services have the most\b',
            r'\bare there any recurring\b',
            r'\bsummary of\b',
            r'\boverview of (all|our|recent)\b',
            r'\btrend(s|ing)?\b',
            r'\bstatistics\b',
            r'\baggregate\b',
            r'\btotal (number|count)\b',
            r'\baverage\b',
            r'\bfrequen(cy|t)\b',
            r'\bhistor(y|ical) (of|analysis)\b',
        ]
        
        for pattern in analysis_patterns:
            if re.search(pattern, query_lower):
                return True
        
        # Entity listing/aggregation patterns - route to aggregation handler
        if self._is_entity_listing_query(query_text):
            return True
        
        return False
    
    def _is_entity_listing_query(self, query_text: str) -> bool:
        """
        Detect if query is asking to list entities by type.
        E.g., "List all PROCESS entities", "Show all ORGANIZATION entities"
        """
        query_lower = query_text.lower()
        
        listing_patterns = [
            r'\b(list|show|display|get|find)\s+(all|the|every)\s+(\w+)\s+(entities|entity)',
            r'\bwhat\s+(\w+)\s+(entities|entity)\s+(exist|are there|do we have)',
            r'\bhow many\s+(\w+)\s+(entities|entity)',
            r'\b(all|every)\s+(\w+)\s+(entities|entity)\s+in',
        ]
        
        for pattern in listing_patterns:
            if re.search(pattern, query_lower):
                return True
        
        return False
    
    def _extract_entity_type_from_listing_query(self, query_text: str) -> Optional[str]:
        """
        Extract the entity type from a listing query.
        E.g., "List all PROCESS entities" -> "PROCESS"
        """
        query_lower = query_text.lower()
        
        # Each pattern has the entity type in the last capturing group before 'entities'
        patterns_with_type_index = [
            # "list all PROCESS entities" - entity type is group 3
            (r'\b(list|show|display|get|find)\s+(all|the|every)\s+(\w+)\s+(entities|entity)', 3),
            # "what PROCESS entities exist" - entity type is group 1
            (r'\bwhat\s+(\w+)\s+(entities|entity)\s+(exist|are there|do we have)', 1),
            # "how many PROCESS entities" - entity type is group 1
            (r'\bhow many\s+(\w+)\s+(entities|entity)', 1),
            # "all PROCESS entities in" - entity type is group 2
            (r'\b(all|every)\s+(\w+)\s+(entities|entity)\s+in', 2),
        ]
        
        known_types = ['PERSON', 'ORGANIZATION', 'DOCUMENT', 'LOCATION', 
                      'EVENT', 'CONCEPT', 'PROCESS', 'DATE', 'SERVICE',
                      'DATABASE', 'TEAM', 'SYSTEM']
        
        for pattern, type_group_index in patterns_with_type_index:
            match = re.search(pattern, query_lower)
            if match:
                entity_type = match.group(type_group_index).upper()
                if entity_type in known_types:
                    return entity_type
        
        return None
    
    def _handle_entity_listing_query(self, query_text: str, bundle: ContextBundle, 
                                     query_logger: Optional[QueryLogger] = None) -> bool:
        """
        Handle entity listing queries by querying database directly.
        Returns True if handled, False otherwise.
        """
        entity_type = self._extract_entity_type_from_listing_query(query_text)
        if not entity_type:
            return False
        
        try:
            # Entity is already imported at module level from ..models.schema
            entities = self.semantic.session.query(Entity).filter(
                Entity.entity_type == entity_type,
                Entity.lifecycle_state == 'TRUSTED'
            ).order_by(Entity.name).limit(50).all()
            
            # Build semantic entities list for the bundle
            entity_list = []
            for e in entities:
                entity_list.append({
                    "id": str(e.id),
                    "name": e.name,
                    "entity_type": e.entity_type,
                    "description": e.description or "",
                    "lifecycle_state": e.lifecycle_state,
                    "confidence": float(e.confidence) if e.confidence else 0.85
                })
            
            bundle.semantic_entities = entity_list
            bundle.is_aggregation_query = True
            bundle.aggregation_type = entity_type
            bundle.aggregation_count = len(entity_list)
            bundle.target_entity_found = True  # We have results
            
            if query_logger:
                query_logger.log_event("ENTITY_LISTING_QUERY", {
                    "entity_type": entity_type,
                    "count": len(entity_list),
                    "entities": [e["name"] for e in entity_list[:10]]
                })
            
            logger.info(f"Entity listing query: found {len(entity_list)} {entity_type} entities")
            return True
            
        except Exception as e:
            logger.error(f"Error in entity listing query: {e}")
            return False
    
    def _is_edge_facing_entity(self, entity_name: str) -> bool:
        """Check if entity is edge-facing (receives external traffic)."""
        edge_keywords = ['api gateway', 'load balancer', 'cdn', 'ingress', 'edge', 'frontend']
        return any(kw in entity_name.lower() for kw in edge_keywords)
    
    def _detect_sequence_intent(self, query_text: str) -> Tuple[bool, Optional[str]]:
        """
        Detect if the query is asking for an ordered sequence (path, chain, workflow, steps).
        
        Returns (is_sequence, reason) where reason explains why it was detected.
        
        This is DOMAIN-AGNOSTIC - works for escalation paths, approval chains,
        hiring workflows, contract processes, onboarding steps, etc.
        """
        query_lower = query_text.lower()
        
        sequence_patterns = [
            (r'\b(escalation|approval|authorization)\s+(path|chain|route)\b', 'contains path/chain keyword'),
            (r'\bwhat.s the (path|chain|route|workflow|process|procedure)\b', 'asks for path/workflow'),
            (r'\bwhat are the (steps|stages|phases)\b', 'asks for steps/stages'),
            (r'\bhow many (steps|stages)\b', 'asks about step count'),
            (r'\b(first|then|next|after that|finally)\b.*\b(step|stage)\b', 'contains ordinal markers'),
            (r'\bwalk me through\b', 'requests walkthrough'),
            (r'\bstep.by.step\b', 'requests step-by-step'),
            (r'\bin (what|which) order\b', 'asks about order'),
            (r'\bsequence of\b', 'asks for sequence'),
            (r'\bchain of (command|approval|custody)\b', 'asks for chain'),
            (r'\bwho.* then who\b', 'asks for multi-step who'),
            (r'\b(route|proceed|goes?) to\b.*\bthen\b', 'describes multi-hop routing'),
        ]
        
        for pattern, reason in sequence_patterns:
            if re.search(pattern, query_lower):
                return True, reason
        
        sequence_nouns = ['path', 'chain', 'workflow', 'pipeline', 'sequence', 'order']
        sequence_verbs = ['steps', 'stages', 'phases', 'levels', 'tiers']
        
        for noun in sequence_nouns:
            if noun in query_lower:
                return True, f"contains sequence noun '{noun}'"
        
        if any(v in query_lower for v in sequence_verbs):
            if any(q in query_lower for q in ['what are', 'how many', 'list the', 'show me']):
                return True, "asks for multiple steps/stages"
        
        return False, None
    
    def _check_multi_step_evidence(
        self,
        documents: List[Dict],
        rules: List[Dict],
        query_keywords: List[str] = None
    ) -> bool:
        """
        Check if retrieved evidence contains TOPICALLY RELEVANT multi-step sequences.
        
        Multi-step evidence must:
        1. Contain numbered lists, arrows, or sequential markers
        2. Be topically relevant to the query (TOPIC keywords, not structural keywords)
        
        This prevents false positives from unrelated numbered lists.
        """
        step_patterns = [
            r'^\s*[1-9]\.\s+',
            r'^\s*step\s+[1-9]',
            r'^\s*\d+\)\s+',
            r'->\s*\d+\.',
            r'then\s+\d+\.',
            r'first.*then.*finally',
            r'→',
            r'##\s+(step|stage|phase)\s+\d+',
        ]
        
        structural_keywords = {
            'procedure', 'path', 'chain', 'steps', 'process', 'workflow',
            'stage', 'phase', 'order', 'sequence', 'first', 'then', 'next'
        }
        
        query_keywords = query_keywords or []
        topic_keywords = set(
            kw.lower() for kw in query_keywords 
            if len(kw) > 2 and kw.lower() not in structural_keywords
        )
        
        for doc in documents:
            content = doc.get("content", "").lower()
            title = doc.get("title", "").lower()
            
            if topic_keywords:
                title_match_count = sum(1 for kw in topic_keywords if kw in title)
                content_match_count = sum(1 for kw in topic_keywords if kw in content)
                is_topically_relevant = title_match_count >= 1 or content_match_count >= 3
            else:
                is_topically_relevant = True
            
            if not is_topically_relevant:
                continue
            
            numbered_items = re.findall(r'^\s*(\d+)\.\s+\S', content, re.MULTILINE)
            if len(numbered_items) >= 2:
                return True
            
            for pattern in step_patterns:
                if re.search(pattern, content, re.IGNORECASE | re.MULTILINE):
                    if len(re.findall(pattern, content, re.IGNORECASE | re.MULTILINE)) >= 2:
                        return True
            
            if '→' in content or ' -> ' in content:
                return True
        
        if len(rules) >= 2:
            rule_types = set(r.get("rule_type") for r in rules)
            if len(rule_types) >= 2:
                return True
        
        return False
    
    def _classify_query_type(self, query_text: str) -> str:
        """
        Classify the query type to determine the retrieval strategy.
        
        Returns one of:
        - 'entity': Looking for information about a specific entity
        - 'rule': Looking for policies, procedures, escalation paths, approval flows
        - 'impact': Blast radius / cascade analysis (already handled separately)
        - 'analysis': Aggregation/pattern queries requiring statistical analysis
        - 'general': General question that needs all memory layers
        
        RULE QUERIES are characterized by:
        - Asking about processes, procedures, policies
        - Questions with "should", "when", "what's the process"
        - Escalation, approval, notification questions
        - No specific named entity being queried
        
        ANALYSIS QUERIES are characterized by:
        - Asking for patterns, trends, summaries across data
        - Aggregation questions (most common, how many, which services have)
        - These require statistical capabilities beyond simple retrieval
        """
        query_lower = query_text.lower()
        
        if self._is_analysis_query(query_text):
            return 'analysis'
        
        if self._is_impact_query(query_text):
            return 'impact'
        
        rule_patterns = [
            r'\bwho should\b',
            r'\bwhat.s the (process|procedure|policy|escalation|approval)\b',
            r'\bwhat is the (process|procedure|policy|escalation|approval)\b',
            r'\bhow (do|does|should) (we|i|one)\b',
            r'\bwhen (do|does|should) (we|i|one)\b',
            r'\bwhat (happens|do we do) (if|when)\b',
            r'\bescalation path\b',
            r'\bapproval (required|needed|process)\b',
            r'\bnotif(y|ied|ication)\b.*\b(if|when)\b',
            r'\brequire.* approval\b',
            r'\bwho (approves|reviews|signs off)\b',
            r'\bwho (gets|should be) (notified|paged|alerted)\b',
        ]
        
        for pattern in rule_patterns:
            if re.search(pattern, query_lower):
                return 'rule'
        
        rule_keywords = [
            'escalation', 'approval process', 'notification policy',
            'what\'s the procedure', 'what\'s the policy', 'what\'s the process',
            'budget request', 'contract expires', 'security breach',
            'sev1', 'sev2', 'sev 1', 'sev 2', 'severity 1', 'severity 2',
            'incident response', 'runbook', 'playbook',
        ]
        
        if any(kw in query_lower for kw in rule_keywords):
            return 'rule'
        
        return 'entity'
    
    def _extract_rule_context_keywords(self, query_text: str) -> List[str]:
        """
        Extract keywords relevant to rule/policy search.
        
        For rule queries, we want to find rules that match the scenario,
        not entity names.
        """
        query_lower = query_text.lower()
        keywords = []
        
        scenario_keywords = {
            'security': ['security', 'breach', 'attack', 'vulnerability'],
            'escalation': ['escalation', 'escalate', 'sev1', 'sev2', 'sev 1', 'sev 2', 'severity'],
            'approval': ['approval', 'approve', 'budget', 'request', 'sign off'],
            'notification': ['notify', 'notification', 'alert', 'page', 'pager'],
            'incident': ['incident', 'outage', 'failure', 'down'],
            'hiring': ['hire', 'hiring', 'headcount', 'team size'],
            'contract': ['contract', 'vendor', 'expires', 'renewal'],
            'database': ['database', 'db', 'data'],
            'payment': ['payment', 'transaction', 'financial'],
            'auth': ['auth', 'authentication', 'login', 'access'],
        }
        
        for category, kws in scenario_keywords.items():
            if any(kw in query_lower for kw in kws):
                keywords.append(category)
                keywords.extend([k for k in kws if k in query_lower])
        
        return list(set(keywords))
    
    def _match_known_entity_in_query(self, query_text: str) -> Optional[str]:
        """
        Search for known entity names from the database within the query.
        
        Uses the 3-stage EntityResolver for robust matching:
        1. Exact match (case-insensitive)
        2. Semantic search (OpenAI embeddings with cosine similarity > 0.75)
        3. Fuzzy match (Levenshtein ratio with threshold 0.70)
        
        When disambiguation is needed, prefers SERVICE/TEAM/DATABASE over INCIDENT
        unless the query explicitly mentions incidents.
        
        Returns the best matching entity name found.
        """
        entity_phrase = self._extract_entity_phrase_from_query(query_text)
        if not entity_phrase:
            return None
        
        result = self.entity_resolver.resolve(entity_phrase)
        
        if result.entity:
            logger.debug(f"EntityResolver found: {result.entity.name} (stage: {result.match_stage}, conf: {result.confidence:.2f})")
            return result.entity.name
        
        if result.needs_disambiguation and result.candidates:
            query_lower = query_text.lower()
            has_incident_hint = any(w in query_lower for w in ['incident', 'outage', 'inc-', 'sev1', 'sev2'])
            
            if not has_incident_hint:
                core_types = {'SERVICE', 'TEAM', 'DATABASE', 'COMPONENT', 'PERSON'}
                core_candidates = [c for c in result.candidates if c.entity_type in core_types]
                if core_candidates:
                    logger.debug(f"EntityResolver disambiguation: prioritizing core type {core_candidates[0].name}")
                    return core_candidates[0].name
            
            logger.debug(f"EntityResolver disambiguation: {len(result.candidates)} candidates, returning top: {result.candidates[0].name}")
            return result.candidates[0].name
        
        logger.debug(f"EntityResolver: no match for '{entity_phrase}' (stage: {result.match_stage})")
        return None
    
    def _extract_entity_phrase_from_query(self, query_text: str) -> Optional[str]:
        """
        Extract the most likely entity phrase from a natural language query.
        
        This pre-processes the query before sending to EntityResolver to get
        a cleaner entity phrase for matching.
        """
        quoted = re.findall(r'["\']([^"\']+)["\']', query_text)
        if quoted:
            return quoted[0]
        
        if_fails = re.search(
            r'\bif\s+(?:the\s+)?([A-Za-z][a-zA-Z0-9\s]*?)\s+(?:goes?\s+down|fails?|is\s+down)',
            query_text, re.IGNORECASE
        )
        if if_fails:
            return if_fails.group(1).strip()
        
        depends_on = re.search(
            r'(?:depends?\s+on|uses?|calls?|connects?\s+to)\s+(?:the\s+)?([A-Za-z][a-zA-Z0-9\s]*?)(?:\?|$|\s+(?:and|or|for|to|from))',
            query_text, re.IGNORECASE
        )
        if depends_on:
            return depends_on.group(1).strip()
        
        about_pattern = re.search(
            r'(?:about|on|for)\s+(?:the\s+)?([A-Za-z][a-zA-Z0-9\s]*?)(?:\?|$|\s+(?:and|or|to|from))',
            query_text, re.IGNORECASE
        )
        if about_pattern:
            phrase = about_pattern.group(1).strip()
            if len(phrase) > 2 and phrase.lower() not in {'a', 'an', 'the', 'this', 'that', 'it'}:
                return phrase
        
        with_the = re.search(
            r'(?:issues?|problems?|status|info|information|details?)\s+(?:with|of|for)\s+(?:the\s+)?([A-Za-z][a-zA-Z0-9\s]*?)(?:\?|$|\.)',
            query_text, re.IGNORECASE
        )
        if with_the:
            phrase = with_the.group(1).strip()
            if len(phrase) > 2:
                return phrase
        
        return None
    
    def _extract_target_entity(self, query_text: str) -> Optional[str]:
        """
        Extract the specific entity the query is asking about.
        
        This is CRITICAL for preventing hallucinations - we need to know if
        the entity being queried actually exists in the graph.
        
        STRATEGY (in order of priority):
        1. First, search for KNOWN entity names from the database in the query
        2. Only fall back to regex patterns if no known entities match
        
        This approach is more reliable because it matches against actual 
        entities rather than trying to parse natural language with regex.
        """
        # PRIORITY 1: Match known entity names from database
        known_match = self._match_known_entity_in_query(query_text)
        if known_match:
            return known_match
        
        # PRIORITY 2: Fall back to regex patterns for entities not yet in DB
        # Entity type suffixes we look for (case-insensitive)
        ENTITY_SUFFIXES = r'(?:[Ss]ervice|[Dd]atabase|[Tt]eam|[Cc]ache|[Qq]ueue|[Gg]ateway|API|api|[Ss]ystem|[Ee]ngine|[Pp]latform|[Cc]luster)'
        # Entity pattern - accepts letters and numbers (e.g., "FakeService123", "API Gateway")
        ENTITY_PATTERN = rf'([A-Za-z][a-zA-Z0-9]*(?:\s+[A-Za-z][a-zA-Z0-9]*)*(?:\s+{ENTITY_SUFFIXES})?)'
        
        # Pattern 1: Quoted entity names (highest priority)
        quoted = re.findall(r'["\']([^"\']+)["\']', query_text)
        if quoted:
            return self._normalize_entity_name(quoted[0])
        
        # Pattern 2: "if <Entity> fails/goes down" - HIGHEST priority for impact queries
        # Matches: "if FakeService123 fails", "if API Gateway goes down"
        if_fails_pattern = re.search(
            rf'\bif\s+(?:the\s+)?{ENTITY_PATTERN}\s+(?:goes?\s+down|fails?|is\s+down|crashes?|times?\s+out|becomes?\s+unavailable)\b',
            query_text, re.IGNORECASE
        )
        if if_fails_pattern:
            return self._normalize_entity_name(if_fails_pattern.group(1))
        
        # Pattern 3: "the <Entity Name>" - only match if properly capitalized like a proper entity
        # e.g., "the Payment Service" but NOT "the education system in France"
        # Must have Capital First Letter to distinguish entities from common nouns
        the_pattern = re.search(
            rf'\bthe\s+([A-Z][a-zA-Z0-9]*(?:\s+[A-Z][a-zA-Z0-9]*)*)\b',
            query_text
        )
        if the_pattern:
            return self._normalize_entity_name(the_pattern.group(1))
        
        # Pattern 4: "<Entity> goes down" / "<Entity> fails" / "<Entity> is down"
        # (without "if" prefix - that's handled in Pattern 2)
        fails_pattern = re.search(
            rf'\b{ENTITY_PATTERN}\s+(?:goes?\s+down|fails?|is\s+down|crashes?|times?\s+out)\b',
            query_text, re.IGNORECASE
        )
        if fails_pattern:
            return self._normalize_entity_name(fails_pattern.group(1))
        
        # Pattern 4a: "depends on <Entity>" / "depend on <Entity>"
        depends_pattern = re.search(
            rf'\bdepends?\s+on\s+(?:the\s+)?{ENTITY_PATTERN}\b',
            query_text, re.IGNORECASE
        )
        if depends_pattern:
            return self._normalize_entity_name(depends_pattern.group(1))
        
        # Pattern 4b: "what does <Entity> depend on" / "does <Entity> depend on"
        what_depends_pattern = re.search(
            rf'\b(?:what\s+)?does\s+(?:the\s+)?{ENTITY_PATTERN}\s+depend',
            query_text, re.IGNORECASE
        )
        if what_depends_pattern:
            return self._normalize_entity_name(what_depends_pattern.group(1))
        
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
        # Only match if entity ends with a known suffix (to avoid matching generic nouns like "France")
        about_pattern = re.search(
            rf'\b(?:about|regarding|concerning)\s+(?:the\s+)?([A-Za-z][a-zA-Z0-9]*(?:\s+[A-Za-z][a-zA-Z0-9]*)*\s+{ENTITY_SUFFIXES})\b',
            query_text, re.IGNORECASE
        )
        if about_pattern:
            return self._normalize_entity_name(about_pattern.group(1))
        
        # NOTE: Removed Pattern 11 (greedy fallback) to prevent matching generic phrases
        # like "Education System" in "What is the education system in France?"
        # The guard should only trigger for explicit entity extraction patterns (1-10).
        
        return None
    
    def _strip_scenario_suffix(self, name: str) -> str:
        """
        Strip scenario/action phrases from the end of an extracted entity name.
        
        For example:
        - "User Database Is Corrupted" -> "User Database"
        - "Auth Service Goes Down" -> "Auth Service"
        - "Payment Gateway Fails" -> "Payment Gateway"
        
        This prevents the entity extractor from capturing scenario descriptions
        as part of the entity name.
        """
        if not name:
            return name
        
        # Scenario phrases to strip (order matters - check longer phrases first)
        SCENARIO_PHRASES = [
            # Multi-word scenario phrases
            r'\s+is\s+corrupted$',
            r'\s+is\s+down$',
            r'\s+goes\s+down$',
            r'\s+go\s+down$',
            r'\s+times\s+out$',
            r'\s+timed\s+out$',
            r'\s+is\s+unavailable$',
            r'\s+is\s+offline$',
            r'\s+is\s+unreachable$',
            r'\s+has\s+failed$',
            r'\s+has\s+issues$',
            r'\s+is\s+slow$',
            r'\s+is\s+failing$',
            r'\s+stops\s+working$',
            r'\s+becomes\s+unavailable$',
            # Single-word scenario suffixes
            r'\s+fails?$',
            r'\s+crashes?$',
            r'\s+dies?$',
            r'\s+breaks?$',
            # Trailing "is" / "are" / "has" / "have" (when followed by nothing)
            r'\s+is$',
            r'\s+are$',
            r'\s+has$',
            r'\s+have$',
            r'\s+was$',
            r'\s+were$',
        ]
        
        result = name.strip()
        for pattern in SCENARIO_PHRASES:
            result = re.sub(pattern, '', result, flags=re.IGNORECASE)
        
        # Also strip trailing punctuation
        result = result.rstrip('.,?!;:')
        
        return result.strip()
    
    def _normalize_entity_name(self, name: str) -> str:
        """
        Normalize entity name to title case for consistent database lookups.
        First strips scenario suffixes, then handles special cases like 'API'.
        """
        if not name:
            return name
        
        # First, strip any scenario suffixes
        name = self._strip_scenario_suffix(name)
        
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
        ONLY matches phrases that end with known entity suffixes to prevent
        false positives like "Capital Of France".
        Returns title-cased versions for consistent comparison.
        """
        # Entity type suffixes (case-insensitive)
        ENTITY_SUFFIXES = r'(?:[Ss]ervice|[Dd]atabase|[Tt]eam|[Cc]ache|[Qq]ueue|[Gg]ateway|API|api|[Ss]ystem|[Ee]ngine|[Pp]latform|[Cc]luster|[Pp]rocessor)'
        
        # Find all phrases that end with an entity suffix (case-insensitive)
        # This is the ONLY pattern we use - no greedy fallback
        pattern = rf'\b([A-Za-z][a-zA-Z0-9]*(?:\s+[A-Za-z][a-zA-Z0-9]*)*\s+{ENTITY_SUFFIXES})\b'
        matches = re.findall(pattern, query_text, re.IGNORECASE)
        
        # Filter out common false positives (check lowercase version)
        false_positives = {'what', 'who', 'where', 'when', 'how', 'which', 'the', 'are', 'does', 'can', 'is', 'of'}
        filtered = [m for m in matches if m.split()[0].lower() not in false_positives]
        
        # Convert to title case for consistent database lookups
        title_cased = [m.title() for m in filtered]
        
        # Sort by length (longer matches first) to prefer more specific entities
        return sorted(title_cased, key=len, reverse=True)
    
    def _query_semantic_memory(
        self,
        keywords: List[str],
        entity_types: List[str],
        traverse_depth: int,
        max_entities: int,
        query_logger: Optional[QueryLogger],
        is_impact_query: bool = False,
        target_entity_name: Optional[str] = None,
        as_of_date = None
    ) -> Dict:
        """
        Query semantic memory (knowledge graph) for relevant entities and relationships.
        
        For impact/blast radius queries, we traverse INCOMING DEPENDS_ON relationships
        to find what depends on the target entity (downstream impact).
        
        Args:
            as_of_date: Optional datetime for temporal queries. If provided, only returns
                        entities and relationships that were valid at this date.
        """
        entities = []
        relationships = []
        seen_entity_ids: Set[str] = set()
        
        schema = get_schema_loader().schema
        default_types = schema.get_entity_type_names()
        
        for keyword in keywords:
            found = self.semantic.search_entities(
                keyword,
                entity_types=entity_types if entity_types else default_types,
                trusted_only=True,
                limit=5,
                as_of_date=as_of_date
            )
            
            for entity in found:
                entity_dict = entity.to_dict()
                if entity_dict["id"] not in seen_entity_ids:
                    seen_entity_ids.add(entity_dict["id"])
                    entities.append(entity_dict)
        
        entities_to_traverse = list(entities)[:10]
        
        traversal_result: Optional[TraversalResult] = None
        
        if is_impact_query and target_entity_name:
            # Use SCHEMA-DRIVEN graph traversal for blast radius queries
            # Traversal rules are read from the schema YAML, not hardcoded
            # This handles multiple relationship types (DEPENDS_ON, ROUTES_TO, etc.)
            # Returns TraversalResult with confirmed entities, frontier nodes, and gaps
            traversal_result = self.semantic.get_schema_driven_blast_radius(
                target_entity_name,
                mode="impact",  # Uses schema-defined traversal rules for impact mode
                max_depth=10,
                as_of_date=as_of_date
            )
            
            if traversal_result.traversal_complete:
                # Add source entity
                source_entity = self.semantic.find_entity_by_name(traversal_result.start_entity_name)
                if source_entity:
                    source_dict = source_entity.to_dict()
                    if source_dict["id"] not in seen_entity_ids:
                        seen_entity_ids.add(source_dict["id"])
                        entities.insert(0, source_dict)
                
                # Add ALL confirmed entities (schema-driven, deterministic)
                for confirmed in traversal_result.confirmed_entities:
                    if confirmed.entity_id not in seen_entity_ids:
                        seen_entity_ids.add(confirmed.entity_id)
                        entity = self.semantic.session.query(Entity).get(uuid.UUID(confirmed.entity_id))
                        if entity:
                            entities.append(entity.to_dict())
                
                # Add ALL traversed relationships (schema-driven, includes ROUTES_TO, DEPENDS_ON, etc.)
                for rel_dict in traversal_result.traversed_relationships:
                    if rel_dict not in relationships:
                        relationships.append(rel_dict)
                
                logger.info(
                    f"Schema-driven traversal ({traversal_result.mode}): "
                    f"{len(traversal_result.confirmed_entities)} confirmed, "
                    f"{len(traversal_result.frontier_nodes)} frontier nodes, "
                    f"{len(traversal_result.gaps_identified)} gaps"
                )
                
                if self._is_edge_facing_entity(target_entity_name):
                    edge_note = {
                        "id": "edge-impact-note",
                        "name": "External Traffic Impact",
                        "entity_type": "NOTE",
                        "description": f"If {target_entity_name} becomes unavailable, all external traffic is blocked. No external clients can reach services behind the gateway.",
                        "confidence": 1.0,
                        "lifecycle_state": "TRUSTED",
                        "properties": {"type": "impact_note", "severity": "critical"}
                    }
                    entities.append(edge_note)
        
        for entity in entities_to_traverse:
            entity_id_str = entity.get("id")
            if not entity_id_str or entity_id_str == "edge-impact-note":
                continue
            entity_id = uuid.UUID(entity_id_str)
            
            if is_impact_query:
                # For impact queries, relationships are already collected via schema-driven traversal
                # which includes all relationship types marked with include=true for mode=impact
                # (DEPENDS_ON incoming, ROUTES_TO outgoing, etc.)
                # Skip hardcoded relationship collection here
                continue
            else:
                rels = self.semantic.get_entity_relationships(
                    entity_id,
                    direction="both",
                    trusted_only=True,
                    as_of_date=as_of_date
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
        
        result = {
            "entities": entities,
            "relationships": relationships
        }
        
        # Include traversal result with frontier detection for impact queries
        if is_impact_query and target_entity_name and traversal_result:
            if traversal_result.traversal_complete:
                # Confirmed entities from traversal
                result["blast_radius_entities"] = sorted([
                    e.entity_name for e in traversal_result.confirmed_entities
                ])
                result["blast_radius_complete"] = True
                result["blast_radius_mode"] = traversal_result.mode
                
                # NEW: Frontier nodes (where knowledge ends)
                result["frontier"] = [f.to_dict() for f in traversal_result.frontier_nodes]
                
                # NEW: Documentation gaps identified
                result["gaps_identified"] = traversal_result.gaps_identified
                
                # NEW: Full traversal result for structured response
                result["traversal_result"] = traversal_result.to_dict()
                
                logger.info(
                    f"Traversal result ({traversal_result.mode}): "
                    f"{len(result['blast_radius_entities'])} confirmed, "
                    f"{len(result['frontier'])} frontier nodes, "
                    f"{len(result['gaps_identified'])} gaps"
                )
        
        return result
    
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
    
    def _get_rule_document_keywords(self, query_text: str) -> List[str]:
        """
        Extract keywords for finding relevant documents for rule queries.
        
        Prioritizes finding procedure/path documents when sequence queries are detected.
        """
        query_lower = query_text.lower()
        keywords = []
        
        is_path_query = any(p in query_lower for p in ['path', 'chain', 'steps', 'order', 'sequence', 'procedure'])
        
        keyword_map = {
            'escalation': ['escalation', 'escalate', 'procedure', 'path'],
            'notification': ['notification', 'notify', 'alert', 'page'],
            'approval': ['approval', 'approve', 'budget', 'authority', 'chain'],
            'procedure': ['procedure', 'process', 'playbook', 'runbook', 'steps'],
            'security': ['security', 'breach', 'incident', 'vulnerability'],
            'hiring': ['hiring', 'headcount', 'team'],
        }
        
        for category, kws in keyword_map.items():
            if any(kw in query_lower for kw in kws):
                keywords.extend(kws)
        
        if 'sev1' in query_lower or 'sev 1' in query_lower:
            if is_path_query:
                keywords.extend(['sev1', 'escalation', 'procedure', 'path'])
            else:
                keywords.extend(['sev1', 'incident', 'escalation', 'commander'])
        
        if is_path_query:
            keywords.extend(['procedure', 'path', 'steps', 'chain'])
        
        return list(set(keywords)) if keywords else ['procedure', 'policy', 'process']
    
    def _query_episodic_memory_for_rules(
        self,
        query_text: str,
        rule_keywords: List[str],
        max_documents: int,
        query_logger: Optional[QueryLogger]
    ) -> List[Dict]:
        """Query episodic memory specifically for rule context documents."""
        documents = self.episodic.search_for_rule_context(
            rule_keywords,
            doc_types=['RUNBOOK', 'PROCEDURE'],
            limit=max_documents
        )
        
        if len(documents) < max_documents:
            vector_docs = self.episodic.search_similar(
                query_text,
                limit=max_documents - len(documents),
                min_similarity=0.0
            )
            
            seen_ids = {d["id"] for d in documents}
            for doc in vector_docs:
                if doc["id"] not in seen_ids:
                    documents.append(doc)
        
        if query_logger:
            similarities = [d.get("similarity", 0) for d in documents]
            query_logger.log_event("EPISODIC_QUERY_FOR_RULES", {
                "documents_count": len(documents),
                "keywords_used": rule_keywords,
                "top_docs": [d.get("title") for d in documents[:3]]
            })
        
        logger.debug(f"Rule episodic query: {len(documents)} documents for keywords {rule_keywords}")
        
        return documents
    
    def _extract_person_references_from_rules(self, rules: List[Dict]) -> List[str]:
        """Extract person name references from rule actions and conditions."""
        person_refs = []
        
        name_pattern = re.compile(r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b')
        
        title_patterns = [
            r'\b(VP\s+(?:of\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'\b(Director\s+(?:of\s+)?[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)',
            r'\b(CTO|CEO|CFO|COO|CPO)\b',
        ]
        
        for rule in rules:
            action = rule.get("action", "")
            condition = rule.get("condition", "")
            description = rule.get("description", "")
            
            full_text = f"{action} {condition} {description}"
            
            names = name_pattern.findall(full_text)
            for name in names:
                if name.lower() not in ['team lead', 'incident commander', 'service owner']:
                    person_refs.append(name)
            
            for pattern in title_patterns:
                matches = re.findall(pattern, full_text)
                person_refs.extend(matches)
        
        return list(set(person_refs))
    
    def _resolve_person_references(
        self,
        person_refs: List[str],
        query_logger: Optional[QueryLogger]
    ) -> List[Dict]:
        """Look up person references in semantic memory and get their context."""
        resolved = []
        
        for ref in person_refs:
            entities = self.semantic.search_entities(
                ref,
                entity_types=["PERSON"],
                trusted_only=True,
                limit=1
            )
            
            if entities:
                person = entities[0]
                person_dict = person.to_dict()
                
                rel_types = [
                    "MEMBER_OF",
                    "MANAGES",
                    "OWNS",
                    "ESCALATES_TO"
                ]
                relationships = self.semantic.get_entity_relationships(
                    str(person.id),
                    relationship_types=rel_types
                )
                
                person_dict["resolved_from_rule"] = True
                person_dict["role_context"] = []
                
                for rel in relationships:
                    rel_info = {
                        "type": rel.get("relationship_type", "UNKNOWN"),
                        "target": rel.get("connected_entity", {}).get("name", "Unknown")
                    }
                    person_dict["role_context"].append(rel_info)
                
                resolved.append(person_dict)
                logger.debug(f"Resolved person reference '{ref}': {person.name} with {len(relationships)} relationships")
        
        return resolved
    
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
    
    def _query_symbolic_memory_for_rules(
        self,
        query_text: str,
        context_keywords: List[str],
        max_rules: int,
        query_logger: Optional[QueryLogger]
    ) -> List[Dict]:
        """
        Query symbolic memory specifically for rule/policy queries.
        
        For rule queries, we fetch ALL relevant rules and score them by
        keyword match - this ensures we don't miss applicable policies.
        """
        query_lower = query_text.lower()
        
        rule_keywords = list(context_keywords)
        
        keyword_expansions = {
            'escalation': ['escalation', 'escalate', 'sev1', 'sev2', 'severity', 'incident'],
            'notification': ['notification', 'notify', 'alert', 'page', 'pager'],
            'approval': ['approval', 'approve', 'budget', 'authority', 'sign off'],
            'security': ['security', 'breach', 'attack', 'vulnerability', 'incident'],
            'hiring': ['hiring', 'hire', 'headcount', 'team', 'director', 'vp'],
            'database': ['database', 'db', 'platform'],
            'payment': ['payment', 'transaction', 'financial'],
        }
        
        for category, kws in keyword_expansions.items():
            if any(kw in query_lower for kw in kws):
                rule_keywords.extend(kws)
        
        rule_keywords = list(set(rule_keywords))
        
        all_rules = self.symbolic.get_active_rules()
        scored_rules = []
        
        for rule in all_rules:
            score = 0
            match_reasons = []
            
            rule_text = f"{rule.name} {rule.description} {rule.condition} {rule.action}".lower()
            
            for keyword in rule_keywords:
                if keyword.lower() in rule_text:
                    score += 2
                    match_reasons.append(f"keyword: {keyword}")
            
            if 'escalat' in query_lower and rule.rule_type.value == 'ESCALATION_POLICY':
                score += 5
                match_reasons.append("rule_type: escalation")
            if 'notif' in query_lower and 'notify' in rule_text:
                score += 5
                match_reasons.append("action: notification")
            if 'approv' in query_lower and 'approval' in rule_text:
                score += 5
                match_reasons.append("action: approval")
            if 'sev1' in query_lower or 'sev 1' in query_lower:
                if 'sev1' in rule_text or 'severity' in rule_text:
                    score += 5
                    match_reasons.append("severity match")
            
            if score > 0:
                scored_rules.append({
                    **rule.to_dict(),
                    "match_score": score,
                    "match_reasons": match_reasons
                })
        
        scored_rules.sort(key=lambda x: (x["match_score"], x["priority"]), reverse=True)
        
        if len(scored_rules) == 0:
            logger.info("No matched rules for rule query, returning all active rules")
            scored_rules = [r.to_dict() for r in all_rules[:max_rules]]
        else:
            scored_rules = scored_rules[:max_rules]
        
        if query_logger:
            query_logger.log_event("SYMBOLIC_QUERY_FOR_RULES", {
                "rules_found": len(scored_rules),
                "rule_names": [r["name"] for r in scored_rules],
                "keywords_used": rule_keywords
            })
        
        logger.debug(f"Rule query symbolic search: {len(scored_rules)} applicable rules")
        
        return scored_rules
    
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
