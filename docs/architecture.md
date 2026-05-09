# Context Foundry — Architecture (Canonical)

> **Status:** Canonical target architecture document. Locked May 2026.
> **Supersedes:** `docs/archive/architecture_intent_2025-12.md`, `docs/archive/architecture_summary_intent.md`.
> **Companion:** `docs/decisions.md` (ADRs).
>
> Sections 1–8 describe the **target** architecture. Section 9 preserves the May 2026 current-state audit verbatim as a snapshot. Sections 10 and below are governance: authority rule, alignment block protocol, implementation gate, and recorded implementation gaps.

---

## 1. What Context Foundry Is

> Context Foundry is a system that turns enterprise documents into a governed, domain-aware world model that AI agents query through a refuse-or-answer-with-evidence contract. The product surface is the **ContextBundle**. The graph is an internal substrate, not the product.

---

## 2. The Target Pipeline

```
Document arrives
        ↓
Classifier: assigns primary_domain, secondary_domains, document_type, confidence, evidence
        ↓
Extractor: domain-scoped ontology + document-type hints → entities, relationships, values, evidence spans
        ↓
STAGING (facts tagged with domain, document_type, source, evidence span)
        ↓
Verification: LLM checks fact against evidence
        ↓
Gardener: validates against domain-scoped ontology, checks corroboration, promotes
        ↓
TRUSTED (governed world model)
        ↓
Query arrives
        ↓
Query Interpreter → Retrieval Router → Data Gates
        ↓
├─ refuse → Gap Detector emits typed gap
└─ pass → LLM synthesis → QA Verifier
        ↓
ContextBundle (answer or refusal + entities + facts + provenance + confidence + gates fired + gaps + reasoning trace)
```

---

## 3. Domain Model

Eight canonical domains:

- `core` — shared/foundation ontology, cross-domain types
- `it_infrastructure`
- `healthcare`
- `finance`
- `aviation`
- `supply_chain`
- `manufacturing`
- `construction`

`core` is shared/foundation scope, **not** an "unknown" bucket.

Document type is separate from domain. Documents have:

- `primary_domain`
- `secondary_domains` (list)
- `document_type`
- `classification_confidence`
- `classification_evidence`

`domain` controls **ontology scope** (which entity types and relationships are allowed). `document_type` controls **extraction hints and source authority** (board minutes are authoritative for executive appointments; policies are authoritative for ownership; etc.).

---

## 4. Governance Model

Facts enter STAGING.

Gardener promotes to TRUSTED based on:

- confidence threshold (type-specific)
- corroboration count
- time in staging
- domain coherence (fact's type belongs to document's primary domain, an allowed secondary domain, or `core`)
- verification status

Cross-domain facts are not auto-rejected. Facts whose type sits outside the document's allowed domain scope are held in STAGING and surface as `GAP_DOMAIN_MISMATCH` for review.

Schema changes go through the Ontology Foundry lifecycle:

```
PROPOSED → APPROVED → ACTIVE
```

Direct writes to `ontology.types` and `ontology.relations` outside this lifecycle are not part of the target design.

---

## 5. Query Model

Query Interpreter classifies question shape (triple lookup, attribute, scalar, list, date, range, ownership, aggregation).

Retrieval Router dispatches to the appropriate handler.

Data Gates refuse before LLM call when entity not found, no relevant chunks, or unverified evidence.

On refusal, Gap Detector emits a typed gap to the GapQueue.

On pass, LLM synthesis produces a grounded answer; QA Verifier validates structural and semantic consistency before return.

---

## 6. ContextBundle Contract

Every query response is a ContextBundle containing:

- `answer` (text) **or** `refusal` (typed)
- `entities` (list, with provenance per entity)
- `facts` (list, with provenance and confidence per fact)
- `provenance` (document IDs, chunk IDs, evidence spans)
- `confidence` (overall, per-fact, per-entity)
- `gates_fired` (list of Data Gate evaluations)
- `gaps` (list of typed GapRecords emitted during this query)
- `reasoning_trace` (the path the system took)

ContextBundle is the agent-facing contract. Downstream consumers (agents, MCP clients, internal callers) depend on this shape.

---

## 7. Implementation Sequence

The work to bring the running system in line with the target design is sequenced as the following Pieces. **No Piece begins without the implementation gate (below) being satisfied.**

