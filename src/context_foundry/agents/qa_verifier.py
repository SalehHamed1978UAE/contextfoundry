"""
Answer Verification Agent

Ensures responses address user questions.
NO KEYWORDS. Data checks + LLM understanding only.
Supports both graph-based and document-based retrieval.
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Optional
from openai import OpenAI

from src.context_foundry.utils.logger import logger


@dataclass
class QAVerdict:
    status: str  # SUPPORTED | OFF_TOPIC | INSUFFICIENT | UNSUPPORTED | REJECTED | REVIEW | SUSPICIOUS
    reason: str
    
    def to_dict(self) -> dict:
        return {"status": self.status, "reason": self.reason}


class AnswerVerifierAgent:
    """
    Two-layer verification: structural rules + LLM semantic check.
    Supports graph retrieval (entities/relationships) and document retrieval (chunks).
    """
    
    def __init__(self, llm_model: str = "gpt-4o-mini"):
        api_key = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        
        if base_url:
            self.llm_client = OpenAI(api_key=api_key, base_url=base_url)
        else:
            self.llm_client = OpenAI(api_key=api_key)
        self.llm_model = llm_model
    
    def verify(
        self, 
        question: str, 
        answer: str, 
        retrieval: Any,
        intent: Optional[Any] = None
    ) -> QAVerdict:
        """Verify answer addresses the question."""
        
        # Layer 1: Structural checks
        structural_verdict = self._structural_rules(retrieval, answer)
        
        if structural_verdict.status == "REJECTED":
            logger.info(f"[QA] Structural rejection: {structural_verdict.reason}")
            return structural_verdict
        
        # Layer 2: LLM semantic verification
        llm_verdict = self._llm_verify(question, answer, retrieval)
        logger.info(f"[QA] LLM verdict: {llm_verdict.status} - {llm_verdict.reason}")
        
        return llm_verdict
    
    def verify_from_bundle(self, question: str, bundle: Any, answer: str) -> QAVerdict:
        """
        Adapter for core.py which uses ContextBundle.
        """
        class BundleAdapter:
            def __init__(self, b):
                self.entity_name = getattr(b, 'target_entity_name', None)
                self.entity_found = getattr(b, 'target_entity_found', True)
                self.entities = getattr(b, 'semantic_entities', []) or []
                self.relationships = getattr(b, 'semantic_relationships', []) or []
                self.chunks = []
        
        return self.verify(question, answer, BundleAdapter(bundle))
    
    def verify_from_tool_calls(self, question: str, answer: str, tool_calls: list) -> QAVerdict:
        """
        Adapter for ToolAgent which returns tool_calls with document chunks.
        
        Extracts:
        - chunks from search_documents, search_chunks, etc.
        - entities from resolve_entities
        - relationships from get_knowledge_bundle, discover_relationships
        """
        chunks = []
        entities = []
        relationships = []
        
        for tc in tool_calls:
            tool_name = tc.get('tool') or tc.get('name', '')
            result = tc.get('result', {})
            
            # Parse JSON string if needed
            if isinstance(result, str):
                try:
                    result = json.loads(result)
                except json.JSONDecodeError:
                    result = {}
            
            # Extract chunks from search tools
            if tool_name in ('search_documents', 'search_chunks', 'summarize_chunks', 'retrieve_documents'):
                chunks.extend(result.get('chunks', []))
            
            # Extract entities from resolve_entities
            # Returns: {"entities": [{"resolved": {...}}, ...]}
            if tool_name == 'resolve_entities':
                for entity_wrapper in result.get('entities', []):
                    resolved = entity_wrapper.get('resolved')
                    if resolved:
                        entities.append(resolved)
            
            # Extract relationships from knowledge tools
            if tool_name in ('get_knowledge_bundle', 'discover_relationships'):
                relationships.extend(result.get('relationships', []))
                relationships.extend(result.get('incoming', []))
                relationships.extend(result.get('outgoing', []))
                if result.get('relationship_summary'):
                    relationships.append(result.get('relationship_summary'))
        
        # Create adapter object
        class ToolResultAdapter:
            def __init__(self, c, e, r):
                self.chunks = c
                self.entities = e
                self.relationships = r
                self.entity_name = e[0].get('name') if e and isinstance(e[0], dict) else None
                self.entity_found = len(c) > 0 or len(e) > 0
        
        return self.verify(question, answer, ToolResultAdapter(chunks, entities, relationships))
    
    def verify_from_retrieval_result(
        self, 
        question: str, 
        answer: str, 
        retrieval_result: Any,
        tool_calls: list = None
    ) -> QAVerdict:
        """
        Adapter for pre-fetched pipeline data + tool calls.
        
        Combines evidence from:
        1. Pipeline pre-fetched data (entities, relationships, chunks, resolved role)
        2. Tool call results (as before)
        
        This ensures QA Verifier sees ALL evidence, even if LLM skipped tool calls.
        """
        entities = []
        relationships = []
        chunks = []
        entity_name = None
        
        if retrieval_result:
            def get_field(obj, field, default=None):
                """Get field from object (attribute) or dict (key)."""
                if isinstance(obj, dict):
                    return obj.get(field, default)
                return getattr(obj, field, default)
            
            rr_entities = get_field(retrieval_result, 'entities')
            if rr_entities:
                entities.extend(rr_entities)
            
            rr_relationships = get_field(retrieval_result, 'relationships')
            if rr_relationships:
                relationships.extend(rr_relationships)
            
            rr_chunks = get_field(retrieval_result, 'chunks')
            if rr_chunks:
                chunks.extend(rr_chunks)
            
            rr_role = get_field(retrieval_result, 'role_resolution')
            if rr_role:
                is_resolved = get_field(rr_role, 'is_resolved', False)
                if is_resolved:
                    entity_name = get_field(rr_role, 'resolved_name')
                    if entity_name:
                        entities.append({'name': entity_name, 'type': 'PERSON', 'from_role_resolution': True})
        
        if tool_calls:
            for tc in tool_calls:
                tool_name = tc.get('tool') or tc.get('name', '')
                result = tc.get('result', {})
                
                if isinstance(result, str):
                    try:
                        result = json.loads(result)
                    except json.JSONDecodeError:
                        result = {}
                
                if tool_name in ('search_documents', 'search_chunks', 'summarize_chunks', 'retrieve_documents'):
                    chunks.extend(result.get('chunks', []))
                
                if tool_name == 'resolve_entities':
                    for entity_wrapper in result.get('entities', []):
                        resolved = entity_wrapper.get('resolved')
                        if resolved:
                            entities.append(resolved)
                
                if tool_name in ('get_knowledge_bundle', 'discover_relationships'):
                    relationships.extend(result.get('relationships', []))
                    relationships.extend(result.get('incoming', []))
                    relationships.extend(result.get('outgoing', []))
        
        class CombinedAdapter:
            def __init__(self, c, e, r, en):
                self.chunks = c
                self.entities = e
                self.relationships = r
                self.entity_name = en or (e[0].get('name') if e and isinstance(e[0], dict) else None)
                self.entity_found = len(c) > 0 or len(e) > 0 or en is not None
        
        logger.info(f"[QA] Combined evidence: entities={len(entities)}, rels={len(relationships)}, chunks={len(chunks)}, resolved_name={entity_name}")
        
        return self.verify(question, answer, CombinedAdapter(chunks, entities, relationships, entity_name))
    
    def _structural_rules(self, retrieval: Any, answer: str) -> QAVerdict:
        """
        Check DATA STRUCTURE only. No text analysis.
        Recognizes entities, relationships, AND chunks as valid data.
        """
        
        if not answer or not answer.strip():
            return QAVerdict("REJECTED", "Empty answer")
        
        # Check all possible data sources
        has_entity = bool(
            getattr(retrieval, 'entity_name', None) or
            getattr(retrieval, 'entities', None) or
            getattr(retrieval, 'affected_entities', None)
        )
        
        relationships = getattr(retrieval, 'relationships', []) or []
        has_relationships = len(relationships) > 0
        
        # Check for document chunks
        chunks = getattr(retrieval, 'chunks', []) or []
        has_chunks = len(chunks) > 0
        
        has_data = has_entity or has_relationships or has_chunks
        
        if not has_data and len(answer) > 200:
            return QAVerdict("SUSPICIOUS", "No data retrieved but detailed answer generated")
        
        return QAVerdict("NEEDS_LLM", "Structural checks passed")
    
    def _llm_verify(self, question: str, answer: str, retrieval: Any) -> QAVerdict:
        """
        LLM handles ALL semantic understanding.
        Includes entity, relationship, AND chunk info in data summary.
        """
        
        # Build entity names list
        entity_names = []
        if getattr(retrieval, 'entity_name', None):
            entity_names.append(retrieval.entity_name)
        if getattr(retrieval, 'entities', None):
            for e in list(retrieval.entities)[:10]:
                entity_names.append(self._get_name(e))
        
        relationships = getattr(retrieval, 'relationships', []) or []
        chunks = getattr(retrieval, 'chunks', []) or []
        
        # Extract document names and text excerpts from chunks
        chunk_sources = []
        chunk_excerpts = []
        for chunk in chunks[:5]:
            if isinstance(chunk, dict):
                doc_name = chunk.get('document', chunk.get('source', 'unknown'))
                chunk_sources.append(doc_name)
                # Include text excerpt for LLM to verify answer against
                text = chunk.get('text', '')[:400]
                if text:
                    chunk_excerpts.append(f"[{doc_name}]: {text}")
        
        data_summary = {
            "entities_found": len(entity_names),
            "entity_names": list(set(entity_names))[:10],
            "relationships_found": len(relationships),
            "relationship_types": list(set(self._get_type(r) for r in relationships[:20])),
            "chunks_found": len(chunks),
            "chunk_sources": list(set(chunk_sources))[:5],
            "chunk_excerpts": chunk_excerpts[:3],  # Include first 3 chunk excerpts for verification
            "has_data": len(entity_names) > 0 or len(relationships) > 0 or len(chunks) > 0
        }
        
        # DEBUG LOGGING
        logger.info(f"[QA_DEBUG] Question: {question}")
        logger.info(f"[QA_DEBUG] Answer preview: {answer[:200]}...")
        logger.info(f"[QA_DEBUG] Data summary: {json.dumps(data_summary)}")
        
        prompt = f"""You are a QA verification system for a knowledge base.

