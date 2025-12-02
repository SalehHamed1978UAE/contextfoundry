"""
Reasoning Agent - Uses LLM to generate responses from ContextBundles.
Produces responses with confidence scores and evidence chains.

Uses Replit AI Integrations for OpenAI access (no API key required, billed to credits).
"""
import os
import json
from typing import Dict, List, Optional
from openai import OpenAI

from ..models.context_bundle import ContextBundle, EvidenceItem
from ..utils.logger import logger, QueryLogger

AI_INTEGRATIONS_OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY")
AI_INTEGRATIONS_OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")

REASONING_SYSTEM_PROMPT = """You are a Context Foundry reasoning agent for IT operations.

You will receive a ContextBundle containing:
1. SEMANTIC MEMORY: Entities and relationships from the knowledge graph (services, teams, people, incidents)
2. EPISODIC MEMORY: Similar documents and runbooks from vector search
3. SYMBOLIC MEMORY: Business rules and policies that apply

Your task is to answer the user's query based ONLY on the provided context.

CRITICAL RULES:
1. Only use information from the provided context - NEVER make up facts
2. If the context says "TARGET ENTITY NOT FOUND", you MUST:
   - Set confidence to 0.1 or lower
   - State clearly that the entity does not exist in the knowledge graph
   - Do NOT fabricate relationships or information about non-existent entities
   - Do NOT cite relationships from unrelated entities as if they apply to the missing entity
3. Only cite relationships that are EXPLICITLY shown in the context
4. If information is missing or uncertain, explicitly say so
5. Rate your confidence (0.0-1.0) based on context quality
6. Always check if any rules apply to your response

RESPONSE FORMAT (JSON):
{
    "answer": "Your detailed answer here",
    "confidence": 0.85,
    "confidence_level": "high|medium|low|very_low",
    "evidence_chain": [
        {
            "type": "entity|relationship|document|rule",
            "description": "What this evidence shows",
            "source": "Name of source entity/document/rule",
            "confidence": 0.9
        }
    ],
    "uncertainty": {
        "uncertain_facts": ["List of facts you're unsure about"],
        "reasons": ["Why you're uncertain"],
        "would_help": ["What additional info would help"]
    },
    "rules_applied": ["List of rules that apply to this response"],
    "caveats": ["Any important caveats or warnings"]
}"""


class ReasoningAgent:
    """
    Agent that uses an LLM to reason over ContextBundles.
    Generates responses with full provenance and confidence scoring.
    
    Uses Replit AI Integrations for OpenAI access.
    """
    
    def __init__(self):
        self.client = OpenAI(
            api_key=AI_INTEGRATIONS_OPENAI_API_KEY,
            base_url=AI_INTEGRATIONS_OPENAI_BASE_URL
        )
        self.model = "gpt-4o-mini"
        logger.info(f"ReasoningAgent initialized with model: {self.model}")
    
    def reason(
        self,
        bundle: ContextBundle,
        query_logger: Optional[QueryLogger] = None
    ) -> Dict:
        """
        Generate a reasoned response from a ContextBundle.
        
        Returns a structured response with answer, confidence, evidence, and uncertainty.
        """
        # CRITICAL: Check if target entity was not found - return early with low confidence
        if bundle.target_entity_name and not bundle.target_entity_found:
            logger.warning(f"Reasoning with missing target entity: {bundle.target_entity_name}")
            return self._create_entity_not_found_response(bundle)
        
        context_str = bundle.to_llm_context()
        
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
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": REASONING_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_completion_tokens=2000,
                response_format={"type": "json_object"}
            )
            
            response_text = response.content[0].text if hasattr(response, 'content') else response.choices[0].message.content
            
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                result = self._parse_fallback(response_text)
            
            result = self._validate_and_enrich_response(result, bundle)
            
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
    
    def _validate_and_enrich_response(self, result: Dict, bundle: ContextBundle) -> Dict:
        """Validate and enrich the LLM response with additional context."""
        if "answer" not in result:
            result["answer"] = "Unable to generate answer from context."
        
        if "confidence" not in result:
            result["confidence"] = bundle.confidence
        
        confidence = result.get("confidence", 0.5)
        if confidence >= 0.85:
            result["confidence_level"] = "high"
        elif confidence >= 0.70:
            result["confidence_level"] = "medium"
        elif confidence >= 0.50:
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
            "query_text": bundle.query_text
        }
    
    def _create_entity_not_found_response(self, bundle: ContextBundle) -> Dict:
        """
        Create a structured response when the target entity doesn't exist.
        
        CRITICAL: This prevents hallucinations by explicitly stating the entity
        doesn't exist rather than fabricating information about it.
        """
        target = bundle.target_entity_name
        
        return {
            "answer": f"I cannot answer this query because the entity '{target}' does not exist in the knowledge graph. "
                     f"The system searched for '{target}' but found no matching entity. "
                     f"This could mean: (1) the entity name is misspelled, (2) the entity hasn't been ingested yet, "
                     f"or (3) the entity genuinely doesn't exist in your infrastructure. "
                     f"Please verify the entity name or add it to the knowledge graph if it should exist.",
            "confidence": 0.1,
            "confidence_level": "very_low",
            "entity_not_found": True,
            "target_entity": target,
            "evidence_chain": [],
            "uncertainty": {
                "uncertain_facts": [f"Whether '{target}' exists or is named differently"],
                "reasons": [f"Entity '{target}' not found in knowledge graph"],
                "would_help": [
                    f"Verify the exact name of '{target}'",
                    "Check if the entity has been ingested",
                    "Try alternative names or spellings"
                ]
            },
            "rules_applied": [],
            "caveats": [
                f"The entity '{target}' does not exist in the knowledge graph",
                "No relationships or facts can be provided for non-existent entities"
            ],
            "bundle_id": bundle.query_id,
            "query_text": bundle.query_text
        }
