# Context Foundry — Build Status, Successes & Known Problems

> **Date:** February 9, 2026  
> **Author:** Session Summary  
> **Scope:** Complete description of how the system was built, what works, and what is currently broken

---

## What Context Foundry Is

Context Foundry is a **Cognitive Operating System for the Enterprise** — not a chatbot, not a search engine, not a RAG system. It is cognitive middleware: the layer that sits between raw enterprise documents and any AI application that needs to reason about organizational reality. The one-liner is "organizational object permanence for AI." The golden rule, encoded into every architectural decision, is:

> **Never hallucinate. Admit uncertainty. Show your work.**

---

## How It Was Built — Phase by Phase

### Phase 1: MVP — Proving the Architecture

The first question was whether the core idea — a tri-memory architecture — was actually better than what existed. The system was built around three distinct memory types modeled on cognitive science:

#### Semantic Memory ("The What")

A knowledge graph stored in PostgreSQL using pgvector. Every entity (person, organization, project, product, service, role, department, team, incident, document, policy, metric, specification, event, contract) gets its own row in the `entities` table with:

- UUID primary key
- Name (text)
- Entity type (one of 16 defined types)
- Properties (JSONB bag for flexible attributes)
- 1536-dimensional embedding (OpenAI `text-embedding-3-small`)
- Lifecycle state: STAGING / TRUSTED / ARCHIVED
- Confidence score (0.0–1.0)
- `tenant_id` (UUID for multi-tenancy isolation)
- `created_at` / `updated_at`

Every relationship between entities lives in the `relationships` table with `source_id`, `target_id`, `relationship_type`, `confidence`, `tenant_id`, `source_document_id` (provenance), `source_sentence` (the exact text), and `raw_relationship_type` (what the LLM originally extracted before normalization).

#### Episodic Memory ("The When")

Document chunks with embeddings. Every document ingested gets chunked into 512-token overlapping pieces. Each chunk is embedded and stored in `document_chunks` with its parent `document_id`, `chunk_index`, and `tenant_id`. This gives the system a timeline of what it has read, from where, and when.

#### Symbolic Memory ("The Rules")

Business logic, constraints, and typed relationships stored in the same PostgreSQL database. Escalation rules, org hierarchies, dependencies, and policies live as first-class entities in the `relationships` table and a separate `rules` table.

**Precedence order: Symbolic > Semantic > Episodic.** Retrieval checks the structured graph before falling back to document chunks, and rules can override semantic answers.

#### Phase 1 Proof Points

- Tri-memory architecture: operational
- Entity lifecycle governance (STAGING → TRUSTED → ARCHIVED): operational
- Data Gates (pre-LLM sufficiency check): operational, 0% hallucination
- Multi-hop reasoning: operational
- **Beat Microsoft GraphRAG 12–3 in A/B evaluation** on 100 queries

---

### Phase 2: MVP+ — Scale, Extraction, and Evaluation

Phase 2 built out the extraction pipeline and hardened the system for real enterprise corpora.

#### The Extraction Pipeline

1. A document (PDF, DOCX, XLSX, TXT, Markdown) is uploaded to the platform service (Flask, port 5000). Documents are stored in `platform.documents` with SHA256 checksums.

2. The `DocumentLoader` parses the file. PDFs with complex layouts use Claude Sonnet 4 (vision LLM) for OCR. Plain text/markdown goes directly to chunking.

3. The `Chunker` creates 512-token overlapping chunks and stores them in `document_chunks` with embeddings.

4. The `ExtractionPipeline` runs in parallel workers (`ThreadPoolExecutor`) and processes each chunk:
   - **EntityExtractor**: GPT-4o-mini extracts entities from each chunk → JSON array of `{name, entity_type, properties, source_span, confidence}`
   - **RelationExtractor**: GPT-4o-mini extracts relationships given the known entity list → JSON array of `{relation_type, source_name, target_name, source_span, confidence}`
   - **PostProcessor**: Deterministic regex patterns catch relationships the LLM missed — 11 generalizable patterns for: energy density (Wh/kg), temperature ranges (°C/°F), production capacity (kg/hr, MW), material compositions (chemical formulas), efficiency percentages, cycle life, charge time, conductivity, thickness, and pressure. Extracted 152 SPECIFICATION entities.
   - **DuplicateDetector**: Before inserting, checks for name collisions using exact match, semantic similarity, and rapidfuzz fuzzy matching.

