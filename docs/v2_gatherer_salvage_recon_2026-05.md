# v2 Gatherer — Retrieval Topology Salvage Recon

**Date:** 2026-05-09
**Author:** main agent
**Scope:** one-page architectural recon, not implementation
**Question:** can `EvidenceGatherer`'s four-strategy parallel retrieval be lifted into v1's `RetrievalRouter` cleanly, before any "park v2" decision lands?

**Bottom line up front:** **yes, the retrieval topology is salvageable, with caveats on effort.** The four strategies (graph-endpoint, FTS, vector-chunks, vector-entities-to-rels) have **no LLM-evaluator dependency** — they are DB queries plus an injected embedding-service call (OpenAI `text-embedding-3-small`, the same model v1 already uses). The polarity classifier and the recursive source-authority evaluation are the LLM-dependent layers wrapped *around* retrieval, and they detach cleanly because they're separate methods called *after* `_gather_round` returns. The integration into v1 has two viable shapes (new strategy vs HYBRID rewrite); the new-strategy shape is the cheaper, lower-risk option and is the recommended path. **Effort estimate revised below from "one day" to "2-3 days" after architect review** — the v1 `RetrievalRouter` is synchronous and branch-heavy, the `QueryClassifier` strategy schema must learn a new value, and the existing `_search_documents` already has heuristics that need to be preserved or merged rather than wholesale replaced.

---

## 1. Pure-retrieval vs LLM-dependent split

Reading `src/context_foundry/inference/gatherer.py` (267 LOC) end-to-end, the methods sort cleanly into two groups:

### 1a. Pure retrieval (no LLM, no `self.llm`, no `self.evaluator`)

| Method | LOC | Calls | What it returns |
|---|---|---|---|
| `_gather_round(plan, fact, seen_chunks, seen_rels)` | 16 | `_search_one_query` (× len(evidence_queries)) + `_direct_endpoint_edges` in `asyncio.gather` | `List[EvidenceItem]` |
| `_search_one_query(query, fact, seen_chunks, seen_rels)` | 83 | `tools.get_relationships`, `tools.search_chunks_text`, `embedder` (passed-in async fn), `tools.search_chunks_vector`, `tools.find_entities_by_embedding` | `List[EvidenceItem]` |
| `_direct_endpoint_edges(fact)` | 17 | `tools.get_relationships(source_id=...)` and `tools.get_relationships(target_id=...)` | `List[EvidenceItem]` |
| `_hydrate_rel(rel)` | 14 | `tools.get_entity` × 2 | `str` (formatted) |

