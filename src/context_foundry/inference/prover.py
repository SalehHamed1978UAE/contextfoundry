"""Stage 4 — ProofConstructor.

LLM proposes a proof chain. Every cited axiom is verified by a real database
query. The LLM proposes; PostgreSQL disposes.
"""
from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field
from typing import List
from .contracts import Fact, EvaluationPlan, EvidenceItem, ProofAttempt
from .llm.client import LLMClient
from .observability.trace import tracer
from .tools import GraphTools

PROMPT_PATH = Path(__file__).parent / "llm" / "prompts" / "prover_system.md"


class _LLMProofProposal(BaseModel):
    succeeded: bool
    chain: List[str] = Field(default_factory=list)
    axioms_used: List[str] = Field(default_factory=list)
    gaps: List[str] = Field(default_factory=list)


class ProofConstructor:
    def __init__(self, llm: LLMClient, tools: GraphTools):
        self.llm = llm
        self.tools = tools
        self._system_prompt = PROMPT_PATH.read_text()

    async def try_prove(self, fact: Fact, evidence: List[EvidenceItem],
                        plan: EvaluationPlan) -> ProofAttempt:
        return await self._attempt(fact, evidence, plan, prove=True)

    async def try_disprove(self, fact: Fact, evidence: List[EvidenceItem],
                           plan: EvaluationPlan) -> ProofAttempt:
        return await self._attempt(fact, evidence, plan, prove=False)

    async def _attempt(self, fact: Fact, evidence: List[EvidenceItem],
                       plan: EvaluationPlan, prove: bool) -> ProofAttempt:
        target = "PROVE" if prove else "DISPROVE"
        rel_evidence = [e for e in evidence if e.relationship_id]
        chunk_evidence = [e for e in evidence if e.chunk_id]
        user_prompt = (
            f"GOAL: {target} the following fact.\n\n"
            f"FACT:\n  source_entity_id={fact.source_entity_id}\n"
            f"  relationship_type={fact.relationship_type}\n"
            f"  target_entity_id={fact.target_entity_id}\n"
            f"  properties={fact.properties}\n\n"
            f"AVAILABLE RELATIONSHIPS (axiom candidates):\n"
            + "\n".join(
                f"  rel_id={e.relationship_id} polarity={e.polarity} speaks_to={e.speaks_to}"
                for e in rel_evidence[:50]
            )
            + f"\n\nAVAILABLE CHUNKS (textual evidence):\n"
            + "\n".join(
                f"  chunk_id={e.chunk_id} polarity={e.polarity} content={e.content[:200]}"
                for e in chunk_evidence[:30]
            )
            + "\n\nReturn a ProofAttempt via the structured tool. If you cannot "
              "construct a valid chain, set succeeded=false and list gaps."
        )
        proposed: _LLMProofProposal = await self.llm.call(
            system_prompt=self._system_prompt,
            user_prompt=user_prompt,
            output_schema=_LLMProofProposal,
        )
        verified_axioms, missing = self._verify_axioms(proposed.axioms_used, fact, prove)
        succeeded = proposed.succeeded and not missing
        gaps = list(proposed.gaps)
        if missing:
            gaps.append(
                f"axioms not found in DB: {sorted(missing)[:10]}"
                f"{' (and more)' if len(missing) > 10 else ''}"
            )
        attempt = ProofAttempt(
            succeeded=succeeded,
            chain=list(proposed.chain),
            axioms_used=sorted(verified_axioms),
            gaps=gaps,
        )
        # Structured trace event so post-hoc benchmark analysis can audit the
        # exact chain + axioms a (dis)proof relied on without re-running.
        tracer.event(
            "prover_proof_attempt" if prove else "prover_disproof_attempt",
            succeeded=attempt.succeeded,
            llm_claimed_succeeded=proposed.succeeded,
            chain=attempt.chain,
            axioms_used=attempt.axioms_used,
            axioms_claimed=list(proposed.axioms_used),
            axioms_missing=sorted(missing),
            gaps=attempt.gaps,
            fact_source=fact.source_entity_id,
            fact_target=fact.target_entity_id,
            fact_relationship_type=fact.relationship_type,
        )
        return attempt

    def _verify_axioms(self, axiom_ids: List[str], fact: Fact, prove: bool):
        """Check every cited axiom is a real, non-archived relationship.

        For try_disprove we additionally require that at least one axiom
        actually contradicts the fact (e.g., same target, different source for
        a single-occupancy role) — otherwise the LLM's "disproof" wasn't
        grounded in real conflicting state.

        Each axiom is looked up by id directly (one O(1) DB hit per id) — we
        never load the whole relationships table.
        """
        from sqlalchemy import text as _sql
        verified, missing = set(), set()
        contradicting_seen = False
        for rid in axiom_ids:
            sql = ("SELECT id::text, source_id::text, relationship_type, "
                   "target_id::text, lifecycle_state::text "
                   "FROM relationships WHERE id = CAST(:rid AS uuid) "
                   "AND lifecycle_state <> 'ARCHIVED'")
            try:
                row = self.tools._exec(sql, {"rid": rid}).fetchone()
            except Exception:
                row = None
            if row is None:
                missing.add(rid)
                continue
            verified.add(rid)
            if not prove:
                # contradicting = same target + same rel_type, different source
                if (row[3] == fact.target_entity_id and
                        row[2] == fact.relationship_type and
                        row[1] != fact.source_entity_id):
                    contradicting_seen = True
        if not prove and verified and not contradicting_seen:
            missing.add("__no_contradicting_axiom__")
        return verified, missing
