"""Stage 1 — EvaluationPlanner.

LLM-driven. Validates that every Condition.fact references real entity_type
and relationship_type from the live schema. Retries up to 3 times.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, List, Set
from .contracts import Fact, EvaluationPlan, Condition

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)


class PlanValidationError(Exception):
    """Raised when the planner cannot produce a valid plan after max_retries.

    The engine catches this and emits a terminal UNDERSPECIFIED verdict
    rather than executing a plan with malformed/ungrounded conditions.
    """
    def __init__(self, message: str, last_plan: "EvaluationPlan"):
        super().__init__(message)
        self.message = message
        self.last_plan = last_plan


from .llm.client import LLMClient

PROMPT_PATH = Path(__file__).parent / "llm" / "prompts" / "planner_system.md"


class EvaluationPlanner:
    def __init__(self, llm: LLMClient, schema_entity_types: Iterable[str],
                 schema_relationship_types: Iterable[str], max_retries: int = 3):
        self.llm = llm
        self.entity_types: Set[str] = {t.upper() for t in schema_entity_types}
        self.rel_types: Set[str] = {t.upper() for t in schema_relationship_types}
        self.max_retries = max_retries
        self._system_prompt = PROMPT_PATH.read_text()

    async def plan(self, fact: Fact, schema_context: str = "") -> EvaluationPlan:
        user_prompt = self._build_user_prompt(fact, schema_context)
        last_error: str = ""
        for attempt in range(self.max_retries):
            extra = f"\n\n---\nPRIOR ATTEMPT INVALID: {last_error}" if attempt else ""
            plan: EvaluationPlan = await self.llm.call(
                system_prompt=self._system_prompt,
                user_prompt=user_prompt + extra,
                output_schema=EvaluationPlan,
            )
            invalid = self._validate(plan, fact=fact)
            if not invalid:
                return self._sort(plan)
            last_error = "; ".join(invalid)
        # Fail-closed: do NOT execute an invalid plan downstream. Engine
        # catches PlanValidationError and emits a terminal UNDERSPECIFIED
        # verdict with the validator messages in rationale.
        raise PlanValidationError(last_error, plan)

    # ------------------------------------------------------------ helpers
    def _build_user_prompt(self, fact: Fact, schema_context: str) -> str:
        nl = fact.natural_language or (
            f"({fact.source_entity_id}) -[{fact.relationship_type}]-> "
            f"({fact.target_entity_id}) properties={fact.properties}"
        )
        return (
            f"FACT UNDER EVALUATION:\n{nl}\n\n"
            f"Structured form:\n  source_entity_id: {fact.source_entity_id}\n"
            f"  relationship_type: {fact.relationship_type}\n"
            f"  target_entity_id: {fact.target_entity_id}\n"
            f"  properties: {fact.properties}\n\n"
            f"GRAPH SCHEMA:\n"
            f"  entity_types ({len(self.entity_types)}): "
            f"{sorted(self.entity_types)[:80]}{'...' if len(self.entity_types) > 80 else ''}\n"
            f"  relationship_types ({len(self.rel_types)}): "
            f"{sorted(self.rel_types)[:80]}{'...' if len(self.rel_types) > 80 else ''}\n\n"
            f"{schema_context}\n\n"
            "Produce an EvaluationPlan via the emit_evaluationplan tool."
        )

    def _validate(self, plan: EvaluationPlan,
                  fact: "Fact | None" = None) -> List[str]:
        problems: List[str] = []
        # Grounding set: entity_ids the planner is allowed to reference.
        # The fact's endpoints are always allowed; everything else must be a
        # syntactically valid UUID AND (when fact is provided) appear in this
        # set. This blocks UUID-shaped hallucinations the regex alone misses.
        grounded: Set[str] = set()
        if fact is not None:
            if fact.source_entity_id:
                grounded.add(fact.source_entity_id)
            if fact.target_entity_id:
                grounded.add(fact.target_entity_id)
        for label, conds in (
            ("truth", plan.truth_conditions),
            ("falsifier", plan.falsifiers),
            ("presupposition", plan.presuppositions),
        ):
            for c in conds:
                # type_check: must have entity_id + expected_entity_type, no fact
                if c.kind == "type_check":
                    if not c.entity_id or not c.expected_entity_type:
                        problems.append(
                            f"{label} '{c.description}' is kind=type_check but "
                            f"missing entity_id or expected_entity_type"
                        )
                    elif not _UUID_RE.match(c.entity_id):
                        problems.append(
                            f"{label} '{c.description}' type_check entity_id "
                            f"'{c.entity_id}' is not a valid UUID; you must "
                            f"reference a real entity_id from the FACT, not "
                            f"invent placeholders like <NAME_ID>"
                        )
                    elif grounded and c.entity_id not in grounded:
                        problems.append(
                            f"{label} '{c.description}' type_check entity_id "
                            f"'{c.entity_id}' is not one of the FACT "
                            f"endpoints {sorted(grounded)}; only entity_ids "
                            f"that appear in the FACT may be referenced"
                        )
                    elif self.entity_types and \
                            c.expected_entity_type.upper() not in self.entity_types:
                        problems.append(
                            f"{label} '{c.description}' type_check expects "
                            f"'{c.expected_entity_type}' which is not in the "
                            f"schema entity_types"
                        )
                    if c.fact is not None:
                        problems.append(
                            f"{label} '{c.description}' is kind=type_check; "
                            f"must NOT carry a fact (use kind=graph_fact for "
                            f"binary edges)"
                        )
                    continue
                # identity_check: must have entity_id (UUID, grounded) +
                # non-empty expected_name. Must NOT carry a fact.
                if c.kind == "identity_check":
                    if not c.entity_id or not c.expected_name \
                            or not c.expected_name.strip():
                        problems.append(
                            f"{label} '{c.description}' is kind=identity_check "
                            f"but missing entity_id or non-empty expected_name"
                        )
                    elif not _UUID_RE.match(c.entity_id):
                        problems.append(
                            f"{label} '{c.description}' identity_check "
                            f"entity_id '{c.entity_id}' is not a valid UUID; "
                            f"you must reference a real entity_id from the "
                            f"FACT, not invent placeholders"
                        )
                    elif grounded and c.entity_id not in grounded:
                        problems.append(
                            f"{label} '{c.description}' identity_check "
                            f"entity_id '{c.entity_id}' is not one of the "
                            f"FACT endpoints {sorted(grounded)}; only "
                            f"entity_ids that appear in the FACT may be "
                            f"referenced"
                        )
                    if c.fact is not None:
                        problems.append(
                            f"{label} '{c.description}' is kind=identity_check; "
                            f"must NOT carry a fact"
                        )
                    continue
                # custom: informational only, no validation beyond description
                if c.kind == "custom":
                    if c.fact is not None:
                        problems.append(
                            f"{label} '{c.description}' is kind=custom; must "
                            f"NOT carry a fact"
                        )
                    continue
                # graph_fact (default): must have a Fact, with valid rel_type,
                # and reject degenerate self-loops which the engine cannot
                # recursively prove (they trigger cycle detection).
                if c.fact is None:
                    problems.append(
                        f"{label} '{c.description}' is kind=graph_fact but "
                        f"has no fact"
                    )
                    continue
                if self.rel_types and \
                        c.fact.relationship_type.upper() not in self.rel_types:
                    problems.append(
                        f"{label} '{c.description}' references unknown "
                        f"relationship_type '{c.fact.relationship_type}'"
                    )
                for end_label, end_id in (
                    ("source_entity_id", c.fact.source_entity_id),
                    ("target_entity_id", c.fact.target_entity_id),
                ):
                    if end_id and not _UUID_RE.match(end_id):
                        problems.append(
                            f"{label} '{c.description}' graph_fact "
                            f"{end_label} '{end_id}' is not a valid UUID; "
                            f"you must reference real entity_ids from the "
                            f"FACT or its neighborhood, not invent "
                            f"placeholders like <NAME_ID>"
                        )
                    elif end_id and grounded and end_id not in grounded:
                        problems.append(
                            f"{label} '{c.description}' graph_fact "
                            f"{end_label} '{end_id}' is not one of the FACT "
                            f"endpoints {sorted(grounded)}; only entity_ids "
                            f"that appear in the FACT may be referenced"
                        )
                if c.fact.source_entity_id and c.fact.target_entity_id and \
                        c.fact.source_entity_id == c.fact.target_entity_id:
                    problems.append(
                        f"{label} '{c.description}' is a degenerate self-loop "
                        f"({c.fact.source_entity_id} -[{c.fact.relationship_type}]-> "
                        f"itself); use kind=type_check for entity-typing "
                        f"presuppositions instead"
                    )
        # Post-plan normalizer: enforce identity_check coverage for both fact
        # endpoints. Architect's recommendation #2 — currently the planner is
        # the sole guarantor that identity_check presuppositions exist. One
        # off-prompt LLM response would silently regress the polarity
        # classifier to UUID-binding failure mode (prior 4/4 DISPROVEN bench).
        # Reject and force replan on missing endpoint identity_checks.
        if fact is not None:
            covered_ids = {
                c.entity_id for c in plan.presuppositions
                if c.kind == "identity_check"
                and c.entity_id
                and c.expected_name and c.expected_name.strip()
                and c.fact is None
            }
            for end_label, end_id in (
                ("source_entity_id", fact.source_entity_id),
                ("target_entity_id", fact.target_entity_id),
            ):
                if end_id and end_id not in covered_ids:
                    problems.append(
                        f"presupposition coverage: missing required "
                        f"identity_check for fact {end_label} '{end_id}'. "
                        f"Every fact endpoint MUST have an identity_check "
                        f"presupposition (kind=identity_check, "
                        f"entity_id={end_id}, expected_name=<the name you "
                        f"believe this entity has>). Without it the polarity "
                        f"classifier cannot bind evidence to the fact."
                    )
        return problems

    @staticmethod
    def _sort(plan: EvaluationPlan) -> EvaluationPlan:
        plan.truth_conditions.sort(key=lambda c: c.description)
        plan.falsifiers.sort(key=lambda c: c.description)
        plan.presuppositions.sort(key=lambda c: c.description)
        plan.competing_hypotheses.sort(key=lambda h: h.description)
        plan.evidence_queries.sort()
        plan.adversarial_prompts.sort()
        return plan
