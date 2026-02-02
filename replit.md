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
- Technical Specification extraction (11 generalizable patterns)
- 152 SPECIFICATION entities extracted
- Post-processor hardening for energy density, temperature, materials
- Multi-hop role traversal code (asset for future use)
- HAS_SPEC relationships added to KG

### Key Metrics
- **ClaudeCode Nexus Industries:** 87/100 questions passing (+3 from 84% baseline)
- **Hallucination Rate:** 0% (Data Gates enforced)
- **Provenance:** 18x better than GraphRAG baseline
- **Failure Analysis:** See `docs/ACCURACY_FAILURES_87.md`

### Next Roadmap Items
1. Evidence Layer Phase 3: Gardener integration for TRUSTED promotion based on verification status
2. Tree-based retrieval architecture
3. Ontology pipeline integration
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