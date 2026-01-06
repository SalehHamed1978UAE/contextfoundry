"""
3-Step Query Pipeline - Orchestrates the full query flow.

Step 1: Query Interpretation (LLM) - Parse natural language into structured intent
Step 2: Directed Retrieval (Code) - Execute precise graph queries
Step 3: Answer Synthesis (LLM) - Format results into human-readable answer

This separation ensures:
- LLM handles flexible language understanding and answer generation
- Code handles precise, deterministic data retrieval
- Results are reproducible and auditable
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from datetime import datetime

from sqlalchemy.orm import Session

from src.context_foundry.agents.query_interpreter import QueryInterpreter, QueryIntent
from src.context_foundry.agents.directed_retriever import DirectedGraphRetriever, RetrievalResult

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Complete result of the 3-step query pipeline."""
    query_text: str
    
    step1_intent: Optional[QueryIntent] = None
    step1_duration_ms: float = 0.0
    
    step2_result: Optional[RetrievalResult] = None
    step2_duration_ms: float = 0.0
    
    step3_answer: Optional[str] = None
    step3_confidence: float = 0.0
    step3_duration_ms: float = 0.0
    
    total_duration_ms: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "query_text": self.query_text,
            "step1_intent": self.step1_intent.to_dict() if self.step1_intent else None,
            "step1_duration_ms": self.step1_duration_ms,
            "step2_result": self.step2_result.to_dict() if self.step2_result else None,
            "step2_duration_ms": self.step2_duration_ms,
            "step3_answer": self.step3_answer,
            "step3_confidence": self.step3_confidence,
            "step3_duration_ms": self.step3_duration_ms,
            "total_duration_ms": self.total_duration_ms,
            "error": self.error
        }


ANSWER_SYNTHESIS_PROMPT = """You are an answer synthesizer for a knowledge graph system.

You will receive:
1. The original user query
2. A structured query intent (what we searched for)
3. Precise retrieval results from the graph
4. A TARGET TYPE (optional) - the type of entity the user specifically asked for

Your task is to synthesize the retrieved data into a clear, accurate answer.

CRITICAL RULES:
1. ONLY use information from the retrieval results - never make up facts
2. If no relationships were found, clearly state that
3. For blast radius queries, list the affected entities with their relationship type
4. Cite the relationship type and confidence for each fact
5. If the entity wasn't found, suggest checking the entity name
6. **TARGET TYPE FILTERING**: If a target_type is specified, ONLY list entities of that type in your answer.
   - If target_type is "TEAM", only list TEAM entities
   - If target_type is "DATABASE", only list DATABASE entities
   - If target_type is null/None, list all discovered entities

For TARGET TYPE queries (e.g., "Which teams...", "What databases..."), structure your answer as:

**[TARGET TYPE]s Affected:**
- [Entity Name] via [relationship chain] (confidence: X.XX)

**Summary:**
[Total count] [TARGET TYPE]s would be affected.

For BLAST RADIUS queries (no target type), structure your answer as:

**Directly Affected (Depth 1):**
- [Entity Name] ([TYPE]) via [RELATIONSHIP_TYPE] (confidence: X.XX)

**Indirectly Affected (Depth 2+):**
- [Entity Name] ([TYPE]) via chain: [path description]

**Summary:**
[Total count] entities would be affected if [Entity] becomes unavailable.

For other queries, provide a clear, structured answer based on the data."""


