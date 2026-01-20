# Context Foundry - Cognitive Operating System for the Enterprise

## Overview
Context Foundry is a Cognitive Operating System for the Enterprise. Its core purpose is to build a dynamic "World Model" that compounds knowledge over time, is grounded in verifiable sources, and remains trustworthy by admitting uncertainty. The project aims to create a domain-agnostic, single substrate for all enterprise AI applications, enabling AI to reason over structured truth, eliminate hallucination, and provide reliable, context-aware answers. It provides AI systems with a coherent, evolving understanding of organizational reality, moving beyond static knowledge representations to a system that learns and adapts.

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
- **Source Attribution**: Extracts and displays sources from various tools.
- **Deterministic Document Fallback**: Automatic document search when KG lacks data.
- **Context Injection**: Passes `vault_context` for target entity resolution.
- **Extraction Hardening**: Post-processor (`ExtractionPostProcessor`) uses regex patterns to catch missed relationships.
- **Role→Attribute/Relationship Query Chaining**: Rewrites role-based queries, handling single/multi-matches and preventing chaining for policy intent.
- **Ambiguity Detection & Disambiguation**: Generalized pattern for handling multiple entity matches using `AmbiguityResult` and a `DisambiguationReasoner`.
- **Extraction Job Tracking System**: Monitors extraction jobs with automatic timeout detection, retry logic (circuit breaker), and verification.
- **Ontology Foundry (Phase 1)**: Identifies unknown relationship/entity types as candidates.
- **Learning Flow**: Adaptive system that detects query gaps, prioritizes learning tasks, and performs targeted extraction.
- **QA Validation Module**: Provides consistent checks across response paths for issues like financial metric distinction, pre-calculated value detection, temporal/year mismatch, and metric type validation.
- **Coherence Checker (Shadow Mode)**: Post-response validation system with checks for `MultipleValues`, `TerminologyMismatch`, `LogicalContradiction`, and `SourceCoverage`.
- **Spreadsheet/Financial Integration**: Auto-detects and processes spreadsheet files, extracts financial metrics, and pre-computes financial calculations.
- **Stale Request Auto-Recovery**: Automatically recovers `extraction_requests` stuck in "processing" after server restarts.
- **Parallel Extraction Workers**: Replaced single-threaded extraction with `ThreadPoolExecutor` for increased throughput.
- **Orphaned Entity Auto-Cleanup**: Cleans up entities from deleted tenants on brain startup.
- **Spreadsheet Entity Extraction**: Extracts PERSON and CLIENT entities with properties and relationships from spreadsheets.
- **Graph-Only Entity Fallback**: Provides direct entity+properties lookup for spreadsheet-extracted entities when document chunks are unavailable.
- **Dynamic Entity Type Handling**: Replaced corpus-specific entity types with generic `ORGANIZATIONAL_UNIT` with a `subtype` property for flexibility.
- **Text Sanitization (NUL Character Fix)**: Centralized `sanitize_text()` utility removes NUL (0x00) and problematic ASCII control characters at storage boundaries before PostgreSQL insertion, preventing silent chunk storage failures from Excel/spreadsheet extraction.
- **Tri-Memory Precedence Pipeline**: Implements "Symbolic > Semantic > Episodic" precedence hierarchy (`PrecedencePipeline` in `src/context_foundry/pipeline/precedence_pipeline.py`).
- **Symbolic Override Engine**: Rule-based system that can override, augment, constrain, or prohibit semantic answers (`SymbolicOverrideEngine` in `src/context_foundry/memory/symbolic_override.py`).
- **Data Gates ("Refuse to Hallucinate")**: Three-level validation system detecting entity not found, no relevant chunks, and ungrounded answers. Uses hedging/fabrication pattern detection (`DataGates` in `src/context_foundry/validation/data_gates.py`).

## Recent Changes
- **Jan 20, 2026**: **State Machine Implementation** - Implemented formal state machine per specification:
  - `TestRunStatus` enum with 7 states: CREATING_VAULT, UPLOADING, EXTRACTING, RUNNING_QA, COMPLETE, FAILED, INTERRUPTED
  - Valid transitions table enforced by `transition_to()` function (the ONLY way to change status)
  - Fresh mode: starts with vault_id=NULL, status=CREATING_VAULT → creates vault → transitions to UPLOADING with vault_id set
  - Auto mode: starts with vault_id set, status=RUNNING_QA (skips delete/create/upload/extract)
  - Heartbeat stale detection (5 minutes) automatically marks tests as INTERRUPTED on startup
  - Resume only allowed from INTERRUPTED status
  - Database is single source of truth - no PID/status.json inference
  - Schema updated: vault_id now nullable, current_question JSONB column added
- **Jan 20, 2026**: **Fresh Mode Fixes** - Fixed critical bugs in the test runner Fresh mode:
  - Fixed delete_vault call: Now uses `find_vault_by_name()` to look up correct vault ID by name before deletion
  - Fixed corpus folder path resolution: Uses `config.get_corpus()` to get root_path from config (with fallback)
  - Added robust connection retry logic: `get_vault_stats()` now uses `_get_vault_stats_with_retry` with 5 retries, timeout handling, and re-authentication on connection errors
  - Fresh mode now correctly finds 114 files in "Manus Healthtec" corpus
- **Jan 20, 2026**: **State Management Refactoring** - Made database the single source of truth for test status:
  - Eliminated conflicting sources of truth between DB and status.json
  - Added try/finally in runner.py to ensure complete_test_run() always called
  - Added startup cleanup: marks all running tests as interrupted on server restart
  - New endpoints: `/api/test-runner/health` (status), `/force-clear` (reset stuck), `/reset` (full cleanup)
  - Removed all PID-based state inference - status derived exclusively from DB
  - Made status.json ephemeral (deleted on completion/failure/startup)
  - 60-second per-query timeout verified working (Q196 timeout handled gracefully)
  - CLI test result: **198/235 (84.3%)** on Manus Healthtec vault
