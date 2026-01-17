"""
RLMExecutor - Main orchestrator for RLM-style iterative reasoning.

Manages the conversation loop between the root LLM and the REPL sandbox,
tracking progress and enforcing timeouts/budgets.
"""

import os
import time
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Any, Dict
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from .schemas import (
    RLMConfig,
    RLMResult,
    RLMError,
    ProgressTracker,
    ExecutionTrace,
    ExecutionTraceEntry,
    REPLExecutionResult,
    EntitySummary,
    Relationship,
    CircuitBreakerTripped,
    BudgetExhaustedError,
)
from .sandbox import REPLSandbox
from .sub_query import SubQueryAPI
from .memory_apis.semantic import SemanticMemoryAPI
from .memory_apis.episodic import EpisodicMemoryAPI
from .memory_apis.symbolic import SymbolicMemoryAPI


SYSTEM_PROMPT = """You are an expert knowledge graph analyst working with a tri-memory architecture:
- semantic: Entity memory (find_entities, find_similar, get_entity, find_by_property)
- episodic: Document chunk memory (search, get_chunk, get_document_chunks, get_provenance)
- symbolic: Relationship memory (get_relationships, find_path, get_related_entities, traverse)

Your task is to answer the user's query by exploring these memory systems iteratively.

## CRITICAL: Answer Generation Rules

1. **Finalize Early**: After 3 iterations of exploration, you MUST attempt to answer.
   - Do NOT keep exploring indefinitely
   - If you have found relevant entities and relationships, synthesize an answer
   - Set the 'answer' variable and call finalize() immediately

2. **Progress Check**: At each iteration, ask yourself:
   - "Do I have enough information to answer the original query?"
   - If YES → Set answer and call finalize() immediately
   - If NO → Continue ONE more exploration step, then reassess

3. **Answer Structure**: Your final answer should:
   - Name specific entities you found (by name, not ID)
   - Describe the relationships between them
   - Directly address the original query
   - Cite confidence based on evidence found

4. **When to Stop Exploring**:
   - You found entities matching the query subject ✓
   - You found relationships connecting them ✓
   - Additional searches return entities you've already seen ✓
   → STOP and synthesize answer NOW

AVAILABLE DATA TYPES (use these attributes):
- EntitySummary: id, name, entity_type, confidence, lifecycle_state, property_count, relationship_count
- EntityDetail: id, name, entity_type, confidence, lifecycle_state, properties, aliases, source_document_ids
- ChunkDetail: id, document_id, chunk_index, content, document_name, document_type, page_numbers
- Relationship: id, source_entity_name, target_entity_name, relationship_type, confidence, properties

EXAMPLE - GOOD BEHAVIOR (finalize after finding data):
```python
# Iteration 1: Find relevant entities
entities = semantic.find_similar("payment service", k=5)
print(f"Found: {[e.entity.name for e in entities]}")

# Iteration 2: Get relationships
if entities:
    rels = symbolic.get_relationships(entities[0].entity.id)
    deps = [r.source_entity_name for r in rels if r.relationship_type == "DEPENDS_ON"]
    print(f"Dependents: {deps}")

# Iteration 3: I have the answer! Finalize NOW.
answer = f"The following services depend on Payment Service: {', '.join(deps)}"
finalize()
```

EXAMPLE - BAD BEHAVIOR (DO NOT DO THIS):
- Found 5 entities and 10 relationships
- Keep exploring "to verify" or "find more"
- Hit circuit breaker with no answer

When ready to answer, write:
```python
answer = "Your comprehensive answer citing specific entities and relationships..."
evidence.append("Source: document_name")
finalize()
```"""


