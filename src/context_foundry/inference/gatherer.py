"""Stage 2 — EvidenceGatherer.

For each evidence_query in the plan, runs four search strategies in parallel:
  (1) graph traversal around fact endpoints
  (2) vector similarity over chunks
  (3) vector similarity over entity names (then expand to their relationships)
  (4) full-text search over chunks

Polarity is classified per item via the LLM. Source-authority recursion is
exposed as a hook (`evaluator`) so it can be wired in by the engine without a
circular import.

Termination: two consecutive search rounds produce no new chunk_ids.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List, Optional, Callable, Awaitable, Set
from pydantic import BaseModel
from .contracts import Fact, EvaluationPlan, EvidenceItem
from .llm.client import LLMClient
from .tools import GraphTools

logger = logging.getLogger(__name__)
POLARITY_PROMPT = (Path(__file__).parent / "llm" / "prompts" / "polarity_system.md").read_text()


class _PolarityResp(BaseModel):
    polarity: str
    reasoning: str = ""


EmbedderFn = Callable[[str], Awaitable[List[float]]]
EvaluatorFn = Callable[[Fact], Awaitable["object"]]  # returns Verdict


class EvidenceGatherer:
    def __init__(self, llm: LLMClient, tools: GraphTools,
                 embedder: Optional[EmbedderFn] = None,
                 evaluator: Optional[EvaluatorFn] = None,
                 max_rounds: int = 3):
        self.llm = llm
        self.tools = tools
        self.embedder = embedder
        self.evaluator = evaluator  # set by FactEvaluator after construction
        self.max_rounds = max_rounds

    async def gather(self, plan: EvaluationPlan, fact: Fact) -> List[EvidenceItem]:
        seen_chunks: Set[str] = set()
        seen_rels: Set[str] = set()
        evidence: List[EvidenceItem] = []
        rounds_without_new = 0
        for round_idx in range(self.max_rounds):
            round_items = await self._gather_round(plan, fact, seen_chunks, seen_rels)
            new_count = sum(1 for it in round_items
                            if (it.chunk_id and it.chunk_id not in seen_chunks)
                            or (it.relationship_id and it.relationship_id not in seen_rels))
            for it in round_items:
                if it.chunk_id:
                    if it.chunk_id in seen_chunks:
                        continue
                    seen_chunks.add(it.chunk_id)
                elif it.relationship_id:
                    if it.relationship_id in seen_rels:
                        continue
                    seen_rels.add(it.relationship_id)
                evidence.append(it)
            if new_count == 0:
                rounds_without_new += 1
                if rounds_without_new >= 2:
                    break
            else:
                rounds_without_new = 0
        # Polarity classification (parallel)
        await self._classify_polarities(evidence, fact)
        # Recursive source-authority (parallel) — only if engine wired the hook
        if self.evaluator is not None:
            await self._evaluate_source_authority(evidence, fact)
        return evidence

    # ------------------------------------------------ per-round retrieval
    async def _gather_round(self, plan: EvaluationPlan, fact: Fact,
                            seen_chunks: Set[str], seen_rels: Set[str]) -> List[EvidenceItem]:
        tasks = []
        for q in plan.evidence_queries:
            tasks.append(self._search_one_query(q, fact))
        # Always also pull direct edges around the fact endpoints
        tasks.append(self._direct_endpoint_edges(fact))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        items: List[EvidenceItem] = []
        for r in results:
            if isinstance(r, Exception):
                logger.warning(f"[Gatherer] sub-search failed: {r}")
                continue
            items.extend(r)
        return items

    async def _search_one_query(self, query: str, fact: Fact) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        # (1) graph: search relationships whose source/target match fact endpoints
        for rel in self.tools.get_relationships(source_id=fact.source_entity_id):
            items.append(EvidenceItem(
                relationship_id=rel.id, chunk_id=rel.source_chunk_id,
                content=f"({rel.source_entity_id})-[{rel.relationship_type}]->({rel.target_entity_id})",
                speaks_to=query, polarity="neutral",
                lifecycle_state=rel.lifecycle_state,
            ))
        # (4) FTS over chunks
        for ch in self.tools.search_chunks_text(query)[:50]:
            items.append(EvidenceItem(
                chunk_id=ch.id, source_document_id=ch.document_id,
                content=ch.text, speaks_to=query, polarity="neutral",
            ))
        # (2,3) vector similarity — only if embedder is wired
        if self.embedder is not None:
            try:
                emb = await self.embedder(query)
                for ch in self.tools.search_chunks_vector(emb, top_k=50):
                    items.append(EvidenceItem(
                        chunk_id=ch.id, source_document_id=ch.document_id,
                        content=ch.text, speaks_to=query, polarity="neutral",
                    ))
                for ent in self.tools.find_entities_by_embedding(emb, top_k=50):
                    for rel in self.tools.get_relationships(source_id=ent.id):
                        items.append(EvidenceItem(
                            relationship_id=rel.id, chunk_id=rel.source_chunk_id,
                            content=f"({ent.name})-[{rel.relationship_type}]->({rel.target_entity_id})",
                            speaks_to=query, polarity="neutral",
                            lifecycle_state=rel.lifecycle_state,
                        ))
            except Exception as e:
                logger.warning(f"[Gatherer] embedder/vector search failed: {e}")
        return items

    async def _direct_endpoint_edges(self, fact: Fact) -> List[EvidenceItem]:
        items: List[EvidenceItem] = []
        for rel in self.tools.get_relationships(source_id=fact.source_entity_id, include_archived=True):
            items.append(EvidenceItem(
                relationship_id=rel.id, chunk_id=rel.source_chunk_id,
                content=f"({rel.source_entity_id})-[{rel.relationship_type}]->({rel.target_entity_id})"
                        + (f" [ARCHIVED]" if rel.lifecycle_state == "ARCHIVED" else ""),
                speaks_to="direct edges from fact source", polarity="neutral",
                lifecycle_state=rel.lifecycle_state,
            ))
        for rel in self.tools.get_relationships(target_id=fact.target_entity_id, include_archived=True):
            items.append(EvidenceItem(
                relationship_id=rel.id, chunk_id=rel.source_chunk_id,
                content=f"({rel.source_entity_id})-[{rel.relationship_type}]->({rel.target_entity_id})"
                        + (f" [ARCHIVED]" if rel.lifecycle_state == "ARCHIVED" else ""),
                speaks_to="direct edges into fact target", polarity="neutral",
                lifecycle_state=rel.lifecycle_state,
            ))
        return items

    # ------------------------------------------------ polarity & authority
    async def _classify_polarities(self, evidence: List[EvidenceItem], fact: Fact):
        nl = fact.natural_language or (
            f"({fact.source_entity_id})-[{fact.relationship_type}]->({fact.target_entity_id})"
        )
        async def one(it: EvidenceItem):
            try:
                resp: _PolarityResp = await self.llm.call(
                    system_prompt=POLARITY_PROMPT,
                    user_prompt=f"FACT: {nl}\n\nEVIDENCE: {it.content[:1000]}",
                    output_schema=_PolarityResp,
                )
                if resp.polarity in ("confirms", "disconfirms", "neutral"):
                    it.polarity = resp.polarity  # type: ignore
            except Exception as e:
                logger.debug(f"polarity failed: {e}")
        await asyncio.gather(*[one(it) for it in evidence])

    async def _evaluate_source_authority(self, evidence: List[EvidenceItem], fact: Fact):
        """Recursively evaluate (chunk, IS_AUTHORITATIVE_FOR, fact_type)."""
        if self.evaluator is None:
            return
        async def one(it: EvidenceItem):
            if not it.chunk_id:
                return
            authority_fact = Fact(
                source_entity_id=it.chunk_id,
                relationship_type="IS_AUTHORITATIVE_FOR",
                target_entity_id=fact.relationship_type,
                tenant_id=fact.tenant_id,
                natural_language=f"chunk {it.chunk_id} is authoritative for facts of type {fact.relationship_type}",
            )
            try:
                v = await self.evaluator(authority_fact)
                it.source_authority_verdict = v
            except Exception as e:
                logger.debug(f"authority recursion failed for chunk {it.chunk_id}: {e}")
        await asyncio.gather(*[one(it) for it in evidence])
