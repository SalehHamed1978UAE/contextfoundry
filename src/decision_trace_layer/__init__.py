"""
Decision Trace Layer (DTL) v1.0

Extends Context Foundry with precedent-aware decision memory.
While CF captures *what exists* (entities, relationships), 
DTL captures *why decisions were made* (rationale, precedents, exceptions, outcomes).
"""

from .models import (
    DecisionTrace,
    DecisionEvidence,
    DecisionEntityLink,
    DecisionPrecedentLink,
    DecisionException,
    DecisionConfidenceScore,
    DecisionExecution,
    DecisionResult,
    DecisionAssessment,
    DecisionCategory,
    SchemaEvolutionProposal,
    DecisionAccessGrant,
    DecisionAccessAudit,
)
from .precedent_search import PrecedentSearchClient, PrecedentResult

__all__ = [
    "DecisionTrace",
    "DecisionEvidence", 
    "DecisionEntityLink",
    "DecisionPrecedentLink",
    "DecisionException",
    "DecisionConfidenceScore",
    "DecisionExecution",
    "DecisionResult",
    "DecisionAssessment",
    "DecisionCategory",
    "SchemaEvolutionProposal",
    "DecisionAccessGrant",
    "DecisionAccessAudit",
    "PrecedentSearchClient",
    "PrecedentResult",
]