class RLMExecutor:
    """
    Orchestrates RLM-style iterative reasoning over the knowledge graph.
    
    The executor manages:
    - Conversation loop with root LLM
    - Sandbox code execution
    - Progress tracking and circuit breaker
    - Budget management
    - Execution trace logging
    """
    
    def __init__(
        self, 
        tenant_id: str, 
        db_session: Session,
        config: RLMConfig = None
    ):
        """
        Initialize RLM Executor.
        
        Args:
            tenant_id: Tenant UUID for memory isolation
            db_session: SQLAlchemy session for memory APIs
            config: RLM configuration (uses defaults if None)
        """
        self.tenant_id = tenant_id
        self.db_session = db_session
        self.config = config or RLMConfig()
        
        self.semantic = SemanticMemoryAPI(tenant_id, db_session)
        self.episodic = EpisodicMemoryAPI(tenant_id, db_session)
        self.symbolic = SymbolicMemoryAPI(tenant_id, db_session)
        
        self.sub_query = SubQueryAPI(
            token_budget=self.config.sub_query_budget,
            max_calls=self.config.max_sub_queries,
            provider=self.config.sub_provider,
            model=self.config.sub_model
        )
        
        self.finalized = False
        
        self.sandbox = REPLSandbox(
            memory_apis={
                "semantic": self.semantic,
                "episodic": self.episodic,
                "symbolic": self.symbolic
            },
            llm_apis={
                "llm_query": self.sub_query.query,
                "llm_verify": self.sub_query.verify,
                "finalize": self._finalize_callback
            },
            timeout_seconds=self.config.iteration_timeout_seconds
        )
        
        self.progress = ProgressTracker()
        
        self.query_id = str(uuid.uuid4())
        self.trace = ExecutionTrace(
            query_id=self.query_id,
            tenant_id=tenant_id,
            original_query="",
            started_at=datetime.utcnow(),
            total_iterations=0,
            final_status="in_progress",
            entries=[],
            total_tokens_used=0,
            total_sub_queries=0,
            total_entities_discovered=0,
            total_relationships_discovered=0,
            estimated_cost_usd=0.0
        )
        
        self.conversation_history: List[Dict[str, str]] = []
    
    def _finalize_callback(self):
        """Callback for when code calls finalize()."""
        self.finalized = True
    
    def _get_next_action(self, query: str, last_result: REPLExecutionResult = None) -> str:
        """
        Get next code action from the root LLM.
        
        Args:
            query: The original query
            last_result: Result from last code execution (if any)
        
        Returns:
            Python code to execute
        """
        if not self.conversation_history:
            self.conversation_history.append({
                "role": "user",
                "content": f"Query to answer: {query}\n\nBegin by exploring relevant entities and relationships."
            })
        elif last_result:
            if last_result.success:
                feedback = f"Code executed successfully.\n\nOutput:\n{last_result.output or '(no output)'}"
                if last_result.new_entities_discovered:
                    feedback += f"\n\nNew entities discovered: {len(last_result.new_entities_discovered)}"
                if last_result.new_relationships_discovered:
                    feedback += f"\n\nNew relationships discovered: {len(last_result.new_relationships_discovered)}"
            else:
                feedback = f"Code execution failed.\n\nError: {last_result.error}"
                if last_result.retry_hint:
                    feedback += f"\n\nHint: {last_result.retry_hint}"
            
            self.conversation_history.append({
                "role": "user",
                "content": feedback
            })
        
        budget_info = self.sub_query.get_remaining_budget()
        remaining_iterations = self.config.max_iterations - (self.progress.iteration + 1)
        
        iteration_warning = ""
        if remaining_iterations <= 2:
            iteration_warning = f"""
⚠️ WARNING: You have {remaining_iterations} iteration(s) remaining before automatic timeout.
You MUST call finalize() with your answer in the next iteration.
If you have found relevant entities/relationships, synthesize your answer NOW.
"""
        elif remaining_iterations <= 4:
            iteration_warning = f"""
Note: {remaining_iterations} iterations remaining. Consider finalizing soon if you have sufficient data.
"""
        
        status = f"""
Iteration: {self.progress.iteration + 1}/{self.config.max_iterations}
Entities discovered: {len(self.progress.entities_discovered)}
Relationships discovered: {len(self.progress.relationships_discovered)}
Sub-query budget: {budget_info['tokens_remaining']} tokens / {budget_info['calls_remaining']} calls remaining
{iteration_warning}
Write Python code to continue your exploration. If you have enough information, set 'answer' and call finalize().
"""
        
        messages = [{"role": "user", "content": SYSTEM_PROMPT}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": status})
        
        if self.config.root_provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
            
            response = client.messages.create(
                model=self.config.root_model,
                max_tokens=2000,
                temperature=self.config.temperature,
                messages=messages
            )
            
            code = response.content[0].text
            tokens = response.usage.input_tokens + response.usage.output_tokens
            
        elif self.config.root_provider == "openai":
            import openai
            client = openai.OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            
            response = client.chat.completions.create(
                model=self.config.root_model,
                max_tokens=2000,
                temperature=self.config.temperature,
                messages=messages
            )
            
            code = response.choices[0].message.content
            tokens = response.usage.total_tokens
        
        else:
            raise ValueError(f"Unsupported provider: {self.config.root_provider}")
        
        self.trace.total_tokens_used += tokens
        
        self.conversation_history.append({
            "role": "assistant",
            "content": code
        })
        
        code = self._extract_code(code)
        
        return code
    
    def _extract_code(self, response: str) -> str:
        """Extract Python code from LLM response."""
        if "```python" in response:
            parts = response.split("```python")
            if len(parts) > 1:
                code = parts[1].split("```")[0]
                return code.strip()
        
        if "```" in response:
            parts = response.split("```")
            if len(parts) > 1:
                code = parts[1]
                if code.startswith("\n"):
                    code = code[1:]
                return code.strip()
        
        return response.strip()
    
    def execute(self, query: str, context_hint: str = None) -> RLMResult:
        """
        Execute RLM reasoning loop for a query.
        
        Args:
            query: The query to answer
            context_hint: Optional context to help focus exploration
        
        Returns:
            RLMResult with answer, evidence, and execution trace
        """
        start_time = time.time()
        self.trace.original_query = query
        self.trace.started_at = datetime.utcnow()
        
        last_result = None
        
        try:
            logger.info(f"[RLM] Starting execution for query: {query[:80]}...")
            while self.progress.iteration < self.config.max_iterations:
                logger.info(f"[RLM] Iteration {self.progress.iteration + 1}/{self.config.max_iterations}")
                code = self._get_next_action(query, last_result)
                logger.debug(f"[RLM] Generated code:\n{code[:200]}...")
                
                result = self.sandbox.execute(code)
                logger.info(f"[RLM] Execution result: success={result.success}, has_output={bool(result.output)}")
                
                made_progress = self.progress.record_iteration(result)
                logger.info(f"[RLM] Progress: entities={len(self.progress.entities_discovered)}, rels={len(self.progress.relationships_discovered)}, finalized={self.finalized}")
                
                entry = ExecutionTraceEntry(
                    iteration=self.progress.iteration,
                    timestamp=datetime.utcnow(),
                    code=code,
                    result=result,
                    sub_queries=self.sub_query.get_logs()[len(self.trace.entries):] if self.trace.entries else self.sub_query.get_logs(),
                    budget_remaining=self.sub_query.get_remaining_budget()['tokens_remaining'],
                    cumulative_entities=len(self.progress.entities_discovered),
                    cumulative_relationships=len(self.progress.relationships_discovered)
                )
                self.trace.entries.append(entry)
                
                if self.finalized:
                    logger.info(f"[RLM] Completed after {self.progress.iteration} iterations")
                    return self._build_result("completed", start_time)
                
                if self.progress.should_trip_breaker(self.config.circuit_breaker_threshold):
                    logger.warning(f"[RLM] Circuit breaker tripped after {self.progress.iteration} iterations")
                    return self._build_result("circuit_breaker", start_time)
                
                last_result = result
            
            logger.warning(f"[RLM] Max iterations ({self.config.max_iterations}) reached without finalization")
            return self._build_result("max_iterations", start_time)
            
        except BudgetExhaustedError as e:
            return self._build_result("budget_exhausted", start_time)
        except Exception as e:
            self.trace.final_status = "error"
            return RLMResult(
                query_id=self.query_id,
                status="error",
                answer=None,
                answer_text=f"Error during execution: {str(e)}",
                confidence=0.0,
                response_mode="GAP",
                evidence_chain=[],
                entities_found=[],
                relationships_found=[],
                execution_trace=self.trace,
                latency_ms=int((time.time() - start_time) * 1000),
                tokens_used=self.trace.total_tokens_used,
                estimated_cost_usd=self._estimate_cost()
            )
    
    def _build_result(self, status: str, start_time: float) -> RLMResult:
        """Build RLMResult from current state."""
        self.trace.final_status = status
        self.trace.completed_at = datetime.utcnow()
        self.trace.total_iterations = self.progress.iteration
        self.trace.total_sub_queries = self.sub_query.calls_made
        self.trace.total_entities_discovered = len(self.progress.entities_discovered)
        self.trace.total_relationships_discovered = len(self.progress.relationships_discovered)
        self.trace.estimated_cost_usd = self._estimate_cost()
        
        answer = self.sandbox.get_variable("answer")
        evidence = self.sandbox.get_variable("evidence") or []
        
        if answer:
            response_mode = "GROUNDED"
            confidence = 0.8
        elif len(self.progress.entities_discovered) > 0 or len(self.progress.relationships_discovered) > 0:
            response_mode = "PARTIAL_ANSWER"
            confidence = 0.6
            answer = self._synthesize_answer_from_discoveries()
        else:
            response_mode = "GAP"
            confidence = 0.0
            answer = "Unable to find relevant information to answer the query."
        
        entities_found = []
        relationships_found = []
        
        return RLMResult(
            query_id=self.query_id,
            status=status,
            answer=answer,
            answer_text=str(answer) if answer else None,
            confidence=confidence,
            response_mode=response_mode,
            evidence_chain=evidence if isinstance(evidence, list) else [str(evidence)],
            entities_found=entities_found,
            relationships_found=relationships_found,
            execution_trace=self.trace,
            latency_ms=int((time.time() - start_time) * 1000),
            tokens_used=self.trace.total_tokens_used,
            estimated_cost_usd=self._estimate_cost()
        )
    
    def _synthesize_answer_from_discoveries(self) -> str:
        """Synthesize an answer from discovered entities and relationships when LLM didn't finalize."""
        entity_ids = list(self.progress.entities_discovered)[:20]
        relationship_ids = list(self.progress.relationships_discovered)[:20]
        
        entity_names = []
        relationship_strs = []
        
        if entity_ids:
            try:
                from sqlalchemy import text
                entity_id_list = ", ".join([f"'{eid}'" for eid in entity_ids])
                result = self.db_session.execute(
                    text(f"""
                        SELECT id, name, entity_type 
                        FROM entities 
                        WHERE id IN ({entity_id_list})
                        AND tenant_id = :tenant_id
                    """),
                    {"tenant_id": self.tenant_id}
                )
                for row in result:
                    entity_names.append(f"{row[1]} ({row[2]})")
            except Exception:
                entity_names = [f"Entity {eid[:8]}..." for eid in entity_ids[:10]]
        
        if relationship_ids:
            try:
                from sqlalchemy import text
                rel_id_list = ", ".join([f"'{rid}'" for rid in relationship_ids])
                result = self.db_session.execute(
                    text(f"""
                        SELECT r.relationship_type, e1.name as source, e2.name as target
                        FROM relationships r
                        JOIN entities e1 ON r.source_entity_id = e1.id
                        JOIN entities e2 ON r.target_entity_id = e2.id
                        WHERE r.id IN ({rel_id_list})
                        AND r.tenant_id = :tenant_id
                    """),
                    {"tenant_id": self.tenant_id}
                )
                for row in result:
                    relationship_strs.append(f"{row[1]} --[{row[0]}]--> {row[2]}")
            except Exception:
                relationship_strs = [f"Relationship {rid[:8]}..." for rid in relationship_ids[:10]]
        
        parts = []
        parts.append(f"Based on the knowledge graph exploration, I found the following relevant information:")
        
        if entity_names:
            parts.append(f"\n\nRelevant entities discovered ({len(entity_names)}):")
            for name in entity_names[:10]:
                parts.append(f"\n  • {name}")
            if len(entity_names) > 10:
                parts.append(f"\n  ... and {len(entity_names) - 10} more")
        
        if relationship_strs:
            parts.append(f"\n\nRelationships found ({len(relationship_strs)}):")
            for rel_str in relationship_strs[:8]:
                parts.append(f"\n  • {rel_str}")
            if len(relationship_strs) > 8:
                parts.append(f"\n  ... and {len(relationship_strs) - 8} more")
        
        parts.append("\n\nNote: This answer was synthesized from partial exploration. For more detailed analysis, please refine your query.")
        
        return "".join(parts)
    
    def _estimate_cost(self) -> float:
        """Estimate USD cost based on token usage."""
        INPUT_COST_PER_1K = 0.003
        OUTPUT_COST_PER_1K = 0.015
        
        estimated_output = self.trace.total_tokens_used * 0.3
        estimated_input = self.trace.total_tokens_used * 0.7
        
        cost = (estimated_input / 1000 * INPUT_COST_PER_1K + 
                estimated_output / 1000 * OUTPUT_COST_PER_1K)
        
        return round(cost, 4)


def execute_rlm_query(
    tenant_id: str,
    query: str,
    db_session: Session,
    config: RLMConfig = None
) -> RLMResult:
    """
    Convenience function to execute an RLM query.
    
    Args:
        tenant_id: Tenant UUID
        query: The query to answer
        db_session: SQLAlchemy session
        config: Optional RLM configuration
    
    Returns:
        RLMResult with answer and execution trace
    """
    executor = RLMExecutor(tenant_id, db_session, config)
    return executor.execute(query)