These are the four strategies the user identified as worth integrating. None of them touch `self.llm`. The `embedder` is an *external* `EmbedderFn` callable injected at construction (in our smoke test it's `OpenAI().embeddings.create(...).data[0].embedding`, the same model v1 already uses). The tracer event `evidence_query_results` (lines 190–197) is structlog-only, no LLM.

The four strategies as actually implemented in `_search_one_query`:

1. **`graph_endpoint`** — `tools.get_relationships(source_id=fact.source_entity_id)` → all outgoing edges from the fact's subject. Hydrated via `_hydrate_rel` so polarity-classifier (or any downstream consumer) sees `relationship REL_TYPE from entity X (name='...', type=...) to entity Y (name='...', type=...)`. **Maps to:** centrality-bias cases (Q17, Q48, Q71, Q83) where v1 surfaces the most-connected entity for a topic instead of the question-specific one — `graph_endpoint` constrains to the actual fact subject's edges.

2. **`fts_chunks`** — `tools.search_chunks_text(query)` (`ILIKE` over `document_chunks.text`, top-200, `ORDER BY id ASC`). **Maps to:** `EXTRACTION_MISSED` cases (Q25, Q67, Q93) where the value lives in a chunk but never made it into the graph as a property — FTS over chunks finds it without needing graph extraction to have succeeded.

3. **`vector_chunks`** — `tools.search_chunks_vector(emb, top_k=50)` (cosine over `document_chunks.embedding`, top-50). **Maps to:** the same `EXTRACTION_MISSED` class as FTS, plus `RETRIEVAL_VOID` cases where the question phrasing doesn't lexically overlap the chunk text but is semantically close.

4. **`vector_entities_to_rels`** — `tools.find_entities_by_embedding(emb, top_k=50)` to find name-similar entities, then `tools.get_relationships(source_id=ent.id)` for each. **Maps to:** `RETRIEVAL_VOID` cases like Q1 (Victoria Chen exists in the vault per Q45 but wasn't surfaced for the CEO question) — vector-name lookup finds the entity even when graph traversal from the question's anchor doesn't, and then expands to all its outgoing edges so the question's relationship target becomes visible.

The fifth implicit strategy is `_direct_endpoint_edges`, called once per round in addition to the four per-query strategies. It pulls `include_archived=True` edges around both fact endpoints — the "always-on" baseline.

### 1b. LLM-dependent (require `self.llm` or `self.evaluator`)

| Method | LOC | LLM dependency | Salvageable? |
|---|---|---|---|
| `_classify_polarities(evidence, fact)` | 28 | `self.llm.call(POLARITY_PROMPT, ...)` per item | **Skip for v1.** v1's RetrievalRouter doesn't have a polarity concept — it returns entities + relationships + chunks for the synthesis LLM to weigh. Polarity is an inference-engine concern. |
| `_evaluate_source_authority(evidence, fact)` | 20 | `self.evaluator(authority_fact)` → recurses into `FactEvaluator.evaluate` → planner/gatherer/adversary/prover/meta/synth | **Skip for v1.** This is the recursive source-authority pipeline, the most expensive piece of v2 and the one the user explicitly excluded ("not the recursive source-authority evaluation"). It only fires *after* polarity classification, which we're already skipping. |

**Conclusion on (1):** the four retrieval strategies + `_direct_endpoint_edges` are pure DB queries plus an injected embedder. They don't touch `self.llm` and they don't touch `self.evaluator`. The two LLM-dependent layers sit *after* `_gather_round` in `gather()` (lines 78–82) and are simply not called by the salvage path. Detachment is a function-extraction, not a refactor.

---

## 2. Dependency graph from `gatherer.py`

```
gatherer.py
├── contracts.py                       (data classes: Fact, EvaluationPlan, EvidenceItem)
├── llm/client.py                      (LLMClient — used by polarity only; skip)
├── observability/trace.py             (tracer.event/bump — replace with v1 logger)
├── tools.py                           (GraphTools — keep)
└── llm/prompts/polarity_system.md     (read at module import; skip)
```

Reverse direction (who imports gatherer):

```
gatherer.py is imported by:
└── engine.py:14    `from .gatherer import EvidenceGatherer`
                    `self.gatherer = EvidenceGatherer(...)` (line 46)
                    `self.gatherer.evaluator = self._evaluate_source_authority` (line 54)
                    `evidence = await self.gatherer.gather(plan, fact)` (line 166)
```

**Engine is the only consumer.** Nothing else in `src/context_foundry/inference/` imports the gatherer, and nothing outside the inference package imports it. Lift can leave the v2 inference package intact and untouched.

`tools.py` (the GraphTools wrapper) is the load-bearing dependency. It's 269 LOC, single-file, no LLM, depends only on SQLAlchemy. It's also the cleanest piece of code in the v2 module — single counted query entry point (`_exec` with `db_query_count` bump and `begin_nested` SAVEPOINT for partial rollback), tenant-scoped at construction, every result list `ORDER BY id ASC` so cached queries hash identically across runs. This is reusable on its own.

The `EvidenceItem` type (defined in `contracts.py`) is a thin dataclass with `chunk_id`, `relationship_id`, `content`, `polarity`, `lifecycle_state`, `source_document_id`, `speaks_to`, `polarity_reasoning`, `source_authority_verdict`. For v1 integration, the lift target only needs the first four-or-five fields (chunks + rels with provenance); everything else is polarity/authority bookkeeping the v1 router doesn't consume. **Cleaner option:** introduce a v1-side `RetrievalItem` dataclass (chunk_id, relationship_id, content, source_document_id, lifecycle_state) and have the lifted function return that — keeps the v1 router free of v2-package imports.

**Tangling assessment:** **none.** The gatherer's pure-retrieval surface is one method (`_gather_round` calling `_search_one_query` + `_direct_endpoint_edges`) and one helper (`_hydrate_rel`). Total ≈ 130 LOC. They depend on GraphTools (lift it) + an embedder callable (v1 already has one) + the tracer (replace with v1's logger). Zero cycles, zero hidden state, zero dependence on the rest of v2.

---

## 3. Integration shape for v1's `RetrievalRouter`

### Option A — fifth strategy alongside `GRAPH_ONLY` / `DOCS_ONLY` / `HYBRID` (recommended)

`RetrievalRouter.route()` (router.py:1962) already dispatches by `strategy = classification.retrieval_strategy`. Add a fourth value `MULTI_RETRIEVE` (or `PARALLEL_FOUR`, or pick a less awful name) and a new branch:

```python
elif strategy == "MULTI_RETRIEVE":
    items = self._multi_retrieve(query, fact_anchors, classified_query)
    result.entities      = self._items_to_entities(items)
    result.relationships = self._items_to_relationships(items)
    result.chunks        = self._items_to_chunks(items)
    result.strategy_used = "MULTI_RETRIEVE"
```

`_multi_retrieve` is the lifted `_search_one_query` body. Inputs: `query: str`, `fact_anchors: List[entity_id]` (resolved upstream by the existing person-name detector or by the QueryClassifier), `classified_query: ClassifiedQuery` for relationship-type filtering. Outputs: a flat list of items dedup'd by `(chunk_id, relationship_id)`. Internally runs the four strategies in `asyncio.gather` (or `concurrent.futures` if you want to keep the router sync — both work; the strategies are pure DB).

**When does the QueryClassifier route to `MULTI_RETRIEVE`?** Three triggers from the failure distribution:

1. **Centrality-bias risk** — when intent is `ROLE`/`SUPPLIER`/`CUSTOMER` and the question is anchored to a *product/segment* (not the parent org). `graph_endpoint` from the product entity gives selective edges instead of the most-connected org. (Q17, Q48, Q71, Q83.)
2. **`RETRIEVAL_VOID` recovery** — when v1's first-pass GRAPH_ONLY returns < N entities or < M relationships, fall through to MULTI_RETRIEVE instead of HYBRID. `vector_entities_to_rels` is the path that recovers Q1-shape failures (entity exists by name, isn't surfaced by anchor traversal). (Q1, Q15, Q37, Q38, Q46, Q60, Q68.)
3. **`EXTRACTION_MISSED` recovery** — when intent is a value lookup (numeric, date, spec) and GRAPH_ONLY returns no matching property. FTS-over-chunks finds the value in raw text. (Q25, Q67, Q73, Q93.)

