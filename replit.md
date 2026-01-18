# Context Foundry - Cognitive Operating System for the Enterprise

## Overview
Context Foundry is a Cognitive Operating System for the Enterprise designed to provide AI systems with a coherent, evolving understanding of organizational reality. Its core purpose is to build a dynamic "World Model" that compounds knowledge over time, is grounded in verifiable sources, and remains trustworthy by admitting uncertainty. The project aims to create a domain-agnostic, single substrate for all enterprise AI applications, moving beyond static knowledge representations to a system that learns and adapts, ultimately enabling AI to reason over structured truth, eliminate hallucination, and provide reliable, context-aware answers.

## User Preferences
- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

## System Architecture
Context Foundry is built around a **Tri-Memory System** consisting of Semantic Memory (knowledge graph), Episodic Memory (event timelines), and Symbolic Memory (rules, constraints). Facts within the system follow a **Fact Lifecycle** (STAGING, TRUSTED, ARCHIVED) and include `_layer`, `_confidence`, `_sources`, and `_lifecycle` metadata.

A core principle is **Context-Attached Knowledge**, where relationships are enriched with metadata like temporal validity and provenance. The system assembles a **Context Bundle** for AI applications, packaging focal entities, relationships, rules, and a confidence summary.

Key agents include:
- **GraphBuilderAgent**: Extracts entities and relationships.
- **RetrievalAgent**: Assembles the Context Bundle.
- **ReasoningAgent**: Utilizes LLMs over the Context Bundle.
- **ValidationAgent**: Applies symbolic rules.
- **GardenerAgent**: Maintains knowledge graph quality.
- **QueryTimeSemanticAgent**: Orchestrates retrieval and reasoning.

The **Query Flow** involves parsing, entity resolution, context bundle retrieval, LLM reasoning, symbolic validation, and response generation with confidence and provenance.

Architectural features include:
- **Tenant Context and RLS**: Enhanced `TenantSession` for Row-Level Security.
- **Query Pipeline**: Features `QueryClassifier`, `RoleResolver` (3-stage with fuzzy matching and document search), and `RetrievalRouter` (GRAPH_ONLY, DOCS_ONLY, HYBRID strategies with fallback).
- **Implicit Role Extraction**: `GraphBuilder` automatically creates `HOLDS_POSITION` relationships.
- **QA Verifier**: Two-layer verification (structural rules + LLM semantic check) for answer quality.
- **Dynamic Confidence Scoring**: Computed scores based on answer quality and evidence.
- **Source Attribution**: Extracts and displays sources from various tools.
- **Deterministic Document Fallback**: Automatic document search when KG lacks data.
- **Context Injection**: Passes `vault_context` for target entity resolution.
- **Extraction Hardening**: Post-processor (`ExtractionPostProcessor`) uses regex patterns to catch missed relationships (e.g., HOLDS_POSITION, HAS_COMPENSATION) after LLM extraction.
- **Role→Attribute/Relationship Query Chaining**: Query pipeline rewrites role-based queries (e.g., "CEO's salary") into person-specific queries, handling single and multi-matches with context prioritization.
- **Ambiguity Detection & Disambiguation**: Generalized pattern for handling multiple entity matches using `AmbiguityResult` and a `DisambiguationReasoner` (LLM-based) to determine the best match or request user clarification.
- **Extraction Job Tracking System**: Monitors extraction jobs with automatic timeout detection, retry logic (circuit breaker), and verification. It uses `ExtractionJobTracker`, `ExtractionCircuitBreaker`, and `ExtractionMonitor` to manage job lifecycle, retries, and health.
- **Ontology Foundry (Phase 1)**: A learning system that identifies unknown relationship/entity types as candidates, stores them in a `CandidateStore` with evidence and confidence, and routes them for potential future approval, preventing ingestion of unapproved types into the main KG.
- **Learning Flow**: An adaptive learning system that detects query gaps (`GapDetector`), prioritizes learning tasks (`LearningQueueManager`), and performs targeted extraction (`TargetedExtractor`) to improve knowledge graph quality, learning from query failures and user feedback.
- **QA Validation Module**: Shared validation in `utils/qa_validation.py` provides consistent checks across all response paths:
  - Issue 2: Financial metric type distinction (net income vs EBITDA) - detects when EBITDA is returned for net income queries
  - Issue 3: Pre-calculated value detection - finds explicitly stated growth rates in documents
  - Issue 4: Temporal/year mismatch detection - warns when response references wrong fiscal year
  - Issue 6: Metric type validation (customer retention vs NRR) - ensures correct metric type is returned
