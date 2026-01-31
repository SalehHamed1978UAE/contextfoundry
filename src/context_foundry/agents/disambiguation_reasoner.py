"""
Disambiguation Reasoner for Context Foundry.

Uses LLM reasoning to determine the best match(es) when multiple entities
match a user's query. Implements fast paths for obvious cases and falls
back to LLM reasoning only when genuinely ambiguous.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


@dataclass
class DisambiguationResult:
    """Result of disambiguation reasoning."""
    single_answer: bool
    primary_result: Optional[Dict[str, Any]] = None
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    show_alternatives: bool = True
    reasoning: str = ""
    used_llm: bool = False


class DisambiguationReasoner:
    """
    Resolves ambiguous matches using fast paths and LLM reasoning.
    
    Fast paths (no LLM needed):
    1. Single match → use it directly
    2. Exact vault context match → use matching entity
    
    LLM reasoning (when genuinely ambiguous):
    - Multiple matches with unclear best choice
    - Vault context doesn't clearly indicate preference
    """
    
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = model
        self.client = OpenAI(
            api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        )
    
    def resolve(
        self,
        query: str,
        matches: List[Dict[str, Any]],
        vault_context: str,
        ambiguity_type: str = "role"
    ) -> DisambiguationResult:
        """
        Resolve ambiguous matches using fast paths or LLM reasoning.
        
        Args:
            query: Original user query
            matches: List of matching entities with name, role, organization fields
            vault_context: Name of the current vault
            ambiguity_type: Type of ambiguity (role, entity, department, etc.)
            
        Returns:
            DisambiguationResult with primary answer and alternatives
        """
        logger.info(f"[DISAMB] Resolving {len(matches)} matches for '{query}' (vault={vault_context})")
        
        if len(matches) == 0:
            return DisambiguationResult(single_answer=False, reasoning="No matches found")
        
        if len(matches) == 1:
            logger.info("[DISAMB] Fast path: single match")
            return DisambiguationResult(
                single_answer=True,
                primary_result=matches[0],
                alternatives=[],
                show_alternatives=False,
                reasoning="Only one match found"
            )
        
        exact_matches = self._find_vault_matches(matches, vault_context)
        
        if len(exact_matches) == 1:
            logger.info(f"[DISAMB] Fast path: exact vault match ({exact_matches[0].get('name')})")
            return DisambiguationResult(
                single_answer=True,
                primary_result=exact_matches[0],
                alternatives=[m for m in matches if m != exact_matches[0]],
                show_alternatives=True,
                reasoning=f"Matched to vault context '{vault_context}'"
            )
        
        logger.info("[DISAMB] Using LLM reasoning for disambiguation")
        return self._llm_reason(query, matches, vault_context, ambiguity_type)
    
    def _find_vault_matches(
        self,
        matches: List[Dict[str, Any]],
        vault_context: str
    ) -> List[Dict[str, Any]]:
        """
        Find matches where ANY organization matches vault context.
        
        Each match may have multiple organizations (e.g., Sarah Chen works at
        TechVentures, HR Operations, and Board Committee). We check if ANY
        of them match the vault context.
        """
        if not vault_context:
            return []
        
        vault_lower = vault_context.lower()
        vault_words = [w.lower() for w in vault_context.split() if len(w) > 2]
        
        exact_matches = []
        for match in matches:
            organizations = match.get("organizations", [])
            if not organizations and match.get("organization"):
                organizations = [match.get("organization")]
            
            if not organizations:
                continue
            
            for org in organizations:
                org_lower = (org or "").lower()
                if not org_lower:
                    continue
                
                if org_lower in vault_lower or vault_lower in org_lower:
                    logger.info(f"[DISAMB] Vault match: {match.get('name')} has org '{org}' matching vault '{vault_context}'")
                    exact_matches.append(match)
                    break
                
                for word in vault_words:
                    if word in org_lower:
                        logger.info(f"[DISAMB] Vault word match: {match.get('name')} has org '{org}' matching vault word '{word}'")
                        exact_matches.append(match)
                        break
                else:
                    continue
                break
        
        return exact_matches
    
    def _llm_reason(
        self,
        query: str,
        matches: List[Dict[str, Any]],
        vault_context: str,
        ambiguity_type: str
    ) -> DisambiguationResult:
        """Use LLM to reason about which match(es) best answer the user's intent."""
        
        def format_orgs(m: Dict[str, Any]) -> str:
            orgs = m.get('organizations', [])
            if not orgs and m.get('organization'):
                orgs = [m.get('organization')]
            return ', '.join(orgs) if orgs else 'Unknown'
        
        matches_description = "\n".join([
            f"- {m.get('name', 'Unknown')} ({m.get('role', 'unknown role')}) → organizations: [{format_orgs(m)}]"
            for m in matches
        ])
        
        prompt = f"""The user asked: "{query}"
Vault context: "{vault_context}"

I found these matches in the knowledge graph:
{matches_description}

Reason about which match(es) best answer the user's intent:
1. Consider the vault context - what organization is this vault about?
2. Consider the relationships - who works where?
3. Determine if there's a clear primary answer or if multiple are relevant

The vault context tells you which organization this knowledge base is focused on.
If someone works at an organization that matches the vault context, they are likely the intended answer.
Others are probably CEOs of portfolio companies, subsidiaries, or external organizations.

Respond in JSON only:
{{
    "reasoning": "brief explanation of your analysis",
    "single_answer": true if one clear best answer else false,
    "primary_result": {{"name": "...", "role": "...", "organization": "..."}},
    "show_alternatives": true if user should see other options,
    "alternatives": [{{"name": "...", "role": "...", "organization": "..."}}]
}}"""
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You analyze knowledge graph queries and determine the best matching entity. Respond with JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                max_tokens=500
            )
            
            content = response.choices[0].message.content or "{}"
            
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            result = json.loads(content)
            
            logger.info(f"[DISAMB] LLM reasoning: {result.get('reasoning', 'no reasoning')}")
            logger.info(f"[DISAMB] Single answer: {result.get('single_answer')}, Primary: {result.get('primary_result', {}).get('name')}")
            
            return DisambiguationResult(
                single_answer=result.get("single_answer", False),
                primary_result=result.get("primary_result"),
                alternatives=result.get("alternatives", []),
                show_alternatives=result.get("show_alternatives", True),
                reasoning=result.get("reasoning", ""),
                used_llm=True
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"[DISAMB] Failed to parse LLM response: {e}")
            return DisambiguationResult(
                single_answer=False,
                alternatives=matches,
                reasoning="Unable to determine best match"
            )
        except Exception as e:
            logger.error(f"[DISAMB] LLM reasoning failed: {e}")
            return DisambiguationResult(
                single_answer=False,
                alternatives=matches,
                reasoning=f"Reasoning error: {str(e)}"
            )
