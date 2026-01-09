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
3. For ambiguous queries, use discover_relationships to see what data exists before counting.
4. Use get_knowledge_bundle to fetch relationship details after you know what types exist.
5. Use search_documents for information not in structured data.

HANDLING AMBIGUOUS QUERIES:
When queries use ambiguous terms like "jobs", "work", "projects", "experience", "connections":
1. FIRST call discover_relationships to see what relationship types exist with counts
2. Reason about which types are relevant to the user's intent
3. Call get_knowledge_bundle for the relevant relationship types to get details
4. Provide complete answer covering all relevant interpretations

Example for "How many jobs has Saleh done?":
- resolve_entities("Saleh") → get entity_id
- discover_relationships(entity_id) → shows HELD_POSITION (7), WORKED_AT (7), etc.
- Both are relevant: HELD_POSITION = job titles, WORKED_AT = employers
- get_knowledge_bundle to fetch the actual job titles and company names
- Answer: "Saleh has held 7 positions (Head of QData, Director, ...) across 7 companies (ENEC, Contango, ...)"

TOOLS:
- resolve_entities: Look up entity IDs by name. Returns canonical IDs, confidence, disambiguation candidates.
- discover_relationships: See all relationship types for an entity with counts. Use for ambiguous queries.
- run_aggregation: Get exact counts/sums. Returns result_kind: EXACT, LOWER_BOUND ("at least N"), or RANGE.
- get_knowledge_bundle: Get ALL relationships and context for entities. Shows relationship_summary with type counts.
- search_documents: Search uploaded documents via vector similarity.

When answering:
1. Think about what tools you need AND whether the query is ambiguous
2. For ambiguous terms, discover what relationships exist FIRST
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
        conversation_history: Optional[List[Dict[str, str]]] = None,
        debug: bool = False
    ) -> Dict[str, Any]:
        """
        Process a query using tool-calling agent.
        
        Args:
            question: User's question
            conversation_history: Previous messages for context
            debug: If True, include detailed diagnostic info in response
            
        Returns:
            Dict with answer, tool_calls, evidence, etc.
        """
        start_time = time.time()
        
        debug_info = {
            "tool_calls": [],
            "reasoning_trace": [],
            "context_loaded": {
                "system_prompt": AGENT_SYSTEM_PROMPT,
                "conversation_history": conversation_history[-6:] if conversation_history else [],
                "user_question": question
            },
            "raw_llm_responses": [],
            "messages_sent": []
        } if debug else None
        
        messages = [{"role": "system", "content": AGENT_SYSTEM_PROMPT}]
        
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append(msg)
        
        messages.append({"role": "user", "content": question})
        
        tool_calls_made = []
        tool_results = []
        
        for iteration in range(self.MAX_TOOL_CALLS + 1):
            logger.info(f"[AGENT] Iteration {iteration + 1}, messages: {len(messages)}")
            
            if debug_info:
                debug_info["messages_sent"].append({
                    "iteration": iteration + 1,
                    "messages": [self._sanitize_message(m) for m in messages]
                })
            
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
                result = {
                    "answer": f"Error calling AI service: {str(e)}",
                    "tool_calls": tool_calls_made,
                    "iterations": iteration + 1,
                    "time_ms": int((time.time() - start_time) * 1000),
                    "success": False
                }
                if debug_info:
                    result["debug"] = debug_info
                return result
            
            message = response.choices[0].message
            
            if debug_info:
                raw_response = {
                    "iteration": iteration + 1,
                    "role": message.role,
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                        } for tc in (message.tool_calls or [])
                    ],
                    "finish_reason": response.choices[0].finish_reason,
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    } if response.usage else None
                }
                debug_info["raw_llm_responses"].append(raw_response)
            
            if message.tool_calls:
                messages.append(message.model_dump())
                
                if debug_info:
                    debug_info["reasoning_trace"].append({
                        "iteration": iteration + 1,
                        "action": "tool_calls",
                        "thought": message.content,
                        "tools_called": [tc.function.name for tc in message.tool_calls]
                    })
                
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
                    
                    tool_record = {
                        "tool": tool_name,
                        "arguments": arguments,
                        "result": result,
                        "time_ms": int(tool_time * 1000)
                    }
                    tool_calls_made.append(tool_record)
                    tool_results.append(result)
                    
                    if debug_info:
                        debug_info["tool_calls"].append({
                            "iteration": iteration + 1,
                            "tool": tool_name,
                            "arguments": arguments,
                            "result": result,
                            "time_ms": int(tool_time * 1000)
                        })
                        debug_info["reasoning_trace"].append({
                            "iteration": iteration + 1,
                            "action": "observation",
                            "tool": tool_name,
                            "result_summary": self._summarize_result(result)
                        })
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(result)
                    })
            else:
                answer = message.content or "I couldn't find an answer."
                
                if debug_info:
                    debug_info["reasoning_trace"].append({
                        "iteration": iteration + 1,
                        "action": "final_answer",
                        "raw_answer": answer
                    })
                
                answer = self._validate_numeric_claims(answer, tool_results)
                
                total_time = time.time() - start_time
                
                result = {
                    "answer": answer,
                    "tool_calls": tool_calls_made,
                    "iterations": iteration + 1,
                    "time_ms": int(total_time * 1000),
                    "success": True
                }
                if debug_info:
                    result["debug"] = debug_info
                return result
        
        result = {
            "answer": "I reached the maximum number of tool calls. Please try a simpler question.",
            "tool_calls": tool_calls_made,
            "iterations": self.MAX_TOOL_CALLS,
            "time_ms": int((time.time() - start_time) * 1000),
            "success": False
        }
        if debug_info:
            result["debug"] = debug_info
        return result
    
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
    
    def _sanitize_message(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize message for debug output (truncate large content)."""
        result = dict(msg)
        if "content" in result and result["content"]:
            content = str(result["content"])
            if len(content) > 2000:
                result["content"] = content[:2000] + f"... [truncated, {len(content)} chars total]"
        return result
    
    def _summarize_result(self, result: Dict[str, Any]) -> str:
        """Create a brief summary of a tool result for the reasoning trace."""
        if "error" in result:
            return f"ERROR: {result['error'][:100]}"
        
        if "entities" in result:
            entities = result["entities"]
            resolved = [e for e in entities if e.get("resolved")]
            return f"Resolved {len(resolved)}/{len(entities)} entities"
        
        if "relationship_types" in result:
            types = result["relationship_types"]
            type_strs = [f"{t['type']}({t['count']})" for t in types[:5]]
            return f"Found {len(types)} relationship types: {', '.join(type_strs)}"
        
        if "result_kind" in result:
            return f"{result['result_kind']}: {result.get('value', 'N/A')}"
        
        if "relationships" in result:
            rels = result["relationships"]
            return f"Found {len(rels)} relationships"
        
        if "chunks" in result:
            chunks = result["chunks"]
            return f"Found {len(chunks)} document chunks"
        
        return f"Result with keys: {list(result.keys())[:5]}"
