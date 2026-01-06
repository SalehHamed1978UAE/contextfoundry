"""
Query Interpreter Agent - Step 1 of the 3-Step Query Pipeline.

This agent uses an LLM to interpret user queries into structured QueryIntent objects.
The QueryIntent specifies exactly what to retrieve from the graph, including:
- Target entity
- Relationship direction (inbound, outbound, both)
- Relationship types to follow
- Traversal depth

This separation ensures:
1. LLM handles flexible natural language understanding
2. Code handles precise, deterministic graph queries
3. LLM synthesizes results into human-readable answers
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Literal
from openai import OpenAI

logger = logging.getLogger(__name__)

DirectionType = Literal["inbound", "outbound", "both"]


@dataclass
class QueryIntent:
    """
    Structured representation of what the user is asking for.
    
    This is the output of Step 1 (Query Interpretation) and the input
    to Step 2 (Directed Graph Retrieval).
    """
    entity: str
    direction: DirectionType
    relationship_types: List[str]
    depth: int = 1
    query_type: str = "graph_traversal"
    include_properties: bool = False
    reasoning: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> "QueryIntent":
        return cls(
            entity=data.get("entity", ""),
            direction=data.get("direction", "both"),
            relationship_types=data.get("relationship_types", []),
            depth=data.get("depth", 1),
            query_type=data.get("query_type", "graph_traversal"),
            include_properties=data.get("include_properties", False),
            reasoning=data.get("reasoning", "")
        )


QUERY_INTERPRETER_PROMPT = """You are a Query Interpreter for a knowledge graph system.

Your task is to interpret natural language questions and output a structured query intent
that specifies exactly what data to retrieve from the graph.

The graph contains:
- Entities: Services, Teams, Databases, Incidents, Systems, etc.
- Relationships: DEPENDS_ON, CALLS, MANAGES, OWNS, AFFECTS, HOSTS, etc.

KEY CONCEPTS:
- "inbound" = relationships where the entity is the TARGET (X → Entity)
- "outbound" = relationships where the entity is the SOURCE (Entity → X)

DIRECTION RULES:
- "Blast radius if X fails" → inbound (find what DEPENDS_ON X, what CALLS X)
- "What does X depend on?" → outbound (find X DEPENDS_ON ?)
- "What services does X call?" → outbound (find X CALLS ?)
- "Who manages X?" → inbound (find ? MANAGES X)
- "What does X manage?" → outbound (find X MANAGES ?)
- "What is affected by incident X?" → outbound (find X AFFECTS ?)
- "What teams own X?" → inbound (find ? OWNS X)
- "Show all relationships for X" → both, all relationship types

RELATIONSHIP TYPE MAPPING:
- Impact/blast radius queries: DEPENDS_ON, CALLS (things that will break)
- Dependency queries: DEPENDS_ON
- Communication queries: CALLS
- Ownership queries: OWNS, MANAGES
- Incident queries: AFFECTS
- Infrastructure queries: HOSTS, RUNS_ON

OUTPUT FORMAT (JSON only, no markdown):
{
  "entity": "Name of the target entity",
  "direction": "inbound" | "outbound" | "both",
  "relationship_types": ["DEPENDS_ON", "CALLS", ...],
  "depth": 1-3,
  "query_type": "graph_traversal" | "property_lookup" | "existence_check",
  "include_properties": true | false,
  "reasoning": "Brief explanation of interpretation"
}

EXAMPLES:

Query: "What's the blast radius if API Gateway fails?"
{
  "entity": "API Gateway",
  "direction": "inbound",
  "relationship_types": ["DEPENDS_ON", "CALLS"],
  "depth": 2,
  "query_type": "graph_traversal",
  "include_properties": false,
  "reasoning": "Blast radius = downstream impact. Find entities that DEPEND_ON or CALL the API Gateway."
}

Query: "What does Order Service depend on?"
{
  "entity": "Order Service",
  "direction": "outbound",
  "relationship_types": ["DEPENDS_ON"],
  "depth": 1,
  "query_type": "graph_traversal",
  "include_properties": false,
  "reasoning": "Direct dependency query - find what Order Service depends on (outbound DEPENDS_ON)."
}

Query: "Who manages the Payment Service?"
{
  "entity": "Payment Service",
  "direction": "inbound",
  "relationship_types": ["MANAGES", "OWNS"],
  "depth": 1,
  "query_type": "graph_traversal",
  "include_properties": false,
  "reasoning": "Ownership query - find teams/people that MANAGE or OWN Payment Service (inbound)."
}

Query: "What was affected by incident INC-2025-1201?"
{
  "entity": "INC-2025-1201",
  "direction": "outbound",
  "relationship_types": ["AFFECTS"],
  "depth": 1,
  "query_type": "graph_traversal",
  "include_properties": false,
  "reasoning": "Incident impact query - find what the incident AFFECTS (outbound)."
}