- **Piece 0:** Domain registry canonicalization (backfill `ontology.types.domain_id`, `ontology.relations.domain_id`; add `core` to classifier; rename orphan YAMLs to `_legacy.yaml`)
- **Piece 1:** Document classification in production extraction (classifier wired before `MultiModelExtractor`; metadata persisted on `platform.documents`)
- **Piece 2:** Domain-aware extraction (`SchemaPromptGenerator` filters by `domain_id`; `MultiModelExtractor` uses domain-scoped prompt; consensus pattern preserved)
- **Piece 3:** Domain-coherent Gardener (promotion validates against domain scope; full 5-pass cycle confirmed running)
- **Piece 4:** Governance gap types (`GAP_DOMAIN_MISMATCH`, `GAP_ONTOLOGY_TYPE_INVALID`, `GAP_ONTOLOGY_RELATION_INVALID`, `GAP_DOCUMENT_TYPE_AUTHORITY_MISMATCH`, `GAP_EXTRACTION_SCOPE_MISSING`)
- **Piece 5:** GapQueue wired into production query pipeline (currently wired to orphan v2 engine; rewire to Data Gate refusal paths)
- **Piece 6:** ContextBundle response contract (query pipeline returns the structured bundle)
- **Piece 7:** Ontology Foundry wired to schema changes (route `_update_reference_ontology` writes through TypeValidator → CollisionDetector → ApprovalManager)
- **Piece 8:** Nexus 100 re-run against the wired-in system; classify remaining failures via the gap taxonomy

---

## 8. Parked and Salvage Modules

- `inference/engine.py` (v2 FactEvaluator) and the planner/gatherer/prover/adversary/meta/synthesizer chain — **parked**. Planner and presupposition outputs are reused as gap signals (D8.1, already shipped). Salvage gatherer strategies if needed for retrieval improvements.
- `validation/coherence_checker.py` — **salvage audit pending**. Decide whether to wire into QAVerifier or archive.
- `agents/graph_builder`, `agents/graph_loader`, `agents/semantic_agent`, `agents/tool_agent`, `agents/directed_retriever` — **salvage audit pending**. Each module gets a one-page disposition (keep and wire, salvage parts, archive, delete).
- Orphan YAMLs (`config/domain_schema.yaml`, `config/fiction_schema.yaml`, `config/investment_schema.yaml`, `config/examples/investment_portfolio.yaml`) — **legacy candidates**, renamed during Piece 0, not deleted until salvage audit completes.

---

## 9. Current State at Design Lock

> The block diagram, module table, and behaviors table below are the **May 2026 read-only audit** of the running system at the moment this target design was locked. Preserved verbatim so the reader can compare target (Sections 1–8) against current state and see the gap. Do not edit this section to track ongoing changes — create a new dated audit instead.

### 9.1 System Summary (current state, May 2026)

Context Foundry ingests enterprise documents into a single Postgres+pgvector store, extracts entities and relationships from each document with an LLM-based extractor (default: dual-pass GPT-4o-mini + Claude Sonnet 4 with consensus reconciliation; alternative under `--use-ontology`: a document-type-classified ontology-constrained pipeline), writes results to a `STAGING` lifecycle state, runs a `VerificationWorker` and a `GardenerAgent.promotion_pass` (which checks confidence/corroboration thresholds and validates types against a flat union of all ontology types), and answers queries via a 4-step `QueryPipeline` (interpret → retrieve via `RetrievalRouter` → LLM synthesize → `QAVerifier`) with `DataGates` short-circuiting before the LLM when an entity is not found, evidence is unverified, or chunks are absent.

### 9.2 Block Diagram (current state, May 2026)

#### 9.2a Default extraction → query path (production)