- **Jan 20, 2026**: **Subprocess Output Buffering Fix** - Fixed test subprocess hanging issues:
  - Added `log()` function with explicit `sys.stdout.flush()` in test_executor.py and runner.py
  - Subprocess output now visible in log files immediately (not buffered)
  - Question IDs now use consistent loop index (i+1) for reliable resume matching
  - Log files at `test_results/test_run_<id>.log` show real-time progress
- **Jan 20, 2026**: **Test Run Persistence & Resume** - Made test runs survive server restarts:
  - Database persistence: Test runs saved to DB immediately when started (not just on completion)
  - Heartbeat mechanism: Progress updated after each question with heartbeat timestamp (migration 024)
  - Interrupted detection: Stale heartbeat (>30s) automatically marks test as "interrupted"
  - Resume functionality: Resume button continues from last answered question
  - Validation: Resume validates ownership (vault_id, question_set_id) and status
  - UI: Interrupted status shows Resume button with clear progress message
- **Jan 20, 2026**: **Test Results Download** - Added ability to view and download test results files:
  - API endpoints: `/api/test-runner/results-files` (list) and `/results-files/<filename>` (download)
  - Secure file access with path traversal protection (regex validation, resolved paths)
  - UI: Download button in Test History for completed/interrupted tests
  - Auto-matching by vault ID prefix and name with fallback file picker modal
- **Jan 20, 2026**: **Vault-Scoped Question Sets** - Redesigned question sets from global to vault-specific:
  - Added `vault_id` column to `question_sets` table with unique constraint `(vault_id, name)` (migration 022)
  - API endpoints require vault_id for all operations (upload, list, get, delete)
  - Security: Vault ownership validation prevents cross-vault access/deletion
  - UI: Question set dropdown appears only after vault selection, with inline upload button
  - Supports JSON, JSONL, and Markdown file formats for question set uploads
- **Jan 20, 2026**: Enhanced **Test Runner Dashboard** (`/test-runner`) with full spec compliance:
  - **Vault Selection**: Dropdown to select existing vaults with entity counts
  - **5-Stage Pipeline Visualization**: Delete → Create → Upload → Extract → Q&A with live status icons
  - **Question Sets Management**: Per-vault question sets with View/Delete actions
  - **History Actions**: Resume interrupted tests, View Results, Retry failed tests
  - **Live Progress Monitoring**: Real-time Q&A progress with current question display
  - **Mode Selection**: Auto (use existing vault) or Fresh (rebuild with corpus folder)
  - **Status Tracking**: Centralized `status.py` module with proper lifecycle transitions (running→finished/failed)
  - API endpoints: `/api/test-runner/vaults`, updated `/start`, question sets CRUD
  - Database tables: `question_sets`, `test_runs`, `test_results` (migrations 021, 022)
- **Jan 19, 2026**: Latest 235Q test run achieved **92.3% accuracy (217/235 passed)** on the MedSync Health test suite. Test infrastructure validated with 30-minute extraction timeout for 114-document corpus. Results saved to `test_results/medsync_health_235q_results.json`.
- **Jan 19, 2026**: Validated tri-memory precedence pipeline with **91.5% accuracy (215/235 passed)** on the MedSync Health 235-question test suite. Precedence metadata now exposed in all API responses (`/api/vault/chat`):
  - `answer_source`: Where the answer came from (symbolic/semantic/episodic/refused)
  - `gate_blocked`: Whether a data gate blocked the answer
  - `gate_name`: Which gate blocked (if any)
  - `precedence_applied`: Whether precedence override was applied
  - `precedence_confidence`: Confidence from precedence pipeline
- **Jan 19, 2026**: Integrated tri-memory thesis validation components: Symbolic Override Engine, Data Gates, and Precedence Pipeline. Added seed script for test rules (`scripts/seed_test_rules.py`).
- **Jan 19, 2026**: Added standardized test infrastructure (`src/test_runner/`) for automated corpus testing with fuzzy evaluation, vault lifecycle management, and CLI interface. Run with `python -m src.test_runner.runner --list` or `--corpus <name>`.
- **Jan 2026**: Fixed critical NUL character bug that prevented Excel spreadsheet chunks from being stored. Test accuracy improved from 78.3% to 91.5% (+13.2 percentage points).

## Test Infrastructure
The test runner in `src/test_runner/` provides:
- **One-command testing**: `python -m src.test_runner.runner --corpus medsync_health`
- **Web Dashboard**: `/test-runner` page for monitoring and controlling tests from the UI
- **Vault lifecycle**: Automatic vault creation/deletion, document upload, 3-phase extraction waiting
- **Fuzzy evaluation**: Semantic answer matching (numbers, percentages, uncertainty phrases)
- **Results tracking**: JSON output with accuracy metrics and failure analysis
- **Checkpoint resume**: Automatic resume from last answered question on restart
- **Configuration**: `src/test_config.json` defines corpora, paths, and settings
- **API endpoints**: `/api/test-runner/*` for programmatic access (requires authentication)

## External Dependencies
- **Database:** PostgreSQL (with pgvector)
- **LLM:** OpenAI `gpt-4o-mini`
- **Vision LLM:** Anthropic Claude Sonnet 4
- **Vector Embeddings:** `text-embedding-3-small`
- **Web Framework:** Flask
- **Deployment:** Gunicorn
- **Authentication:** Magic Link, API Keys, JWT Sessions, Google OAuth