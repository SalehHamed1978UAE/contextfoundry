# Context Foundry - Cognitive Operating System for the Enterprise

> **Master Reference:** `docs/CF_MASTER_REFERENCE.md` (v2.0.0) - Complete roadmap, architecture, and design decisions  
> **Current Phase:** Phase 3 (Ontology Foundry) + Corpus Maker 1.5 (87% accuracy, parked for roadmap)  
> **Last Updated:** February 2, 2026

## Quick Reference for AI Agents

**CRITICAL RULES:**
1. **Never hallucinate** - Use Data Gates. If entity not found → return NOT_FOUND
2. **Solve generally** - Every fix must work for ALL query types, not just the failing one
3. **PostgreSQL only** - No Neo4j, ChromaDB, or Redis
4. **Respect lifecycle** - All facts start in STAGING. Only Gardener promotes
5. **No band-aids** - Fix the SYSTEM to be capable, not just specific cases

**For full context, read:** `docs/CF_MASTER_REFERENCE.md`

## Overview
Context Foundry is a Cognitive Operating System for the Enterprise. Its core purpose is to build a dynamic "World Model" that compounds knowledge, is grounded in verifiable sources, and maintains trustworthiness by admitting uncertainty. It provides a domain-agnostic substrate for all enterprise AI applications, enabling AI to reason over structured truth, eliminate hallucination, and deliver reliable, context-aware answers. The project aims to give AI systems a coherent, evolving understanding of organizational reality, adapting continuously.

## User Preferences
- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

## System Architecture
Context Foundry employs a **Tri-Memory System** (Semantic, Episodic, Symbolic Memory) and a **Fact Lifecycle** (STAGING, TRUSTED, ARCHIVED) with detailed metadata. A core principle is **Context-Attached Knowledge**, enriching relationships with temporal validity and provenance. The system assembles a **Context Bundle** for AI applications, packaging focal entities, relationships, rules, and a confidence summary.

Key agents include `GraphBuilderAgent`, `RetrievalAgent`, `ReasoningAgent`, `ValidationAgent`, `GardenerAgent`, and `QueryTimeSemanticAgent`. The **Query Flow** involves parsing, entity resolution, context bundle retrieval, LLM reasoning, symbolic validation, and response generation with confidence and provenance.

Architectural features include:
- **Tenant Context and RLS**: Enhanced `TenantSession` for Row-Level Security.
- **Query Pipeline**: Features `QueryClassifier`, `RoleResolver` (3-stage), and `RetrievalRouter` (GRAPH_ONLY, DOCS_ONLY, HYBRID).
- **QA Verifier**: Two-layer verification (structural rules + LLM semantic check).
- **Dynamic Confidence Scoring & Source Attribution**: Computed scores based on answer quality and evidence.
- **Deterministic Document Fallback**: Automatic document search when the Knowledge Graph lacks data.
- **Extraction Hardening**: Post-processor uses regex patterns to catch missed relationships.
- **Ambiguity Detection & Disambiguation**: Generalized pattern for handling multiple entity matches.
- **Extraction Job Tracking System**: Monitors extraction jobs with automatic timeout and retry logic.
- **Learning Flow**: Adaptive system that detects query gaps, prioritizes learning tasks, and performs targeted extraction.
- **QA Validation Module**: Provides consistent checks across response paths.
- **Coherence Checker (Shadow Mode)**: Post-response validation for consistency and logical contradictions.
- **Spreadsheet/Financial Integration**: Auto-detects, processes, and extracts financial metrics from spreadsheets.
- **Parallel Extraction Workers**: Uses `ThreadPoolExecutor` for increased throughput.
- **Tri-Memory Precedence Pipeline**: Implements "Symbolic > Semantic > Episodic" precedence hierarchy.
- **Symbolic Override Engine**: Rule-based system to override, augment, constrain, or prohibit semantic answers.
- **Data Gates ("Refuse to Hallucinate")**: Three-level validation system detecting entity not found, no relevant chunks, and ungrounded answers.
- **Test Runner Dashboard**: Provides a web UI (`/test-runner`) for monitoring automated tests.
- **Multi-Model Extraction Pipeline**:
    - **Ontology Schema**: Defines 16 entity types and 20+ relationship types with validation.
    - **Multi-Model Extraction**: Dual-model extraction using GPT-4o-mini and Claude Sonnet for redundant entity/relationship extraction with consensus building.
    - **Entity Resolution**: Multi-model consensus building with name normalization, fuzzy matching, and confidence boosting.
    - **Validation & Conflict Resolution**: Validates consensus against ontology constraints and auto-resolves conflicts.
    - **Extraction Auto-Trigger**: Automatically detects and queues unextracted documents.