```
scripts/run_vault_extraction.py  (no flags)
        │
        ▼
get_documents_for_extraction(skip_multi=True)
        │
        ▼
PHASE 1 — run_extraction_from_db
        │  per doc:
        ▼
MultiModelExtractor ── gpt-4o-mini ──┐    (hardcoded EXTRACTION_SYSTEM_PROMPT
                  └── claude-sonnet ─┤     14 entity types, 16 relation types;
                                     │     NO classifier, NO domain signal)
                                     ▼
                              JSON files on disk
                                     │
                                     ▼
PHASE 2-4 — run_consensus_and_ingest
   run_consensus → validate_consensus → resolve_conflicts → KGIngestor.ingest
                                     │
                                     ▼
                       entities + relationships @ STAGING
                                     │
                                     ▼
PHASE 5 — VerificationWorker.run() ──► fact_verifications, sets verified=true on a fraction
                                     │
                                     ▼
PHASE 6 — GardenerAgent.promotion_pass
   confidence/corroboration check + validate_against_ontology (flat 1016-type union)
   require_verification_for_promotion=True (set by script; Gardener default is False)
                                     │
                                     ▼
                       entities + relationships @ TRUSTED
                                     │
                                     ▼
══════════════════════════════════════════════════════════════════════
QUERY PATH  (web_app.py /api/vault/chat → QueryPipeline.execute)
══════════════════════════════════════════════════════════════════════
QueryInterpreter → RetrievalRouter.route(...) ──┬─ default route (GRAPH_ONLY|DOCS_ONLY|HYBRID)
                                                │
                                                └─ ─ ─ TreeBasedRetriever  [CF_TREE_BASED_RETRIEVAL]
                                                        + _is_graph_hopping_query gate
        │
        ▼
DataGates.evaluate ── ENTITY_NOT_FOUND ──┐
                  ── NO_RELEVANT_CHUNKS ─┤── trip → return GATED, NO LLM CALL
                  ── UNVERIFIED_EVIDENCE ┤
        │ pass                          │
        ▼                               │
LLM synthesize (gpt-4o-mini) ───────────┘
        │
        ▼
QAVerifier.verify ── status in {OFF_TOPIC, INSUFFICIENT, UNSUPPORTED, SUSPICIOUS, REJECTED, REVIEW}
   → answer overridden with canned message; confidence floored
        │
        ▼
PipelineResult → _trigger_learning_flow (LearningOrchestrator.on_query_response)
```

#### 9.2b Alternative + orphan modules (current state, May 2026)

