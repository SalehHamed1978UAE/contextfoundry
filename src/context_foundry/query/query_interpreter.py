"""Query Interpreter — Converts natural language queries to structured QueryIntent.

This module is consumed by directed_retriever.py and other graph traversal
components. The QueryIntent dataclass describes a structured query plan that
can be executed deterministically against the knowledge graph.

Field naming preserves backward compatibility with directed_retriever.py
(which references `intent.entity`) while also exposing a `primary_entity`
alias for newer call sites.
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class QueryIntent:
    """Structured representation of query intent for directed retrieval."""
    entity: Optional[str] = None
    entity_type_hint: Optional[str] = None
    relationship_types: List[str] = field(default_factory=list)
    direction: str = "either"  # "outbound", "inbound", "either"
    target_type: Optional[str] = None
    depth: int = 1
    aggregation: Optional[str] = None  # "list", "max", "min", "sum", "count"
    temporal_filter: Optional[Dict[str, str]] = None
    attribute_filter: Optional[str] = None
    query_text: str = ""

    @property
    def primary_entity(self) -> Optional[str]:
        """Alias for `entity` used by newer interpreter code."""
        return self.entity

    @primary_entity.setter
    def primary_entity(self, value: Optional[str]) -> None:
        self.entity = value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity": self.entity,
            "entity_type_hint": self.entity_type_hint,
            "relationship_types": list(self.relationship_types),
            "direction": self.direction,
            "target_type": self.target_type,
            "depth": self.depth,
            "aggregation": self.aggregation,
            "temporal_filter": self.temporal_filter,
            "attribute_filter": self.attribute_filter,
            "query_text": self.query_text,
        }


@dataclass
class InterpretationResult:
    """Result of query interpretation."""
    intent: QueryIntent
    confidence: float = 1.0
    interpretation_notes: List[str] = field(default_factory=list)


class QueryInterpreter:
    """Interprets natural language queries into structured QueryIntents."""

    ROLE_PATTERNS = [
        "who is", "who chairs", "who leads", "who heads", "who manages",
        "who directs", "who oversees", "who runs", "who is the",
        "director of", "vp of", "vice president", "head of",
        "president of", "chief of", "ceo of", "cfo of", "cto of",
        "manager of", "leader of", "chair of",
    ]

    AGGREGATION_PATTERNS = {
        "list": ["list ", "who are ", "what are ", "show me ", "members"],
        "max": ["largest", "biggest", "most ", "maximum", "highest"],
        "min": ["smallest", "least", "minimum", "lowest"],
        "sum": ["total", "sum ", "combined", "aggregate"],
        "count": ["how many", "count of", "number of"],
    }

    ROLE_MARKERS = [
        "director of", "vp of", "vice president of", "head of",
        "president of", "chief of", "manager of", "leader of", "chair of",
    ]

    def interpret(self, query: str, context: Optional[Dict] = None) -> InterpretationResult:
        """Convert natural language query to structured QueryIntent."""
        query_lower = query.lower().strip()
        intent = QueryIntent(query_text=query)
        notes: List[str] = []

        # Role-based queries → target a PERSON entity
        if any(pattern in query_lower for pattern in self.ROLE_PATTERNS):
            intent.target_type = "PERSON"
            intent.direction = "inbound"
            intent.entity_type_hint = "PERSON"
            notes.append("Detected role query — targeting PERSON")

            for marker in self.ROLE_MARKERS:
                if marker in query_lower:
                    extracted = query_lower.split(marker, 1)[-1].strip()
                    extracted = extracted.rstrip("?.! ")
                    if extracted:
                        intent.entity = extracted
                    break

        # Aggregation detection
        for agg_type, patterns in self.AGGREGATION_PATTERNS.items():
            if any(p in query_lower for p in patterns):
                intent.aggregation = agg_type
                notes.append(f"Detected aggregation: {agg_type}")
                break

        # Temporal queries
        temporal_markers = ["when", "since", "became", "appointed", "started", "joined"]
        if any(m in query_lower for m in temporal_markers):
            intent.temporal_filter = {"type": "date_lookup"}
            notes.append("Detected temporal query")

        # Financial queries
        financial_markers = [
            "revenue", "capex", "budget", "valuation", "target",
            "forecast", "projection", "expenses", "income", "profit",
        ]
        if any(m in query_lower for m in financial_markers):
            intent.attribute_filter = "financial"
            notes.append("Detected financial query")

        return InterpretationResult(intent=intent, interpretation_notes=notes)


# Singleton accessor
_query_interpreter: Optional[QueryInterpreter] = None


def get_query_interpreter() -> QueryInterpreter:
    """Get or create the singleton QueryInterpreter."""
    global _query_interpreter
    if _query_interpreter is None:
        _query_interpreter = QueryInterpreter()
    return _query_interpreter


__all__ = ["QueryIntent", "InterpretationResult", "QueryInterpreter", "get_query_interpreter"]