QUESTION ASKED:
{question}

ANSWER GENERATED:
{answer}

DATA RETRIEVED FROM KNOWLEDGE BASE:
{json.dumps(data_summary, indent=2)}

EVALUATE:

1. INTENT MATCH - Does the answer address what was actually asked?
   - WHO/WHICH TEAM → should name person(s) or team(s)
   - WHAT/HOW → should explain concept or process
   - WHERE/WHEN → should provide location or time
   - LIST/COMPARE → should cover multiple items

2. EVIDENCE - Is answer supported by retrieved data?
   - If data exists: answer should reflect it
   - If no data: answer should acknowledge this

3. HONESTY - Is confidence level appropriate?

RESPOND WITH JSON ONLY:
{{
    "status": "SUPPORTED | OFF_TOPIC | INSUFFICIENT | UNSUPPORTED",
    "reason": "one sentence explanation"
}}

STATUS MEANINGS:
- SUPPORTED: Addresses question with available evidence. Answers that honestly acknowledge data limitations are SUPPORTED, not INSUFFICIENT.
- OFF_TOPIC: Answers a different question than asked
- INSUFFICIENT: Only use when answer omits available data or fails to acknowledge uncertainty when it should
- UNSUPPORTED: Makes specific claims (names, numbers, facts) without any supporting evidence

