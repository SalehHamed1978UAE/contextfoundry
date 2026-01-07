"""
Reasoning Agent - Uses LLM to generate responses from ContextBundles.
Produces responses with confidence scores and evidence chains.

Uses Replit AI Integrations for OpenAI access (no API key required, billed to credits).

Implements Sufficiency Autorater + Quadrant Confidence + Entity Density Scoring
for calibrated confidence that works for both entity-centric and topic-centric queries.
"""
import os
import json
import re
from typing import Any, Dict, List, Optional, Tuple, Set
from openai import OpenAI

from ..models.context_bundle import ContextBundle, EvidenceItem
from ..utils.logger import logger, QueryLogger
from ..config.domain_schema import get_schema_loader, DomainSchema
from .query_classifier import classify_query, get_data_sufficiency, format_no_relationships_response, format_sparse_response, should_gate_query

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")

SUFFICIENCY_PROMPT = """You are evaluating whether retrieved context is sufficient to answer a user query.

Query: {query}

Retrieved Context:
{context}

Think step by step:
1. What specific information does the query need?
2. Does the context contain that information?
3. Is the information complete or partial?

Respond with EXACTLY this JSON format:
{{
    "classification": "SUFFICIENT" | "PARTIAL" | "INSUFFICIENT",
    "explanation": "Brief 1-2 sentence explanation",
    "key_facts_found": ["list of key facts found in context"],
    "key_facts_missing": ["list of key facts needed but not found"]
}}

SUFFICIENT = Context contains all key information needed to answer confidently
PARTIAL = Context contains some relevant information but is incomplete
INSUFFICIENT = Context does not contain the information needed to answer"""

def _build_reasoning_system_prompt(schema: DomainSchema) -> str:
    """
    Build a domain-agnostic reasoning system prompt.
    
    Uses the currently loaded schema to describe the domain context,
    making the reasoning agent work for any domain (IT Ops, Fiction, Healthcare, etc.).
    """
    entity_types = ", ".join(schema.get_entity_type_names())
    relationship_types = ", ".join(schema.get_relationship_type_names())
    
    return f"""You are a Context Foundry reasoning agent for {schema.domain}.

You will receive a ContextBundle containing:
1. SEMANTIC MEMORY: Entities and relationships from the knowledge graph
   - Entity types in this domain: {entity_types}
   - Relationship types: {relationship_types}
2. EPISODIC MEMORY: Similar documents from vector search
3. SYMBOLIC MEMORY: Business rules and policies that apply

Your task is to answer the user's query based ONLY on the provided context.

CRITICAL RULES:
1. Only use information from the provided context - NEVER make up facts
2. For ENTITY-CENTRIC queries (about specific entities like {entity_types.split(", ")[0] if entity_types else "entities"}):
   - Use semantic memory (entities/relationships) as primary evidence
   - Supplement with episodic memory (documents) for additional detail
3. For TOPIC-CENTRIC queries (about general topics, events, or concepts):
   - Episodic memory (documents) may be the primary evidence source
   - Synthesize information from relevant documents even if no matching entity exists
   - Ground answers by referencing known entities mentioned in documents
4. Only cite facts that are EXPLICITLY stated in the context
5. If information is missing or uncertain, explicitly say so
6. Rate your confidence (0.0-1.0) based on evidence quality and completeness
7. Always check if any rules apply to your response

SPECIAL: IMPACT/BLAST RADIUS QUERIES
For queries about "blast radius", "impact", "what happens if X goes down", "what is affected", or dependency analysis:

CRITICAL DIRECTION RULE:
- BLAST RADIUS = DOWNSTREAM = entities that DEPEND ON the failing service
- You must find: "X DEPENDS_ON [FailingService]" where [FailingService] is the TARGET
- NOT: "[FailingService] DEPENDS_ON Y" (that's upstream, not blast radius)

Your answer MUST follow this exact structure with TWO labeled sections ONLY:

GROUNDED (facts from TRUSTED data only):
- List ONLY entities that DEPEND ON the failing service (downstream dependents)
- Look for relationships where the failing service is the TARGET of DEPENDS_ON
- Use format: "[Dependent] depends on [FailingService] [REL-xxx]" for each - CITE THE RELATIONSHIP ID
- If no entities depend on the failing service, say: "No services are documented as depending on [FailingService]"
- Do NOT list what the failing service depends on (that's upstream, irrelevant to blast radius)
- EVERY claim MUST cite a specific relationship ID from the context

GAPS (what is not documented):
- If information is missing, explicitly state what's not documented
- Say: "No documented [relationship type] for this entity"
- Be explicit about missing information - this is valuable, not a failure

DO NOT INCLUDE AN INFERRED SECTION:
- Do NOT suggest possible or likely relationships
- Do NOT use phrases like "might depend on" or "probably connects to"
- Do NOT use your general knowledge to fill gaps
- If no relationships exist, simply say so - do NOT speculate

EXAMPLE for "What is blast radius if API Gateway becomes unavailable?":
"GROUNDED:
- Payment Service depends on API Gateway [REL-abc123]
- User Authentication depends on API Gateway [REL-def456]

GAPS:
- No documentation about which external clients connect through API Gateway
- Consider updating the service catalog with client information"

WRONG - DO NOT DO THIS:
"Based on typical architecture, Mobile App probably routes through API Gateway..."
This is SPECULATION and is FORBIDDEN. If it's not in the relationships, don't mention it.

RESPONSE FORMAT (JSON):
{{
    "answer": "Your structured answer following GROUNDED/GAPS format for impact queries, or regular format otherwise",
    "confidence": 0.85,
    "confidence_level": "high|medium|low|very_low",
    "evidence_chain": [
        {{
            "type": "entity|relationship|document|rule",
            "description": "What this evidence shows",
            "source": "Name of source entity/document/rule",
            "confidence": 0.9
        }}
    ],
    "uncertainty": {{
        "uncertain_facts": ["List of facts you're unsure about"],
        "reasons": ["Why you're uncertain"],
        "would_help": ["What additional info would help"]
    }},
    "rules_applied": ["List of rules that apply to this response"],
    "caveats": ["Any important caveats or warnings"]
}}"""