class QueryPipeline:
    """
    Orchestrates the 3-step query pipeline.
    
    Usage:
        pipeline = QueryPipeline(session, tenant_id)
        result = pipeline.execute("What's the blast radius if API Gateway fails?")
    """
    
    def __init__(
        self,
        session: Session,
        tenant_id: str,
        model: str = "gpt-4o-mini"
    ):
        self.session = session
        self.tenant_id = str(tenant_id)
        self.model = model
        
        self.interpreter = QueryInterpreter(
            model=model,
            session=session,
            tenant_id=str(tenant_id)
        )
        self.retriever = DirectedGraphRetriever(session, tenant_id)
        
        from openai import OpenAI
        self.openai_client = OpenAI()
        
        logger.info(f"QueryPipeline initialized for tenant {tenant_id[:8]}...")
    
    def execute(self, query_text: str) -> PipelineResult:
        """
        Execute the full 3-step pipeline.
        
        Args:
            query_text: The user's natural language query
            
        Returns:
            PipelineResult with all steps' outputs
        """
        result = PipelineResult(query_text=query_text)
        start_time = datetime.now()
        
        try:
            step1_start = datetime.now()
            intent = self.interpreter.interpret(query_text)
            result.step1_intent = intent
            result.step1_duration_ms = (datetime.now() - step1_start).total_seconds() * 1000
            
            logger.info(f"[Step 1] Intent: {intent.to_dict()}")
            
            step2_start = datetime.now()
            retrieval = self.retriever.execute(intent)
            result.step2_result = retrieval
            result.step2_duration_ms = (datetime.now() - step2_start).total_seconds() * 1000
            
            logger.info(f"[Step 2] Retrieved: {len(retrieval.relationships)} relationships, "
                       f"{len(retrieval.affected_entities)} affected entities")
            
            step3_start = datetime.now()
            answer, confidence = self._synthesize_answer(query_text, intent, retrieval)
            result.step3_answer = answer
            result.step3_confidence = confidence
            result.step3_duration_ms = (datetime.now() - step3_start).total_seconds() * 1000
            
            logger.info(f"[Step 3] Synthesized answer with confidence {confidence:.2f}")
            
        except Exception as e:
            logger.error(f"Pipeline execution failed: {e}")
            result.error = str(e)
        
        result.total_duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        
        return result
    
    def execute_step1_only(self, query_text: str) -> QueryIntent:
        """Execute only Step 1 for debugging/testing."""
        return self.interpreter.interpret(query_text)
    
    def execute_step2_only(self, intent: QueryIntent) -> RetrievalResult:
        """Execute only Step 2 for debugging/testing."""
        return self.retriever.execute(intent)
    
    def _synthesize_answer(
        self,
        query_text: str,
        intent: QueryIntent,
        retrieval: RetrievalResult
    ) -> tuple:
        """
        Step 3: Synthesize the retrieval results into a natural language answer.
        
        Returns:
            Tuple of (answer_text, confidence_score)
        """
        if not retrieval.entity_found:
            return (
                f"Entity '{intent.entity}' was not found in the knowledge graph. "
                f"Please verify the entity name or check if it exists under a different name.",
                0.0
            )
        
        if not retrieval.relationships:
            return (
                f"No {intent.direction} relationships of type {intent.relationship_types} "
                f"were found for '{retrieval.entity_name}'.\n\n"
                f"This means either:\n"
                f"1. No such relationships have been documented\n"
                f"2. The relationships exist but haven't been ingested yet",
                0.3
            )
        
        context = self._format_retrieval_for_synthesis(retrieval)
        
        target_type_instruction = ""
        if intent.target_type:
            target_type_instruction = f"""
TARGET TYPE: {intent.target_type}
IMPORTANT: The user specifically asked for {intent.target_type}s. Your answer must ONLY list entities of type {intent.target_type}.
Do NOT include services, databases, or other entity types unless they are {intent.target_type}s.
"""
        
        try:
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": ANSWER_SYNTHESIS_PROMPT},
                    {"role": "user", "content": f"""
Query: "{query_text}"

Query Intent:
- Target Entity: {intent.entity}
- Direction: {intent.direction}
- Relationship Types: {intent.relationship_types}
- Depth: {intent.depth}
- Target Type: {intent.target_type or "None (show all types)"}
{target_type_instruction}
Retrieval Results:
{context}

Synthesize a clear answer based on these results. Remember: if target_type is specified, ONLY list entities of that type."""}
                ],
                temperature=0.0,
                max_completion_tokens=1000
            )
            
            answer = response.choices[0].message.content
            
            avg_confidence = sum(r.confidence for r in retrieval.relationships) / len(retrieval.relationships)
            confidence = min(avg_confidence, 0.95)
            
            return (answer, confidence)
            
        except Exception as e:
            logger.error(f"Answer synthesis failed: {e}")
            return (
                f"Found {len(retrieval.relationships)} relationships for '{retrieval.entity_name}', "
                f"but failed to synthesize answer: {e}",
                0.5
            )
    
    def _format_retrieval_for_synthesis(self, retrieval: RetrievalResult) -> str:
        """Format retrieval results for the synthesis LLM."""
        lines = []
        
        lines.append(f"Entity: {retrieval.entity_name} ({retrieval.entity_type})")
        lines.append(f"Total Relationships Found: {len(retrieval.relationships)}")
        lines.append(f"Unique Affected Entities: {len(retrieval.affected_entities)}")
        lines.append("")
        
        by_depth = {}
        for rel in retrieval.relationships:
            depth = rel.depth
            if depth not in by_depth:
                by_depth[depth] = []
            by_depth[depth].append(rel)
        
        for depth in sorted(by_depth.keys()):
            lines.append(f"--- Depth {depth} ---")
            for rel in by_depth[depth]:
                if rel.direction_relative_to_entity == "inbound":
                    lines.append(
                        f"  {rel.source_name} --[{rel.relationship_type}]--> {rel.target_name} "
                        f"(confidence: {rel.confidence:.2f})"
                    )
                else:
                    lines.append(
                        f"  {rel.source_name} --[{rel.relationship_type}]--> {rel.target_name} "
                        f"(confidence: {rel.confidence:.2f})"
                    )
            lines.append("")
        
        lines.append("Affected Entities:")
        for entity in retrieval.affected_entities:
            lines.append(f"  - {entity['name']} ({entity['type']}) via {entity['discovered_via']}")
        
        return "\n".join(lines)
