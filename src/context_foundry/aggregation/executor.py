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
    counted_entities: List[Dict[str, Any]] = field(default_factory=list)
    
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
            # Rollback any failed transaction state before executing
            try:
                self.session.rollback()
            except Exception:
                pass
            
            # Set tenant context for RLS
            self.session.execute(
                text("SET LOCAL app.current_tenant_id = :tenant_id"),
                {"tenant_id": str(self.tenant_id)}
            )
            
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
        
        # Also fetch the actual entities that were counted (for rich responses)
        counted_entities = self._fetch_counted_entities(plan)
        
        return RawAggregationResult(
            value=value,
            metadata={"sample_size": getattr(row, "sample_size", None)},
            counted_entities=counted_entities,
        )
    
    def _fetch_counted_entities(self, plan: ExecutionPlan, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Fetch the actual entities that were counted (for rich responses).
        
        Derives an entity fetch query from the count plan's SQL and params.
        """
        try:
            # If the plan's SQL is a relationship count, fetch target entities
            if "relationships" in plan.sql and "source_id" in plan.sql:
                # Build query to fetch target entity details (without attributes column)
                entity_sql = """
                    SELECT DISTINCT e.id, e.name, e.entity_type, r.relationship_type
                    FROM relationships r
                    JOIN entities e ON r.target_id = e.id
                    WHERE r.tenant_id = :tenant_id
                      AND r.source_id = :anchor_id
                      AND r.relationship_type = :rel_type
                    LIMIT :entity_limit
                """
                params = {
                    "tenant_id": plan.params.get("tenant_id"),
                    "anchor_id": plan.params.get("anchor_id"),
                    "rel_type": plan.params.get("rel_type"),
                    "entity_limit": limit,
                }
                
                result = self.session.execute(text(entity_sql), params)
                rows = result.fetchall()
                
                entities = []
                for row in rows:
                    entity = {
                        "id": str(row.id) if hasattr(row, "id") else None,
                        "name": row.name if hasattr(row, "name") else None,
                        "entity_type": row.entity_type if hasattr(row, "entity_type") else None,
                        "relationship_type": row.relationship_type if hasattr(row, "relationship_type") else None,
                    }
                    entities.append(entity)
                
                logger.info(f"Fetched {len(entities)} counted entities for rich response")
                return entities
            
            return []
            
        except Exception as e:
            logger.warning(f"Failed to fetch counted entities: {e}")
            return []
    
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
