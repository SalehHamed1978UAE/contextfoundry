"""
Answer Verification Agent

Ensures responses address user questions.
NO KEYWORDS. Data checks + LLM understanding only.
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


class AnswerVerifierAgent:
    """Two-layer verification: structural rules + LLM semantic check."""
    
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
        
        if structural_verdict.status in ("REJECTED", "SUSPICIOUS"):
            logger.info(f"[QA] Structural flag: {structural_verdict.status} - {structural_verdict.reason}")
            return structural_verdict
        
        # Layer 2: LLM semantic verification
        llm_verdict = self._llm_verify(question, answer, retrieval)
        logger.info(f"[QA] LLM verdict: {llm_verdict.status} - {llm_verdict.reason}")
        
        return llm_verdict
    
    def _structural_rules(self, retrieval: Any, answer: str) -> QAVerdict:
        """Check DATA STRUCTURE only. No text analysis."""
        
        if not answer or not answer.strip():
            return QAVerdict("REJECTED", "Empty answer")
        
        # Check what data exists (handle various RetrievalResult structures)
        has_entity = bool(
            getattr(retrieval, 'entity_name', None) or
            getattr(retrieval, 'entities', None) or
            getattr(retrieval, 'affected_entities', None) or
            getattr(retrieval, 'entity_found', False)
        )
        relationships = getattr(retrieval, 'relationships', []) or []
        has_relationships = len(relationships) > 0
        has_data = has_entity or has_relationships
        
        if not has_data and len(answer) > 200:
            return QAVerdict("SUSPICIOUS", "No data retrieved but detailed answer generated")
        
        return QAVerdict("NEEDS_LLM", "Structural checks passed")
    
    def _llm_verify(self, question: str, answer: str, retrieval: Any) -> QAVerdict:
        """LLM handles ALL semantic understanding."""
        
        # Build data summary from actual retrieval structure
        entity_names = []
        if getattr(retrieval, 'entity_name', None):
            entity_names.append(retrieval.entity_name)
        if getattr(retrieval, 'entities', None):
            entity_names.extend([self._get_name(e) for e in list(retrieval.entities)[:10]])
        if getattr(retrieval, 'affected_entities', None):
            entity_names.extend([self._get_name(e) for e in list(retrieval.affected_entities)[:10]])
        
        relationships = getattr(retrieval, 'relationships', []) or []
        
        data_summary = {
            "entities_found": len(entity_names),
            "entity_names": list(set(entity_names))[:10],
            "relationships_found": len(relationships),
            "relationship_types": list(set(self._get_type(r) for r in relationships[:20])),
            "has_data": len(entity_names) > 0 or len(relationships) > 0
        }
        
        prompt = f"""You are a QA verification system for a knowledge base.

QUESTION ASKED:
{question}

ANSWER GENERATED:
{answer}

DATA RETRIEVED FROM KNOWLEDGE BASE:
{json.dumps(data_summary, indent=2)}

EVALUATE:

1. INTENT MATCH - Does the answer address what was asked?
   - WHO/WHICH TEAM → should name person(s) or team(s)
   - WHAT/HOW → should explain concept or process
   - WHERE/WHEN → should provide location or time

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
- SUPPORTED: Addresses question appropriately (with evidence OR honest uncertainty)
- OFF_TOPIC: Answers a different question than asked
- INSUFFICIENT: Right topic but missing key information
- UNSUPPORTED: Makes claims without supporting evidence"""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
                max_tokens=150
            )
            
            content = response.choices[0].message.content.strip()
            
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
            return QAVerdict(result["status"], result["reason"])
            
        except json.JSONDecodeError as e:
            logger.error(f"[QA] JSON parse error: {e}")
            return QAVerdict("REVIEW", "Could not parse verification response")
        except Exception as e:
            logger.error(f"[QA] Verification error: {e}")
            return QAVerdict("REVIEW", f"Verification failed: {type(e).__name__}")
    
    def _get_name(self, entity: Any) -> str:
        if hasattr(entity, 'name'):
            return entity.name
        if isinstance(entity, dict):
            return entity.get('name', str(entity))
        return str(entity)
    
    def _get_type(self, relationship: Any) -> str:
        if hasattr(relationship, 'relationship_type'):
            return relationship.relationship_type
        if hasattr(relationship, 'type'):
            return relationship.type
        if isinstance(relationship, dict):
            return relationship.get('relationship_type', relationship.get('type', str(relationship)))
        return str(relationship)
