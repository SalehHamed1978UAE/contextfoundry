"""
Context Foundry Agents.

Agent modules for the tri-memory cognitive architecture:
- GraphLoaderAgent: Loads data into the knowledge graph
- GraphBuilderAgent: Ingests documents, extracts entities/relationships, writes to STAGING
- StagingValidatorAgent: Validates STAGING data against schema rules
- Retrieval: Retrieves context from all memory layers
- Reasoning: LLM-powered reasoning with context
- Validation: Rule-based response validation
- Gardener: Maintains knowledge graph health (decay, promotion, conflict, demotion)
- IdentityResolver: Detects and merges duplicate entities
- GardenerScheduler: Runs Gardener on 5-minute cycles
"""
from .graph_loader import GraphLoaderAgent
from .graph_builder import GraphBuilderAgent, ExtractionResult
from .staging_validator import StagingValidatorAgent, ValidationResult, ValidationIssue
from .retrieval import RetrievalAgent
from .reasoning import ReasoningAgent
from .validation import ValidationAgent
from .gardener import (
    GardenerAgent, Gardener, GardenerConfig, GardenerCycleResult,
    DecayResult, PromotionResult, ConflictResult, DemotionResult, CleanupResult,
    ConflictType, ConflictResolution
)
from .identity_resolver import IdentityResolver, IdentityResolutionConfig, DuplicateCandidate
from .scheduler import GardenerScheduler, SchedulerConfig, start_scheduler, stop_scheduler

__all__ = [
    "GraphLoaderAgent",
    "GraphBuilderAgent",
    "ExtractionResult",
    "StagingValidatorAgent",
    "ValidationResult",
    "ValidationIssue",
    "RetrievalAgent", 
    "ReasoningAgent",
    "ValidationAgent",
    "GardenerAgent",
    "Gardener",
    "GardenerConfig",
    "GardenerCycleResult",
    "DecayResult",
    "PromotionResult",
    "ConflictResult",
    "DemotionResult",
    "CleanupResult",
    "ConflictType",
    "ConflictResolution",
    "IdentityResolver",
    "IdentityResolutionConfig",
    "DuplicateCandidate",
    "GardenerScheduler",
    "SchedulerConfig",
    "start_scheduler",
    "stop_scheduler",
]
