"""
AggregationExecutor - Executes query plans with RLS enforcement.

Per v1.3 spec §7, execution happens inside the existing SQLAlchemy session
so RLS/tenant context is automatically enforced.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from .planner import ExecutionPlan, ExecutionStrategy
from .models import EvidenceEnvelope

logger = logging.getLogger(__name__)


@dataclass
class RawAggregationResult:
    """Raw result from query execution."""
    value: Any
    sample_ids: List[str] = field(default_factory=list)
    row_count: int = 0
    sources: List["SourceEvidence"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def has_multiple_sources(self) -> bool:
        return len(self.sources) >= 2


@dataclass
class SourceEvidence:
    """Evidence from a single data source."""
    source_name: str
    entities: List[str]
    count: int
    confidence: float = 1.0


class AggregationExecutor:
    """
    Executes aggregation plans using existing SQLAlchemy session.
    
    RLS is enforced at the database level via current_setting('app.current_tenant').
    """
    
    # Statement timeout for safety
    STATEMENT_TIMEOUT_MS = 10000  # 10 seconds
    
    def __init__(self, session: Session, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id
    
    def execute(
        self,
        plan: ExecutionPlan,
    ) -> tuple:
        """
        Execute the plan and return raw result + evidence envelope.
        
        Returns:
            Tuple of (RawAggregationResult, EvidenceEnvelope)
        """
        logger.info(f"Executing plan: strategy={plan.strategy}, hash={plan.plan_hash}")
        
        try:
            # Set statement timeout
            self.session.execute(
                text(f"SET LOCAL statement_timeout = '{self.STATEMENT_TIMEOUT_MS}'")
            )
            
            # Execute based on strategy
            if plan.strategy == ExecutionStrategy.SQL_AGG:
                result = self._execute_sql(plan)
            elif plan.strategy == ExecutionStrategy.GRAPH_TRAVERSAL:
                result = self._execute_graph(plan)
            elif plan.strategy == ExecutionStrategy.CACHE:
                result = self._execute_cache(plan)
            else:
                raise ValueError(f"Unsupported strategy: {plan.strategy}")
            
            # Build evidence envelope
            evidence = EvidenceEnvelope(
                plan_hash=plan.plan_hash,
                sql=plan.sql,
                params={k: str(v) for k, v in plan.params.items()},
                snapshot_time=datetime.utcnow(),
                sample_ids=result.sample_ids[:10],  # Limit sample size
            )
            
            return result, evidence
            
        except Exception as e:
            logger.exception(f"Execution failed: {e}")
            raise
    
    def _execute_sql(self, plan: ExecutionPlan) -> RawAggregationResult:
        """Execute SQL aggregation."""
        result = self.session.execute(text(plan.sql), plan.params)
        row = result.fetchone()
        
        if row is None:
            return RawAggregationResult(value=0)
        
        # Handle different result shapes
        if hasattr(row, "result"):
            value = row.result
        elif hasattr(row, "_mapping"):
            value = row._mapping.get("result", row[0])
        else:
            value = row[0]
        
        return RawAggregationResult(
            value=value,
            metadata={"sample_size": getattr(row, "sample_size", None)},
        )
    
    def _execute_graph(self, plan: ExecutionPlan) -> RawAggregationResult:
        """Execute graph traversal."""
        result = self.session.execute(text(plan.sql), plan.params)
        row = result.fetchone()
        
        value = row.result if row else 0
        
        return RawAggregationResult(
            value=value,
            metadata={"max_depth": plan.max_depth},
        )
    
    def _execute_cache(self, plan: ExecutionPlan) -> RawAggregationResult:
        """Return cached result."""
        # In production, would query aggregation_metadata table
        raise NotImplementedError("Cache execution not yet implemented")