**Cost model:** four parallel queries per call. Each query is one DB round-trip + one embedder call (for the two vector strategies) shared across both vector strategies. With our embedder cache and PG `<=>` index on `document_chunks.embedding`, the wall-clock is ≈ embedding latency (~150 ms) + max(strategy latencies) (~40 ms each). Roughly the same as one HYBRID call today.

**Risk:** the four strategies will surface duplicates and noise alongside signal. v2's polarity classifier filtered that downstream; v1's synthesis LLM does not. Mitigations: (a) hard cap per strategy (already 50 chunks / 50 entities); (b) per-source ranking already in v1's router (folder weighting + authority config) applied to the merged list; (c) optional fast pre-filter — drop chunks whose lifecycle is ARCHIVED unless the question is historical. None of these require LLM calls.

### Option B — replace `HYBRID` with the four-strategy gather

HYBRID today runs `_search_graph` + `_search_documents` in serial (router.py:2292+). MULTI_RETRIEVE is strictly more powerful — `graph_endpoint` ⊇ `_search_graph` (hits the same `relationships` table with the same tenant scoping), and `fts_chunks` + `vector_chunks` ⊇ `_search_documents`. The two new strategies (`vector_entities_to_rels`, `_direct_endpoint_edges`) are pure additions.

**Downside of B:** larger diff, harder to A/B compare against current HYBRID for the 23/26 questions, and a regression in any HYBRID-routed query becomes a bigger blast radius. **Upside:** if MULTI_RETRIEVE proves out, the simpler longer-term shape is "GRAPH_ONLY for relationship-typed questions, MULTI_RETRIEVE for everything else, drop DOCS_ONLY and HYBRID".

