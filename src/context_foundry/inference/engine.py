"""FactEvaluator — top-level orchestrator.

Wires Stage 1-6 together. Owns recursion guard, depth limit, replan loop, and
the recursive source-authority hook on the gatherer.
"""
from __future__ import annotations

import asyncio
import json
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
from .gaps import (GapRecord, GapSource, GapType, GapSeverity,
                    current_gap_queue, current_run_id, current_question_id)

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
                    if guard.depth == 0:
                        self._enqueue_gap(GapRecord(
                            run_id=current_run_id() or "unknown_run",
                            question_id=current_question_id(),
                            source=GapSource.PLANNER_PRESUPPOSITION,
                            gap_type=GapType.GAP_PLANNER_FAILED,
                            severity=GapSeverity.HIGH,
                            fact_key=fact.key(),
                            trigger_stage="planner",
                            trigger_rule="PlanValidationError",
                            trigger_verdict="UNDERSPECIFIED",
                            explanation=(
                                f"Planner failed validation after retries: "
                                f"{pve.message}"),
                            remediation_hint=(
                                "Inspect planner prompt + schema_context; "
                                "human may need to provide a manual plan or "
                                "answer."),
                        ))
                    final = self._terminal(
                        fact, "UNDERSPECIFIED",
                        [f"planner failed validation after retries: "
                         f"{pve.message}"],
                        guard.depth)
                    return self._maybe_stamp_root(final, is_root, is_outer_call)
            # Plan summary event — diagnostic runs need plan_hash + presup
            # counts to distinguish planner-cache-hit from gather-blocked.
            try:
                import hashlib as _hl
                _plan_blob = json.dumps({
                    "tc": [c.model_dump(mode="json") for c in plan.truth_conditions],
                    "fa": [c.model_dump(mode="json") for c in plan.falsifiers],
                    "ps": [c.model_dump(mode="json") for c in plan.presuppositions],
                    "eq": list(plan.evidence_queries),
                }, sort_keys=True).encode()
                _plan_hash = _hl.sha256(_plan_blob).hexdigest()[:16]
            except Exception:
                _plan_hash = "unhashable"
            tracer.event(
                "planner_complete",
                plan_hash=_plan_hash,
                presupposition_count=len(plan.presuppositions),
                evidence_query_count=len(plan.evidence_queries),
                falsifier_count=len(plan.falsifiers),
            )

            # Snapshot the plan into the trace so we can compare initial
            # vs replan offline. `which_plan` is "initial" on the first
            # call and "replan_<n>" on each replan recursion.
            tracer.event(
                "plan_snapshot",
                which_plan=("initial" if replans_used == 0
                            else f"replan_{replans_used}"),
                truth_conditions=[c.model_dump(mode="json")
                                  for c in plan.truth_conditions],
                falsifiers=[c.model_dump(mode="json")
                            for c in plan.falsifiers],
                presuppositions=[c.model_dump(mode="json")
                                 for c in plan.presuppositions],
                evidence_queries=list(plan.evidence_queries),
                adversarial_prompts=list(plan.adversarial_prompts),
            )

            sub_verdicts: List[Verdict] = []
            graph_fact_presups = [c for c in plan.presuppositions
                                  if c.kind == "graph_fact" and c.fact is not None]
            type_check_presups = [c for c in plan.presuppositions
                                  if c.kind == "type_check"]
            identity_check_presups = [c for c in plan.presuppositions
                                      if c.kind == "identity_check"]
            # `custom` presuppositions are surfaced in the plan but never
            # block the verdict — they're for human review only.
            if graph_fact_presups or type_check_presups or identity_check_presups:
                with tracer.span(
                    "presuppositions",
                    graph_fact=len(graph_fact_presups),
                    type_check=len(type_check_presups),
                    identity_check=len(identity_check_presups),
                ):
                    type_check_verdicts = [
                        self._eval_type_check(c, fact, guard.depth + 1)
                        for c in type_check_presups
                    ]
                    identity_check_verdicts = [
                        self._eval_identity_check(c, fact, guard.depth + 1)
                        for c in identity_check_presups
                    ]
                    graph_fact_verdicts = list(await asyncio.gather(*[
                        self.evaluate(c.fact, guard.child(fact))
                        for c in graph_fact_presups
                    ])) if graph_fact_presups else []
                    sub_verdicts = (type_check_verdicts
                                    + identity_check_verdicts
                                    + graph_fact_verdicts)
                tracer.event(
                    "presuppositions_complete",
                    results=[{"kind": c.kind,
                              "status": sv.status,
                              "fact_key": (c.fact.key() if c.fact else None)}
                             for c, sv in zip(
                                 graph_fact_presups + type_check_presups
                                 + identity_check_presups, sub_verdicts)],
                    any_disproven=any(sv.status == "DISPROVEN" for sv in sub_verdicts),
                )
                # ---- D8.1: emit typed Gaps for any disproven presup ----
                # Direct method-call enqueue; do NOT rely on log subscription
                # (structlog bypasses stdlib logging — see design §10.6).
                # ROOT-ONLY emission BY DESIGN (architect-confirmed): nested
                # presup checks (graph_fact recursive eval) run at depth>0
                # and never reach depth==0 themselves, so they do NOT emit
                # standalone gaps. The aggregate GATE gap at the root carries
                # graph_fact sub-fact keys in evidence_refs as compensation.
                # If D8.2/D8.3 needs nested visibility, change here, not at
                # the call sites.
                if guard.depth == 0:
                    self._emit_presupposition_gaps(
                        fact, plan,
                        type_check_presups, type_check_verdicts,
                        identity_check_presups, identity_check_verdicts,
                        graph_fact_presups, graph_fact_verdicts,
                    )
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
                tracer.event("meta_audit", verdict=audit.model_dump())

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
            # ---- D8.1: gather succeeded but verdict insufficient ----
            if guard.depth == 0 and verdict.status in (
                "UNDERSUPPORTED", "UNKNOWN", "UNDERSPECIFIED",
            ):
                self._enqueue_gap(GapRecord(
                    run_id=current_run_id() or "unknown_run",
                    question_id=current_question_id(),
                    source=GapSource.EVALUATOR,
                    gap_type=GapType.GAP_EVIDENCE_INSUFFICIENT,
                    severity=GapSeverity.MEDIUM,
                    fact_key=fact.key(),
                    trigger_stage="synthesizer",
                    trigger_rule="post_gather_insufficient",
                    trigger_verdict=verdict.status,
                    explanation=(
                        f"Gather opened and produced {len(evidence)} evidence "
                        f"item(s), but synthesizer returned {verdict.status}. "
                        f"Human should review the gathered evidence."),
                    evidence_refs=[
                        {"chunk_id": getattr(e, "chunk_id", None)}
                        for e in (evidence or [])[:10]
                        if getattr(e, "chunk_id", None) is not None
                    ],
                    remediation_hint=(
                        "Either confirm the answer from gathered evidence "
                        "(human-in-loop writeback) or escalate to chunk-"
                        "extractor handler per gap routing."),
                ))
            return verdict

    # ------------------------------------------------------------------
    # D8.1: typed-gap emit helpers
    # ------------------------------------------------------------------
    def _enqueue_gap(self, gap: GapRecord) -> None:
        """Send a GapRecord to the active GapQueue (if any). No-op when
        the engine runs outside a `gap_context()` block."""
        q = current_gap_queue()
        if q is None:
            return
        try:
            q.enqueue(gap)
        except Exception:
            logger.exception("[engine] GapQueue.enqueue failed (non-fatal)")

    def _emit_presupposition_gaps(
        self, fact, plan,
        type_check_presups, type_check_verdicts,
        identity_check_presups, identity_check_verdicts,
        graph_fact_presups, graph_fact_verdicts,
    ) -> None:
        """Emit one GapRecord per disproven presup, plus an aggregate
        GAP_PLANNER_PRESUPPOSITION_GATE when the engine will short-circuit.
        Called only at depth=0; recursive sub-evaluates emit their own.
        """
        run_id = current_run_id() or "unknown_run"
        qid = current_question_id()
        any_disproven = False

        for cond, sv in zip(type_check_presups, type_check_verdicts):
            if sv.status != "DISPROVEN":
                continue
            any_disproven = True
            self._enqueue_gap(GapRecord(
                run_id=run_id, question_id=qid,
                source=GapSource.PLANNER_PRESUPPOSITION,
                gap_type=GapType.GAP_TYPE_MISMATCH,
                severity=GapSeverity.MEDIUM,
                fact_key=fact.key(),
                candidate_type=getattr(cond, "expected_type", None)
                                or getattr(cond, "type_name", None),
                trigger_stage="planner.presuppositions",
                trigger_rule="type_check.DISPROVEN",
                trigger_verdict=sv.status,
                explanation=(
                    "Planner asserted the candidate entity should be of "
                    "a type that the type_check verifier disproved. Either "
                    "the entity is misclassified (re-extract) or the "
                    "planner over-narrowed (planner-prompt review)."),
                evidence_refs=list(getattr(cond, "evidence_refs", []) or []),
                remediation_hint=(
                    "Surface candidate + asserted type to a human; route "
                    "to ontology / re-extraction handler."),
            ))

        for cond, sv in zip(identity_check_presups, identity_check_verdicts):
            if sv.status != "DISPROVEN":
                continue
            any_disproven = True
            self._enqueue_gap(GapRecord(
                run_id=run_id, question_id=qid,
                source=GapSource.PLANNER_PRESUPPOSITION,
                gap_type=GapType.GAP_IDENTITY_AMBIGUITY,
                severity=GapSeverity.MEDIUM,
                fact_key=fact.key(),
                trigger_stage="planner.presuppositions",
                trigger_rule="identity_check.DISPROVEN",
                trigger_verdict=sv.status,
                explanation=(
                    "identity_check verifier disproved that the candidate "
                    "IS the entity the question asks about. Possible "
                    "duplicate/disambiguation issue."),
                evidence_refs=list(getattr(cond, "evidence_refs", []) or []),
                remediation_hint=(
                    "Surface both candidate and asserted entity to a human "
                    "for disambiguation."),
            ))

        # graph_fact presups disproven also count as gate-blocking. No
        # specialized typed gap for graph_fact (yet) — collect their
        # sub-fact keys here so the aggregate gate gap actually carries
        # the actionable detail (architect D8.1 review fix).
        graph_fact_disproven_refs: list[dict] = []
        for cond, sv in zip(graph_fact_presups, graph_fact_verdicts):
            if sv.status != "DISPROVEN":
                continue
            any_disproven = True
            try:
                sub_key = cond.fact.key() if cond.fact else None
            except Exception:
                sub_key = None
            graph_fact_disproven_refs.append({
                "kind": "graph_fact",
                "sub_fact_key": sub_key,
                "trigger_verdict": sv.status,
            })

        if any_disproven:
            self._enqueue_gap(GapRecord(
                run_id=run_id, question_id=qid,
                source=GapSource.PLANNER_PRESUPPOSITION,
                gap_type=GapType.GAP_PLANNER_PRESUPPOSITION_GATE,
                severity=GapSeverity.HIGH,
                fact_key=fact.key(),
                trigger_stage="planner.presuppositions",
                trigger_rule="any_presup_DISPROVEN",
                trigger_verdict="UNDERSPECIFIED",
                explanation=(
                    "Engine will short-circuit at the presupposition gate; "
                    "gatherer + prover + adversary will not run. The "
                    "companion-specific gaps (GAP_TYPE_MISMATCH / "
                    "GAP_IDENTITY_AMBIGUITY) carry per-presup detail; "
                    "any graph_fact disprovals are listed in evidence_refs."),
                evidence_refs=graph_fact_disproven_refs,
                trace_refs=[],  # populated by trace plumbing in D8.2
                remediation_hint=(
                    "Route through chunk-extractor handler per question "
                    "shape (DateExtractor, ScalarExtractor, etc.) — see "
                    "config/gap_routing.yaml."),
            ))

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

    def _eval_identity_check(self, cond: Condition, parent_fact: Fact,
                              depth: int) -> Verdict:
        """Direct DB lookup for an identity_check presupposition. No recursion.

        Returns a synthetic Verdict the parent synthesizer can inspect:
        - SUPPORTED if the entity exists and its name (case-insensitively,
          trimmed) matches expected_name
        - DISPROVEN if the entity exists with a different name
        - UNDERSUPPORTED if the entity is not found in the tenant
        """
        synthetic_fact = Fact(
            source_entity_id=cond.entity_id or "",
            relationship_type="HAS_NAME",
            target_entity_id=cond.expected_name or "",
            tenant_id=parent_fact.tenant_id,
            natural_language=cond.description,
        )
        try:
            sql = ("SELECT name FROM entities "
                   "WHERE id = CAST(:id AS uuid)")
            params = {"id": cond.entity_id}
            tid = parent_fact.tenant_id or self.tools.tenant_id
            if tid:
                sql += " AND tenant_id = CAST(:tid AS uuid)"
                params["tid"] = tid
            row = self.tools._exec(sql, params).fetchone()
        except Exception as e:
            logger.warning(f"[identity_check] DB lookup failed for "
                           f"{cond.entity_id}: {e}")
            return self._terminal(synthetic_fact, "UNDERSUPPORTED",
                                  [f"identity_check DB error: {e}"], depth)
        if row is None:
            return self._terminal(synthetic_fact, "UNDERSUPPORTED",
                                  ["entity not found for identity_check"], depth)
        actual = (row[0] or "").strip().lower()
        expected = (cond.expected_name or "").strip().lower()
        if actual == expected:
            return self._terminal(
                synthetic_fact, "SUPPORTED",
                [f"entity name '{row[0]}' matches expected '{cond.expected_name}'"],
                depth)
        return self._terminal(
            synthetic_fact, "DISPROVEN",
            [f"identity mismatch: expected '{cond.expected_name}', "
             f"found '{row[0]}'"], depth)

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