IMPORTANT: An answer that says "I found X, Y, Z but detailed financial data is not available" is SUPPORTED because it honestly acknowledges limits."""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=150
            )
            
            content = response.choices[0].message.content.strip()
            
            # DEBUG LOGGING
            logger.info(f"[QA_DEBUG] LLM raw response: {content}")
            
            # Parse JSON (handle markdown wrapping)
            if "```" in content:
                parts = content.split("```")
                for part in parts:
                    part = part.strip()
                    if part.startswith("json"):
                        part = part[4:].strip()
                    if part.startswith("{"):
                        content = part
                        break
            
            result = json.loads(content)
            logger.info(f"[QA_DEBUG] Parsed result: {result}")
            return QAVerdict(result["status"], result["reason"])
            
        except json.JSONDecodeError as e:
            logger.error(f"[QA] JSON parse error: {e}")
            return QAVerdict("REVIEW", "Could not parse verification response")
        except Exception as e:
            logger.error(f"[QA] Verification error: {e}")
            return QAVerdict("REVIEW", f"Verification failed: {type(e).__name__}")
    
    def _get_name(self, entity: Any) -> str:
        """Safely get entity name."""
        if hasattr(entity, 'name'):
            return entity.name
        if isinstance(entity, dict):
            return entity.get('name', str(entity))
        return str(entity)
    
    def _get_type(self, relationship: Any) -> str:
        """Safely get relationship type."""
        if hasattr(relationship, 'relationship_type'):
            return relationship.relationship_type
        if hasattr(relationship, 'type'):
            return relationship.type
        if isinstance(relationship, dict):
            return relationship.get('relationship_type', relationship.get('type', str(relationship)))
        return str(relationship)