- **Coherence Checker (Shadow Mode)**: Post-response validation system in `validation/coherence_checker.py` with 4 generalizable checks:
  - MultipleValuesCheck: Detects when sources contain multiple numeric values that could confuse the answer
  - TerminologyMismatchCheck: Flags when query terms don't match response terms (e.g., "retention" vs "NRR")
  - LogicalContradictionCheck: Identifies ambiguous patterns like "Close 150 (Target: 140)"
  - SourceCoverageCheck: Verifies answer numbers appear in source documents
  - Currently logs results without modifying responses (shadow mode for threshold tuning)

## Test Suites

Context Foundry has two distinct test suites for validating query accuracy:

### E2E Lifecycle Test (49 queries, 5 vaults)
- **Location:** `scripts/e2e_lifecycle_test.py` + `scripts/e2e_config.py`
- **Vaults:** TechVentures, Morrison & Sterling, Riverside Medical Center, Titan Manufacturing, Launchpad Ventures
- **Queries per vault:** 9-10 each (49 total)
- **Roadmap status:** 100% accuracy claimed

### NexaTech Q&A Bible (105 questions, 1 vault)
- **Location:** `attached_assets/context_foundry_bible_*.md` (validation document)
- **Test script:** `scripts/qa_accuracy_test.py`
- **Tenant ID:** `bbdef43c-2817-41dd-a5e4-0192893cbf19`
- **Current accuracy:** **99/105 (94.3%)** - Honest baseline without hardcoded rules (Jan 17, 2026)
- **Target:** 100/105 (95.2%)
- **Remaining failures:** 
  - Q15: Net margin improvement (20.3 percentage points) - calculation required
  - Q28: Customer count FY2024 (2,147) - retrieval issue
  - Q58: Customer retention rate (94%) - NRR vs retention confusion (coherence flagged)
  - Q59: Target new customers Q1 2024 (150 vs 140) - ambiguous OKR format
  - Q72: ISO 27001 certified (Yes) - retrieval issue
  - Q76: GDPR access requests 2024 - missing data

### MedSync Test Suites (CRITICAL MAPPING - DO NOT MIX UP)

**WARNING:** Three separate MedSync corpuses exist with identical company names. Always verify vault-to-test-folder mapping before running tests.

| Vault Name | Test Documents Folder | Company in Docs | Questions |
|------------|----------------------|-----------------|-----------|
| **Manus HealthTech** | `test_documents/medsync_health/` | MedSync Health, Inc. | 100 Q&A + 200 extended |
| **Manus MedSync** | `test_documents/manus_medsync/` | MedSync Health, Inc. | 100 Q&A + 200 extended |
| **claudecode medsync** | `test_documents/claudecode_medsync/` | MedSync Health, Inc. | 200 Q&A (qa_pairs.json) + 20 ambiguous cases |

**Before running any MedSync tests:**
1. Confirm which vault you're testing
2. Use the CORRECT test documents folder
3. Never mix test questions between vaults - they have identical company names but different test data

## Bible Validations Status (10 Things to Prove)

From the Context Foundry Bible, these validations need proof:

| # | Validation | Status |
|---|-----------|--------|
| 1 | Tri-memory outperforms single-memory | NOT PROVEN |
| 2 | Symbolic precedence matters | NOT PROVEN |
| 3 | Entity/relationship beats flat retrieval | PARTIAL |
| 4 | Shared context across apps | NOT PROVEN |
| 5 | Domain-independent abstraction | PARTIAL |
| 6 | Context portability | NOT PROVEN |
| 7 | Reduces development time | NOT PROVEN |
| 8 | Abstraction is complete | NOT PROVEN |
| 9 | Developers understand it | NOT PROVEN |
| 10 | Better enough to switch | NOT PROVEN |

## Roadmap Status (Jan 2026)

### Completed
- Core Extraction Pipeline ✅
- Entity Hygiene ✅
- Relationship Extraction ✅
- E2E Test Suite (5 vaults) ✅
- Extraction Job Tracking ✅
- Circuit Breaker ✅
- Background Monitor ✅
- Verification Layer ✅
- UI Status Indicators ✅
- **Learning Flow Integration ✅** (Jan 17, 2026)
  - Gap detection threshold: 70%
  - 24 NO_ANSWER patterns for response analysis
  - Validated: 5/5 queries → gaps detected → queue items created
- **QA Validation Module ✅** (Jan 17, 2026)
  - Centralized validation in `utils/qa_validation.py`
  - Financial metric mismatch detection (net income vs EBITDA)
  - Temporal/year mismatch warnings
  - Integrated into both ReasoningAgent and ToolAgent direct answer paths
  - Caveats now appear in API responses
- **Coherence Checker ✅** (Jan 17, 2026)
  - 4 generalizable checks: MultipleValues, TerminologyMismatch, LogicalContradiction, SourceCoverage
  - Integrated into tool_agent.py direct answer path
  - **Response modification enabled**: LOW/MEDIUM confidence answers include caveats
  - Caveat format: Confidence level (%), why, "Please verify against source documents"
  - Q58: MEDIUM (70%) - "Query asks for 'customer retention' but answer mentions 'nrr'"
  - Q59: MEDIUM (67%) - "Answer uses 140 but source shows 'Close 150 (Target: 140)'"
  - Bug fixes: source_chunks key ('content' not 'text'), year-filtering in LogicalContradictionCheck
  - Honest baseline: 99/105 (94.3%) without hardcoded metric rules
- **Spreadsheet/Financial Integration ✅** (Jan 17, 2026)
  - Integrated into existing upload flow (same endpoint, same UI)
  - Auto-detects file type (.xlsx, .xls, .csv) and routes to SpreadsheetLoader
  - SpreadsheetLoader: Parses multi-sheet Excel files, extracts financial metrics
  - FinancialCalculator: Pre-computes growth rates, margins, CAGR, ratios
  - FinancialQueryHandler: Answers financial queries from pre-calculated metrics (bypasses LLM)
  - Query priority: FinancialQueryHandler → RLM → Pipeline → LLM
  - Entities created: FINANCIAL_METRIC (raw values) + CALCULATED_METRIC (derived values)
  - Properties stored: value, unit, time_period, formula, metric_type, source_document
  - Eliminates LLM calculation errors for questions like "What was revenue growth FY23 to FY24?"
- **Stale Request Auto-Recovery ✅** (Jan 18, 2026)
  - Fixed gap where `extraction_requests` stuck in "processing" weren't recovered after server restart
  - New `recover_stale_requests()` method in ExtractionMonitor
  - Auto-resets requests stuck >10 minutes back to "pending" for retry
  - Runs on every scheduler cycle (30 seconds)
  - Prevents 10+ hour stalls when server idles or restarts

### Planned
- Ontology Foundry Phase 2 (Admin UI)
- Multi-Vault Queries
- Semantic Search Improvements

## External Dependencies
- **Database:** PostgreSQL (with pgvector)
- **LLM:** OpenAI `gpt-4o-mini`
- **Vision LLM:** Anthropic Claude Sonnet 4
- **Vector Embeddings:** `text-embedding-3-small`
- **Web Framework:** Flask
- **Deployment:** Gunicorn
- **Authentication:** Magic Link, API Keys, JWT Sessions, Google OAuth