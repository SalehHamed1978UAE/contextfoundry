# Context Foundry - Cognitive Operating System for the Enterprise

## Overview
Context Foundry is a Cognitive Operating System for the Enterprise designed to build a dynamic "World Model." This system compounds knowledge over time, is grounded in verifiable sources, and maintains trustworthiness by admitting uncertainty. Its primary purpose is to provide a domain-agnostic, single substrate for all enterprise AI applications, enabling AI to reason over structured truth, eliminate hallucination, and deliver reliable, context-aware answers. The project aims to give AI systems a coherent, evolving understanding of organizational reality, moving beyond static knowledge representations to a system that learns and adapts continuously.

## User Preferences
- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

## System Architecture
Context Foundry is built around a **Tri-Memory System** (Semantic, Episodic, Symbolic Memory) and a **Fact Lifecycle** (STAGING, TRUSTED, ARCHIVED) with metadata such as `_layer`, `_confidence`, `_sources`, and `_lifecycle`. A core principle is **Context-Attached Knowledge**, enriching relationships with temporal validity and provenance. The system assembles a **Context Bundle** for AI applications, packaging focal entities, relationships, rules, and a confidence summary.

Key agents include `GraphBuilderAgent`, `RetrievalAgent`, `ReasoningAgent`, `ValidationAgent`, `GardenerAgent`, and `QueryTimeSemanticAgent`. The **Query Flow** involves parsing, entity resolution, context bundle retrieval, LLM reasoning, symbolic validation, and response generation with confidence and provenance.

Architectural features include:
- **Tenant Context and RLS**: Enhanced `TenantSession` for Row-Level Security.
- **Query Pipeline**: Features `QueryClassifier`, `RoleResolver` (3-stage), and `RetrievalRouter` (GRAPH_ONLY, DOCS_ONLY, HYBRID).
- **Implicit Role Extraction**: `GraphBuilder` automatically creates `HOLDS_POSITION` relationships.
- **QA Verifier**: Two-layer verification (structural rules + LLM semantic check).
- **Dynamic Confidence Scoring**: Computed scores based on answer quality and evidence.
- **Source Attribution**: Extracts and displays sources from various tools. Knowledge graph relationship sources now include the original document filename (via platform.documents JOIN).
- **Deterministic Document Fallback**: Automatic document search when KG lacks data.
- **Context Injection**: Passes `vault_context` for target entity resolution.
- **Extraction Hardening**: Post-processor (`ExtractionPostProcessor`) uses regex patterns to catch missed relationships.
- **Role→Attribute/Relationship Query Chaining**: Rewrites role-based queries, handling single/multi-matches.
- **Ambiguity Detection & Disambiguation**: Generalized pattern for handling multiple entity matches using `AmbiguityResult` and a `DisambiguationReasoner`.
- **Extraction Job Tracking System**: Monitors extraction jobs with automatic timeout detection, retry logic (circuit breaker), and verification.
- **Ontology Foundry (Phase 1)**: Identifies unknown relationship/entity types as candidates.
- **Learning Flow**: Adaptive system that detects query gaps, prioritizes learning tasks, and performs targeted extraction.
- **QA Validation Module**: Provides consistent checks across response paths for issues like financial metric distinction, pre-calculated value detection, temporal/year mismatch, and metric type validation.
- **Coherence Checker (Shadow Mode)**: Post-response validation system with checks for `MultipleValues`, `TerminologyMismatch`, `LogicalContradiction`, and `SourceCoverage`.
- **Spreadsheet/Financial Integration**: Auto-detects and processes spreadsheet files, extracts financial metrics, and pre-computes financial calculations.
- **Stale Request Auto-Recovery**: Automatically recovers `extraction_requests` stuck in "processing" after server restarts.
- **Parallel Extraction Workers**: Uses `ThreadPoolExecutor` for increased throughput.
- **Orphaned Entity Auto-Cleanup**: Cleans up entities from deleted tenants on brain startup.
- **Spreadsheet Entity Extraction**: Extracts PERSON and CLIENT entities with properties and relationships from spreadsheets.
- **Graph-Only Entity Fallback**: Provides direct entity+properties lookup for spreadsheet-extracted entities when document chunks are unavailable.
- **Dynamic Entity Type Handling**: Replaced corpus-specific entity types with generic `ORGANIZATIONAL_UNIT` with a `subtype` property for flexibility.
- **Text Sanitization (NUL Character Fix)**: Centralized `sanitize_text()` utility removes NUL (0x00) and problematic ASCII control characters at storage boundaries before PostgreSQL insertion.
- **Tri-Memory Precedence Pipeline**: Implements "Symbolic > Semantic > Episodic" precedence hierarchy (`PrecedencePipeline`).
- **Symbolic Override Engine**: Rule-based system that can override, augment, constrain, or prohibit semantic answers (`SymbolicOverrideEngine`).
- **Data Gates ("Refuse to Hallucinate")**: Three-level validation system detecting entity not found, no relevant chunks, and ungrounded answers. Uses hedging/fabrication pattern detection (`DataGates`).
- **Test Runner Dashboard**: Provides a web UI (`/test-runner`) for monitoring and controlling automated tests. Features vault selection, a 5-stage pipeline visualization (Delete → Create → Upload → Extract → Q&A), question set management, history actions (resume, view results, retry), live progress monitoring, and mode selection (Auto/Fresh). Test runs are persistent and resumable with database-backed status tracking and heartbeat mechanisms.
- **Multi-Model Extraction Pipeline** (January 2026):
  - **Phase 0 Ontology Schema** (`src/context_foundry/ontology/`): Defines 16 entity types (PERSON, ORGANIZATION, BUSINESS_UNIT, PROJECT, PRODUCT, SERVICE, CUSTOMER, SUPPLIER, PARTNER, FINANCIAL_METRIC, LOCATION, FACILITY, POLICY, TECHNOLOGY, CONCEPT, DOCUMENT) and 20+ relationship types with validation.
  - **Phase 1 Multi-Model Extraction** (`src/context_foundry/extraction/multi_extractor.py`): Dual-model extraction using GPT-4o-mini and Claude Sonnet for redundant entity/relationship extraction with consensus building.
  - **Batch Extraction Runner** (`scripts/run_multi_extraction.py`): Processes entire corpora, stores outputs per model in `extraction_outputs/{vault_id}/{model}/`.
  - **Partial Parse Recovery**: Fallback regex parsing for incomplete JSON responses with metadata flag for down-weighting.
  - **Document Truncation**: Large documents (>15k chars) truncated to avoid token limits with metadata flag.