5. All extracted facts land in `STAGING` state. Nothing enters the trusted graph directly.

#### The Gardener Agent

Runs on a 5-minute background cycle and performs five passes:

| Pass | Name | What It Does |
|------|------|-------------|
| 1 | Decay | Reduce confidence of facts not recently corroborated |
| 2 | Promotion | STAGING → TRUSTED when confidence + corroboration + age thresholds met |
| 3 | Conflict Resolution | Detect contradictory facts, flag or auto-resolve |
| 4 | Demotion | Move TRUSTED → ARCHIVED when confidence drops below floor |
| 5 | Cleanup | Delete STAGING facts that age out without promoting |

**Promotion thresholds are type-weighted:**

| Entity Type | Confidence Threshold | Corroborations Required | Min Age |
|-------------|---------------------|------------------------|---------|
| Person | 0.85 | 2 | 4 hours |
| Service | 0.75 | 1 | 1 hour |
| Incident | 0.80 | 3 | 2 hours |
| Default | 0.70 | 1 | 1 hour |

#### The Query Pipeline

Every query flows through:

1. `EntityResolver` — 3-stage: exact name match → semantic vector search → fuzzy string match
2. `QueryClassifier` — classifies as: impact, ownership, dependency, escalation, expertise, specification
3. `RoleResolver` — 3-stage: exact title → org hierarchy traversal → semantic match (handles "Who is the CEO?")
4. `RetrievalRouter` — decides GRAPH_ONLY, DOCS_ONLY, or HYBRID based on query type and data sufficiency
5. `RetrievalAgent` — queries all three memory layers, assembles a `ContextBundle`
6. **Data Gates** — three-level pre-LLM check: (1) entity not found, (2) no relevant chunks, (3) ungrounded answer detection
7. `ReasoningAgent` — LLM reasoning over the ContextBundle (only called if Data Gates pass)
8. `ValidationAgent` — checks reasoning against symbolic rules
9. Response with FULL_ANSWER / PARTIAL_ANSWER / GUIDANCE / CLARIFY / NOT_FOUND + confidence + provenance

#### The ContextBundle

The structured contract between retrieval and reasoning:

```python
ContextBundle:
  target_entity_name: str
  target_entity_found: bool
  query_type: str
  semantic_entities: List[Entity]         # From knowledge graph
  semantic_relationships: List[Relationship]
  blast_radius_entities: List[Entity]     # For impact queries
  episodic_documents: List[DocumentChunk] # From document search
  symbolic_rules: List[Rule]              # Business rules
  confidence_summary: ConfidenceSummary
  knowledge_boundaries: List[str]         # Explicit gaps
```

#### Test Infrastructure

A full test runner with:
- Web UI at `/test-runner`
- CLI runner: `python -m src.test_runner.runner --corpus "..."`
- State machine: `creating_vault → uploading → extracting → running_qa → complete/failed/interrupted`
- Heartbeat tracking: 5-minute timeout detects dead worker processes
- Progress checkpointing: can resume interrupted runs
- Per-question trace logging: captures retrieved files, scores, query types
- `test_runs` table in PostgreSQL as single source of truth

#### Multi-Tenant Vault Isolation

Every table has a `tenant_id` column. All queries, extractions, and Gardener cycles are scoped to it. A `TenantSession` enforces Row-Level Security. Multiple vaults can run independently with no data leakage.

#### Corpus Maker

Web UI at `/corpus-maker` for managing corpora:
- Selective folder upload with checkbox UI for subfolder inclusion/exclusion
- Auto-exclusion of metadata files (questions.json, manifest.json, readme.md, hidden files)
- Document categorization with auto-detection
- SHA256 checksum manifests for integrity verification
- Multi-vault creation from one corpus
- Corpus cards with vault association tracking