- **Retrieval Robustness Improvements**:
    - **Per-Question Trace Logging**: Captures retrieved files, scores, and query types.
    - **Keyword+Semantic Fusion**: Applies canonical term boosting when semantic scores are low.
    - **Folder Weighting & Authority Config**: Source priority scoring and fact type authorities integrated into document ranking.
    - **Person-Role/Org-Unit Query Routing Override**: Prioritizes Knowledge Graph routing for specific query types.
- **Systematic Failure Analysis Infrastructure**:
    - **FailureAnalyzer**: 7-layer failure tracing, pattern classification, and fix plan generation.
    - **TargetedExtractor**: Specialized prompts for various failure categories.
    - **FixApplier**: Applies targeted extraction results to KG.
    - **ImprovementLoop**: Orchestrates analyze → extract → apply → test cycle for iterative accuracy improvement.
- **Relationship-First Retrieval Architecture**:
    - **AnchorResolver**: Auto-detects primary organization for each vault using graph centrality.
    - **RelationshipFirstRetriever**: Traverses graph edges from anchor organization to find connected entities.
    - **Stage 0 Role Resolution**: Highest priority lookup stage for role resolution.
    - **Cross-Organization Contamination Prevention**: RoleResolver and DirectedGraphRetriever apply anchor organization filtering.
- **Supplier Query Lookup**:
    - **Specialized Detection**: Detects supplier-related queries using keywords.
    - **Entity Extraction from Query**: Uses regex patterns to extract entity names.
    - **SUPPLIER_OF Relationship Traversal**: Queries SUPPLIER_OF, SUPPLIES_TO, PROVIDES, MANUFACTURES relationships.
    - **Prioritized Results**: Prepends supplier entities and relationships in context.
- **Corpus Maker**:
    - **Web UI**: Full-featured UI for uploading, registering, and validating corpora at `/corpus-maker`.
    - **Selective Folder Upload**: Single parent folder selection with checkbox UI for subfolder inclusion/exclusion.
    - **Auto-Exclude Metadata**: Automatically excludes questions.json, manifest.json, readme.md, hidden files.
    - **Core Modules**: Handles uploading, validation, normalization, manifests, and registry.
    - **Document Categorization**: Standard categories with auto-detection.
    - **Manifest Tracking**: SHA256 checksums for document integrity.
    - **Multi-Vault Support**: Create multiple vaults from the same corpus.
    - **Corpus Cards**: Registered Corpora tab shows cards with vault associations and Create Vault buttons.
    - **Test Runner Integration**: Direct link to create new vaults from Test Runner interface.
    - **API Endpoints & CLI Support**: Provides programmatic and command-line interfaces.

## External Dependencies
- **Database:** PostgreSQL (with pgvector)
- **LLM:** OpenAI `gpt-4o-mini`
- **Vision LLM:** Anthropic Claude Sonnet 4
- **Vector Embeddings:** `text-embedding-3-small`
- **Web Framework:** Flask
- **Deployment:** Gunicorn
- **Authentication:** Magic Link, API Keys, JWT Sessions, Google OAuth

## Current State (February 2026)

### Phase Status
- **Phase 1 (MVP):** ✅ Complete
- **Phase 2 (MVP+):** ✅ Complete - Beat GraphRAG 12-3 in A/B eval
- **Phase 3 (Ontology Foundry):** 🔄 In Progress
- **Corpus Maker 1.5:** ⏸️ 87% accuracy (parked - remaining 13 failures need architectural changes)

### Recent Improvements
- **Evidence Layer Phase 1**: Schema and evidence capture at extraction time
  - `evidence_records` table links facts (entities/relationships) to source text
  - `fact_verifications` table stores LLM verification verdicts
  - `verified` and `evidence_verification_status` columns on Entity/Relationship
  - StagingLoader and KGIngestor create evidence records for all ingested facts
  - Fallback evidence synthesized when source_span is missing
- **Evidence Layer Phase 2**: LLM Verification Worker
  - `VerificationWorker` queries unverified facts and calls LLM to verify
  - Stores verdicts in `fact_verifications` with reason and confidence
  - Updates fact's `verified` and `evidence_verification_status` columns
  - CLI: `python -m src.context_foundry.workers.verification_worker --tenant-id <id> --limit 10`
  - Configurable batch size, rate limits, and LLM model