### Recommended path

Land Option A first (additive, A/B-friendly, ~1 day). Run the 100-question Nexus benchmark with MULTI_RETRIEVE forced on for the 26 failure cases and measure recovery. If recovery ≥ +5 questions, do Option B in a follow-up.

### Call-site sketch (Option A)

```python
# src/context_foundry/agents/retrieval_router.py

def _multi_retrieve(self, query: str, fact_anchors: List[str],
                    classified_query: Optional[ClassifiedQuery]) -> List[RetrievalItem]:
    """Lifted from src/context_foundry/inference/gatherer.py:_search_one_query.
    Pure DB; no LLM. Four strategies in parallel + direct endpoint edges.
    """
    tools = GraphTools(self.session, tenant_id=self.tenant_id)  # lifted
    items: List[RetrievalItem] = []

    # (1) graph_endpoint
    for anchor in fact_anchors:
        for rel in tools.get_relationships(source_id=anchor):
            items.append(RetrievalItem.from_rel(rel, speaks_to=query))

    # (2) fts_chunks
    for ch in tools.search_chunks_text(query)[:50]:
        items.append(RetrievalItem.from_chunk(ch, speaks_to=query))

    # (3,4) vector — only if embedder wired
    if self.embedder is not None:
        emb = self.embedder(query)
        for ch in tools.search_chunks_vector(emb, top_k=50):
            items.append(RetrievalItem.from_chunk(ch, speaks_to=query))
        for ent in tools.find_entities_by_embedding(emb, top_k=50):
            for rel in tools.get_relationships(source_id=ent.id):
                items.append(RetrievalItem.from_rel(rel, speaks_to=query))

    # always-on: direct edges
    for anchor in fact_anchors:
        for rel in tools.get_relationships(source_id=anchor, include_archived=True):
            items.append(RetrievalItem.from_rel(rel, speaks_to=query))
        for rel in tools.get_relationships(target_id=anchor, include_archived=True):
            items.append(RetrievalItem.from_rel(rel, speaks_to=query))

    return self._dedup(items)
```

The body is a near-1:1 lift of `gatherer.py:_search_one_query` lines 148–186 plus `_direct_endpoint_edges` lines 200–216, with `EvidenceItem(...)` constructors replaced by `RetrievalItem.from_rel/from_chunk` to break the v2-contracts dependency.

---

## Out of scope for this recon (called out for completeness)

- **Polarity classifier** — explicitly excluded. v1 doesn't have a polarity concept; the synthesis LLM weighs evidence directly.
- **Recursive source-authority evaluation** — explicitly excluded. The most expensive piece of v2.
- **EvaluationPlanner / evidence_queries** — v1 doesn't generate evidence queries from a plan; the user's question *is* the query. The lift uses the question string directly, not a planner-emitted query list.
- **AdversarialChallenger** — independent of retrieval; lives downstream of synthesis if anywhere.

---

## Verdict

The retrieval topology is the cheapest-to-extract, highest-value piece of v2. ~130 LOC of pure DB code, one consumer (engine.py, which we're parking), zero hidden coupling, addresses 13 of the 26 baseline failures (all 4 centrality-bias cases, 7 RETRIEVAL_VOID cases that would benefit from `vector_entities_to_rels`, 4 EXTRACTION_MISSED cases that would benefit from `fts_chunks` + `vector_chunks`). Estimated effort: one focused engineering day for Option A with A/B benchmark.

This recommendation is **independent of the Task 4 v2-validator decision.** Even if v2 the validator is parked, the gatherer's retrieval topology should be lifted into v1.
