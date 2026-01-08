"""
AggregationPlanner - Maps CAT to executable query plans.

Per v1.3 spec §7, the planner:
1. Never generates free-form SQL from LLM at runtime
2. Uses allow-listed AST operators
3. Compiles CAT → parameterized SQL
"""

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from .models import (
    CAT,
    IntentKind,
    TargetSource,
    ClosurePolicy,
    Filter,
)

logger = logging.getLogger(__name__)


class ExecutionStrategy(str, Enum):
    """Execution strategy per §7.2."""
    SQL_AGG = "SQL_AGG"           # Direct SQL aggregate
    GRAPH_TRAVERSAL = "GRAPH_TRAVERSAL"  # Recursive CTE
    HYBRID = "HYBRID"             # Retrieval for citations only
    CACHE = "CACHE"               # Return cached result


@dataclass
class ExecutionPlan:
    """
    Executable query plan generated from CAT.
    
    Contains deterministic SQL/graph query with parameters.
    """
    strategy: ExecutionStrategy
    sql: str
    params: Dict[str, Any]
    
    # Metadata
    plan_hash: str = ""
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    # For graph traversal
    max_depth: int = 1
    
    # For caching
    cache_key: Optional[str] = None
    cache_ttl_seconds: int = 300
    
    def __post_init__(self):
        if not self.plan_hash:
            self.plan_hash = self._compute_hash()
    
    def _compute_hash(self) -> str:
        """Compute deterministic hash of the plan."""
        content = f"{self.sql}:{sorted(self.params.items())}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class AggregationPlanner:
    """
    Builds execution plans from CAT.
    
    Maps taxonomy classes (§3.1-3.10) to SQL templates.
    """
    
    # SQL templates for each aggregation type
    SQL_TEMPLATES = {
        IntentKind.COUNT: """
            SELECT COUNT(*) as result
            FROM {table} t
            WHERE t.tenant_id = :tenant_id
            {filters}
        """,
        
        IntentKind.COUNT_DISTINCT: """
            SELECT COUNT(DISTINCT {grouping_expr}) as result
            FROM {table} t
            WHERE t.tenant_id = :tenant_id
            {filters}
        """,
        
        IntentKind.SUM: """
            SELECT COALESCE(SUM({value_expr}), 0) as result
            FROM {table} t
            WHERE t.tenant_id = :tenant_id
            {filters}
        """,
        
        IntentKind.AVG: """
            SELECT COALESCE(AVG({value_expr}), 0) as result,
                   COUNT(*) as sample_size
            FROM {table} t
            WHERE t.tenant_id = :tenant_id
            {filters}
        """,
        
        IntentKind.MIN: """
            SELECT MIN({value_expr}) as result
            FROM {table} t
            WHERE t.tenant_id = :tenant_id
            {filters}
        """,
        
        IntentKind.MAX: """
            SELECT MAX({value_expr}) as result
            FROM {table} t
            WHERE t.tenant_id = :tenant_id
            {filters}
        """,
        
        IntentKind.GROUP_BY: """
            SELECT {group_key}, COUNT(*) as count
            FROM {table} t
            WHERE t.tenant_id = :tenant_id
            {filters}
            GROUP BY {group_key}
            ORDER BY count DESC
            LIMIT :limit
        """,
        
        IntentKind.TOP_K: """
            SELECT {select_expr}, {metric_expr} as metric
            FROM {table} t
            WHERE t.tenant_id = :tenant_id
            {filters}
            ORDER BY metric DESC
            LIMIT :k
        """,
    }
    
    # Graph traversal template
    GRAPH_CTE_TEMPLATE = """
        WITH RECURSIVE reachable AS (
            -- Base case: direct relationships
            SELECT 
                target_id as entity_id,
                1 as depth,
                ARRAY[source_id, target_id] as path
            FROM relationships r
            WHERE r.tenant_id = :tenant_id
              AND r.source_id = :start_entity_id
              AND r.relationship_type = :relationship_type
              {direction_filter}
            
            UNION ALL
            
            -- Recursive case
            SELECT 
                r.target_id,
                reachable.depth + 1,
                reachable.path || r.target_id
            FROM relationships r
            JOIN reachable ON r.source_id = reachable.entity_id
            WHERE r.tenant_id = :tenant_id
              AND r.relationship_type = :relationship_type
              AND reachable.depth < :max_depth
              AND NOT r.target_id = ANY(reachable.path)  -- Prevent cycles
        )
        SELECT COUNT(DISTINCT entity_id) as result
        FROM reachable
    """
    
    # DTL queries
    DTL_TEMPLATE = """
        SELECT COUNT(*) as result
        FROM dtl_decisions d
        WHERE d.tenant_id = :tenant_id
          AND d.decision_type = :decision_type
          {outcome_filter}
          {time_filter}
    """
    
    # Document mentions (requires doc_entity_mentions table)
    DOC_MENTIONS_TEMPLATE = """
        SELECT COUNT(DISTINCT doc_id) as result
        FROM doc_entity_mentions m
        WHERE m.tenant_id = :tenant_id
          AND m.entity_id = :entity_id
    """
    
    def build_plan(self, cat: CAT) -> ExecutionPlan:
        """
        Build execution plan from CAT.
        
        Args:
            cat: The Canonical Aggregation Target
            
        Returns:
            ExecutionPlan ready for execution
        """
        # Check cache first (in production, would check aggregation_metadata)
        cache_key = self._compute_cache_key(cat)
        
        # Select strategy based on target source and intent
        if cat.target.source == TargetSource.KG_RELATIONSHIP:
            if cat.aggregation.op == IntentKind.GRAPH_COUNT:
                return self._build_graph_plan(cat, cache_key)
            else:
                return self._build_relationship_plan(cat, cache_key)
        
        elif cat.target.source == TargetSource.DTL_DECISION:
            return self._build_dtl_plan(cat, cache_key)
        
        elif cat.target.source == TargetSource.DOCUMENT_MENTION:
            return self._build_doc_mentions_plan(cat, cache_key)
        
        else:
            return self._build_entity_plan(cat, cache_key)
    
    def _build_entity_plan(self, cat: CAT, cache_key: str) -> ExecutionPlan:
        """Build plan for entity table aggregation."""
        template = self.SQL_TEMPLATES.get(cat.aggregation.op)
        if not template:
            template = self.SQL_TEMPLATES[IntentKind.COUNT]
        
        # Build filter clause
        filters, filter_params = self._build_filters(cat.filters, cat.time)
        
        # Build grouping expression
        grouping_expr = ", ".join(cat.aggregation.grouping_key) if cat.aggregation.grouping_key else "t.id"
        
        # Substitute template
        table = f"entities"  # Would be dynamic based on entity_type
        sql = template.format(
            table=table,
            grouping_expr=grouping_expr,
            value_expr=cat.aggregation.value_expr or "1",
            group_key=", ".join(cat.aggregation.grouping_key) if cat.aggregation.grouping_key else "t.entity_type",
            select_expr="t.*",
            metric_expr="COUNT(*)",
            filters=f"AND {filters}" if filters else "",
        )
        
        params = {
            "tenant_id": str(cat.tenant_id),
            "limit": 100,
            "k": 10,
            **filter_params,
        }
        
        return ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql=sql.strip(),
            params=params,
            cache_key=cache_key,
        )
    
    def _build_relationship_plan(self, cat: CAT, cache_key: str) -> ExecutionPlan:
        """Build plan for relationship aggregation."""
        template = self.SQL_TEMPLATES.get(cat.aggregation.op, self.SQL_TEMPLATES[IntentKind.COUNT])
        
        filters, filter_params = self._build_filters(cat.filters, cat.time)
        
        # Add anchor filter if present (use 't' alias to match template)
        anchor_filter = ""
        if cat.anchor:
            anchor_filter = "AND t.source_id = :anchor_id"
            filter_params["anchor_id"] = str(cat.anchor.entity_id)
        
        # Add relationship type filter (use 't' alias to match template)
        rel_filter = ""
        if cat.target.relationship_type:
            rel_filter = "AND t.relationship_type = :rel_type"
            filter_params["rel_type"] = cat.target.relationship_type
        
        grouping_expr = ", ".join(cat.aggregation.grouping_key) if cat.aggregation.grouping_key else "t.target_id"
        
        sql = template.format(
            table="relationships",
            grouping_expr=grouping_expr,
            value_expr=cat.aggregation.value_expr or "1",
            group_key=", ".join(cat.aggregation.grouping_key) if cat.aggregation.grouping_key else "t.relationship_type",
            select_expr="t.*",
            metric_expr="COUNT(*)",
            filters=f"{anchor_filter} {rel_filter} {'AND ' + filters if filters else ''}",
        )
        
        params = {
            "tenant_id": str(cat.tenant_id),
            "limit": 100,
            "k": 10,
            **filter_params,
        }
        
        return ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql=sql.strip(),
            params=params,
            cache_key=cache_key,
        )
    
    def _build_graph_plan(self, cat: CAT, cache_key: str) -> ExecutionPlan:
        """Build plan for graph traversal aggregation."""
        if not cat.anchor:
            raise ValueError("Graph traversal requires anchor entity")
        
        max_depth = cat.graph.max_hops if cat.graph else 3
        
        # Direction filter
        direction_filter = ""
        if cat.graph and cat.graph.direction == "incoming":
            direction_filter = "-- Note: Query structure assumes outgoing; swap for incoming"
        
        sql = self.GRAPH_CTE_TEMPLATE.format(direction_filter=direction_filter)
        
        params = {
            "tenant_id": str(cat.tenant_id),
            "start_entity_id": str(cat.anchor.entity_id),
            "relationship_type": cat.target.relationship_type or "DEPENDS_ON",
            "max_depth": max_depth,
        }
        
        return ExecutionPlan(
            strategy=ExecutionStrategy.GRAPH_TRAVERSAL,
            sql=sql.strip(),
            params=params,
            max_depth=max_depth,
            cache_key=cache_key,
        )
    
    def _build_dtl_plan(self, cat: CAT, cache_key: str) -> ExecutionPlan:
        """Build plan for DTL decision aggregation."""
        filters, filter_params = self._build_filters(cat.filters, cat.time)
        
        # Outcome filter (e.g., outcome = 'granted')
        outcome_filter = ""
        for f in cat.filters:
            if "outcome" in f.path.lower():
                outcome_filter = f"AND d.outcome = :outcome"
                filter_params["outcome"] = f.value
                break
        
        # Time filter
        time_filter = ""
        if cat.time and cat.time.start:
            time_filter = "AND d.created_at >= :time_start"
            filter_params["time_start"] = cat.time.start
        if cat.time and cat.time.end:
            time_filter += " AND d.created_at <= :time_end"
            filter_params["time_end"] = cat.time.end
        
        sql = self.DTL_TEMPLATE.format(
            outcome_filter=outcome_filter,
            time_filter=time_filter,
        )
        
        params = {
            "tenant_id": str(cat.tenant_id),
            "decision_type": cat.target.entity_type or "exception",
            **filter_params,
        }
        
        return ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql=sql.strip(),
            params=params,
            cache_key=cache_key,
        )
    
    def _build_doc_mentions_plan(self, cat: CAT, cache_key: str) -> ExecutionPlan:
        """Build plan for document mentions aggregation."""
        if not cat.anchor:
            raise ValueError("Document mention count requires anchor entity")
        
        sql = self.DOC_MENTIONS_TEMPLATE
        
        params = {
            "tenant_id": str(cat.tenant_id),
            "entity_id": str(cat.anchor.entity_id),
        }
        
        return ExecutionPlan(
            strategy=ExecutionStrategy.SQL_AGG,
            sql=sql.strip(),
            params=params,
            cache_key=cache_key,
        )
    
    def _build_filters(
        self,
        filters: List[Filter],
        time: Optional[Any],
    ) -> tuple:
        """Build SQL filter clause from Filter objects."""
        clauses = []
        params = {}
        
        for i, f in enumerate(filters):
            if not f.path:
                continue
            
            param_name = f"filter_{i}"
            
            if f.op == "IN":
                clauses.append(f"t.{f.path} = ANY(:{param_name})")
                params[param_name] = f.value
            elif f.op == "BETWEEN":
                clauses.append(f"t.{f.path} BETWEEN :{param_name}_start AND :{param_name}_end")
                params[f"{param_name}_start"] = f.value[0]
                params[f"{param_name}_end"] = f.value[1]
            else:
                clauses.append(f"t.{f.path} {f.op} :{param_name}")
                params[param_name] = f.value
        
        # Add time filter
        if time and time.field:
            if time.start:
                clauses.append(f"t.{time.field} >= :time_start")
                params["time_start"] = time.start
            if time.end:
                clauses.append(f"t.{time.field} <= :time_end")
                params["time_end"] = time.end
        
        return " AND ".join(clauses), params
    
    def _compute_cache_key(self, cat: CAT) -> str:
        """Compute cache key for CAT."""
        content = f"{cat.tenant_id}:{cat.target.source}:{cat.aggregation.op}:{cat.aggregation.grouping_key}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
