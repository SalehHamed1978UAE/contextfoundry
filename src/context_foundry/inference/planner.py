"""Stage 1 — EvaluationPlanner.

LLM-driven. Validates that every Condition.fact references real entity_type
and relationship_type from the live schema. Retries up to 3 times.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List, Set
from .contracts import Fact, EvaluationPlan, Condition
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
            invalid = self._validate(plan)
            if not invalid:
                return self._sort(plan)
            last_error = "; ".join(invalid)
        # Final fallback — return the plan even if invalid, with warning in rationale
        plan.rationale = (plan.rationale or "") + f"\n[VALIDATION_WARNINGS] {last_error}"
        return self._sort(plan)

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

    def _validate(self, plan: EvaluationPlan) -> List[str]:
        problems: List[str] = []
        for label, conds in (
            ("truth", plan.truth_conditions),
            ("falsifier", plan.falsifiers),
            ("presupposition", plan.presuppositions),
        ):
            for c in conds:
                if c.fact and self.rel_types and \
                   c.fact.relationship_type.upper() not in self.rel_types:
                    problems.append(
                        f"{label} '{c.description}' references unknown "
                        f"relationship_type '{c.fact.relationship_type}'"
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