---

### Phase 3: Ontology Foundry — Schema Governance (Current)

Phase 3 was motivated by a critical problem: Phase 2 extracts "whatever it finds." Without schema governance, aggressive LLM extraction creates type pollution — entities typed as COMPETITOR when they should be CUSTOMER, relationships typed as SUPPLIES when they should be CUSTOMER_OF, divisions typed as TEAM instead of ORGANIZATION. The graph works at 87% but the remaining 13% often fail because the schema is inconsistent.

#### The Four-Layer Ontology Model

```
Layer 0: Meta-Core (IMMUTABLE)
├── Entity, Event, Record, Relation
├── Hardcoded into CF — never modified
└── UUID scheme: 00000000-0000-4000-a000-*

Layer 1: Common Core (SHARED)
├── Asset, Agent, Person, Organization
├── Shared across all domains
└── UUID scheme: 00000000-0000-4001-a000-*

Layer 2: Domain Templates (PER-DOMAIN)
├── IT Ops: Service, Database, Incident, Runbook, etc.
├── Maritime: Vessel, Port, Cargo, Route, etc.
├── Healthcare: Patient, Diagnosis, Treatment, etc.

Layer 3: Tenant Extensions (PER-CUSTOMER)
├── Customer-specific entity types
└── Must inherit from Layer 1 or Layer 2
```

The ontology schema lives in the `ontology` PostgreSQL schema:
- `ontology.types` — entity type definitions (`type_name`, `layer`, `display_name`, `description`, `status`, `confidence`, `version`)
- `ontology.relations` — relationship type definitions (`relation_type`, `source_type_id`, `target_type_id`, `cardinality`, `status`)
- Supporting tables: `canonical_entity_types`, `canonical_relations`, `type_migrations`, `type_translation`, `approval_requests`

#### What Was Built in Phase 3

- `--use-ontology` flag on `scripts/run_vault_extraction.py` routes to `OntologyCentricPipeline`
- Ontology-centric pipeline stages directly to KG (bypasses the standard consensus phase)
- Gardener validates entity and relationship types against the ontology before promotion
- Loaded 1,026 entity types and 230 relationship types into Gardener's validation cache
- `ontology_candidates` table tracks relationship types the LLM proposes that aren't in the ontology (PENDING/APPROVED/REJECTED)

#### The Evidence Layer

Built as a Phase 3 sub-initiative:

- `evidence_records` table: links every extracted fact to the exact `source_span` text that justifies it
- `fact_verifications` table: stores LLM verification verdicts (VERIFIED/UNVERIFIED/DISPUTED) with reason and confidence
- `verified` boolean column on entities and relationships
- `VerificationWorker`: CLI worker that queries unverified facts, calls LLM to verify, updates `verified` column
- Gardener requires `verified = true` before STAGING → TRUSTED promotion (configurable via `GardenerConfig.require_verification_for_promotion`)
- ContextBundle shows `[VERIFIED]`/`[UNVERIFIED]` badges for every entity and relationship shown to the reasoning LLM

#### Supply-Chain Schema (Added This Session)

After discovering CUSTOMER_OF was missing from the ontology, the following were seeded into `ontology.relations`:

| Relation Type | Display Name | Status |
|---|---|---|
| SUPPLIES | Supplies | ACTIVE |
| CUSTOMER_OF | Customer Of | ACTIVE |
| SUPPLIER_OF | Supplier Of | ACTIVE |
| SUPPLIES_TO | Supplies To | ACTIVE |

Migration file: `migrations/017_add_supply_chain_relations.sql`

---

## Agent Inventory