REASONING_SYSTEM_PROMPT = None


class ReasoningAgent:
    """
    Agent that uses an LLM to reason over ContextBundles.
    Generates responses with full provenance and confidence scoring.
    
    Uses Replit AI Integrations for OpenAI access.
    
    Implements 3-phase confidence calibration:
    1. Sufficiency Autorater - LLM evaluates if context can answer the query
    2. Quadrant Confidence - 4-quadrant scoring based on entity+docs presence
    3. Entity Density Scoring - Proxy grounding via known entity mentions
    """
    
    SIMILARITY_THRESHOLD = 0.35
    
    def __init__(self):
        self.client = OpenAI(
            api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
            base_url=AI_INTEGRATIONS_OPENAI_BASE_URL
        )
        self.model = "gpt-4o-mini"
        self._known_entities: Optional[Set[str]] = None
        logger.info(f"ReasoningAgent initialized with model: {self.model}")
    
    def _get_known_entities(self) -> Set[str]:
        """Lazily load and cache known entity names from the database."""
        if self._known_entities is None:
            try:
                from ..models.schema import Entity, get_session
                session = get_session()
                entities = session.query(Entity.name).all()
                self._known_entities = {e[0].lower() for e in entities}
                session.close()
                logger.debug(f"Cached {len(self._known_entities)} known entities")
            except Exception as e:
                logger.warning(f"Failed to load known entities: {e}")
                self._known_entities = set()
        return self._known_entities
    
    def check_sufficiency(self, query: str, context: str) -> Tuple[str, Dict]:
        """
        Phase 1: Sufficiency Autorater
        
        Uses LLM to evaluate if retrieved context is sufficient to answer the query.
        Returns: (classification, details_dict)
        - classification: "SUFFICIENT" | "PARTIAL" | "INSUFFICIENT"
        - details_dict: explanation, key_facts_found, key_facts_missing
        """
        try:
            prompt = SUFFICIENCY_PROMPT.format(query=query, context=context[:8000])
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,  # Deterministic for consistency
                max_completion_tokens=500,
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content or ""
            result = json.loads(response_text)
            
            classification = result.get("classification", "PARTIAL").upper()
            if classification not in ["SUFFICIENT", "PARTIAL", "INSUFFICIENT"]:
                classification = "PARTIAL"
            
            logger.info(f"Sufficiency check: {classification} - {result.get('explanation', '')[:100]}")
            return classification, result
            
        except Exception as e:
            logger.warning(f"Sufficiency check failed: {e}, defaulting to PARTIAL")
            return "PARTIAL", {"explanation": "Sufficiency check failed", "key_facts_found": [], "key_facts_missing": []}
    
    def calculate_entity_density(self, documents: List[Dict]) -> Tuple[float, List[str]]:
        """
        Phase 3: Entity Density Scoring
        
        Measures how many known entities are mentioned in retrieved documents.
        High density = proxy grounding = higher confidence for topic-centric queries.
        
        Returns: (density_score 0.0-1.0, list of known entities found)
        """
        known_entities = self._get_known_entities()
        if not known_entities or not documents:
            return 0.0, []
        
        doc_text = " ".join([
            doc.get("content", "") + " " + doc.get("title", "")
            for doc in documents
        ]).lower()
        
        found_entities = []
        for entity in known_entities:
            if len(entity) >= 3:
                pattern = r'\b' + re.escape(entity) + r'\b'
                if re.search(pattern, doc_text):
                    found_entities.append(entity)
        
        if not found_entities:
            return 0.0, []
        
        density = min(len(found_entities) / 10.0, 1.0)
        
        logger.debug(f"Entity density: {density:.2f} ({len(found_entities)} entities found: {found_entities[:5]})")
        return density, found_entities
    
    def calculate_quadrant_confidence(
        self,
        bundle: ContextBundle,
        sufficiency: str,
        entity_density: float
    ) -> Tuple[float, str]:
        """
        Phase 2: Quadrant Confidence Calculation
        
        Replaces the entity-not-found guard with nuanced quadrant logic:
        
        Quadrant 1: Entity found + Good docs → 0.90 base (best case)
        Quadrant 2: Entity found + No docs → 0.70 base (graph only)
        Quadrant 3: No entity + Good docs → 0.65 base (topic-centric - WAS BROKEN)
        Quadrant 4: No entity + No docs → 0.10 base (no evidence)
        
        Adjusted by sufficiency rating and entity density.
        
        Returns: (confidence, quadrant_name)
        """
        entity_found = bundle.target_entity_found
        
        has_good_docs = False
        if bundle.episodic_documents:
            top_similarity = bundle.episodic_documents[0].get('similarity', 0)
            has_good_docs = top_similarity > self.SIMILARITY_THRESHOLD
        
        if entity_found and has_good_docs:
            base = 0.90
            quadrant = "Q1_entity_and_docs"
        elif entity_found and not has_good_docs:
            base = 0.70
            quadrant = "Q2_entity_only"
        elif not entity_found and has_good_docs:
            base = 0.65
            quadrant = "Q3_docs_only"
            if entity_density > 0.3:
                base += 0.10
                quadrant = "Q3_docs_grounded"
        else:
            base = 0.10
            quadrant = "Q4_no_evidence"
        
        if sufficiency == "SUFFICIENT":
            confidence = min(base + 0.10, 0.95)
        elif sufficiency == "PARTIAL":
            confidence = base * 0.85
        else:
            # INSUFFICIENT sufficiency - but entity existence still counts as evidence
            if quadrant in ["Q1_entity_and_docs", "Q3_docs_grounded"]:
                confidence = base * 0.55
            elif quadrant == "Q2_entity_only":
                # Entity exists but no supporting docs - moderate penalty
                # The entity's existence IS evidence, so don't drop too low
                confidence = base * 0.65  # 0.70 * 0.65 = 0.455 → rounds to ~0.45
            else:
                # Q3_docs_only or Q4_no_evidence with INSUFFICIENT
                confidence = min(base, 0.20)
        
        # CRITICAL: If the query explicitly targets an entity that doesn't exist,
        # cap confidence low regardless of related document matches.
        # This prevents hallucination when asking about non-existent entities.
        if bundle.target_entity_name and not entity_found:
            max_confidence_when_target_missing = 0.40
            if confidence > max_confidence_when_target_missing:
                logger.info(f"Capping confidence: target entity '{bundle.target_entity_name}' not found in graph")
                confidence = max_confidence_when_target_missing
                quadrant = f"{quadrant}_TARGET_MISSING"
        
        logger.info(f"Quadrant confidence: {quadrant} base={base:.2f} sufficiency={sufficiency} → {confidence:.2f}")
        return confidence, quadrant
    
    def reason(
        self,
        bundle: ContextBundle,
        query_logger: Optional[QueryLogger] = None
    ) -> Dict:
        """
        Generate a reasoned response from a ContextBundle.
        
        Uses 3-phase confidence calibration:
        1. Sufficiency Autorater - LLM evaluates if context can answer the query
        2. Quadrant Confidence - 4-quadrant scoring based on entity+docs presence
        3. Entity Density Scoring - Proxy grounding via known entity mentions
        
        Returns a structured response with answer, confidence, evidence, and uncertainty.
        """
        if self._is_blast_radius_query(bundle.query_text) and bundle.target_entity_name and not bundle.target_entity_found:
            logger.warning(f"ENTITY NOT FOUND: '{bundle.target_entity_name}' - refusing to hallucinate for blast radius query")
            if query_logger:
                query_logger.log_event("ENTITY_NOT_FOUND_GUARD", {
                    "target_entity": bundle.target_entity_name,
                    "query_type": "blast_radius",
                    "action": "short_circuit"
                })
            return self._create_entity_not_found_response(bundle)
        
        relationship_guard_result = self._check_relationship_guard(bundle, query_logger)
        if relationship_guard_result:
            return relationship_guard_result
        
        context_str = bundle.to_llm_context()
        
        entity_density, grounding_entities = self.calculate_entity_density(bundle.episodic_documents)
        
        sufficiency, sufficiency_details = self.check_sufficiency(bundle.query_text, context_str)
        
        calibrated_confidence, quadrant = self.calculate_quadrant_confidence(
            bundle, sufficiency, entity_density
        )
        
        if quadrant == "Q4_no_evidence" and sufficiency == "INSUFFICIENT":
            logger.info(f"Insufficient evidence for query, returning low-confidence response")
            return self._create_insufficient_evidence_response(bundle, sufficiency_details)
        
        user_prompt = f"""Query: {bundle.query_text}

{context_str}

Based on the above context, answer the query. Follow the JSON format specified.
If the context doesn't contain enough information, acknowledge the uncertainty.
Cite specific entities, relationships, documents, and rules in your evidence chain."""

        try:
            if query_logger:
                query_logger.log_event("LLM_CALL_START", {
                    "model": self.model,
                    "context_length": len(context_str),
                    "query": bundle.query_text
                })
            
            schema = get_schema_loader().schema
            reasoning_prompt = _build_reasoning_system_prompt(schema)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": reasoning_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,  # Deterministic for consistent answers
                max_completion_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content or ""
            
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                result = self._parse_fallback(response_text)
            
            result = self._validate_and_enrich_response(
                result, bundle, calibrated_confidence, quadrant, 
                sufficiency, entity_density, grounding_entities
            )
            
            if query_logger:
                query_logger.log_reasoning(
                    result.get("answer", ""),
                    result.get("confidence", 0),
                    result.get("evidence_chain", [])
                )
            
            logger.info(f"Reasoning complete: confidence={result.get('confidence', 0):.2f}")
            return result
            
        except Exception as e:
            error_response = self._create_error_response(str(e), bundle)
            
            if query_logger:
                query_logger.log_error("LLM_ERROR", str(e), {
                    "model": self.model,
                    "query": bundle.query_text
                })
            
            logger.error(f"Reasoning error: {e}")
            return error_response
    
    def _parse_fallback(self, response_text: str) -> Dict:
        """Fallback parsing if JSON parsing fails."""
        return {
            "answer": response_text,
            "confidence": 0.5,
            "confidence_level": "low",
            "evidence_chain": [],
            "uncertainty": {
                "uncertain_facts": [],
                "reasons": ["Response was not in expected format"],
                "would_help": []
            },
            "rules_applied": [],
            "caveats": ["Response format was non-standard"]
        }
    
    def _synthesize_structured_answer(self, structured_data: Any, confidence: float) -> str:
        """
        Synthesize structured GROUNDED/GAPS data into natural language with confidence markers.
        
        Converts JSON like {"GROUNDED": [...], "GAPS": [...]} into readable prose.
        """
        if not isinstance(structured_data, dict):
            return str(structured_data)
        
        lines = []
        confidence_marker = "🟢" if confidence >= 0.85 else "🟡" if confidence >= 0.70 else "🟠" if confidence >= 0.50 else "🔴"
        
        grounded = structured_data.get("GROUNDED", structured_data.get("grounded", []))
        gaps = structured_data.get("GAPS", structured_data.get("gaps", []))
        
        if grounded:
            lines.append(f"{confidence_marker} **Confirmed Impact** (from documented relationships):")
            if isinstance(grounded, list):
                for item in grounded:
                    lines.append(f"  • {item}")
            else:
                lines.append(f"  • {grounded}")
            lines.append("")
        
        if gaps:
            lines.append("⚠️ **Documentation Gaps** (not yet documented):")
            if isinstance(gaps, list):
                for item in gaps:
                    lines.append(f"  • {item}")
            else:
                lines.append(f"  • {gaps}")
            lines.append("")
        
        if not grounded and not gaps:
            import json as json_module
            return json_module.dumps(structured_data)
        
        conf_level = "high" if confidence >= 0.85 else "medium" if confidence >= 0.70 else "low" if confidence >= 0.50 else "very low"
        lines.append(f"_Confidence: {conf_level} ({confidence:.0%})_")
        
        return "\n".join(lines)
    
    def _validate_and_enrich_response(
        self, 
        result: Dict, 
        bundle: ContextBundle,
        calibrated_confidence: float,
        quadrant: str,
        sufficiency: str,
        entity_density: float,
        grounding_entities: List[str]
    ) -> Dict:
        """
        Validate and enrich the LLM response with additional context.
        
        Applies calibrated confidence from the 3-phase system instead of
        relying solely on LLM's self-reported confidence.
        """
        if "answer" not in result:
            result["answer"] = "Unable to generate answer from context."
        elif not isinstance(result["answer"], str):
            result["answer"] = self._synthesize_structured_answer(result["answer"], calibrated_confidence)
        
        result["confidence"] = calibrated_confidence
        
        result["confidence_calibration"] = {
            "quadrant": quadrant,
            "sufficiency": sufficiency,
            "entity_density": entity_density,
            "grounding_entities": grounding_entities[:10],
            "llm_self_confidence": result.get("confidence", 0.5)
        }
        
        if calibrated_confidence >= 0.85:
            result["confidence_level"] = "high"
        elif calibrated_confidence >= 0.70:
            result["confidence_level"] = "medium"
        elif calibrated_confidence >= 0.50:
            result["confidence_level"] = "low"
        else:
            result["confidence_level"] = "very_low"
        
        if "evidence_chain" not in result:
            result["evidence_chain"] = []
        
        for entity in bundle.semantic_entities[:3]:
            result["evidence_chain"].append({
                "type": "entity",
                "description": f"Entity from knowledge graph: {entity.get('name')}",
                "source": entity.get("name"),
                "source_document": entity.get("source_document_id"),
                "source_sentence": entity.get("source_sentence"),
                "confidence": entity.get("confidence", 0.5),
                "memory_layer": "semantic"
            })
        
        for rel in bundle.semantic_relationships[:3]:
            result["evidence_chain"].append({
                "type": "relationship",
                "description": f"{rel.get('source_name')} -[{rel.get('relationship_type')}]-> {rel.get('target_name')}",
                "source": f"{rel.get('source_name')} -> {rel.get('target_name')}",
                "source_document": rel.get("source_document_id"),
                "source_sentence": rel.get("source_sentence"),
                "confidence": rel.get("confidence", 0.5),
                "memory_layer": "semantic"
            })
        
        for doc in bundle.episodic_documents[:2]:
            result["evidence_chain"].append({
                "type": "document",
                "description": f"Related document: {doc.get('title')}",
                "source": doc.get("title"),
                "source_document": doc.get("source_document_id"),
                "similarity": doc.get("similarity", 0),
                "memory_layer": "episodic"
            })
        
        for rule in bundle.symbolic_rules[:2]:
            result["evidence_chain"].append({
                "type": "rule",
                "description": f"Applicable rule: {rule.get('name')}",
                "source": rule.get("name"),
                "rule_type": rule.get("rule_type"),
                "action": rule.get("action"),
                "memory_layer": "symbolic"
            })
        
        if "uncertainty" not in result:
            result["uncertainty"] = {}
        
        if bundle.uncertainty:
            result["uncertainty"]["context_confidence"] = bundle.uncertainty.overall_confidence
            result["uncertainty"]["context_recommendation"] = bundle.uncertainty.recommendation
            if bundle.uncertainty.uncertainty_reasons:
                result["uncertainty"]["context_issues"] = bundle.uncertainty.uncertainty_reasons
        
        result["bundle_id"] = bundle.query_id
        result["query_text"] = bundle.query_text
        result["context_bundle"] = bundle.to_dict()
        
        return result
    
    def _create_error_response(self, error_message: str, bundle: ContextBundle) -> Dict:
        """Create a structured error response."""
        return {
            "answer": f"Unable to generate response due to an error: {error_message}",
            "confidence": 0.0,
            "confidence_level": "very_low",
            "error": True,
            "error_message": error_message,
            "evidence_chain": [],
            "uncertainty": {
                "uncertain_facts": ["All facts are uncertain due to error"],
                "reasons": [error_message],
                "would_help": ["Retry the query", "Check LLM availability"]
            },
            "rules_applied": [],
            "caveats": ["This response was generated due to an error"],
            "bundle_id": bundle.query_id,
            "query_text": bundle.query_text,
            "context_bundle": bundle.to_dict()
        }
    
    def _create_insufficient_evidence_response(self, bundle: ContextBundle, sufficiency_details: Dict) -> Dict:
        """
        Create a structured response when there's insufficient evidence to answer.
        
        This replaces the old entity-not-found guard with a more nuanced approach
        that uses the Sufficiency Autorater to determine if we can answer.
        
        Returns a low-confidence response that honestly states limitations.
        """
        missing_facts = sufficiency_details.get("key_facts_missing", [])
        explanation = sufficiency_details.get("explanation", "Insufficient information in the knowledge base")
        
        return {
            "answer": f"I don't have enough information to confidently answer this query. "
                     f"{explanation} "
                     f"The knowledge base was searched but relevant facts were not found. "
                     f"This could mean the topic hasn't been documented, or it may be referred to differently.",
            "confidence": 0.10,
            "confidence_level": "very_low",
            "insufficient_evidence": True,
            "confidence_calibration": {
                "quadrant": "Q4_no_evidence",
                "sufficiency": "INSUFFICIENT",
                "entity_density": 0.0,
                "grounding_entities": [],
                "llm_self_confidence": 0.1
            },
            "evidence_chain": [],
            "uncertainty": {
                "uncertain_facts": missing_facts or ["The information needed to answer this query"],
                "reasons": ["Insufficient evidence in the knowledge base"],
                "would_help": [
                    "Add relevant documents about this topic",
                    "Try rephrasing the query with different terms",
                    "Check if the topic is documented under a different name"
                ]
            },
            "rules_applied": [],
            "caveats": [
                "The knowledge base does not contain sufficient information to answer this query",
                "This is an honest abstention rather than a fabricated answer"
            ],
            "bundle_id": bundle.query_id,
            "query_text": bundle.query_text,
            "context_bundle": bundle.to_dict()
        }
    
    def _is_blast_radius_query(self, query_text: str) -> bool:
        """
        Detect if this is a blast radius / impact analysis query.
        
        These queries REQUIRE the target entity to exist - we cannot hallucinate
        about the impact of a non-existent entity.
        """
        query_lower = query_text.lower()
        blast_radius_patterns = [
            'blast radius',
            'impact',
            'impacted',
            'what happens if',
            'what would happen if',
            'goes down',
            'becomes unavailable',
            'fails',
            'failure',
            'affected',
            'affects',
            'depends on',
            'dependencies'
        ]
        return any(pattern in query_lower for pattern in blast_radius_patterns)
    
    def _find_similar_entities(self, target_name: str, limit: int = 5) -> List[str]:
        """
        Find entities with similar names to suggest as alternatives.
        
        Uses simple substring matching and word overlap.
        """
        from ..models.schema import Entity, LifecycleState, get_session
        
        session = get_session()
        try:
            all_entities = session.query(Entity.name).filter(
                Entity.lifecycle_state.in_([LifecycleState.TRUSTED, LifecycleState.STAGING])
            ).distinct().limit(500).all()
            
            target_lower = target_name.lower()
            target_words = set(target_lower.split())
            
            scored = []
            for (name,) in all_entities:
                name_lower = name.lower()
                score = 0
                if target_lower in name_lower or name_lower in target_lower:
                    score += 3
                name_words = set(name_lower.split())
                common_words = target_words & name_words
                score += len(common_words) * 2
                if score > 0:
                    scored.append((name, score))
            
            scored.sort(key=lambda x: -x[1])
            return [name for name, _ in scored[:limit]]
        except Exception as e:
            logger.warning(f"Failed to find similar entities: {e}")
            return []
        finally:
            session.close()
    
    def _check_relationship_guard(self, bundle: ContextBundle, query_logger: Optional[QueryLogger] = None) -> Optional[Dict]:
        """
        RELATIONSHIP GUARD: Check if query requires relationships but entity has none.
        
        This is the key hallucination prevention mechanism from the 4-LLM consensus:
        "Don't ask the LLM to not hallucinate. Don't give it the opportunity to hallucinate."
        
        Returns:
            - None if query should proceed to LLM
            - Dict response if query should be gated (answered without LLM)
        """
        if not bundle.target_entity_found or not bundle.target_entity_name:
            return None
        
        from ..models.schema import Entity, LifecycleState, get_session
        session = get_session()
        
        try:
            entity = session.query(Entity).filter(
                Entity.name.ilike(bundle.target_entity_name),
                Entity.lifecycle_state == LifecycleState.TRUSTED
            ).first()
            
            if not entity:
                return None
            
            entity_id = str(entity.id)
            entity_type = entity.entity_type
            
            query_type = classify_query(bundle.query_text)
            sufficiency = get_data_sufficiency(session, entity_id)
            
            should_gate, gate_reason = should_gate_query(query_type, sufficiency)
            
            if not should_gate:
                return None
            
            if query_logger:
                query_logger.log_event("RELATIONSHIP_GUARD", {
                    "target_entity": bundle.target_entity_name,
                    "query_type": query_type,
                    "gate_reason": gate_reason,
                    "relationship_count": sufficiency['relationship_count'],
                    "action": "short_circuit"
                })
            
            logger.info(f"RELATIONSHIP GUARD: {bundle.target_entity_name} has {sufficiency['relationship_count']} relationships, gate_reason={gate_reason}")
            
            if gate_reason == 'no_relationships':
                answer = format_no_relationships_response(bundle.target_entity_name, query_type, entity_type)
                return {
                    "answer": answer,
                    "confidence": 1.0,
                    "confidence_level": "high",
                    "grounded": True,
                    "data_gap": "no_relationships",
                    "relationship_count": 0,
                    "entity_found": True,
                    "target_entity": bundle.target_entity_name,
                    "confidence_calibration": {
                        "quadrant": "DATA_GATE_NO_RELATIONSHIPS",
                        "sufficiency": "GROUNDED_GAP",
                        "entity_density": 1.0,
                        "grounding_entities": [bundle.target_entity_name],
                        "llm_self_confidence": None
                    },
                    "evidence_chain": [f"Entity '{bundle.target_entity_name}' exists in knowledge graph"],
                    "uncertainty": {
                        "uncertain_facts": [],
                        "reasons": ["No relationships documented for this entity"],
                        "would_help": [
                            f"Document dependencies for '{bundle.target_entity_name}'",
                            "Upload documentation that describes system connections"
                        ]
                    },
                    "rules_applied": [],
                    "caveats": [
                        "This is a GROUNDED response - we are certain the data gap exists",
                        "No hallucination occurred - LLM was not invoked"
                    ],
                    "bundle_id": bundle.query_id,
                    "query_text": bundle.query_text
                }
            
            elif gate_reason in ['sparse_data', 'insufficient_for_impact']:
                from ..models.schema import Relationship
                from sqlalchemy.orm import joinedload
                rels = session.query(Relationship).options(
                    joinedload(Relationship.source_entity),
                    joinedload(Relationship.target_entity)
                ).filter(
                    Relationship.lifecycle_state == LifecycleState.TRUSTED,
                    (Relationship.source_id == entity_id) | (Relationship.target_id == entity_id)
                ).limit(10).all()
                
                rel_list = []
                for rel in rels:
                    source_name = rel.source_entity.name if rel.source_entity else 'Unknown'
                    target_name = rel.target_entity.name if rel.target_entity else 'Unknown'
                    rel_list.append({
                        'id': str(rel.id)[:8],
                        'source_name': source_name,
                        'target_name': target_name,
                        'relationship_type': rel.relationship_type
                    })
                
                answer = format_sparse_response(bundle.target_entity_name, entity_type, rel_list, sufficiency)
                return {
                    "answer": answer,
                    "confidence": 0.7,
                    "confidence_level": "moderate",
                    "grounded": True,
                    "data_gap": gate_reason,
                    "relationship_count": sufficiency['relationship_count'],
                    "entity_found": True,
                    "target_entity": bundle.target_entity_name,
                    "confidence_calibration": {
                        "quadrant": "DATA_GATE_SPARSE",
                        "sufficiency": "PARTIAL",
                        "entity_density": 1.0,
                        "grounding_entities": [bundle.target_entity_name],
                        "llm_self_confidence": None
                    },
                    "evidence_chain": [f"Entity '{bundle.target_entity_name}' exists with {sufficiency['relationship_count']} relationship(s)"],
                    "uncertainty": {
                        "uncertain_facts": [],
                        "reasons": ["Limited relationship data available"],
                        "would_help": ["Add more documentation about system dependencies"]
                    },
                    "rules_applied": [],
                    "caveats": [
                        "Response based on limited data - no LLM reasoning applied",
                        "Additional relationships may exist but are not documented"
                    ],
                    "bundle_id": bundle.query_id,
                    "query_text": bundle.query_text
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Relationship guard error: {e}")
            return None
        finally:
            session.close()
    
    def _create_entity_not_found_response(self, bundle: ContextBundle) -> Dict:
        """
        Create a structured response when the target entity doesn't exist.
        
        CRITICAL: This prevents hallucination about non-existent entities.
        For blast radius queries, we MUST have a real entity to analyze.
        """
        target_name = bundle.target_entity_name or "Unknown"
        similar_entities = self._find_similar_entities(target_name)
        
        similar_suggestion = ""
        if similar_entities:
            similar_suggestion = f" Did you mean one of these? {', '.join(similar_entities[:3])}"
        
        return {
            "answer": f"Entity '{target_name}' was not found in the knowledge graph. "
                     f"Cannot assess blast radius for a non-existent entity.{similar_suggestion}",
            "confidence": 0.0,
            "confidence_level": "very_low",
            "entity_not_found": True,
            "target_entity": target_name,
            "similar_entities": similar_entities,
            "confidence_calibration": {
                "quadrant": "ENTITY_NOT_FOUND",
                "sufficiency": "NOT_APPLICABLE",
                "entity_density": 0.0,
                "grounding_entities": [],
                "llm_self_confidence": 0.0
            },
            "evidence_chain": [],
            "uncertainty": {
                "uncertain_facts": [f"Entity '{target_name}' does not exist in the knowledge graph"],
                "reasons": ["The queried entity was not found in the knowledge base"],
                "would_help": [
                    f"Add documentation about '{target_name}' to the knowledge base",
                    "Verify the exact name of the entity you're querying",
                    "Check if the entity exists under a different name"
                ]
            },
            "rules_applied": [],
            "caveats": [
                "This is NOT a hallucinated response - the entity genuinely doesn't exist",
                "Context Foundry refuses to fabricate information about non-existent entities"
            ],
            "bundle_id": bundle.query_id,
            "query_text": bundle.query_text,
            "context_bundle": bundle.to_dict()
        }