```
                 [--use-ontology flag]
scripts/run_vault_extraction.py
        │
        ▼
run_ontology_extraction → OntologyCentricPipeline.extract  (per doc)
        │
        ├── _store_document_chunks
        ├── classify_with_fallback (filename hint → brain/classifier LLM)
        ├── _extract_entities_with_ontology  ── uses SchemaPromptGenerator  [PARTIAL: ignores domain_id]
        ├── _extract_relations_with_ontology
        ├── _run_post_processor (regex, 11 spec patterns)
        ├── _resolve_entities_against_existing
        └── _stage_results  →  STAGING  (no multi-model consensus, no JSON files)
        │
        ▼
        joins PHASE 5 + 6 above (verification + Gardener)

┌──────────────── EXISTS BUT UNWIRED ────────────────────────────────────────┐
│ ┌────────────────────────────┐  ┌────────────────────────────────────────┐ │
│ │ src/context_foundry/       │  │ src/context_foundry/inference/         │ │
│ │   inference/engine.py      │  │   gaps/{records,queue}.py  (D8.1)      │ │
│ │   + planner, gatherer,     │  │   wired into engine.py only;           │ │
│ │   prover, adversary,       │  │   engine.py invoked by tests only      │ │
│ │   meta, synthesizer        │  │                                        │ │
│ └────────────────────────────┘  └────────────────────────────────────────┘ │
│ ┌────────────────────────────┐  ┌────────────────────────────────────────┐ │
│ │ ontology_foundry/          │  │ validation/coherence_checker.py        │ │
│ │   type_validator,          │  │   no callers found in repo grep        │ │
│ │   collision_detector,      │  │                                        │ │
│ │   hierarchy_enforcer,      │  │ extraction/document_classifier.py      │ │
│ │   schema_version_manager,  │  │   only caller: entity_extractor.py     │ │
│ │   type_lifecycle_manager,  │  │   (which is itself orphan — not used   │ │
│ │   approval_manager,        │  │   by MultiModelExtractor)              │ │
│ │   deprecation_manager      │  │                                        │ │
│ │   no callers outside dir   │  │ agents/graph_builder, graph_loader,    │ │
│ └────────────────────────────┘  │   semantic_agent, tool_agent,          │ │
│                                 │   directed_retriever — not on default  │ │
│                                 │   query path; need per-import audit    │ │
│                                 └────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 Module Table (current state, May 2026)

| Module | File path | Responsibility (one sentence) | Currently wired? |
|---|---|---|---|
| `MultiModelExtractor` | `src/context_foundry/extraction/multi_extractor.py` | Per-document parallel extraction with GPT-4o-mini + Claude Sonnet using a hardcoded 14-entity / 16-relation prompt. | **PRODUCTION** |
| `run_consensus` | `src/context_foundry/extraction/entity_resolver.py` | Builds entity/relationship consensus across the two model outputs with name normalization + fuzzy matching. | **PRODUCTION** |
| `validate_consensus` / `resolve_conflicts` | `src/context_foundry/extraction/consensus_validator.py` | Validates consensus output against ontology constraints; auto-resolves conflicts. | **PRODUCTION** |
| `KGIngestor.ingest` | `src/context_foundry/extraction/kg_ingestor.py` | Upserts consensus entities/relationships into Postgres at `STAGING`; creates evidence records. | **PRODUCTION** |
| `StagingLoader` | `src/context_foundry/extraction/staging_loader.py` | Alternative writer used by ontology pipeline path; same STAGING semantics. | **FLAG_GATED** (`--use-ontology`) |
| `OntologyCentricPipeline` | `src/context_foundry/extraction/ontology_centric_pipeline.py` | Document-classified, ontology-guided single-pass extraction; bypasses consensus and writes directly to STAGING. | **FLAG_GATED** (`--use-ontology`) |
| `classify_with_fallback` | `src/context_foundry/extraction/document_classifier.py` | LLM document-type classifier (with filename-hint fallback). | **FLAG_GATED** (only `OntologyCentricPipeline` calls it) |
| `entity_extractor.EntityExtractor` | `src/context_foundry/extraction/entity_extractor.py` | Domain-aware single-LLM entity extractor; calls `DomainSchemaLoader` and `classify_with_fallback`. | **ORPHAN** (no production caller; `MultiModelExtractor` uses its own hardcoded prompt) |
| `relation_extractor` | `src/context_foundry/extraction/relation_extractor.py` | Companion to `entity_extractor`. | **ORPHAN** (same reason) |
| `post_processor` | `src/context_foundry/extraction/post_processor.py` | Regex pass for 11 specification patterns; called inside `OntologyCentricPipeline._run_post_processor`. | **FLAG_GATED** (`--use-ontology`) |
| `brain/classifier.py` | `brain/classifier.py` | Domain classifier with 7 domains and 0.50 threshold. | **PARTIAL** (imported by `entity_extractor` which is orphan; not on any production path) |
| `SchemaPromptGenerator` | `src/context_foundry/ontology/prompt_generator.py` | Generates extraction prompts from `ontology.types`/`ontology.relations`. | **PARTIAL** (called by `OntologyCentricPipeline`, but `get_snapshot()` does not filter by `domain_id` — flat union loaded) |
| `OntologyRepository` | `src/context_foundry/ontology/repository.py` | Postgres-backed lookup of types/relations, supports `domain_id` filter. | **PARTIAL** (filter capability exists but not used by production callers) |
| `ontology_foundry/*` (TypeValidator, CollisionDetector, HierarchyEnforcer, ApprovalManager, SchemaVersionManager, TypeLifecycleManager, DeprecationManager) | `src/context_foundry/ontology_foundry/*.py` | Schema-governance agents (PROPOSED→APPROVED→ACTIVE lifecycle, collision/depth checks). | **ORPHAN** (no callers outside the directory itself per repo grep) |
| `VerificationWorker` | `src/context_foundry/workers/verification_worker.py` | LLM-verifies a batch of unverified facts; writes `fact_verifications` and sets `verified=true`. | **PRODUCTION** (invoked by `run_vault_extraction.py` Phase 5) |
| `GardenerAgent.promotion_pass` | `src/context_foundry/agents/gardener.py:731` | Promotes STAGING→TRUSTED on confidence/corroboration thresholds; optionally validates types against ontology and verification status. | **PRODUCTION** (other passes — `decay_pass`, `conflict_resolution_pass`, `demotion_pass`, `cleanup_pass` — exist but are not invoked by the extraction script; require running `run_cycle` separately) |
| `DataGates` | `src/context_foundry/validation/data_gates.py` | Pre-LLM sufficiency check; emits `ENTITY_NOT_FOUND`, `NO_RELEVANT_CHUNKS`, `UNVERIFIED_EVIDENCE`, `ANSWER_NOT_GROUNDED`. | **PRODUCTION** |
| `coherence_checker` | `src/context_foundry/validation/coherence_checker.py` | Post-response consistency / contradiction detector. | **ORPHAN** (no callers found in repo grep) |
| `QueryPipeline` | `src/context_foundry/agents/query_pipeline.py` | 4-step orchestrator: `QueryInterpreter` → retrieval → LLM synthesize → `QAVerifier`. | **PRODUCTION** |
| `RetrievalRouter` | `src/context_foundry/agents/retrieval_router.py` | Routes between `GRAPH_ONLY` / `DOCS_ONLY` / `HYBRID`; conditionally invokes `TreeBasedRetriever`. | **PRODUCTION** |
| `TreeBasedRetriever` | `src/context_foundry/retrieval/tree_retriever.py` | BFS traversal from anchor org with intent-matching and chunk-grounded fallback. | **FLAG_GATED** (`CF_TREE_BASED_RETRIEVAL` env + `_is_graph_hopping_query` regex) |
| `QAVerifier` | `src/context_foundry/agents/qa_verifier.py` | Two-layer (structural + LLM) post-synthesis answer check; can override answer with canned text. | **PRODUCTION** |
| `LearningOrchestrator.on_query_response` | `src/context_foundry/learning/...` | Async hook fired after every query for gap detection. | **PRODUCTION** (fire-and-forget; learning side effects not audited here) |
| `inference/engine.py` (FactEvaluator) + planner / gatherer / prover / adversary / meta / synthesizer | `src/context_foundry/inference/*.py` | Recursive deterministic+adversarial fact evaluator (v2 design). | **ORPHAN** (no production caller; only tests under `tests/inference/`) |
| `inference/gaps/{records,queue}` | `src/context_foundry/inference/gaps/` | Typed `GapRecord` + `GapQueue` emitted by the inference engine at depth==0. | **ORPHAN** (wired into orphan engine only; D8.1 ships scaffolding, no consumer) |
| `agents/graph_builder`, `graph_loader`, `semantic_agent`, `tool_agent`, `directed_retriever` | `src/context_foundry/agents/*.py` | Listed in `CF_MASTER_REFERENCE.md` agent inventory. | **needs per-module audit** — none appear in `QueryPipeline.execute` or `run_vault_extraction.py`; flagged as candidate orphans pending verification |
| `web_app.py` | `web_app.py` | Flask service exposing auth, vault/extraction admin, test-runner UI; `/api/vault/chat` is the live query endpoint (route definition not located in this scan — needs verification, but `QueryPipeline` is the production query orchestrator per code grep). | **PRODUCTION** |

### 9.4 Behaviors Table (current state, May 2026)

| When this happens | The system currently does this | Module(s) involved |
|---|---|---|
| A document is ingested via the default `scripts/run_vault_extraction.py` (no flags). | No document classification runs. The hardcoded `EXTRACTION_SYSTEM_PROMPT` (14 entity types, 16 relation types) is sent to GPT-4o-mini and Claude Sonnet in parallel. Outputs are written to JSON files under `extraction_outputs/<vault_slug>/<model_name>/`. | `MultiModelExtractor` |
| A document is ingested via `--use-ontology`. | `classify_with_fallback` picks a document type (filename hint, then LLM). `SchemaPromptGenerator` builds an ontology-grounded prompt — but loads the **full flat union** of types/relations rather than filtering by document-type or domain (`get_snapshot()` does not apply `domain_id`). One LLM pass extracts entities, one extracts relations, post-processor regex applies, results staged directly via `StagingLoader`. No multi-model consensus. | `OntologyCentricPipeline`, `classify_with_fallback`, `SchemaPromptGenerator` (PARTIAL), `StagingLoader` |
| Default-path extraction completes for a doc batch. | `run_consensus` builds cross-model consensus, `validate_consensus`+`resolve_conflicts` reconciles, `KGIngestor.ingest` upserts entities and relationships into Postgres at `lifecycle_state=STAGING`, creates `evidence_records` rows, and updates `platform.documents.extraction_level='multi'` per document. | `entity_resolver`, `consensus_validator`, `KGIngestor` |
| A fact enters STAGING via `KGIngestor` or `StagingLoader`. | An `evidence_record` row is created linking the fact to its source span (synthesized fallback if span missing). No further validation runs at this point — `StagingValidatorAgent` (`agents/staging_validator.py`) exists but is not invoked by either ingest path. | `KGIngestor`, `StagingLoader`; `StagingValidatorAgent` is **not** triggered |
| `VerificationWorker` runs (Phase 5 of extraction script). | Pulls a batch of unverified facts (default limit configurable), calls LLM for verdict, writes `fact_verifications` rows, sets `verified=true` and `evidence_verification_status` on the fact. Verifies only a fraction of facts per run. | `VerificationWorker` |
| `GardenerAgent.promotion_pass` runs (Phase 6 of extraction script). | For each STAGING entity/relationship, checks (1) confidence ≥ type-weighted threshold + corroboration count + min age; (2) if `require_verification_for_promotion=True` (set by extraction script — Gardener default is `False`), requires `verified=true`; (3) if `validate_against_ontology=True`, checks the type is present in the loaded type/relation list (loaded as a **flat union** of all 1016 entity types and 230 relation types — no `domain_id` filter). On pass, writes `lifecycle_state=TRUSTED`. | `GardenerAgent.promotion_pass` |
| `GardenerAgent.run_cycle` 5-pass loop (`decay_pass`, `promotion_pass`, `conflict_resolution_pass`, `demotion_pass`, `cleanup_pass`) is invoked. | All five passes execute in order. Note: the extraction script invokes only `promotion_pass` directly; the full 5-pass cycle is only run by separate Gardener invocation paths (scheduler / manual). Whether the scheduler is currently running was not verified in this audit. | `GardenerAgent.run_cycle` |
| A query arrives at `/api/vault/chat`. | `QueryPipeline.execute` runs: `QueryInterpreter.interpret(query_text)` → `Retriever.execute(intent)` (which calls `RetrievalRouter.route(...)`) → `_synthesize_answer(...)` (LLM call to gpt-4o-mini) → `QAVerifier.verify(...)`. `_trigger_learning_flow` fires after every response. | `QueryPipeline`, `QueryInterpreter`, `Retriever`, `RetrievalRouter`, `QAVerifier`, `LearningOrchestrator` |
| `RetrievalRouter.route` decides whether to use tree retrieval. | Reads the `CF_TREE_BASED_RETRIEVAL` env flag (or per-request `tree_based_retrieval` override) **and** runs `_is_graph_hopping_query(query)` regex. Tree retrieval is invoked **only when both are true**. Default in `start.sh` is `false`. | `RetrievalRouter.route`, `is_tree_based_retrieval_enabled`, `TreeBasedRetriever` |
| `DataGates.evaluate` trips on `ENTITY_NOT_FOUND` or `NO_RELEVANT_CHUNKS`. | Returns `DataGateEvaluation` with the gate result; the pipeline returns the gated response without calling the synthesis LLM. | `DataGates` |
| `DataGates.evaluate` trips on `UNVERIFIED_EVIDENCE`. | Soft warning — the LLM is still called, but the response carries an unverified-evidence marker. | `DataGates` |
| `QAVerifier.verify` returns a non-`SUPPORTED` / non-`NEEDS_LLM` status. | The synthesized answer is overwritten with a canned message keyed on status (`OFF_TOPIC` → "I found related information but…", `INSUFFICIENT` → "I have partial information…", etc.) and confidence is floored to 0.10–0.25. | `QAVerifier`, `QueryPipeline._synthesize_answer` |
| The `inference/engine.py` `FactEvaluator` is invoked. | Runs `EvaluationPlanner` → `EvidenceGatherer` → `ProofConstructor` → `AdversarialChallenger` → `MetaEvaluator` → `VerdictSynthesizer`, with cycle detection and replan loop (max 3). At depth==0, emits typed `GapRecord` entries to `GapQueue` for 5 wired gap types. **Currently invoked only by tests** — no production caller wires the engine into the query path. | `inference/engine.py`, `inference/{planner,gatherer,prover,adversary,meta,synthesizer}.py`, `inference/gaps/` |
| A `coherence_checker` "shadow mode" check would run after a response. | Module exists at `src/context_foundry/validation/coherence_checker.py`, but no caller invokes it in any path — replit.md describes it as wired, code grep finds no callers. | `coherence_checker` (ORPHAN) |
| A schema change (new entity type, new relationship type) is proposed. | `OntologyCentricPipeline._update_reference_ontology` writes new types directly into `ontology.types` / `ontology.relations` during extraction. The Ontology Foundry governance lifecycle (PROPOSED → VALIDATING → APPROVED → ACTIVE) and its agents (`TypeValidator`, `CollisionDetector`, `HierarchyEnforcer`, `ApprovalManager`, `SchemaVersionManager`, `TypeLifecycleManager`, `DeprecationManager`) **are not invoked** — they exist as code in `src/context_foundry/ontology_foundry/` but no caller outside that directory was found. | `OntologyCentricPipeline._update_reference_ontology`; `ontology_foundry/*` (ORPHAN) |

**Audit notes (cannot determine from code inspection alone):**
- The `web_app.py` `/api/vault/chat` route definition was not located in this scan (grep timed out at line 1049). Existence of `QueryPipeline` as the production query orchestrator is inferred from import graph; the actual route handler should be confirmed by a follow-up grep or by running the system.
- Whether `GardenerAgent.run_cycle` (the full 5-pass loop with decay/conflict/demotion/cleanup) is invoked by any running scheduler in production was not verified — the extraction script only invokes `promotion_pass` standalone.
- Several `agents/*.py` modules (`graph_builder`, `graph_loader`, `semantic_agent`, `tool_agent`, `directed_retriever`) are listed in `CF_MASTER_REFERENCE.md` but were not traced for production callers in this audit. Marked "needs per-module audit" in the table; should not be assumed wired.

---

## 10. Authority Rule

When in doubt, authority order is:

1. User's explicit current instruction
2. This architecture document (`docs/architecture.md`)
3. `docs/decisions.md`
4. Task-specific brief
5. Recent chat context
6. Agent inference

Recent task context does not redefine Context Foundry unless the user explicitly says it does.

---

## Required Replit Alignment Block

> Every Replit response begins with this alignment block before any other content:
>
> ```
> Alignment:
> - Module touched: [name]
> - Product vs implementation: [product-level | implementation-level | both]
> - Architecture-doc consistency: [matches | departs because X]
> - Drift risk: [main risk]
> - Out of scope: [what will not be touched]
> ```
>
> If a task instruction conflicts with the architecture document or the decisions document, flag the conflict in the alignment block and stop before doing work.

---

## Implementation Gate

> No implementation task begins unless:
>
> 1. `docs/architecture.md` has been read.
> 2. `docs/decisions.md` has been read.
> 3. The response begins with the alignment block.
> 4. The task is mapped to a specific implementation Piece (0 through 8) from the implementation sequence.
> 5. The out-of-scope list is explicit.
>
> Tasks that do not satisfy all five conditions stop and request clarification.

---

## Implementation gaps recorded at design lock

### Gap 1: Domain registry not populated (blocking Piece 0)

> `ontology.types.domain_id` is NULL for all 1037 rows. `ontology.relations.domain_id` is NULL for 250 of 254 rows (4 hold the literal `'core'`). The seed files (`00_shared` through `07_construct`) imply domain partitioning by filename but do not persist `domain_id` in their inserts. Therefore, before domain-aware extraction (Piece 2) can function, Piece 0 must construct and backfill the canonical domain registry.
>
> **This finding is recorded, not solved.** Piece 0 implementation is a separate task and is not authorized by this design-lock task.

### Gap 2: 803 ad-hoc types added outside Ontology Foundry governance

> 803 of 1037 `ontology.types` rows were inserted by `OntologyCentricPipeline._update_reference_ontology` during extraction runs in 2026, bypassing the Ontology Foundry `PROPOSED → APPROVED → ACTIVE` lifecycle. These rows have no seed-file provenance and remain `domain_id = NULL` after Piece 0. They are visible only to non-domain-scoped queries (`OntologyRepository.get_all_types()` with no `domain_id` filter).
>
> **This finding is recorded, not solved.** Closing this gap is Piece 7's responsibility: Ontology Foundry wired to schema changes. The 803 rows must be either retroactively classified through governance, archived as legacy, or rebuilt under proper provenance. Until Piece 7 lands, these types are not visible to domain-aware extraction (Piece 2).

### Gap 3: 24 layer-1 foundational types lack seed-file provenance

> 24 layer-1 ACTIVE foundational types (e.g., `Person`, `Event`, `LegalInstrument`, with UUIDs in the `00000000-…` range) were loaded by a 2025-12-06 migration that is not present in `attached_assets/ontology_files/`. Conceptually these may be `core` types, but `core` is not an inference bucket per ADR-002. Types are assigned to `core` only by deterministic provenance. These 24 rows remain `domain_id = NULL` after Piece 0.
>
> **This finding is recorded, not solved.** Closing this gap is a small follow-up task: locate the original 2025-12-06 migration, confirm the types are genuinely foundation/cross-domain, and either reclassify them deterministically into `core` or document why they should remain unscoped.

### Gap 5: 4 ontology.relations rows assigned `core` without seed-file provenance (corrected during Piece 0 closeout)

> Piece 0 closeout audit identified 4 `ontology.relations` rows previously assigned `domain_id = 'core'` that have no seed-file provenance:
>
> - `479a23c5-22a1-45cf-83af-e200aa5ead87` — `HOLDS_POSITION` (PERSON → JOB_TITLE)
> - `9dfd6070-cd8c-4f3c-9c44-9d898c293ff9` — `HAS_COMPENSATION` (PERSON → CONCEPT)
> - `91b9ae86-fa99-4dbb-aa0e-bf5b478ddefa` — `REPORTS_TO` (PERSON → PERSON)
> - `058414f9-7530-41e5-9c20-94789aa32452` — `WORKS_AT` (PERSON → ORGANIZATION)
>
> All four were inserted within a 13-minute window on 2026-01-12 with random v4 UUIDs (not the `30000000-0000-XXXX-...` seed-file scheme), and none appear in any of the 8 seed files in `attached_assets/ontology_files/`. They were assigned `'core'` directly by a runtime/extraction path that bypassed the Ontology Foundry `PROPOSED → APPROVED → ACTIVE` lifecycle. Per Option A's strict-determinism rule (assign `core` only by deterministic seed-file UUID provenance), they were reset to `domain_id = NULL` during Piece 0 closeout. The rows remain `ACTIVE` in the database; only their domain assignment was removed.
>
> **Three observed Ontology Foundry bypass patterns** are now on record. Schema changes have been bypassing the governance lifecycle by three distinct mechanisms:
>
> 1. **`_update_reference_ontology` writes** — 803 layer-2 ad-hoc types from January 2026 onward have no seed-file provenance and remain `domain_id = NULL` after Piece 0. (Gap 2)
> 2. **Pre-seed migration** — 24 layer-1 foundational types from 2025-12-06 have no seed-file provenance and remain `domain_id = NULL` after Piece 0. (Gap 3)
> 3. **Direct `core` assignment without provenance** — 4 `ontology.relations` rows from 2026-01-12 (`HOLDS_POSITION`, `HAS_COMPENSATION`, `REPORTS_TO`, `WORKS_AT`) were previously assigned `domain_id = 'core'` but lacked seed-file provenance. Piece 0 closeout reset them to `domain_id = NULL` under the strict-determinism rule. (Gap 5, this section)
>
> All such rows are preserved in the DB and remain available to non-domain-scoped queries (the `OntologyRepository` snapshot path), but they are not visible to domain-scoped ontology lookups until governed.

#### Piece 0.6 (prerequisite to Piece 2): governed disposition of unscoped foundational relation candidates

> The 4 relations recorded in Gap 5 — `HOLDS_POSITION`, `WORKS_AT`, `REPORTS_TO`, `HAS_COMPENSATION` — are likely **foundational relation candidates for organizational world modeling**. They are exactly the canonical role/employment edges Context Foundry's role-resolution and tree-retrieval paths depend on (see `replit.md` "Tree matcher fix — HOLDS_POSITION + affiliation traversal", 2026-05-08).
>
> **Piece 0.6 must resolve their disposition before Piece 2 (Domain-Aware Extraction) lands**, if domain-aware extraction needs any of these four verbs to appear in scoped prompts. The decision is one of: (a) retroactively bless them into `00_shared_ontology.sql` with their existing UUIDs, (b) re-create them under a governed `PROPOSED → APPROVED → ACTIVE` flow with new UUIDs (requires a corresponding migration to remap referencing rows), or (c) explicitly leave them unscoped and have Piece 2's prompt builder source them by other means.
>
> Piece 7 still owns the broader long-term Ontology Foundry governance lifecycle (Gap 2 + Gap 3 + Gap 5 in aggregate). Piece 0.6 is the **near-term, narrowly-scoped** decision for these 4 specific foundational relation candidates.