| Agent | File | Purpose |
|-------|------|---------|
| GraphBuilderAgent | `graph_builder.py` | Extracts entities/relationships from documents → STAGING |
| GraphLoaderAgent | `graph_loader.py` | Bulk loads structured data into tri-memory |
| StagingValidatorAgent | `staging_validator.py` | Validates STAGING facts against schema rules |
| RetrievalAgent | `retrieval.py` | Queries all 3 memory layers, builds ContextBundle |
| ReasoningAgent | `reasoning.py` | LLM reasoning with 3-phase confidence calibration |
| ValidationAgent | `validation.py` | Checks reasoning against symbolic rules |
| GardenerAgent | `gardener.py` | 5-pass lifecycle management |
| IdentityResolver | `identity_resolver.py` | Detects and merges duplicate entities |
| EntityResolver | `entity_resolver.py` | 3-stage query→entity resolution |
| QueryClassifier | `query_classifier.py` | Classifies queries, checks data sufficiency |
| ToolAgent | `tool_agent.py` | Function-calling agent with KG + document tools |
| RoleResolver | `role_resolver.py` | 3-stage role resolution ("Who is the CEO?") |
| AnchorResolver | `anchor_resolver.py` | Auto-detects primary organization via graph centrality |
| RelationshipFirstRetriever | `relationship_first_retriever.py` | Traverses graph from anchor org outward |
| FailureAnalyzer | `failure_analyzer.py` | 7-layer failure tracing + fix plan generation |
| TargetedExtractor | `targeted_extractor.py` | Specialized extraction prompts per failure category |
| ImprovementLoop | `improvement_loop.py` | Orchestrates analyze → extract → apply → test cycle |
| VerificationWorker | `verification_worker.py` | LLM-verifies unverified facts in batches |
| CoherenceChecker | `coherence_checker.py` | Shadow-mode post-response contradiction detection |

---

## Technology Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| Web Framework | Flask | Two services: Platform (5000), Brain (3000) |
| Database | PostgreSQL | Single DB with pgvector extension |
| Vector Store | pgvector | All embeddings — NOT ChromaDB, NOT Neo4j |
| Embeddings | OpenAI text-embedding-3-small | 1536-dimensional |
| LLM (Primary) | OpenAI gpt-4o-mini | Primary extraction and reasoning |
| LLM (Vision) | Anthropic Claude Sonnet 4 | Complex PDFs + consensus building |
| Background Jobs | Python threading + PostgreSQL | NOT Celery, NOT Redis |
| Fuzzy Matching | rapidfuzz | Entity resolution |
| Deployment | Gunicorn | WSGI server |
| Auth | Magic Link, API Keys, JWT, Google OAuth | Four auth methods |

**Explicitly NOT used:** Neo4j, ChromaDB, FastAPI, Celery, Redis. Everything in PostgreSQL — unified storage eliminates sync issues.

---

## What Has Worked — Successes

### 1. Zero Hallucination Rate

The Data Gates architecture prevents the LLM from being called when evidence is insufficient. The system explicitly returns "Entity not found," "Insufficient data," or "I don't know" rather than fabricating. Hallucination rate: **0% across all evaluations.**

### 2. Beat GraphRAG 12–3

In a 100-query A/B evaluation against Microsoft GraphRAG on the ClaudeCode Nexus Industries corpus:

| Metric | Context Foundry | GraphRAG | Difference |
|--------|----------------|----------|------------|
| Head-to-head wins | 12 | 3 | CF wins |
| Provenance score | 2.32/3 | 0.13/3 | **18× better** |
| Relationship citations | 32% | 10% | **3× better** |
| Rule citations | 100% | 3% | **33× better** |
| Response detail | 5,602 chars | 322 chars | **17× more** |
| Hallucination rate | 0% | Not measured | CF wins |

GraphRAG returned confident-sounding wrong answers. CF returned honest answers with explicit uncertainty.

### 3. 87% Accuracy on 100-Question Corpus

The ClaudeCode Nexus Industries corpus (100 questions, 100-document enterprise knowledge base) reached **87/100 questions passing** with zero hallucinations. Trajectory: 82% baseline → 84% → 87% through systematic extraction improvements.

### 4. Supply-Chain Directionality Correct

The extraction pipeline correctly identifies suppliers as source and customers as target in SUPPLIES relationships. In this session's diagnostic on vault `176a4fb2`: Nel Hydrogen, Honeywell, Collins, First Solar, JinkoSolar, and General Atomics all correctly appear as sources supplying Boeing as the target. Boeing and Lockheed never appear as sources — they are correctly identified as customers. The direction semantics are right.

