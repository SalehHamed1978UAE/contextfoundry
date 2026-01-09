"""
Tool-Calling Agent for Context Foundry.

Implements ReAct-style reasoning: Think → Tool Call → Observe → Repeat → Answer
"""
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional
from uuid import UUID

from openai import OpenAI
from sqlalchemy.orm import Session

from .tools.definitions import TOOL_DEFINITIONS
from .tools.wrappers import ToolExecutor
from ..models.schema import set_tenant_context

logger = logging.getLogger(__name__)

AGENT_SYSTEM_PROMPT = '''You are Context Foundry, an AI assistant with access to a knowledge graph and documents.

RULES:
1. For ANY numeric answer (counts, sums, totals), you MUST use run_aggregation. Never guess numbers.
2. Always resolve_entities FIRST before KG operations to get canonical IDs.
3. Use get_knowledge_bundle to see ALL relationships for an entity.
4. Use search_documents for information not in structured data.

HANDLING AMBIGUOUS QUERIES:
When a query uses ambiguous terms, reason about MULTIPLE interpretations and gather data for ALL:
- "jobs" → could mean: positions held (HELD_POSITION) OR companies worked at (WORKED_AT)
- "projects" → could mean: led, participated in, owned
- "connections" → could mean: colleagues, mentors, organizations

For counting ambiguous terms:
1. Call run_aggregation MULTIPLE times with different specific phrasings
2. Example for "how many jobs": call with "positions held by X" AND "companies X worked at"
3. Compose answer that addresses BOTH: "Saleh has held X positions across Y companies"

TOOLS:
- resolve_entities: Look up entity IDs by name. Returns canonical IDs, confidence, disambiguation candidates.
- run_aggregation: Get exact counts/sums. Returns result_kind: EXACT, LOWER_BOUND ("at least N"), or RANGE.
- get_knowledge_bundle: Get ALL relationships and context for entities. Shows relationship_summary with type counts.
- search_documents: Search uploaded documents via vector similarity.

When answering:
1. Think about what tools you need AND whether the query is ambiguous
2. Call tools to gather facts - for ambiguous queries, gather MULTIPLE interpretations
3. For numbers, cite result_kind (e.g., "exactly 7" for EXACT, "at least 7" for LOWER_BOUND)
4. Compose response that addresses all reasonable interpretations
5. For enumeration questions, list ALL items - do NOT summarize'''


class ToolAgent:
    """
    ReAct-style tool-calling agent.
    
    Usage:
        agent = ToolAgent(session, tenant_id)
        response = agent.query("How many jobs has Saleh done?", conversation_history=[])
    """
    
    MAX_TOOL_CALLS = 5
    TOOL_TIMEOUT = 10.0
    
    def __init__(
        self,
        session: Session,
        tenant_id: str,
        model: str = "gpt-4o-mini"
    ):
        self.session = session
        self.tenant_id = tenant_id
        self.model = model
        set_tenant_context(session, tenant_id)
        
        self.tool_executor = ToolExecutor(session, tenant_id)
        
        self.client = OpenAI(
            api_key=os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY"),
            base_url=os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL")
        )
    
    def query(
        self,
        question: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Process a query using tool-calling agent.
        
        Args:
            question: User's question
            conversation_history: Previous messages for context
            
        Returns:
            Dict with answer, tool_calls, evidence, etc.
        """
        start_time = time.time()
        
        messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
        
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append(msg)
        
        messages.append({"role": "user", "content": question})
        
        tool_calls_made = []
        tool_results = []
        
        for iteration in range(self.MAX_TOOL_CALLS + 1):
            logger.info(f"[AGENT] Iteration {iteration + 1}, messages: {len(messages)}")
            
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=TOOL_DEFINITIONS,
                    tool_choice="auto" if iteration < self.MAX_TOOL_CALLS else "none",
                    temperature=0.0,
                    max_tokens=800
                )
            except Exception as e:
                logger.error(f"[AGENT] OpenAI API error: {e}")
                return {
                    "answer": f"Error calling AI service: {str(e)}",
                    "tool_calls": tool_calls_made,
                    "iterations": iteration + 1,
                    "time_ms": int((time.time() - start_time) * 1000),
                    "success": False
                }
            
            message = response.choices[0].message
            
            if message.tool_calls:
                messages.append(message.model_dump())
                
                for tool_call in message.tool_calls:
                    tool_name = tool_call.function.name
                    try:
                        arguments = json.loads(tool_call.function.arguments)
                    except json.JSONDecodeError:
                        arguments = {}
                    
                    logger.info(f"[AGENT] Tool call: {tool_name}({arguments})")
                    
                    tool_start = time.time()
                    try:
                        result = self.tool_executor.execute(tool_name, arguments)
                    except Exception as e:
                        logger.error(f"[AGENT] Tool error: {e}")
                        result = {"error": str(e)}
                    tool_time = time.time() - tool_start
                    
                    tool_calls_made.append({
                        "tool": tool_name,
                        "arguments": arguments,
                        "result": result,
                        "time_ms": int(tool_time * 1000)
                    })
                    tool_results.append(result)
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })
            else:
                answer = message.content or "I couldn't find an answer."
                
                answer = self._validate_numeric_claims(answer, tool_results)
                
                total_time = time.time() - start_time
                
                return {
                    "answer": answer,
                    "tool_calls": tool_calls_made,
                    "iterations": iteration + 1,
                    "time_ms": int(total_time * 1000),
                    "success": True
                }
        
        return {
            "answer": "I reached the maximum number of tool calls. Please try a simpler question.",
            "tool_calls": tool_calls_made,
            "iterations": self.MAX_TOOL_CALLS,
            "time_ms": int((time.time() - start_time) * 1000),
            "success": False
        }
    
    def _validate_numeric_claims(self, answer: str, tool_results: List[Dict]) -> str:
        """Flag numeric claims without tool evidence."""
        numbers = re.findall(r'\b\d+\b', answer)
        
        has_agg_evidence = any(
            r.get("result_kind") or r.get("value") is not None
            for r in tool_results
        )
        
        if numbers and not has_agg_evidence:
            logger.warning(f"[AGENT] Numeric claims without aggregation evidence: {numbers}")
        
        return answer
