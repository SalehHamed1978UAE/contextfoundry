"""FactEvaluator — top-level orchestrator.

Wires Stage 1-6 together. Owns recursion guard, depth limit, replan loop, and
the recursive source-authority hook on the gatherer.
"""
from __future__ import annotations

import asyncio
import logging
from typing import List, Optional, Iterable
from sqlalchemy import text as _sql_text
from .contracts import Fact, Verdict, MetaAudit, Condition
from .planner import EvaluationPlanner, PlanValidationError
from .gatherer import EvidenceGatherer
from .adversary import AdversarialChallenger
from .prover import ProofConstructor
from .meta import MetaEvaluator
from .synthesizer import VerdictSynthesizer
from .recursion import RecursionGuard
from .tools import GraphTools
from .llm.client import LLMClient
from .observability.trace import tracer

logger = logging.getLogger(__name__)


from contextlib import contextmanager
@contextmanager
def _noop_cm():
    yield None


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
        # Per-trace diagnostics (reset on each top-level evaluate() call)
        self._diag_source_authority_evals: int = 0
        self._diag_max_depth_reached: int = 0
        self._diag_replans_used: int = 0
        self._diag_terminated_by_ceiling: bool = False

    async def evaluate(self, fact: Fact, guard: Optional[RecursionGuard] = None,
                        replans_used: int = 0) -> Verdict:
        # `is_root` controls trace lifecycle + diagnostics stamping.
        # Distinct from `is_outer_call` (which controls diag *reset* and
        # final stamping): a replan recurses with replans_used>0 but is
        # still semantically the same top-level evaluation, so we must NOT
        # reset counters and we MUST stamp diagnostics on the returned
        # verdict. `is_outer_call` is True iff this is the user-initiated
        # call (no guard passed) OR a replan re-entry of one.
        is_outer_call = guard is None
        if guard is None:
            guard = RecursionGuard(max_depth=self.max_depth)
        is_root = guard.depth == 0 and replans_used == 0
        if is_root:
            # Reset per-fact diagnostics on the outermost call only.
            self._diag_source_authority_evals = 0
            self._diag_max_depth_reached = 0
            self._diag_replans_used = 0
            self._diag_terminated_by_ceiling = False
        if guard.depth > self._diag_max_depth_reached:
            self._diag_max_depth_reached = guard.depth
        trace_cm = tracer.trace(fact_key=fact.key(), depth=guard.depth) \
            if is_root else _noop_cm()
        with trace_cm:
            if guard.has_visited(fact):
                tracer.event("cycle_detected", fact_key=fact.key())
                return self._terminal(fact, "UNDERSPECIFIED",
                                      ["recursion cycle detected"], guard.depth)
            if guard.at_max_depth():
                tracer.event("max_depth_reached", fact_key=fact.key())
                self._diag_terminated_by_ceiling = True
                return self._terminal(fact, "UNDERSPECIFIED",
                                      ["max recursion depth reached"], guard.depth,
                                      terminated_by_ceiling=True)

            with tracer.span("planner"):
                try:
                    plan = await self.planner.plan(fact, self.schema_context)
                except PlanValidationError as pve:
                    tracer.event("plan_validation_failed",
                                 message=pve.message)
                    final = self._terminal(
                        fact, "UNDERSPECIFIED",
                        [f"planner failed validation after retries: "
                         f"{pve.message}"],
                        guard.depth)
                    return self._maybe_stamp_root(final, is_root, is_outer_call)

            sub_verdicts: List[Verdict] = []
            graph_fact_presups = [c for c in plan.presuppositions
                                  if c.kind == "graph_fact" and c.fact is not None]
            type_check_presups = [c for c in plan.presuppositions
                                  if c.kind == "type_check"]
            # `custom` presuppositions are surfaced in the plan but never
            # block the verdict — they're for human review only.
            if graph_fact_presups or type_check_presups:
                with tracer.span(
                    "presuppositions",
                    graph_fact=len(graph_fact_presups),
                    type_check=len(type_check_presups),
                ):
                    type_check_verdicts = [
                        self._eval_type_check(c, fact, guard.depth + 1)
                        for c in type_check_presups
                    ]
                    graph_fact_verdicts = list(await asyncio.gather(*[
                        self.evaluate(c.fact, guard.child(fact))
                        for c in graph_fact_presups
                    ])) if graph_fact_presups else []
                    sub_verdicts = type_check_verdicts + graph_fact_verdicts
                if any(sv.status == "DISPROVEN" for sv in sub_verdicts):
                    final = self._terminal(fact, "UNDERSPECIFIED",
                                           ["presupposition disproven"], guard.depth,
                                           plan=plan, sub_verdicts=sub_verdicts)
                    return self._maybe_stamp_root(final, is_root, is_outer_call)

            with tracer.span("gatherer"):
                evidence = await self.gatherer.gather(plan, fact)
                tracer.event("evidence_gathered", count=len(evidence))

            with tracer.span("adversary"):
                challenges = await self.adversary.challenge(fact, evidence, plan)
                tracer.event(
                    "challenges_generated",
                    total=len(challenges),
                    surviving=sum(1 for c in challenges if c.survived_rebuttal),
                )

            with tracer.span("prover"):
                proof, disproof = await asyncio.gather(
                    self.prover.try_prove(fact, evidence, plan),
                    self.prover.try_disprove(fact, evidence, plan),
                )
                tracer.event("proof_outcome",
                             proof_succeeded=proof.succeeded,
                             disproof_succeeded=disproof.succeeded)

            with tracer.span("meta"):
                audit = await self.meta.audit(plan, evidence, challenges, proof, disproof)

            if audit.recommend_replan and replans_used < self.max_replans:
                self._diag_replans_used = replans_used + 1
                tracer.event("replan", attempt=replans_used + 1)
                inner = await self.evaluate(fact, guard, replans_used + 1)
                # Stamp diagnostics on the replan-returned verdict if THIS
                # call is the user-initiated outer one. The replan recursion
                # has is_root=False (replans_used > 0), so it skips stamping;
                # we own the final stamp here.
                return self._maybe_stamp_root(inner, is_root, is_outer_call)
            if audit.recommend_replan and replans_used >= self.max_replans:
                self._diag_terminated_by_ceiling = True
                tracer.event("replan_ceiling_hit", max_replans=self.max_replans)

            with tracer.span("synthesizer"):
                verdict = self.synth.synthesize(
                    fact, plan, evidence, challenges, proof, disproof, audit,
                    sub_verdicts, depth=guard.depth,
                )
            verdict = self._maybe_stamp_root(verdict, is_root, is_outer_call)
            tracer.event("verdict", status=verdict.status,
                         surviving_challenges=len(verdict.surviving_challenges))
            return verdict

    def _maybe_stamp_root(self, verdict: Verdict, is_root: bool,
                           is_outer_call: bool) -> Verdict:
        """Stamp diagnostics + ceiling flag onto a root verdict.

        Stamps when EITHER (a) this is the original is_root call (depth=0,
        replans_used=0) returning normally, OR (b) this is the outermost
        user-initiated call observing a replan-recursed inner verdict that
        was itself not stamped because its is_root was False.
        """
        if not (is_root or is_outer_call):
            return verdict
        ceiling_hit = (
            self._diag_terminated_by_ceiling
            or getattr(self.adversary, "last_terminated_by_ceiling", False)
        )
        verdict.terminated_by_ceiling = ceiling_hit
        verdict.diagnostics = {
            "adversary_rounds_executed": getattr(
                self.adversary, "last_rounds_executed", 0),
            "adversary_max_rounds": self.adversary.max_rounds,
            "source_authority_evals_spawned": self._diag_source_authority_evals,
            "max_recursion_depth_reached": self._diag_max_depth_reached,
            "max_recursion_depth_cap": self.max_depth,
            "replans_used": self._diag_replans_used,
            "max_replans_cap": self.max_replans,
            "authority_cache_size": len(self._authority_cache),
        }
        tracer.event(
            "evaluate_summary",
            status=verdict.status,
            terminated_by_ceiling=ceiling_hit,
            **verdict.diagnostics,
        )
        return verdict

    def _eval_type_check(self, cond: Condition, parent_fact: Fact,
                         depth: int) -> Verdict:
        """Direct DB lookup for a type_check presupposition. No recursion.

        Returns a synthetic Verdict the parent synthesizer can inspect:
        - SUPPORTED if the entity exists with the expected type
        - DISPROVEN if the entity exists with a different type
        - UNDERSUPPORTED if the entity is not found in the tenant
        """
        synthetic_fact = Fact(
            source_entity_id=cond.entity_id or "",
            relationship_type="HAS_TYPE",
            target_entity_id=cond.expected_entity_type or "",
            tenant_id=parent_fact.tenant_id,
            natural_language=cond.description,
        )
        try:
            sql = ("SELECT entity_type FROM entities "
                   "WHERE id = CAST(:id AS uuid)")
            params = {"id": cond.entity_id}
            tid = parent_fact.tenant_id or self.tools.tenant_id
            if tid:
                sql += " AND tenant_id = CAST(:tid AS uuid)"
                params["tid"] = tid
            row = self.tools._exec(sql, params).fetchone()
        except Exception as e:
            logger.warning(f"[type_check] DB lookup failed for {cond.entity_id}: {e}")
            return self._terminal(synthetic_fact, "UNDERSUPPORTED",
                                  [f"type_check DB error: {e}"], depth)
        if row is None:
            return self._terminal(synthetic_fact, "UNDERSUPPORTED",
                                  ["entity not found for type_check"], depth)
        actual_type = (row[0] or "").upper()
        expected = (cond.expected_entity_type or "").upper()
        if actual_type == expected:
            return self._terminal(synthetic_fact, "SUPPORTED",
                                  [f"entity is typed as {actual_type}"], depth)
        return self._terminal(synthetic_fact, "DISPROVEN",
                              [f"expected {expected}, found {actual_type}"], depth)

    # -------------------------------------------------- source-authority
    async def _evaluate_source_authority(self, authority_fact: Fact) -> Verdict:
        """Bounded recursive authority check. Cached per (chunk_id, fact_type)."""
        key = authority_fact.key()
        if key in self._authority_cache:
            return self._authority_cache[key]
        # Counter for per-fact diagnostics — only counts cache misses, since
        # those are the calls that actually do work (DB hit + verdict synth).
        self._diag_source_authority_evals += 1
        tracer.bump("source_authority_evals_spawned")
        # Use a lightweight authority guard so the recursive call doesn't
        # explode — depth 1 is enough; we don't want authority-of-authority-of...
        guard = RecursionGuard(max_depth=1)
        guard = guard.child(authority_fact)  # pre-mark to short-circuit deeper recursion
        # Default: SUPPORTED if the chunk exists (presence proves the source
        # made the claim). A more sophisticated implementation would inspect
        # source_predicate / document type / publication date.
        chunk = self.tools._exec(
            "SELECT id::text FROM document_chunks WHERE id = CAST(:c AS uuid)",
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
                  sub_verdicts=None, terminated_by_ceiling: bool = False) -> Verdict:
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
            terminated_by_ceiling=terminated_by_ceiling,
        )
