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
        
        query_type = self._classify_query_type(query_text)
        bundle.query_type = query_type
        
        if query_logger:
            query_logger.log_event("QUERY_CLASSIFICATION", {
                "query_type": query_type,
                "query": query_text[:100]
            })
        
        if query_type == 'rule':
            logger.info(f"RULE QUERY detected: skipping entity extraction")
            keywords = self._extract_rule_context_keywords(query_text)
            entity_types = []
            target_entity_name = None
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
                "inferred_entity_types": [t.value for t in entity_types] if entity_types else [],
                "target_entity": target_entity_name,
                "target_entity_found": bundle.target_entity_found,
                "query_type": query_type
            })
        
        if query_type != 'rule' and not target_entity_name:
            potential_entities = self._find_potential_entity_names(query_text)
            if potential_entities:
                for pe in potential_entities:
                    found, entity_match = self._verify_target_entity_exists(pe)
                    if not found:
                        bundle.target_entity_name = pe
                        bundle.target_entity_found = False
                        bundle.target_entity_match = None
                        logger.warning(f"POTENTIAL ENTITY NOT FOUND: '{pe}' detected in query but not in graph")
                        break
        
        is_impact = self._is_impact_query(query_text)
        if is_impact and query_logger:
            query_logger.log_event("IMPACT_QUERY_DETECTED", {
                "target_entity": target_entity_name,
                "traversal_direction": "incoming"
            })
        
        semantic_results = self._query_semantic_memory(
            keywords, entity_types, traverse_depth, max_entities, query_logger,
            is_impact_query=is_impact,
            target_entity_name=target_entity_name
        )
        bundle.semantic_entities = semantic_results["entities"]
        bundle.semantic_relationships = semantic_results["relationships"]
        
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
        else:
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
    
    def _is_impact_query(self, query_text: str) -> bool:
        """
        Detect if this is a blast radius / impact analysis query.
        
        These queries ask "if X breaks, what else breaks?" which means we need
        to find entities that DEPEND ON X (incoming DEPENDS_ON), not what X depends on.
        """
        query_lower = query_text.lower()
        impact_keywords = [
            'blast radius', 'impact', 'affected', 'affects', 
            'goes down', 'becomes unavailable', 'fails', 'failure',
            'breaks', 'crashes', 'is down', 'is corrupted', 'is unavailable',
            'what services', 'which services', 'what depends', 'what breaks',
            'downstream', 'cascade', 'ripple effect'
        ]
        return any(kw in query_lower for kw in impact_keywords)
    
    def _is_edge_facing_entity(self, entity_name: str) -> bool:
        """Check if entity is edge-facing (receives external traffic)."""
        edge_keywords = ['api gateway', 'load balancer', 'cdn', 'ingress', 'edge', 'frontend']
        return any(kw in entity_name.lower() for kw in edge_keywords)
    
    def _classify_query_type(self, query_text: str) -> str:
        """
        Classify the query type to determine the retrieval strategy.
        
        Returns one of:
        - 'entity': Looking for information about a specific entity
        - 'rule': Looking for policies, procedures, escalation paths, approval flows
        - 'impact': Blast radius / cascade analysis (already handled separately)
        - 'general': General question that needs all memory layers
        
        RULE QUERIES are characterized by:
        - Asking about processes, procedures, policies
        - Questions with "should", "when", "what's the process"
        - Escalation, approval, notification questions
        - No specific named entity being queried
        """
        query_lower = query_text.lower()
        
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
        
        This is the PRIMARY method for entity extraction - it's more reliable
        than regex patterns because it matches against actual entities that exist.
        
        ROBUST MATCHING STRATEGY:
        1. Exact match (case-insensitive with word boundaries)
        2. Fuzzy match: "Marketing team" → finds "Marketing Department" 
        3. Core word match: extracts significant words and matches
        4. Type prioritization: prefer SERVICE/TEAM/DATABASE over INCIDENT
        
        Returns the longest matching entity name found in the query.
        """
        try:
            entities = self.session.query(Entity.name, Entity.entity_type).filter(
                Entity.lifecycle_state == 'TRUSTED'
            ).all()
            entity_data = {e[0]: e[1] for e in entities}
            entity_names = list(set([e[0] for e in entities]))
        except Exception:
            return None
        
        if not entity_names:
            return None
        
        query_lower = query_text.lower()
        query_normalized = re.sub(r'[^\w\s]', ' ', query_lower)
        query_words = set(query_normalized.split())
        
        matches = []
        
        for name in entity_names:
            name_lower = name.lower()
            name_normalized = re.sub(r'[^\w\s]', ' ', name_lower)
            
            if re.search(rf'\b{re.escape(name_lower)}\b', query_lower):
                matches.append((name, 100, len(name)))
                continue
            
            name_words = set(name_normalized.split())
            common_words = name_words & query_words
            
            type_suffixes = {'team', 'department', 'service', 'database', 'cache', 'queue', 'gateway', 'api', 'system'}
            query_stop_words = {'the', 'a', 'an', 'for', 'of', 'what', 'who', 'is', 'are', 'does', 'do', "what's", 'whats', 'budget', 'issues', 'problems', 'status'}
            significant_name_words = name_words - type_suffixes - {'org', 'the', 'a', 'an'}
            significant_query_words = query_words - type_suffixes - query_stop_words
            
            if significant_name_words and significant_name_words <= significant_query_words:
                score = len(common_words) * 10 + len(name)
                matches.append((name, score, len(name)))
                continue
            
            for sig_word in significant_name_words:
                if len(sig_word) > 3:
                    if re.search(rf'\b{re.escape(sig_word)}\b', query_lower):
                        score = len(common_words) * 5 + len(name)
                        matches.append((name, score, len(name)))
                        break
        
        if not matches:
            return None
        
        has_org_hint = 'org:' in query_lower or ' org ' in query_lower
        has_incident_hint = any(w in query_lower for w in ['incident', 'outage', 'inc-', 'sev1', 'sev2'])
        
        if len(matches) > 1:
            if has_org_hint:
                org_matches = [m for m in matches if m[0].lower().startswith('org:')]
                if org_matches:
                    matches = org_matches
            else:
                non_org_matches = [m for m in matches if not m[0].lower().startswith('org:')]
                if non_org_matches:
                    matches = non_org_matches
            
            if not has_incident_hint:
                core_types = {'SERVICE', 'TEAM', 'DATABASE', 'COMPONENT', 'PERSON'}
                core_matches = [m for m in matches if entity_data.get(m[0]) in core_types]
                if core_matches:
                    matches = core_matches
        
        matches.sort(key=lambda x: (-x[1], len(x[0])))
        
        logger.debug(f"Entity match candidates: {[m[0] for m in matches[:3]]}, selected: {matches[0][0]}")
        return matches[0][0]
    
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
        # Entity pattern - now accepts both lower and upper case starting letters
        ENTITY_PATTERN = rf'([A-Za-z][a-zA-Z]*(?:\s+[A-Za-z][a-zA-Z]*)*(?:\s+{ENTITY_SUFFIXES})?)'
        
        # Pattern 1: Quoted entity names (highest priority)
        quoted = re.findall(r'["\']([^"\']+)["\']', query_text)
        if quoted:
            return self._normalize_entity_name(quoted[0])
        
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
        query_logger: Optional[QueryLogger],
        is_impact_query: bool = False,
        target_entity_name: Optional[str] = None
    ) -> Dict:
        """
        Query semantic memory (knowledge graph) for relevant entities and relationships.
        
        For impact/blast radius queries, we traverse INCOMING DEPENDS_ON relationships
        to find what depends on the target entity (downstream impact).
        """
        entities = []
        relationships = []
        seen_entity_ids: Set[str] = set()
        
        for keyword in keywords:
            found = self.semantic.search_entities(
                keyword,
                entity_types=entity_types if entity_types else list(EntityType),
                trusted_only=True,
                limit=5
            )
            
            for entity in found:
                entity_dict = entity.to_dict()
                if entity_dict["id"] not in seen_entity_ids:
                    seen_entity_ids.add(entity_dict["id"])
                    entities.append(entity_dict)
        
        entities_to_traverse = list(entities)[:10]
        
        if is_impact_query and target_entity_name:
            target_entity = self.semantic.find_entity_by_name(target_entity_name)
            if target_entity:
                target_dict = target_entity.to_dict()
                if target_dict["id"] not in seen_entity_ids:
                    seen_entity_ids.add(target_dict["id"])
                    entities.insert(0, target_dict)
                
                downstream = self.semantic.traverse_dependencies(
                    target_entity.id,
                    relationship_type=RelationshipType.DEPENDS_ON,
                    direction="incoming",
                    max_depth=traverse_depth
                )
                
                for item in downstream:
                    connected = item["entity"]
                    if connected["id"] not in seen_entity_ids:
                        seen_entity_ids.add(connected["id"])
                        entities.append(connected)
                    
                    rel_dict = item["relationship"]
                    if rel_dict not in relationships:
                        relationships.append(rel_dict)
                
                logger.info(f"Impact query: found {len(downstream)} downstream dependencies for {target_entity_name}")
                
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
                rels = self.semantic.get_entity_relationships(
                    entity_id,
                    relationship_types=[RelationshipType.DEPENDS_ON],
                    direction="incoming",
                    trusted_only=True
                )
            else:
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
