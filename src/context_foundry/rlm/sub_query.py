"""
SubQueryAPI - LLM sub-query interface for RLM REPL.

Provides llm_query() and llm_verify() functions that the RLM can call
from within the sandbox to verify findings or get clarification.
Manages token budget to prevent runaway costs.
"""

import os
from datetime import datetime
from typing import Optional, List, Any, Dict

from .schemas import (
    VerificationResult,
    SubQueryLog,
    BudgetExhaustedError,
)


class SubQueryAPI:
    """
    Provides sub-query capabilities to RLM sandbox.
    
    Tracks token usage against budget and logs all calls
    for execution trace.
    """
    
    def __init__(
        self, 
        token_budget: int = 5000,
        max_calls: int = 20,
        provider: str = "anthropic",
        model: str = "claude-haiku-4-5-20251001"
    ):
        """
        Initialize SubQueryAPI.
        
        Args:
            token_budget: Maximum tokens to use for sub-queries
            max_calls: Maximum number of sub-query calls
            provider: LLM provider (anthropic or openai)
            model: Model identifier
        """
        self.token_budget = token_budget
        self.max_calls = max_calls
        self.provider = provider
        self.model = model
        
        self.tokens_used = 0
        self.calls_made = 0
        self.call_logs: List[SubQueryLog] = []
    
    def _check_budget(self, estimated_tokens: int = 500):
        """Check if budget allows another call."""
        if self.calls_made >= self.max_calls:
            raise BudgetExhaustedError("sub-query calls", self.max_calls)
        if self.tokens_used + estimated_tokens > self.token_budget:
            raise BudgetExhaustedError("token", self.token_budget)
    
    def _call_llm(self, prompt: str, max_tokens: int = 500) -> tuple:
        """
        Call the LLM and return response with token usage.
        
        Returns:
            Tuple of (response_text, tokens_used)
        """
        import time
        start_time = time.time()
        
        if self.provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
            
            response = client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens
            
        elif self.provider == "openai":
            import openai
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.choices[0].message.content
            tokens = response.usage.total_tokens
        
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        return response_text, tokens, duration_ms
    
    def query(
        self, 
        prompt: str,
        context: str = None
    ) -> str:
        """
        Ask the LLM a question about the current context.
        
        Args:
            prompt: The question or request
            context: Optional additional context
        
        Returns:
            LLM response text
        
        Raises:
            BudgetExhaustedError: If budget is exhausted
        """
        self._check_budget()
        
        full_prompt = prompt
        if context:
            full_prompt = f"Context:\n{context}\n\nQuestion: {prompt}"
        
        response_text, tokens, duration_ms = self._call_llm(full_prompt)
        
        self.tokens_used += tokens
        self.calls_made += 1
        
        self.call_logs.append(SubQueryLog(
            query_type="query",
            prompt_preview=full_prompt[:200],
            response_preview=response_text[:200],
            tokens_used=tokens,
            duration_ms=duration_ms
        ))
        
        return response_text
    
    def verify(
        self,
        claim: str,
        evidence: List[str]
    ) -> VerificationResult:
        """
        Verify a claim against evidence.
        
        Args:
            claim: The claim to verify
            evidence: List of evidence strings
        
        Returns:
            VerificationResult with supported/confidence/reasoning
        
        Raises:
            BudgetExhaustedError: If budget is exhausted
        """
        self._check_budget()
        
        evidence_text = "\n".join([f"- {e}" for e in evidence])
        
        prompt = f"""Analyze if the following claim is supported by the evidence.

CLAIM: {claim}

EVIDENCE:
{evidence_text}

Respond with a JSON object containing:
- "supported": true or false
- "confidence": 0.0 to 1.0
- "reasoning": Brief explanation (1-2 sentences)
- "evidence_quotes": List of specific quotes from evidence that support/refute the claim

JSON response:"""
        
        response_text, tokens, duration_ms = self._call_llm(prompt, max_tokens=400)
        
        self.tokens_used += tokens
        self.calls_made += 1
        
        self.call_logs.append(SubQueryLog(
            query_type="verify",
            prompt_preview=prompt[:200],
            response_preview=response_text[:200],
            tokens_used=tokens,
            duration_ms=duration_ms
        ))
        
        try:
            import json
            response_text = response_text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            
            data = json.loads(response_text)
            return VerificationResult(
                supported=data.get("supported", False),
                confidence=data.get("confidence", 0.5),
                reasoning=data.get("reasoning", "No reasoning provided"),
                evidence_quotes=data.get("evidence_quotes", [])
            )
        except json.JSONDecodeError:
            return VerificationResult(
                supported=False,
                confidence=0.0,
                reasoning=f"Failed to parse LLM response: {response_text[:100]}",
                evidence_quotes=[]
            )
    
    def summarize(
        self,
        findings: List[Dict[str, Any]],
        query: str
    ) -> str:
        """
        Summarize findings to answer the original query.
        
        Args:
            findings: List of finding dictionaries
            query: The original query
        
        Returns:
            Summary text answering the query
        
        Raises:
            BudgetExhaustedError: If budget is exhausted
        """
        self._check_budget()
        
        findings_text = ""
        for i, f in enumerate(findings[:10]):
            findings_text += f"\n{i+1}. {f}"
        
        prompt = f"""Based on the following findings, provide a concise answer to the query.

QUERY: {query}

FINDINGS:
{findings_text}

Provide a clear, factual answer based only on the findings above. If the findings are insufficient, say so.

Answer:"""
        
        response_text, tokens, duration_ms = self._call_llm(prompt, max_tokens=500)
        
        self.tokens_used += tokens
        self.calls_made += 1
        
        self.call_logs.append(SubQueryLog(
            query_type="summarize",
            prompt_preview=prompt[:200],
            response_preview=response_text[:200],
            tokens_used=tokens,
            duration_ms=duration_ms
        ))
        
        return response_text
    
    def get_remaining_budget(self) -> Dict[str, int]:
        """Get remaining budget information."""
        return {
            "tokens_remaining": self.token_budget - self.tokens_used,
            "tokens_used": self.tokens_used,
            "calls_remaining": self.max_calls - self.calls_made,
            "calls_made": self.calls_made
        }
    
    def get_logs(self) -> List[SubQueryLog]:
        """Get all sub-query call logs."""
        return self.call_logs
    
    def reset(self):
        """Reset budget tracking."""
        self.tokens_used = 0
        self.calls_made = 0
        self.call_logs = []