- **Retrieval Robustness Improvements** (January 2026):
  - **Per-Question Trace Logging**: Captures retrieved files, semantic scores, query_type, and match_type to JSONL traces for debugging retrieval quality.
  - **Keyword+Semantic Fusion**: When semantic scores < 0.4, applies canonical term boosting for project names, business units, and executives using config-driven terms.
  - **Folder Weighting**: Source priority scoring (strategy > finances > operations > meeting_notes) integrated into document ranking via `authority_config`.
  - **Authority Config** (`config/authority_map.json`): Defines fact type authorities, folder priorities, and canonical terms with per-corpus overrides.
  - **Evaluator Entity Aliases**: Supports abbreviation matching (e.g., "GDS" ↔ "Global Defense Systems") in answer evaluation.
  - **Detailed Failure Categories**: Evaluator classifies failures as `ALTERNATE_SOURCE`, `FORMAT_MISMATCH`, `NOT_FOUND` instead of generic mismatch.
  - **Person-Role/Org-Unit Query Routing Override**: QueryClassifier now detects person-role queries (e.g., "What is Sarah Chen's role?") and org-unit queries (e.g., "What are the business units?") with proper name validation (`_is_proper_name()`) to prioritize Knowledge Graph routing with HYBRID fallback. Prevents false positives on generic queries like "Who is the CEO?" which use existing role resolution.

## External Dependencies
- **Database:** PostgreSQL (with pgvector)
- **LLM:** OpenAI `gpt-4o-mini`
- **Vision LLM:** Anthropic Claude Sonnet 4
- **Vector Embeddings:** `text-embedding-3-small`
- **Web Framework:** Flask
- **Deployment:** Gunicorn
- **Authentication:** Magic Link, API Keys, JWT Sessions, Google OAuth