### 5. Gardener Lifecycle Works

The 5-pass Gardener cycle correctly promotes facts from STAGING to TRUSTED based on type-weighted confidence thresholds, runs every 5 minutes in the background, and enforces ontology type validation before promotion.

### 6. Evidence Layer Fully Wired

Evidence records are captured at extraction time, the verification worker verifies facts via LLM, and the Gardener enforces verification before promotion. The ContextBundle shows verified/unverified badges. A complete evidence chain exists from source text → knowledge graph → reasoning.

### 7. Test Infrastructure Robust

The test runner handles state machine progression, heartbeat timeout detection (5-minute window), progress checkpointing (resume interrupted runs), per-question trace logging, and a full web UI with history, vault selection, and real-time progress.

### 8. Multi-Vault Isolation Solid

Every query, extraction, and Gardener cycle is scoped to a `tenant_id`. Multiple vaults run independently with no data leakage.

### 9. Ontology Schema Now Has Full Supply-Chain Types

CUSTOMER_OF, SUPPLIER_OF, SUPPLIES_TO, and SUPPLIES are all ACTIVE in `ontology.relations`. The schema is ready to accept these types from extraction. Migration `017_add_supply_chain_relations.sql` is correct and idempotent.

---

## What Is Currently Broken or Incomplete

### 1. CUSTOMER_OF Never Gets Extracted

The LLM extraction prompt includes instructions and examples for CUSTOMER_OF, but the model consistently outputs SUPPLIES for everything supply-chain related. Zero CUSTOMER_OF relationships exist in any vault's knowledge graph. The schema is ready but the extraction prompt is not strong enough to force the distinction.

**Diagnostic evidence:** `raw_customer_of = 0, final_customer_of = 0` across all relationships in vault `176a4fb2`.

### 2. Customer Profile Documents Extract Wrong Targets

- `01_boeing_customer_profile.md` → produces `Nexus Aerospace → AeroMaterials (SUPPLIES)` instead of `Nexus Aerospace → Boeing (SUPPLIES)`
- `14_lockheed_martin_customer.md` → produces `Nexus → F-35 Block 4`, `Nexus → NGAD (6th Gen Fighter)`, `Nexus → Hypersonic Missile` instead of `Nexus → Lockheed Martin`

The LLM is anchoring on the nearest concrete noun (program name) rather than identifying the customer organization. The supply relationship to the actual customer is not captured from customer-profile documents.

### 3. Nel Hydrogen Supplier Document Produces Zero Supply-Chain Edges

`09_nel_hydrogen_supplier.md` — a document explicitly about a supplier — produced zero supply-chain relationships. The Nel Hydrogen → Boeing relationship only appears in `12_supplier_performance_review.md`. Something in the document structure causes extraction to completely miss it.

### 4. raw_relationship_type Always Null

The ontology pipeline writes directly to `relationship_type` without recording what the LLM originally output in `raw_relationship_type`. Confirmed: all 584 relationships in vault `176a4fb2` have `raw_relationship_type = NULL`. This means:
- Cannot audit what the LLM originally said before normalization
- Type normalization/mapping cannot be traced
- If the LLM outputs a variant (e.g., "CUSTOMER" vs "CUSTOMER_OF"), you cannot see it happened
- The raw LLM output is silently discarded

### 5. Boeing Entity Fragmented Across 7 Entries

Boeing appears as seven separate entities:

| Entity Name | Entity Type |
|---|---|
| Boeing | COMPETITOR |
| Boeing Commercial Airplanes | CUSTOMER |
| Boeing workforce constraints | INCIDENT |
| Boeing Programs Investment | INVESTMENT |
| boeing.account@nexus-aerospace.com | KEY_CONTACT |
| The Boeing Company | ORGANIZATION |
| Boeing Programs | PROJECT |

These should be one ORGANIZATION with the others as properties or sub-entities. Entity resolution is not merging them. The same fragmentation almost certainly exists for Lockheed Martin and other major entities.

