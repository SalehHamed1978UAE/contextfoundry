"""Stage 5 — MetaEvaluator.

Audits plan completeness, evidence thoroughness, and proof validity. Returns
recommend_replan when either plan or evidence-gathering looks deficient.
"""
from __future__ import annotations

from pathlib import Path
from typing import List
from .contracts import (
    EvaluationPlan, EvidenceItem, Challenge, ProofAttempt, MetaAudit,
)
from .llm.client import LLMClient

PROMPT = (Path(__file__).parent / "llm" / "prompts" / "meta_system.md").read_text()


class MetaEvaluator:
    def __init__(self, llm: LLMClient):
        self.llm = llm

    async def audit(self, plan: EvaluationPlan, evidence: List[EvidenceItem],
                    challenges: List[Challenge], proof: ProofAttempt,
                    disproof: ProofAttempt) -> MetaAudit:
        # Quick structural checks without LLM
        missing_falsifier_hint = self._missing_falsifier_hint(plan, challenges)
        ev_categories = {e.speaks_to for e in evidence}
        missing_ev_categories = [
            q for q in plan.evidence_queries if q not in ev_categories
        ]
        proof_attempted = bool(
            (proof and (proof.succeeded or proof.chain or proof.gaps))
            or (disproof and (disproof.succeeded or disproof.chain or disproof.gaps))
        )

        user_prompt = self._build_user_prompt(
            plan, evidence, challenges, proof, disproof,
            missing_falsifier_hint, missing_ev_categories,
        )
        try:
            audit: MetaAudit = await self.llm.call(
                system_prompt=PROMPT, user_prompt=user_prompt,
                output_schema=MetaAudit,
            )
            return audit
        except Exception:
            # Conservative fallback: structural verdict
            return MetaAudit(
                plan_completeness_verdict="incomplete" if missing_falsifier_hint else "complete",
                missing_falsifiers=missing_falsifier_hint,
                evidence_thoroughness_verdict="shallow" if missing_ev_categories else "thorough",
                untested_hypotheses=[],
                proof_validity_verdict="valid" if proof_attempted else "no_proof_attempted",
                recommend_replan=bool(missing_falsifier_hint or missing_ev_categories),
            )

    @staticmethod
    def _missing_falsifier_hint(plan: EvaluationPlan,
                                challenges: List[Challenge]) -> List[str]:
        """If the adversary surfaced a challenge whose theme isn't in the plan's
        falsifier list, the plan was incomplete."""
        plan_falsifier_text = " ".join(c.description.lower() for c in plan.falsifiers)
        out = []
        for ch in challenges:
            if not ch.survived_rebuttal:
                continue
            words = [w for w in ch.description.lower().split() if len(w) > 4]
            if not any(w in plan_falsifier_text for w in words):
                out.append(ch.description)
        return out

    @staticmethod
    def _build_user_prompt(plan, evidence, challenges, proof, disproof,
                           missing_falsifier_hint, missing_ev_categories) -> str:
        return (
            f"PLAN.fact_type: {plan.fact_type}\n"
            f"PLAN.truth_conditions ({len(plan.truth_conditions)}): "
            + "; ".join(c.description for c in plan.truth_conditions[:10])
            + f"\nPLAN.falsifiers ({len(plan.falsifiers)}): "
            + "; ".join(c.description for c in plan.falsifiers[:10])
            + f"\nPLAN.evidence_queries ({len(plan.evidence_queries)}): "
            + "; ".join(plan.evidence_queries[:10])
            + f"\n\nEVIDENCE GATHERED: {len(evidence)} items, polarities="
            + str({p: sum(1 for e in evidence if e.polarity == p) for p in ('confirms','disconfirms','neutral')})
            + f"\nMISSING EVIDENCE CATEGORIES: {missing_ev_categories}\n\n"
            f"SURVIVING CHALLENGES ({sum(1 for c in challenges if c.survived_rebuttal)}): "
            + "; ".join(c.description for c in challenges if c.survived_rebuttal)
            + f"\nCHALLENGES NOT IN PLAN'S FALSIFIERS: {missing_falsifier_hint}\n\n"
            f"PROOF: succeeded={proof.succeeded if proof else 'n/a'} chain_len="
            f"{len(proof.chain) if proof else 0} gaps={proof.gaps if proof else []}\n"
            f"DISPROOF: succeeded={disproof.succeeded if disproof else 'n/a'} chain_len="
            f"{len(disproof.chain) if disproof else 0} gaps={disproof.gaps if disproof else []}\n\n"
            "Return a MetaAudit via the structured tool."
        )
