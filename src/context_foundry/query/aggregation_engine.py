"""Aggregation Engine — Handles list, max, min, sum, count queries.

P2.1: Foundation for multi-entity aggregation queries that the standard
single-entity retriever cannot answer (e.g. 'list Executive Team members',
'which division has the largest budget', 'total of top 3 customer contracts').
"""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class AggregationResult:
    result: Any = None
    source_entities: List[str] = field(default_factory=list)
    aggregation_type: str = ""
    confidence: float = 1.0


class AggregationEngine:
    """Handles multi-entity aggregation queries."""

    def handle_list_query(self, entities: List[Dict]) -> AggregationResult:
        """Return all entities in a list (e.g., 'Executive Team members')."""
        names = [e.get("name", str(e)) for e in entities]
        return AggregationResult(
            result=names,
            source_entities=[e.get("id", str(e)) for e in entities],
            aggregation_type="list",
        )

    def handle_max_query(self, entities: List[Dict], attribute: str = "budget") -> AggregationResult:
        """Return entity with maximum attribute value (e.g., 'largest budget')."""
        if not entities:
            return AggregationResult(result=None, aggregation_type="max")

        best = None
        best_value = float('-inf')
        for e in entities:
            val = self._extract_numeric(e, attribute)
            if val is not None and val > best_value:
                best_value = val
                best = e

        return AggregationResult(
            result=best,
            source_entities=[best.get("id")] if best else [],
            aggregation_type="max",
        )

    def handle_min_query(self, entities: List[Dict], attribute: str = "budget") -> AggregationResult:
        """Return entity with minimum attribute value."""
        if not entities:
            return AggregationResult(result=None, aggregation_type="min")

        best = None
        best_value = float('inf')
        for e in entities:
            val = self._extract_numeric(e, attribute)
            if val is not None and val < best_value:
                best_value = val
                best = e

        return AggregationResult(
            result=best,
            source_entities=[best.get("id")] if best else [],
            aggregation_type="min",
        )

    def handle_sum_query(self, entities: List[Dict], attribute: str = "value") -> AggregationResult:
        """Sum attribute values across entities (e.g., 'total of top 3 customers')."""
        total = 0.0
        sources = []
        for e in entities:
            val = self._extract_numeric(e, attribute)
            if val is not None:
                total += val
                sources.append(e.get("id", str(e)))

        return AggregationResult(
            result=total,
            source_entities=sources,
            aggregation_type="sum",
        )

    def handle_count_query(self, entities: List[Dict]) -> AggregationResult:
        """Return the count of entities (e.g., 'how many divisions')."""
        return AggregationResult(
            result=len(entities),
            source_entities=[e.get("id", str(e)) for e in entities],
            aggregation_type="count",
        )

    def _extract_numeric(self, entity: Dict, attribute: str) -> Optional[float]:
        """Extract numeric value from entity properties.

        Handles formatted strings like '$5M', '5,000,000', '5 million', '5B', '5K'.
        """
        props = entity.get("properties", {}) or {}
        if attribute not in props:
            return None
        val = props[attribute]
        try:
            if isinstance(val, str):
                val = val.replace("$", "").replace(",", "").strip()
                # Handle 'X million', 'X billion'
                lower = val.lower()
                if lower.endswith(" million"):
                    return float(lower.replace(" million", "").strip()) * 1_000_000
                if lower.endswith(" billion"):
                    return float(lower.replace(" billion", "").strip()) * 1_000_000_000
                if lower.endswith(" thousand"):
                    return float(lower.replace(" thousand", "").strip()) * 1_000
                # Handle 'XM', 'XB', 'XK' suffixes
                if val.upper().endswith("M"):
                    return float(val[:-1]) * 1_000_000
                if val.upper().endswith("B"):
                    return float(val[:-1]) * 1_000_000_000
                if val.upper().endswith("K"):
                    return float(val[:-1]) * 1_000
                # Strip percent sign
                if val.endswith("%"):
                    return float(val[:-1])
                return float(val)
            return float(val)
        except (ValueError, TypeError):
            return None

    def should_aggregate(self, query: str) -> Optional[str]:
        """Check if query needs aggregation and return type ('list'|'max'|'min'|'sum'|'count'|None)."""
        query_lower = query.lower()

        count_patterns = ["how many ", "count of ", "number of "]
        if any(p in query_lower for p in count_patterns):
            return "count"

        max_patterns = ["largest", "biggest", "most ", "maximum", "highest", "top ", "greatest"]
        if any(p in query_lower for p in max_patterns):
            return "max"

        min_patterns = ["smallest", "least ", "minimum", "lowest", "fewest"]
        if any(p in query_lower for p in min_patterns):
            return "min"

        sum_patterns = ["total ", "sum ", "combined", "aggregate "]
        if any(p in query_lower for p in sum_patterns):
            return "sum"

        list_patterns = ["list ", "who are ", "what are ", "show me ", "all ", " members"]
        if any(p in query_lower for p in list_patterns):
            return "list"

        return None


# Singleton
_aggregation_engine: Optional[AggregationEngine] = None


def get_aggregation_engine() -> AggregationEngine:
    global _aggregation_engine
    if _aggregation_engine is None:
        _aggregation_engine = AggregationEngine()
    return _aggregation_engine