### 6. Nexus and Nexus Industries Are Two Separate Entities

Diagnostic showed: `Nexus Industries` (ORGANIZATION, 29 edges) and `Nexus` (ORGANIZATION, 28 edges) exist as two separate entities. They are the same company. This causes split context — some relationships point to "Nexus Industries," others to "Nexus," so queries about the organization miss half their relevant connections.

### 7. Nexus Divisions Typed as TEAM Instead of ORGANIZATION/DIVISION

`Nexus Advanced Materials`, `Nexus Aerospace`, and `Nexus Energy Systems` are all typed as TEAM. They are business divisions. Type-based routing and filtering will mismatch them — a query asking "Which division supplies to SpaceX?" would not find them if it's looking for ORGANIZATION or DIVISION typed entities.

### 8. Test Workflows Fail on Cold Start

All four test workflows (ClaudeCode Nexus, Manus Orion, ClaudeCode Medsync, Ontology Vault) fail with "Connection refused" when launched from Replit's workflow panel. They start simultaneously with the server and try to authenticate before Flask is up. There is no retry/wait logic — the runner fails immediately on first connection attempt.

**Error seen:** `HTTPConnectionPool(host='localhost', port=5000): Max retries exceeded... [Errno 111] Connection refused`

### 9. 13 Failing QA Questions at 87% — Root Causes

The remaining 13 failures are architectural:

**Role Resolution Failures (4):**
- Q37: Director of GreenHydrogen → David Park (multi-hop not triggering in Stage 0)
- Q75: VP of Engineering for Nexus Digital Solutions → Dr. Alan Chen (role entity returns position, not person)
- Q91: VP Trade Compliance (returns multiple VPs instead of following relationship)
- Q68: Who chairs Export Control Committee → VP Trade Compliance (role→person lookup incomplete)

**Multi-Entity Aggregation Failures (3):**
- Q29: Executive Team members list (incomplete aggregation)
- Q34: Project with largest budget (multiple budget values, wrong selection)
- Q100: Total value of top 3 customers (summing not working correctly)

**Financial/Numeric Retrieval Failures (3):**
- Q66: FY2026 capex (wrong fiscal year data retrieved)
- Q79: 2030 revenue target (document text preferred over KG)
- Q45: When Victoria Chen became CEO (temporal relationship not extracted)

**Ambiguous Entity Resolution Failures (3):**
- Q14: When Robert Kim was appointed (multiple Robert Kims, wrong one selected)
- Q32: CEO of Toyota JV (JV entity not linked to leadership)
- Q71: Mining automation partner (Caterpillar relationship not retrieved)

### 10. 9 LSP Diagnostics in persistence.py

`src/test_runner/persistence.py` has 9 unresolved static analysis warnings. Not yet investigated.

### 11. GitHub Sync Not Working

Repository has a GitHub remote (`origin: https://github.com/SalehHamed1978UAE/contextfoundry.git`) but sync is not working. A `.git/index.lock` file was detected, indicating a previous git operation didn't finish cleanly, which blocks new commits and pushes.

### 12. No Regression Baseline Available

The C5 regression diff query confirmed the old baseline vault (`4668fc6d`) has zero relationships for the 5 diagnostic slice documents — it was deleted. Without a working baseline vault, there is no apples-to-apples comparison for the current ontology extraction run.

---

## Where Things Stand

The system has a sound architecture, a proven track record against GraphRAG, and an 87% accuracy ceiling with zero hallucinations. The current blockers are all in the extraction layer:

1. The LLM is not using CUSTOMER_OF — it maps everything to SUPPLIES
2. Customer-profile documents extract program names as targets instead of the customer organization
3. Entity fragmentation (Boeing → 7 entries, Nexus → 2 entries) prevents unified context assembly

Fixing these three extraction issues — combined with the role resolution multi-hop work already coded and sitting ready — would be the clearest path to breaking through the 87% ceiling toward 90%+.

---

*Context Foundry — "Intelligence requires a world model. This is that world model."*
