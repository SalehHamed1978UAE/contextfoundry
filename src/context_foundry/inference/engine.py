"""FactEvaluator — top-level orchestrator.

Wires Stage 1-6 together. Owns recursion guard, depth limit, replan loop, and
the recursive source-authority hook on the gatherer.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Iterable
from .contracts import Fact, Verdict, MetaAudit
from .planner import EvaluationPlanner
from .gatherer import EvidenceGatherer
from .adversary import AdversarialChallenger
from .prover import ProofConstructor
from .meta import MetaEvaluator
from .synthesizer import VerdictSynthesizer
from .recursion import RecursionGuard
from .tools import GraphTools
from .llm.client import LLMClient

logger = logging.getLogger(__name__)


class FactEvaluator:
    def __init__(self, session, llm_client: LLMClient,
                 schema_entity_types: Iterable[str],
                 schema_relationship_types: Iterable[str],
                 tenant_id: Optional[str] = None,
                 embedder=None,
                 max_depth: int = 5, max_replans: int = 3):
        self.session = session
        self.llm = llm_client
        self.tenant_id = tenant_id
        self.tools = GraphTools(session, tenant_id=tenant_id)
        self.planner = EvaluationPlanner(llm_client, schema_entity_types,
                                          schema_relationship_types)
        self.gatherer = EvidenceGatherer(llm_client, self.tools, embedder=embedder)
        self.adversary = AdversarialChallenger(llm_client)
        self.prover = ProofConstructor(llm_client, self.tools)
        self.meta = MetaEvaluator(llm_client)
        self.synth = VerdictSynthesizer()
        self.max_depth = max_depth
        self.max_replans = max_replans
        # Wire recursive source-authority hook (now that engine exists).
        self.gatherer.evaluator = self._evaluate_source_authority
        self.schema_context = ""
        self._authority_cache: dict = {}

    async def evaluate(self, fact: Fact, guard: Optional[RecursionGuard] = None,
                        replans_used: int = 0) -> Verdict:
        if guard is None:
            guard = RecursionGuard(max_depth=self.max_depth)
        if guard.has_visited(fact):
            logger.debug(f"[Engine] cycle on {fact.key()}")
            return self._terminal(fact, "UNDERSPECIFIED",
                                  ["recursion cycle detected"], guard.depth)
        if guard.at_max_depth():
            return self._terminal(fact, "UNDERSPECIFIED",
                                  ["max recursion depth reached"], guard.depth)

        # 1. Plan
        plan = await self.planner.plan(fact, self.schema_context)

        # 2. Evaluate presuppositions recursively (siblings get fresh guards)
        presup_facts = [c.fact for c in plan.presuppositions if c.fact is not None]
        sub_verdicts: List[Verdict] = []
        if presup_facts:
            sub_verdicts = list(await asyncio.gather(*[
                self.evaluate(pf, guard.child(fact)) for pf in presup_facts
            ]))
            if any(sv.status == "DISPROVEN" for sv in sub_verdicts):
                return self._terminal(fact, "UNDERSPECIFIED",
                                      ["presupposition disproven"], guard.depth,
                                      plan=plan, sub_verdicts=sub_verdicts)

        # 3. Gather evidence (recursive source-authority via the wired hook)
        evidence = await self.gatherer.gather(plan, fact)

        # 4. Adversarial challenges
        challenges = await self.adversary.challenge(fact, evidence, plan)

        # 5. Proof attempts (parallel)
        proof, disproof = await asyncio.gather(
            self.prover.try_prove(fact, evidence, plan),
            self.prover.try_disprove(fact, evidence, plan),
        )

        # 6. Meta-audit
        audit = await self.meta.audit(plan, evidence, challenges, proof, disproof)

        # 7. Replan loop (max 3)
        if audit.recommend_replan and replans_used < self.max_replans:
            logger.info(f"[Engine] replan #{replans_used+1} on {fact.key()}")
            return await self.evaluate(fact, guard, replans_used + 1)

        # 8. Synthesize
        verdict = self.synth.synthesize(
            fact, plan, evidence, challenges, proof, disproof, audit,
            sub_verdicts, depth=guard.depth,
        )
        return verdict

    # -------------------------------------------------- source-authority
    async def _evaluate_source_authority(self, authority_fact: Fact) -> Verdict:
        """Bounded recursive authority check. Cached per (chunk_id, fact_type)."""
        key = authority_fact.key()
        if key in self._authority_cache:
            return self._authority_cache[key]
        # Use a lightweight authority guard so the recursive call doesn't
        # explode — depth 1 is enough; we don't want authority-of-authority-of...
        guard = RecursionGuard(max_depth=1)
        guard = guard.child(authority_fact)  # pre-mark to short-circuit deeper recursion
        # Default: SUPPORTED if the chunk exists (presence proves the source
        # made the claim). A more sophisticated implementation would inspect
        # source_predicate / document type / publication date.
        chunk = self.tools.session.execute(
            __import__("sqlalchemy").text(
                "SELECT id::text FROM document_chunks WHERE id = CAST(:c AS uuid)"
            ),
            {"c": authority_fact.source_entity_id},
        ).fetchone()
        if not chunk:
            v = self._terminal(authority_fact, "UNDERSUPPORTED",
                               ["chunk not found"], 1)
        else:
            v = self._terminal(authority_fact, "SUPPORTED",
                               ["chunk exists; presence-based authority"], 1)
        self._authority_cache[key] = v
        return v

    @staticmethod
    def _terminal(fact: Fact, status, caveats, depth, plan=None,
                  sub_verdicts=None) -> Verdict:
        return Verdict(
            status=status, fact=fact, plan=plan,
            evidence=[], surviving_challenges=[], proof_attempt=None,
            disproof_attempt=None,
            meta_audit=MetaAudit(
                plan_completeness_verdict="complete",
                evidence_thoroughness_verdict="thorough",
                proof_validity_verdict="no_proof_attempted",
                recommend_replan=False,
            ),
            sub_verdicts=sub_verdicts or [],
            trace=[f"terminal verdict: {status}"],
            caveats=list(caveats), depth=depth,
        )