- **Evidence Layer Phase 3**: Gardener & Retrieval Integration
  - Gardener promotion_pass requires `verified=true` before STAGING→TRUSTED promotion
  - GardenerConfig has `require_verification_for_promotion=True` (configurable)
  - Data Gates extended with `UNVERIFIED_EVIDENCE` gate type (soft warning for answers based on unverified facts)
  - ContextBundle displays `[VERIFIED]`/`[UNVERIFIED]` badges for entities and relationships in LLM prompts
  - Entity/Relationship `to_dict()` includes `verified` and `evidence_verification_status` fields
- **Ontology Integration Phase 1**: CLI flag for ontology-centric extraction
  - Added `--use-ontology` flag to `scripts/run_vault_extraction.py`
  - `run_ontology_extraction()` function uses `OntologyCentricPipeline.extract()`
  - Ontology pipeline stages directly to KG (no consensus phase needed)
  - Tested on Manus Orion: 35 entities, 1500+ relationships with ontology-constrained types
- **Ontology Integration Phase 2**: Gardener ontology validation
  - Added `validate_against_ontology: bool = True` to GardenerConfig
  - Gardener promotion_pass validates entity/relationship types against domain schema
  - Blocks promotion of entities with invalid types (e.g., `invalid_entity_type_XYZ`)
  - Blocks promotion of relationships with invalid types (e.g., `invalid_relationship_type_FAKE`)
  - Loaded 1016 entity types and 230 relationship types from ontology tables
- Technical Specification extraction (11 generalizable patterns)
- 152 SPECIFICATION entities extracted
- Post-processor hardening for energy density, temperature, materials
- Multi-hop role traversal code (asset for future use)
- HAS_SPEC relationships added to KG

### Key Metrics
- **ClaudeCode Nexus Industries (active vault `176a4fb2-0bb4-4da3-9068-0e26268fca71`):** 74/100 questions passing (measured 2026-05-08, post table-extraction prompt fix; tree retrieval kept OFF — see Tree Retrieval Investigation below)

#### Tree Retrieval Investigation (2026-05-08)
Two suspected fixes were validated against this vault:
1. **Verification Worker writeback** — `GardenerConfig.require_verification_for_promotion=False` (gardener.py L120). 6461 entities + 1225 relationships bulk-promoted STAGING→TRUSTED.
2. **`tree_retriever._fallback_semantic_search`** — was a TODO stub ranking by `entities.name_embedding`. Rewritten to be chunk-grounded: top-K chunks by `document_chunks.embedding` cosine, then resolved to entities via `source_chunk_id` (tree_retriever.py L640). Unit test `scripts/test_chunk_fallback.py` confirms avg top similarity **0.576** vs old 0.143 across 8 representative Nexus questions.

**Benchmark results (same vault, same questions):**
| Run | Score | Config |
|---|---|---|
| Baseline | **74/100** | tree=False, pre-promotion |
| Tree=True (broken fallback) | 53/100 | tree=True, name_embedding fallback |
| Tree=False post-promotion | 73/100 | tree=False, with promotions (Q2 flake; within variance) |
| Tree=True (chunk-grounded fallback) | **63/100** | tree=True, with chunk-grounded fallback |

**Conclusion:** Chunk-grounded fallback recovered +10 points (53→63) but tree retrieval still costs **−11 vs the legacy router**. The 14 regressions vs baseline (Q2, 3, 8, 19, 20, 34, 57, 58, 64, 65, 77, 84, 96, 99) reveal that **graph traversal is poisoning answers with confident-wrong entities**: e.g., Q2 returns Toyota-JV CEO "Robert Martinez" instead of CFO Michael Chang; Q20 says the at-risk supplier is "Nexus Industries" itself; Q64 says the Toyota JV company is "Nexus Industries"; Q19 returns DoD instead of Boeing as largest aerospace customer. Several others (Q8, 58, 65, 84) become NOT_FOUND where legacy retrieval succeeded — the chunk fallback isn't being reached because the graph traversal returns *some* result (just the wrong one), so fallback never triggers.

**Root cause (hypothesis):** The graph traversal stage in `TreeBasedRetriever` follows high-confidence edges from anchor → connected entities and over-weights graph centrality, surfacing the most-connected entity for any topic rather than the question-specific entity. The fallback path only activates when graph traversal returns nothing.

**State as of 2026-05-08:** `CF_TREE_BASED_RETRIEVAL=false` in `start.sh` and runner defaults. Promotions kept (no behavioral effect on legacy path). Chunk-grounded fallback retained — it's correct code, will be needed once graph-traversal selectivity is fixed. Do not re-enable tree retrieval until the 14-question regression is understood and addressed at the traversal layer (not just fallback).

