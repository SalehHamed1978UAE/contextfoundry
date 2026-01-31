"""
Query Interpreter Agent - Step 1 of the 3-Step Query Pipeline.

This agent uses an LLM to interpret user queries into structured QueryIntent objects.
The QueryIntent specifies exactly what to retrieve from the graph, including:
- Target entity
- Relationship direction (inbound, outbound, both)
- Relationship types to follow
- Traversal depth
- Target answer type (what type of entities the user wants in the answer)

This separation ensures:
1. LLM handles flexible natural language understanding
2. Code handles precise, deterministic graph queries
3. LLM synthesizes results into human-readable answers

The system is domain-agnostic: it learns what entity types exist from the tenant's
schema rather than using hardcoded types.
"""

import json
import logging
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Literal
from openai import OpenAI
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)

DirectionType = Literal["inbound", "outbound", "both"]


def get_tenant_entity_types(session: Session, tenant_id: str) -> List[str]:
    """
    Get all entity types that exist for this tenant from the database.
    
    This makes the system domain-agnostic - it learns what types exist
    from the data rather than using hardcoded types.
    """
    try:
        result = session.execute(text("""
            SELECT DISTINCT entity_type 
            FROM entities 
            WHERE tenant_id = :tenant_id
            ORDER BY entity_type
        """), {'tenant_id': tenant_id})
        types = [row[0] for row in result.fetchall()]
        logger.debug(f"Found {len(types)} entity types for tenant: {types}")
        return types
    except Exception as e:
        logger.error(f"Failed to get entity types: {e}")
        session.rollback()
        return []


def get_tenant_relationship_types(session: Session, tenant_id: str) -> List[str]:
    """
    Get all relationship types that exist for this tenant from the database.
    """
    try:
        result = session.execute(text("""
            SELECT DISTINCT relationship_type 
            FROM relationships 
            WHERE tenant_id = :tenant_id
            ORDER BY relationship_type
        """), {'tenant_id': tenant_id})
        types = [row[0] for row in result.fetchall()]
        logger.debug(f"Found {len(types)} relationship types for tenant: {types}")
        return types
    except Exception as e:
        logger.error(f"Failed to get relationship types: {e}")
        session.rollback()
        return []


@dataclass
class QueryIntent:
    """
    Structured representation of what the user is asking for.
    
    This is the output of Step 1 (Query Interpretation) and the input
    to Step 2 (Directed Graph Retrieval).
    
    Attributes:
        entity: The starting entity for graph traversal
        direction: Which direction to traverse (inbound, outbound, both)
        relationship_types: Which relationship types to follow
        depth: How many hops to traverse
        target_type: The type of entity the user wants in the answer (e.g., TEAM, SERVICE)
                     None means return all types found
        query_type: Type of query operation
        include_properties: Whether to include entity properties
        reasoning: LLM's explanation of interpretation
    """
    entity: str
    direction: DirectionType
    relationship_types: List[str]
    depth: int = 1
    target_type: Optional[str] = None
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
            target_type=data.get("target_type"),
            query_type=data.get("query_type", "graph_traversal"),
            include_properties=data.get("include_properties", False),
            reasoning=data.get("reasoning", "")
        )


