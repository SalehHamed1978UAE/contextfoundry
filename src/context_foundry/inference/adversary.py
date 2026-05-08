"""Stage 3 — AdversarialChallenger.

Spawns N parallel attack stances, generates challenges, then runs a rebuttal
pass per challenge. Iterates until a full round produces no new challenges.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List, Set
from pydantic import BaseModel, Field
from .contracts import Fact, EvidenceItem, EvaluationPlan, Challenge
from .llm.client import LLMClient

logger = logging.getLogger(__name__)
ADV_PROMPT = (Path(__file__).parent / "llm" / "prompts" / "adversary_system.md").read_text()
REB_PROMPT = (Path(__file__).parent / "llm" / "prompts" / "rebuttal_system.md").read_text()


class _LLMChallengeList(BaseModel):
    challenges: List[Challenge] = Field(default_factory=list)


class _LLMRebuttal(BaseModel):
    survived_rebuttal: bool
    rebuttal_reason: str = ""


DEFAULT_STANCES = [
    "Assume this fact is FALSE. Construct the most plausible alternative.",
    "Find any logical inconsistency between this fact and the existing graph axioms.",
    "Identify any source whose authority is questionable and re-evaluate.",
    "Find any presupposition that the planner missed.",
    "Construct a worldview where the existing evidence supports the OPPOSITE conclusion.",
]


class AdversarialChallenger:
    def __init__(self, llm: LLMClient, max_rounds: int = 3, stances: List[str] = None):
        self.llm = llm
        self.max_rounds = max_rounds
        self.stances = stances or list(DEFAULT_STANCES)

    async def challenge(self, fact: Fact, evidence: List[EvidenceItem],
                        plan: EvaluationPlan) -> List[Challenge]:
        all_challenges: List[Challenge] = []
        seen_descs: Set[str] = set()
        # Plan-supplied adversarial prompts also get their own attack
        stances = list(self.stances) + list(plan.adversarial_prompts or [])
        for round_idx in range(self.max_rounds):
            new_round = await self._spawn_round(fact, evidence, plan, stances)
            new_added = 0
            for ch in new_round:
                k = ch.description.strip().lower()
                if k in seen_descs:
                    continue
                seen_descs.add(k)
                all_challenges.append(ch)
                new_added += 1
            if new_added == 0:
                break
        # Rebuttal pass — parallel
        await asyncio.gather(*[
            self._rebut(ch, fact, evidence) for ch in all_challenges
        ])
        all_challenges.sort(key=lambda c: c.description.lower())
        return all_challenges

    async def _spawn_round(self, fact: Fact, evidence: List[EvidenceItem],
                           plan: EvaluationPlan, stances: List[str]) -> List[Challenge]:
        async def one(stance: str) -> List[Challenge]:
            user_prompt = self._build_user_prompt(fact, evidence, plan, stance)
            try:
                resp: _LLMChallengeList = await self.llm.call(
                    system_prompt=ADV_PROMPT,
                    user_prompt=user_prompt,
                    output_schema=_LLMChallengeList,
                )
                return list(resp.challenges)
            except Exception as e:
                logger.warning(f"[Adversary] stance failed ({stance[:40]}...): {e}")
                return []
        results = await asyncio.gather(*[one(s) for s in stances])
        out: List[Challenge] = []
        for r in results:
            out.extend(r)
        return out

    @staticmethod
    def _build_user_prompt(fact: Fact, evidence: List[EvidenceItem],
                           plan: EvaluationPlan, stance: str) -> str:
        nl = fact.natural_language or (
            f"({fact.source_entity_id})-[{fact.relationship_type}]->({fact.target_entity_id})"
        )
        ev_summary = "\n".join(
            f"  - polarity={e.polarity} lifecycle={e.lifecycle_state or '-'} "
            f"chunk={e.chunk_id} rel={e.relationship_id} "
            f"speaks_to={e.speaks_to[:60]} content={(e.content or '')[:200]}"
            for e in evidence[:60]
        )
        return (
            f"FACT:\n{nl}\n\n"
            f"YOUR ATTACK STANCE:\n{stance}\n\n"
            f"PLANNER'S COMPETING HYPOTHESES:\n"
            + "\n".join(f"  - {h.description}" for h in plan.competing_hypotheses)
            + f"\n\nGATHERED EVIDENCE ({len(evidence)} items):\n{ev_summary}\n\n"
            "Return a list of Challenges via the structured tool. Each must be "
            "grounded in real chunks/relationships listed above."
        )

    async def _rebut(self, challenge: Challenge, fact: Fact,
                     evidence: List[EvidenceItem]) -> None:
        nl = fact.natural_language or fact.key()
        ev_summary = "\n".join(
            f"  - polarity={e.polarity} lifecycle={e.lifecycle_state or '-'} "
            f"chunk={e.chunk_id} rel={e.relationship_id} "
            f"content={(e.content or '')[:200]}"
            for e in evidence[:50]
        )
        ce_summary = "\n".join(
            f"  - lifecycle={e.lifecycle_state or '-'} chunk={e.chunk_id} "
            f"rel={e.relationship_id} content={(e.content or '')[:200]}"
            for e in challenge.counter_evidence[:20]
        )
        user_prompt = (
            f"FACT: {nl}\n\nCHALLENGE: {challenge.description}\n\n"
            f"COUNTER_EVIDENCE PROVIDED BY ADVERSARY:\n{ce_summary or '  (none)'}\n\n"
            f"ALL GATHERED EVIDENCE:\n{ev_summary}\n\n"
            "Decide whether this challenge survives rebuttal."
        )
        try:
            resp: _LLMRebuttal = await self.llm.call(
                system_prompt=REB_PROMPT,
                user_prompt=user_prompt,
                output_schema=_LLMRebuttal,
            )
            challenge.survived_rebuttal = bool(resp.survived_rebuttal)
            challenge.rebuttal_reason = resp.rebuttal_reason
        except Exception as e:
            logger.warning(f"[Rebuttal] failed, defaulting to survived=True: {e}")
            challenge.survived_rebuttal = True
            challenge.rebuttal_reason = f"rebuttal failed: {e}"
        # Auto-rebut if no counter_evidence was grounded
        if not challenge.counter_evidence:
            challenge.survived_rebuttal = False
            challenge.rebuttal_reason = (challenge.rebuttal_reason or "") + \
                " | auto-rebutted: no counter_evidence"