Query: "Which team should be paged if Orders Database fails?"
{
  "entity": "Orders Database",
  "direction": "inbound",
  "relationship_types": ["DEPENDS_ON", "OWNS", "MANAGES"],
  "depth": 2,
  "query_type": "graph_traversal",
  "include_properties": false,
  "reasoning": "Need to find: 1) Services that depend on Orders Database, 2) Teams that own those services."
}

Respond with ONLY the JSON object, no additional text."""


class QueryInterpreter:
    """
    Step 1 of the 3-Step Query Pipeline: Query Interpretation.
    
    Uses an LLM to interpret natural language queries into structured QueryIntent objects.
    """
    
    def __init__(self, model: str = "gpt-4o-mini"):
        self.client = OpenAI()
        self.model = model
        logger.info(f"QueryInterpreter initialized with model: {model}")
    
    def interpret(self, query_text: str) -> QueryIntent:
        """
        Interpret a natural language query into a structured QueryIntent.
        
        Args:
            query_text: The user's natural language question
            
        Returns:
            QueryIntent object specifying what to retrieve from the graph
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": QUERY_INTERPRETER_PROMPT},
                    {"role": "user", "content": f"Query: \"{query_text}\""}
                ],
                temperature=0.0,
                max_completion_tokens=500,
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content
            intent_data = json.loads(response_text)
            
            intent = QueryIntent.from_dict(intent_data)
            
            logger.info(f"Query interpreted: entity='{intent.entity}', "
                       f"direction={intent.direction}, "
                       f"types={intent.relationship_types}, "
                       f"depth={intent.depth}")
            logger.debug(f"Interpretation reasoning: {intent.reasoning}")
            
            return intent
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse query interpretation response: {e}")
            return self._fallback_interpretation(query_text)
        except Exception as e:
            logger.error(f"Query interpretation failed: {e}")
            return self._fallback_interpretation(query_text)
    
    def _fallback_interpretation(self, query_text: str) -> QueryIntent:
        """
        Fallback interpretation using keyword-based heuristics.
        
        Used when LLM interpretation fails.
        """
        query_lower = query_text.lower()
        
        entity = self._extract_entity_heuristic(query_text)
        
        if any(kw in query_lower for kw in ['blast radius', 'impact', 'fails', 'goes down', 'unavailable']):
            return QueryIntent(
                entity=entity,
                direction="inbound",
                relationship_types=["DEPENDS_ON", "CALLS"],
                depth=2,
                reasoning="Fallback: detected blast radius keywords"
            )
        
        if 'depend' in query_lower and 'on' in query_lower:
            if any(kw in query_lower for kw in ['what does', 'what services does']):
                return QueryIntent(
                    entity=entity,
                    direction="outbound",
                    relationship_types=["DEPENDS_ON"],
                    depth=1,
                    reasoning="Fallback: 'what does X depend on' pattern"
                )
            else:
                return QueryIntent(
                    entity=entity,
                    direction="inbound",
                    relationship_types=["DEPENDS_ON"],
                    depth=1,
                    reasoning="Fallback: 'what depends on X' pattern"
                )
        
        if any(kw in query_lower for kw in ['who manages', 'who owns', 'which team']):
            return QueryIntent(
                entity=entity,
                direction="inbound",
                relationship_types=["MANAGES", "OWNS"],
                depth=1,
                reasoning="Fallback: ownership query keywords"
            )
        
        if 'affected by' in query_lower or 'incident' in query_lower:
            return QueryIntent(
                entity=entity,
                direction="outbound",
                relationship_types=["AFFECTS"],
                depth=1,
                reasoning="Fallback: incident impact query"
            )
        
        return QueryIntent(
            entity=entity,
            direction="both",
            relationship_types=["DEPENDS_ON", "CALLS", "MANAGES", "OWNS"],
            depth=1,
            reasoning="Fallback: no specific pattern detected, using broad search"
        )
    
    def _extract_entity_heuristic(self, query_text: str) -> str:
        """
        Simple heuristic to extract entity name from query.
        
        Looks for quoted strings or capitalized phrases.
        """
        import re
        
        quoted = re.findall(r'"([^"]+)"', query_text)
        if quoted:
            return quoted[0]
        
        quoted = re.findall(r"'([^']+)'", query_text)
        if quoted:
            return quoted[0]
        
        capitalized = re.findall(r'\b([A-Z][a-zA-Z]*(?:\s+[A-Z][a-zA-Z]*)*)\b', query_text)
        service_like = [c for c in capitalized if len(c) > 3 and c not in ['What', 'Who', 'Which', 'How', 'Why', 'The', 'Show']]
        if service_like:
            return service_like[0]
        
        return ""
