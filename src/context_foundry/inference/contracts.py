"""Pydantic data contracts for the FactEvaluator inference engine.

Every value passed between stages is a pydantic model defined here. IDs are
UUID strings (not ints — the live CF schema is uuid). Adding a new contract
field requires no migration; the synthesiser and engine are the only places
that interpret them.
"""
from __future__ import annotations

from typing import Literal, Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


VerdictStatus = Literal[
    "PROVEN",                 # formal proof, no surviving falsifier
    "STRONGLY_SUPPORTED",     # multiple independent confirmations, falsifiers searched
    "SUPPORTED",              # confirmation exists, counter-evidence searched
    "CONTESTED",              # both supporting and contradicting evidence survive
    "UNDERSPECIFIED",         # presupposition unverified or fact ambiguous
    "UNDERSUPPORTED",         # insufficient evidence in either direction
    "DISPROVEN",              # formal disproof or surviving decisive falsifier
]


class Fact(BaseModel):
    """A claim under evaluation (source -[rel]-> target).

    Properties may carry literal-valued claims like {'amount_usd': 50_000_000}.
    """
    model_config = ConfigDict(frozen=True)

    source_entity_id: str
    relationship_type: str
    target_entity_id: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    natural_language: Optional[str] = None
    tenant_id: Optional[str] = None

    def key(self) -> str:
        """Stable hashable identity for cycle detection.

        Properties ARE included (sorted, JSON-canonical) so that two facts
        about the same edge with different literal-valued claims — e.g.
        `HAS_BUDGET {amount: 50M}` vs `HAS_BUDGET {amount: 100M}` — are
        treated as distinct nodes in the recursive proof DAG. Without this,
        the engine would short-circuit them as a "cycle".
        """
        import json as _json
        props_canonical = _json.dumps(self.properties, sort_keys=True,
                                      separators=(",", ":"), default=str)
        return (f"{self.source_entity_id}|{self.relationship_type}|"
                f"{self.target_entity_id}|{props_canonical}")


ConditionKind = Literal["graph_fact", "type_check", "custom"]


class Condition(BaseModel):
    """A sub-claim that must be evaluated.

    Three variants discriminated by `kind`:

    - "graph_fact" (default for back-compat): a recursively-evaluable subject-
      predicate-object claim. Requires `fact`. Engine will recurse into
      `evaluate(fact)`. Use this for claims like "Robert Kim REPORTS_TO
      Victoria Chen" that are themselves graph edges.
    - "type_check": a unary entity-typing presupposition. Requires `entity_id`
      + `expected_entity_type`. NO recursion — engine performs a direct DB
      lookup against the entities table. Use for claims like "Nexus is typed
      as ORG in the schema" or "Victoria Chen is a PERSON".
    - "custom": informational / not directly evaluable. Engine skips it for
      blocking purposes (it does NOT propagate UNDERSPECIFIED to the parent).
      Use for nuanced presuppositions like "the role is single-occupant" that
      we surface to humans but cannot mechanically check.
    """
    description: str
    kind: ConditionKind = "graph_fact"
    fact: Optional[Fact] = None
    entity_id: Optional[str] = None
    expected_entity_type: Optional[str] = None
    custom_check: Optional[str] = None
    decisive: bool = False


class Hypothesis(BaseModel):
    """An alternative explanation that must be ruled out."""
    description: str
    falsifying_evidence_required: List[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    """One piece of gathered evidence, labeled with polarity and provenance."""
    chunk_id: Optional[str] = None
    relationship_id: Optional[str] = None
    entity_id: Optional[str] = None
    content: str
    speaks_to: str
    polarity: Literal["confirms", "disconfirms", "neutral"]
    # Recursive trust check — populated by EvidenceGatherer once the engine
    # exists. Until then it stays None and the synthesiser treats unknown
    # authority as 'unverified' (still counts as evidence, never authoritative).
    source_authority_verdict: Optional["Verdict"] = None
    source_document_id: Optional[str] = None
    # Lifecycle of the underlying graph object (relationship/entity), surfaced
    # so that downstream prompts (adversary, rebuttal) can see it. Values:
    # 'STAGING' | 'TRUSTED' | 'ARCHIVED'. None when the evidence is a chunk
    # without an associated graph object.
    lifecycle_state: Optional[str] = None


class EvaluationPlan(BaseModel):
    """Output of the planner — what would make this fact true/false."""
    fact_type: str
    truth_conditions: List[Condition] = Field(default_factory=list)
    falsifiers: List[Condition] = Field(default_factory=list)
    presuppositions: List[Condition] = Field(default_factory=list)
    competing_hypotheses: List[Hypothesis] = Field(default_factory=list)
    evidence_queries: List[str] = Field(default_factory=list)
    adversarial_prompts: List[str] = Field(default_factory=list)
    rationale: str = ""


class ProofAttempt(BaseModel):
    """Result of try_prove or try_disprove. Steps are LLM-proposed, axioms DB-verified."""
    succeeded: bool
    chain: List[str] = Field(default_factory=list)
    axioms_used: List[str] = Field(default_factory=list)  # relationship UUIDs
    gaps: List[str] = Field(default_factory=list)


class Challenge(BaseModel):
    """An adversarial counter-argument and whether it survived rebuttal."""
    description: str
    counter_evidence: List[EvidenceItem] = Field(default_factory=list)
    survived_rebuttal: bool
    rebuttal_reason: Optional[str] = None


class MetaAudit(BaseModel):
    """Stage-5 audit of plan completeness, evidence thoroughness, proof validity."""
    plan_completeness_verdict: Literal["complete", "incomplete"]
    missing_falsifiers: List[str] = Field(default_factory=list)
    evidence_thoroughness_verdict: Literal["thorough", "shallow"]
    untested_hypotheses: List[Hypothesis] = Field(default_factory=list)
    proof_validity_verdict: Literal["valid", "invalid", "no_proof_attempted"]
    recommend_replan: bool = False


class Verdict(BaseModel):
    """Final categorical verdict for a Fact, with full reasoning trace."""
    status: VerdictStatus
    fact: Fact
    plan: Optional[EvaluationPlan] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)
    surviving_challenges: List[Challenge] = Field(default_factory=list)
    proof_attempt: Optional[ProofAttempt] = None
    disproof_attempt: Optional[ProofAttempt] = None
    meta_audit: Optional[MetaAudit] = None
    sub_verdicts: List["Verdict"] = Field(default_factory=list)
    trace: List[str] = Field(default_factory=list)
    caveats: List[str] = Field(default_factory=list)
    depth: int = 0
    # True when ANY hard ceiling fired during evaluation (adversary max_rounds
    # without convergence, max_replans hit, source-authority depth cap, or
    # max_depth recursion cap). Distrust the verdict when this is True.
    terminated_by_ceiling: bool = False
    # Per-fact bookkeeping for benchmark diagnostics.
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


# Late binding — Verdict references itself recursively via EvidenceItem.
EvidenceItem.model_rebuild()
Verdict.model_rebuild()