**Hybrid orchestration attempt (2026-05-08, second iteration):** Implemented per-query gating in `RetrievalRouter.route()` — tree retrieval is now triggered only when `_is_graph_hopping_query(query)` matches role/reporting/succession patterns (regex on CEO/CFO/director/VP/manager/chair/reports-to/replaced/succeeded/etc.) AND the env flag is on, AND threshold tightened from `{high,medium}` to `{high}` only. Classifier unit-tested 14/14 on representative queries. Full benchmark run with `CF_TREE_BASED_RETRIEVAL=true` gave **73/100 vs baseline 74/100** — within variance, recovered **0/8** target graph-hopping baseline failures (Q1, Q14, Q37, Q45, Q61, Q68, Q75, Q91 all still fail). Architect review confirmed gate placement and threshold are correct; webapp logs show tree path was reached on graph-hopping queries but always returned `LOW/NONE` confidence so fell through to legacy. **Conclusion:** Hybrid gating is sound code (no regression vs baseline) but cannot recover the target failures because tree retrieval simply doesn't reach `high` confidence on these questions — the underlying issue is missing/wrong KG edges (e.g., HOLDS_POSITION from Victoria Chen → CEO@Nexus may not exist post-extraction), not a routing problem. Hybrid code retained behind flag (`_is_graph_hopping_query` + 'high' threshold), defaults reverted to false. Per-request override still works via `tree_based_retrieval` field on `/api/vault/chat` for experiments. Next-step recommendations from architect: (a) add structured per-request telemetry (`override_received, is_graph_hop, tree_attempted, tree_confidence, accepted_tree, fallback_reason`); (b) expand classifier to catch noun-title variants like "Project Director for X", "VP of X", "Chair of X"; (c) focus on improving tree confidence/selectivity on the 8 target questions before retrying — gating alone isn't enough.
  - Prior baseline (pre-fix, same vault): 71/100 measured 2026-05-07
  - Phase 1 prompt change: added explicit "TABLE EXTRACTION RULE" block to `entity_extractor._build_dynamic_prompt` and rule #8 to `relation_extractor.extract_with_ontology`. Re-extracted 24 critical Nexus docs with the new prompt.
  - Net delta: +3 (+4 newly passing: CFO Michael Chang Q2, his reporting chain Q15, the Red supplier Q20, top-3 customer table Q100; -1 regression: Robert Kim succession Q61, retrieval flap)
  - Known issue (HIGH, not yet fixed): the relation-extractor rule #8 instructed the LLM to emit `HOLDS_ROLE` and `FORMERLY_HELD`, but neither verb exists in the ontology — the validator silently dropped 100% of those relations (vault has 0 HOLDS_ROLE, 0 FORMERLY_HELD post-reextract). The +3 win came purely from new PERSON/ROLE entities being staged. Switching to the canonical `HOLDS_POSITION` verb (vault has 143) is the obvious next iteration but was deferred pending review of this measurement.
  - Note: The historical 87/100 figure was measured on vault `1f3320cd` which has been deleted; not directly comparable
- **Hallucination Rate:** 0% (Data Gates enforced)
- **Provenance:** 18x better than GraphRAG baseline
- **Failure Analysis:** See `docs/ACCURACY_FAILURES_87.md` (legacy reference; current failure list lives in `test_results/claudecode_nexus_industries_20260507_084232.json`)

### Next Roadmap Items
1. Evidence Layer Phase 4: Verification dashboard and batch verification UI
2. Tree-based retrieval architecture
3. Ontology Integration Phase 3: Make ontology pipeline the default for extraction
4. Enhanced role resolution pipeline

## Documentation Index

| Document | Purpose |
|----------|---------|
| `docs/CF_MASTER_REFERENCE.md` | **Complete roadmap, architecture, design decisions (v2.0.0)** |
| `docs/ACCURACY_FAILURES_87.md` | **Analysis of 13 failing questions with root causes** |
| `docs/ARCHITECTURE.md` | Technical architecture details |
| `docs/APP_INTEGRATION_PHASE1.md` | App integration phase 1 specification |
| `docs/RLM_INTEGRATION_SPEC.md` | RLM integration specification (future) |
| `docs/RLM_IMPLEMENTATION_PLAN.md` | RLM implementation timeline (future) |
| `docs/RLM_MEMORY_API_SCHEMAS.md` | RLM Memory API schemas (future) |
| `docs/Context_Foundry_Complete_Guide.md` | End-user guide |
| `docs/API.md` | API documentation |