def build_query_interpreter_prompt(entity_types: List[str], relationship_types: List[str]) -> str:
    """
    Build the query interpreter prompt dynamically based on tenant's schema.
    
    This makes the system domain-agnostic - it works for IT, healthcare,
    legal, finance, etc. based on what entity types exist in the data.
    """
    entity_types_str = ", ".join(entity_types) if entity_types else "SERVICE, DATABASE, TEAM, INCIDENT"
    rel_types_str = ", ".join(relationship_types) if relationship_types else "DEPENDS_ON, CALLS, MANAGES, OWNS"
    
    return f"""You are a Query Interpreter for a knowledge graph system.

Your task is to interpret natural language questions and output a structured query intent
that specifies exactly what data to retrieve from the graph.

AVAILABLE ENTITY TYPES IN THIS DOMAIN:
{entity_types_str}

AVAILABLE RELATIONSHIP TYPES:
{rel_types_str}

KEY CONCEPTS:
- "inbound" = relationships where the entity is the TARGET (X → Entity)
- "outbound" = relationships where the entity is the SOURCE (Entity → X)
- "target_type" = the TYPE of entity the user wants in the answer (e.g., if user asks "which teams", target_type is TEAM)

TARGET TYPE EXTRACTION:
Users ask questions in terms of concepts. Map their concept to an entity type:
- "which teams..." → target_type: "TEAM"
- "what services..." → target_type: "SERVICE"
- "which databases..." → target_type: "DATABASE"
- "what incidents..." → target_type: "INCIDENT"
- "which customers..." → target_type: "CUSTOMER" (if available)
- "what systems..." → target_type: "SYSTEM"
If the question doesn't specify a type, set target_type to null.

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
{{
  "entity": "Name of the target entity (the starting point for traversal)",
  "direction": "inbound" | "outbound" | "both",
  "relationship_types": ["DEPENDS_ON", "CALLS", ...],
  "depth": 1-3,
  "target_type": "TEAM" | "SERVICE" | null (what type of entity user wants in answer),
  "query_type": "graph_traversal" | "property_lookup" | "existence_check",
  "include_properties": true | false,
  "reasoning": "Brief explanation of interpretation"
}}

EXAMPLES:

Query: "Which teams would be affected by a Checkout Service outage?"
{{
  "entity": "Checkout Service",
  "direction": "inbound",
  "relationship_types": ["DEPENDS_ON", "CALLS", "OWNS", "MANAGES"],
  "depth": 2,
  "target_type": "TEAM",
  "query_type": "graph_traversal",
  "include_properties": false,
  "reasoning": "User asks for TEAMS affected. Find services that depend on Checkout Service, then find teams that own those services."
}}

Query: "What's the blast radius if API Gateway fails?"
{{
  "entity": "API Gateway",
  "direction": "inbound",
  "relationship_types": ["DEPENDS_ON", "CALLS"],
  "depth": 2,
  "target_type": null,
  "query_type": "graph_traversal",
  "include_properties": false,
  "reasoning": "Blast radius = downstream impact. Find all entities that DEPEND_ON or CALL the API Gateway."
}}

Query: "What does Order Service depend on?"
{{
  "entity": "Order Service",
  "direction": "outbound",
  "relationship_types": ["DEPENDS_ON"],
  "depth": 1,
  "target_type": null,
  "query_type": "graph_traversal",
  "include_properties": false,
  "reasoning": "Direct dependency query - find what Order Service depends on (outbound DEPENDS_ON)."
}}

Query: "Who manages the Payment Service?"
{{
  "entity": "Payment Service",
  "direction": "inbound",
  "relationship_types": ["MANAGES", "OWNS"],
  "depth": 1,
  "target_type": "TEAM",
  "query_type": "graph_traversal",
  "include_properties": false,
  "reasoning": "User asks WHO (teams/people). Find teams/people that MANAGE or OWN Payment Service."
}}

Query: "Which databases does the Order Service use?"
{{
  "entity": "Order Service",
  "direction": "outbound",
  "relationship_types": ["DEPENDS_ON", "USES", "CONNECTS_TO"],
  "depth": 1,
  "target_type": "DATABASE",
  "query_type": "graph_traversal",
  "include_properties": false,
  "reasoning": "User asks for DATABASES. Find databases that Order Service depends on."
}}

Respond with ONLY the JSON object, no additional text."""


class QueryInterpreter:
    """
    Step 1 of the 3-Step Query Pipeline: Query Interpretation.
    
    Uses an LLM to interpret natural language queries into structured QueryIntent objects.
    The interpreter is schema-aware - it learns what entity types and relationship types
    exist from the tenant's data, making it domain-agnostic.
    """
    
    def __init__(
        self, 
        model: str = "gpt-4o-mini",
        session: Optional[Session] = None,
        tenant_id: Optional[str] = None
    ):
        self.client = OpenAI()
        self.model = model
        self.session = session
        self.tenant_id = tenant_id
        
        self.entity_types: List[str] = []
        self.relationship_types: List[str] = []
        
        if session and tenant_id:
            self.entity_types = get_tenant_entity_types(session, tenant_id)
            self.relationship_types = get_tenant_relationship_types(session, tenant_id)
            logger.info(f"QueryInterpreter initialized with {len(self.entity_types)} entity types, "
                       f"{len(self.relationship_types)} relationship types")
        else:
            logger.info(f"QueryInterpreter initialized with model: {model} (no schema context)")
    
    def interpret(self, query_text: str) -> QueryIntent:
        """
        Interpret a natural language query into a structured QueryIntent.
        
        Args:
            query_text: The user's natural language question
            
        Returns:
            QueryIntent object specifying what to retrieve from the graph
        """
        try:
            prompt = build_query_interpreter_prompt(self.entity_types, self.relationship_types)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Query: \"{query_text}\""}
                ],
                temperature=0.0,
                max_completion_tokens=500,
                response_format={"type": "json_object"}
            )
            
            response_text = response.choices[0].message.content
            intent_data = json.loads(response_text)
            
            intent = QueryIntent.from_dict(intent_data)
            
            if intent.target_type and self.entity_types:
                if intent.target_type not in self.entity_types:
                    logger.warning(f"LLM returned target_type '{intent.target_type}' not in schema. "
                                  f"Available types: {self.entity_types}")
                    intent.target_type = self._find_closest_type(intent.target_type)
            
            logger.info(f"Query interpreted: entity='{intent.entity}', "
                       f"direction={intent.direction}, "
                       f"types={intent.relationship_types}, "
                       f"depth={intent.depth}, "
                       f"target_type={intent.target_type}")
            logger.debug(f"Interpretation reasoning: {intent.reasoning}")
            
            return intent
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse query interpretation response: {e}")
            return self._fallback_interpretation(query_text)
        except Exception as e:
            logger.error(f"Query interpretation failed: {e}")
            return self._fallback_interpretation(query_text)
    
    def _find_closest_type(self, target_type: str) -> Optional[str]:
        """Find the closest matching entity type from available types."""
        if not self.entity_types:
            return None
        
        target_lower = target_type.lower()
        for et in self.entity_types:
            if et.lower() == target_lower:
                return et
            if target_lower in et.lower() or et.lower() in target_lower:
                return et
        
        return None
    
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
