"""
Context Foundry Aggregation Framework v1.3

This module provides quantitative query handling for CF, enabling
safe counting and aggregation over KG, DTL, and document data.

Key components:
- router: Detects and routes aggregation queries
- intent: DSPy-based intent classification and CAT resolution
- registry: CRUD for agg_definitions (semantic contracts)
- planner: Maps CAT to execution plans (SQL/graph)
- executor: Runs deterministic queries with RLS
- crc: Lincoln-Petersen Capture-Recapture estimation
- sufficiency: Numeric sufficiency gate (EXACT/LOWER_BOUND/RANGE/INSUFFICIENT)
- formatter: Composes user-visible answers

Usage:
    from context_foundry.aggregation import AggregationService
    
    service = AggregationService(session, tenant_ctx)
    result = service.handle_query(question, user_ctx)
"""

from .service import AggregationService
from .models import (
    AggIntent,
    CAT,
    ResultKind,
    AggregationResult,
    EvidenceEnvelope,
    BoundedCount,
)

__all__ = [
    "AggregationService",
    "AggIntent",
    "CAT",
    "ResultKind",
    "AggregationResult",
    "EvidenceEnvelope",
    "BoundedCount",
]
