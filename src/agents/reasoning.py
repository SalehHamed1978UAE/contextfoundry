"""
Reasoning Agent

Consumes ContextBundles and generates responses using LLM.
Surfaces uncertainty and builds evidence chains.
"""

import json
import uuid
from typing import Dict, Any, List
from datetime import datetime

from src.config import settings
from src.models.schemas import (
    ContextBundle,
    ReasoningResponse,
    EvidenceItem,
    AlternativeInterpretation,
    ConfidenceLevel
)
from src.utils.llm import LLMClient


class ReasoningAgent:
    """Generates responses from context bundles using LLM"""

    def __init__(self, db_manager):
        self.db = db_manager
        self.llm = LLMClient()

    async def reason(
        self,
        bundle: ContextBundle,
        require_alternatives: bool = True
    ) -> ReasoningResponse:
        """
        Generate reasoning response from context bundle

        Args:
            bundle: ContextBundle with retrieved context
            require_alternatives: Generate alternatives if confidence < 0.7

        Returns:
            ReasoningResponse with answer, confidence, and evidence
        """

        start_time = datetime.utcnow()

        # Build prompt from context bundle
        prompt = self._build_prompt(bundle)

        # Generate response from LLM
        print(f"Calling LLM with prompt length: {len(prompt)}")
        try:
            llm_response = await self.llm.chat(
                messages=[
                    {
                        "role": "system",
                        "content": self._get_system_prompt()
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3  # Lower temperature for factual responses
            )
            print(f"LLM response received: {llm_response.get('text', '')[:100]}")
        except Exception as e:
            print(f"Exception in reasoning agent LLM call: {type(e).__name__}: {str(e)}")
            llm_response = {"error": str(e), "text": "", "fallback": True}

        # Check for LLM errors
        if llm_response.get("fallback"):
            return self._create_fallback_response(bundle, llm_response.get("error"))

        answer_text = llm_response.get("text", "")

        # Parse response (expecting JSON format)
        print(f"Raw LLM answer text: '{answer_text}'")
        try:
            parsed = self._parse_llm_response(answer_text)
            # Normalize answer field - LLM sometimes returns a list instead of string
            if isinstance(parsed.get("answer"), list):
                parsed["answer"] = " ".join(str(item) for item in parsed["answer"])
            if not isinstance(parsed.get("answer"), str):
                parsed["answer"] = str(parsed.get("answer", ""))
            print(f"Parsed successfully: {parsed.get('answer', '')[:100]}")
        except Exception as e:
            print(f"JSON parse failed: {e}. Using fallback with raw text.")
            # Fallback to plain text if parsing fails
            parsed = {
                "answer": answer_text if answer_text else "No response generated",
                "confidence": 0.5,
                "evidence": [],
                "caveats": ["Unable to parse structured response from LLM"]
            }

        # Build evidence chain from bundle
        evidence_chain = self._build_evidence_chain(bundle)

        # Determine confidence level
        confidence = parsed.get("confidence", bundle.uncertainty.overall_confidence)
        confidence_level = self._determine_confidence_level(confidence)

        # Generate alternatives if needed
        alternatives = []
        if confidence < 0.7 and require_alternatives:
            alternatives = await self._generate_alternatives(bundle, answer_text)

        # Calculate latency
        latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        return ReasoningResponse(
            bundle_id=bundle.id,
            answer=parsed.get("answer", "Unable to generate answer"),
            confidence=confidence,
            confidence_level=confidence_level,
            uncertain_facts=parsed.get("uncertain_facts", []),
            uncertainty_reasons=bundle.uncertainty.uncertainty_reasons,
            would_help=parsed.get("would_help", []),
            caveats=parsed.get("caveats", []),
            evidence_chain=evidence_chain,
            rules_checked=[],  # Will be populated by Validation Agent
            rules_passed=True,  # Will be set by Validation Agent
            alternatives=alternatives,
            total_latency_ms=latency_ms + (bundle.retrieval_latency_ms or 0)
        )

    def _get_system_prompt(self) -> str:
        """Get system prompt for reasoning agent"""

        return """You are a reasoning agent in an enterprise operations knowledge system.

Your task is to answer questions based ONLY on the provided context from three memory layers:
1. Semantic Memory (knowledge graph entities and relationships)
2. Episodic Memory (similar documents and incidents)
3. Symbolic Memory (rules and policies)

IMPORTANT INSTRUCTIONS:
- Only use information from the provided context
- If context is insufficient, say so explicitly
- Surface uncertainty and provide caveats
- Build evidence chains linking answer to source documents
- Assess your confidence honestly

Response format (JSON):
{
  "answer": "Direct answer to the question",
  "confidence": 0.0-1.0 (your confidence in this answer),
  "evidence": ["fact 1 from context", "fact 2 from context"],
  "uncertain_facts": ["facts you're uncertain about"],
  "caveats": ["important caveats or limitations"],
  "would_help": ["what additional information would improve answer"]
}"""

    def _build_prompt(self, bundle: ContextBundle) -> str:
        """Build prompt from context bundle"""

        prompt_parts = []

        # Add query
        prompt_parts.append(f"QUESTION: {bundle.query_text}\n")

        # Add session context for multi-turn conversations
        if bundle.session_context:
            prompt_parts.append("CONVERSATION HISTORY:")
            for turn in bundle.session_context:
                prompt_parts.append(f"  User: {turn.get('query', '')}")
                prompt_parts.append(f"  Assistant: {turn.get('response', '')}")
            prompt_parts.append("")

        # Add semantic memory context - include entity names and source text
        if bundle.semantic_entities:
            prompt_parts.append("KNOWLEDGE GRAPH ENTITIES:")
            for entity in bundle.semantic_entities[:10]:
                name = entity.get('canonical_name') or entity.get('source_sentence') or 'unknown'
                prompt_parts.append(
                    f"  - {entity.get('entity_type')}: {name} "
                    f"(confidence={entity.get('confidence', 0):.2f})"
                )
                if entity.get('source_sentence'):
                    prompt_parts.append(f"    Source: {entity['source_sentence'][:200]}")

        if bundle.semantic_relationships:
            prompt_parts.append(f"\nKNOWLEDGE GRAPH RELATIONSHIPS:")
            for rel in bundle.semantic_relationships[:15]:
                source = rel.get('source_name') or rel.get('source_type')
                target = rel.get('target_name') or rel.get('target_type')
                prompt_parts.append(
                    f"  - {source} --[{rel.get('relationship_type')}]--> {target}"
                )

        # Add episodic memory context - include MORE text from documents
        if bundle.episodic_documents:
            prompt_parts.append("\nRELEVANT DOCUMENTS:")
            for doc in bundle.episodic_documents[:5]:  # Top 5 instead of 3
                prompt_parts.append(f"\n--- {doc.get('title', 'Untitled')} (similarity={doc.get('similarity', 0):.2f}) ---")
                prompt_parts.append(doc.get('text', '')[:1500])  # 1500 chars instead of 500

        # Add symbolic rules
        if bundle.symbolic_rules_applied:
            prompt_parts.append("\nAPPLICABLE RULES:")
            for rule in bundle.symbolic_rules_applied[:5]:
                prompt_parts.append(f"  - {rule.get('rule_name')}: {rule.get('description')}")

        prompt_parts.append("\nAnswer the question using ONLY the context above. Respond in JSON format as specified.")

        return "\n".join(prompt_parts)

    def _parse_llm_response(self, text: str) -> Dict[str, Any]:
        """Parse LLM response (expecting JSON)"""

        # Try to find JSON in response
        text = text.strip()

        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        return json.loads(text)

    def _build_evidence_chain(self, bundle: ContextBundle) -> List[EvidenceItem]:
        """Build evidence chain from bundle context"""

        evidence = []

        # Add high-confidence entities as evidence
        for entity in bundle.semantic_entities[:5]:
            if entity.get("confidence", 0) >= 0.7:
                evidence.append(EvidenceItem(
                    fact=f"{entity.get('entity_type')} entity found in knowledge graph",
                    source={
                        "type": "semantic_memory",
                        "entity_id": entity.get("entity_id"),
                        "source_document": entity.get("source_document_id"),
                        "source_sentence": entity.get("source_sentence")
                    },
                    confidence=entity.get("confidence", 0.5)
                ))

        # Add high-similarity documents as evidence
        for doc in bundle.episodic_documents[:3]:
            if doc.get("similarity", 0) >= 0.7:
                evidence.append(EvidenceItem(
                    fact=f"Similar {doc.get('document_type')} found: {doc.get('title', '')}",
                    source={
                        "type": "episodic_memory",
                        "document_id": doc.get("document_id"),
                        "title": doc.get("title"),
                        "similarity": doc.get("similarity")
                    },
                    confidence=doc.get("similarity", 0.5)
                ))

        return evidence

    def _determine_confidence_level(self, confidence: float) -> ConfidenceLevel:
        """Convert numeric confidence to confidence level"""

        if confidence >= settings.confidence_threshold_high:
            return ConfidenceLevel.HIGH
        elif confidence >= settings.confidence_threshold_medium:
            return ConfidenceLevel.MEDIUM
        elif confidence >= settings.confidence_threshold_low:
            return ConfidenceLevel.LOW
        else:
            return ConfidenceLevel.VERY_LOW

    async def _generate_alternatives(
        self,
        bundle: ContextBundle,
        primary_answer: str
    ) -> List[AlternativeInterpretation]:
        """Generate alternative interpretations for low-confidence answers"""

        # For MVP, return placeholder
        # In production, would prompt LLM for alternatives
        return []

    def _create_fallback_response(
        self,
        bundle: ContextBundle,
        error: str
    ) -> ReasoningResponse:
        """Create fallback response when LLM fails"""

        return ReasoningResponse(
            bundle_id=bundle.id,
            answer=f"Unable to generate answer due to LLM error: {error}",
            confidence=0.0,
            confidence_level=ConfidenceLevel.VERY_LOW,
            uncertain_facts=[],
            uncertainty_reasons=[*bundle.uncertainty.uncertainty_reasons, f"LLM error: {error}"],
            would_help=["LLM must be operational"],
            caveats=["System degraded - LLM unavailable"],
            evidence_chain=self._build_evidence_chain(bundle),
            rules_checked=[],
            rules_passed=True,
            alternatives=[],
            total_latency_ms=bundle.retrieval_latency_ms or 0
        )
