"""
RLM (Recursive Language Models) Integration for Context Foundry.

This module implements RLM-style iterative reasoning over the tri-memory architecture,
allowing LLMs to write code to navigate memory and recursively sub-query for verification.
"""

from .schemas import (
    LifecycleState,
    EntitySummary,
    EntityDetail,
    EntityMatch,
    ChunkSummary,
    ChunkDetail,
    ChunkMatch,
    ProvenanceInfo,
    Relationship,
    PathStep,
    Path,
    SubGraph,
    VerificationResult,
    REPLExecutionResult,
    ProgressTracker,
    SubQueryLog,
    ExecutionTraceEntry,
    ExecutionTrace,
    RLMConfig,
    RLMResult,
    RLMError,
    StaleEntityError,
    BudgetExhaustedError,
    REPLExecutionError,
    CircuitBreakerTripped,
)
from .sandbox import REPLSandbox, generate_retry_hint
from .sub_query import SubQueryAPI
from .executor import RLMExecutor, execute_rlm_query
from .router import QueryComplexityRouter, QueryTier, route_query, should_use_rlm

__all__ = [
    "LifecycleState",
    "EntitySummary",
    "EntityDetail",
    "EntityMatch",
    "ChunkSummary",
    "ChunkDetail",
    "ChunkMatch",
    "ProvenanceInfo",
    "Relationship",
    "PathStep",
    "Path",
    "SubGraph",
    "VerificationResult",
    "REPLExecutionResult",
    "ProgressTracker",
    "SubQueryLog",
    "ExecutionTraceEntry",
    "ExecutionTrace",
    "RLMConfig",
    "RLMResult",
    "RLMError",
    "StaleEntityError",
    "BudgetExhaustedError",
    "REPLExecutionError",
    "CircuitBreakerTripped",
    "REPLSandbox",
    "generate_retry_hint",
    "SubQueryAPI",
    "RLMExecutor",
    "execute_rlm_query",
    "QueryComplexityRouter",
    "QueryTier",
    "route_query",
    "should_use_rlm",
]
