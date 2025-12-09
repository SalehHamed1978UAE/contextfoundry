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
from typing import Dict, List, Optional, Tuple, Set
from openai import OpenAI

from ..models.context_bundle import ContextBundle, EvidenceItem
from ..utils.logger import logger, QueryLogger
from ..config.domain_schema import get_schema_loader, DomainSchema

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
    
    return f"""You are a helpful expert explaining system information to a colleague in the {schema.domain} domain.

You have access to:
1. SEMANTIC MEMORY: Entities and relationships from the knowledge graph
   - Entity types: {entity_types}
   - Relationship types: {relationship_types}
2. EPISODIC MEMORY: Related documents (runbooks, incident reports, procedures)
3. SYMBOLIC MEMORY: Business rules and policies

COMMUNICATION STYLE:
- Write like a knowledgeable colleague, NOT a database query result
- Answer the ACTUAL question asked (who to notify, what's affected, etc.)
- Explain WHY each thing is affected (the causal chain)
- Mention who owns/manages affected services if that info is in the context
- Acknowledge what you DON'T know naturally, without structured headers
- Be conversational and helpful

DO NOT:
- List raw entity names with dashes like "- Auth Gateway"
- Use robotic headers like "Confirmed Impact:" or "Inferred Impact:"
- Output structured data formats in your answer text
- Sound like a database query result
- Include the START entity (the thing failing) in your impact list - it's the CAUSE, not an EFFECT

DO:
- Explain in natural conversational English
- Include team/owner names when they exist in entity properties
- Explain the causal chain (X fails -> Y is affected because...)
- Suggest who to contact when you have that information
- Be honest about gaps: "I don't have documented owners for X - you may need to check Slack."

QUESTION TYPES - Answer the SPECIFIC question:
- "who to notify" or "who should I contact" -> Include teams, owners, contacts from entity properties
- "what's affected" -> List services with explanation of WHY
- "blast radius" -> Show the cascade of failures with causal explanation
- "escalation path" -> Pull from symbolic memory rules and ESCALATES_TO relationships

EXAMPLE GOOD ANSWER:
"The Auth Gateway will fail immediately since it queries User Database on every request. 
Frontend App will start showing login errors within seconds. You should notify the 
Platform Team who owns both services. I don't have contact info for the DBA team in 
my records, but they should probably be looped in for corruption assessment."

EXAMPLE BAD ANSWER:
"Confirmed Impact: - Auth Gateway - Frontend App. Knowledge Boundaries: - Frontend App"

RESPONSE FORMAT (JSON):
{{
    "answer": "Your conversational answer here - NO structured headers like 'Confirmed:' in this text",
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
    
    SIMILARITY_THRESHOLD = 0.40
    
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
        
        OPTIMIZATION: Skip sufficiency LLM call for impact queries with traversal results,
        since we can calculate confidence directly from the traversal data.
        
        Returns a structured response with answer, confidence, evidence, and uncertainty.
        """
        import time
        timing = {"start": time.time()}
        
        context_str = bundle.to_llm_context()
        timing["context_build"] = time.time()
        
        entity_density, grounding_entities = self.calculate_entity_density(bundle.episodic_documents)
        timing["entity_density"] = time.time()
        
        # OPTIMIZATION: Skip sufficiency check for impact queries with confirmed traversal
        # This saves ~3-5 seconds per query by avoiding an extra LLM call
        has_traversal_results = bundle.blast_radius_entities or bundle.frontier
        
        # Log optimization check details
        logger.info(f"OPTIMIZATION CHECK: query_type={bundle.query_type}, "
                   f"has_blast_radius={bool(bundle.blast_radius_entities)}, "
                   f"blast_radius_count={len(bundle.blast_radius_entities) if bundle.blast_radius_entities else 0}, "
                   f"has_frontier={bool(bundle.frontier)}")
        
        if bundle.query_type == 'impact' and has_traversal_results:
            # For impact queries with traversal, we can directly determine sufficiency
            # - If we have confirmed entities: SUFFICIENT (we know what's affected)
            # - If we only have frontier: PARTIAL (we know where knowledge ends)
            if bundle.blast_radius_entities:
                sufficiency = "SUFFICIENT"
                sufficiency_details = {
                    "classification": "SUFFICIENT",
                    "explanation": f"Graph traversal found {len(bundle.blast_radius_entities)} affected entities",
                    "key_facts_found": bundle.blast_radius_entities,
                    "key_facts_missing": bundle.gaps_identified if bundle.gaps_identified else []
                }
            else:
                sufficiency = "PARTIAL"
                sufficiency_details = {
                    "classification": "PARTIAL",
                    "explanation": "Graph traversal found no affected entities, only frontier nodes",
                    "key_facts_found": [],
                    "key_facts_missing": bundle.gaps_identified if bundle.gaps_identified else []
                }
            logger.info(f"OPTIMIZATION TRIGGERED: Skipped sufficiency LLM call for impact query")
            timing["sufficiency"] = time.time()
        else:
            logger.info(f"OPTIMIZATION NOT TRIGGERED: Running sufficiency LLM call")
            sufficiency, sufficiency_details = self.check_sufficiency(bundle.query_text, context_str)
            timing["sufficiency"] = time.time()
        
        calibrated_confidence, quadrant = self.calculate_quadrant_confidence(
            bundle, sufficiency, entity_density
        )
        timing["confidence_calc"] = time.time()
        
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
            timing["prompt_build"] = time.time()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": reasoning_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.0,  # Deterministic for consistent answers
                max_completion_tokens=3500,  # Increased from 2000 for conversational responses
                response_format={"type": "json_object"}
            )
            timing["llm_call"] = time.time()
            
            response_text = response.choices[0].message.content or ""
            
            # Check for truncation - warn if response seems incomplete
            finish_reason = response.choices[0].finish_reason
            if finish_reason == "length":
                logger.warning(f"RESPONSE TRUNCATED: finish_reason=length, tokens may have hit limit")
            elif response_text.endswith(('...', '…')) or (len(response_text) > 100 and not response_text.rstrip().endswith(('}', '"', '.', '!', '?'))):
                logger.warning(f"POTENTIAL TRUNCATION: response ends with '{response_text[-50:]}'")
            
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                result = self._parse_fallback(response_text)
            
            result = self._validate_and_enrich_response(
                result, bundle, calibrated_confidence, quadrant, 
                sufficiency, entity_density, grounding_entities
            )
            timing["end"] = time.time()
            
            # Log timing breakdown
            timing_breakdown = {
                "context_build_ms": int((timing["context_build"] - timing["start"]) * 1000),
                "entity_density_ms": int((timing["entity_density"] - timing["context_build"]) * 1000),
                "sufficiency_ms": int((timing["sufficiency"] - timing["entity_density"]) * 1000),
                "confidence_calc_ms": int((timing["confidence_calc"] - timing["sufficiency"]) * 1000),
                "prompt_build_ms": int((timing["prompt_build"] - timing["confidence_calc"]) * 1000),
                "llm_call_ms": int((timing["llm_call"] - timing["prompt_build"]) * 1000),
                "total_ms": int((timing["end"] - timing["start"]) * 1000)
            }
            logger.info(f"REASONING TIMING: {timing_breakdown}")
            
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
            import json as json_module
            result["answer"] = json_module.dumps(result["answer"]) if isinstance(result["answer"], (dict, list)) else str(result["answer"])
        
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
