# Context Foundry - Cognitive Operating System for the Enterprise

## Overview
Context Foundry is a Cognitive Operating System for the Enterprise designed to build a dynamic "World Model" that compounds knowledge over time, is grounded in verifiable sources, and maintains trustworthiness by admitting uncertainty. Its primary purpose is to provide a domain-agnostic, single substrate for all enterprise AI applications, enabling AI to reason over structured truth, eliminate hallucination, and deliver reliable, context-aware answers. The project aims to give AI systems a coherent, evolving understanding of organizational reality, moving beyond static knowledge representations to a system that learns and adapts continuously.

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
- **QA Verifier**: Two-layer verification (structural rules + LLM semantic check).
- **Dynamic Confidence Scoring & Source Attribution**: Computed scores based on answer quality and evidence, with source extraction from various tools.
- **Deterministic Document Fallback**: Automatic document search when the Knowledge Graph lacks data.
- **Extraction Hardening**: Post-processor uses regex patterns to catch missed relationships.
- **Ambiguity Detection & Disambiguation**: Generalized pattern for handling multiple entity matches.
- **Extraction Job Tracking System**: Monitors extraction jobs with automatic timeout detection and retry logic.
- **Learning Flow**: Adaptive system that detects query gaps, prioritizes learning tasks, and performs targeted extraction.
- **QA Validation Module**: Provides consistent checks across response paths for various issues.
- **Coherence Checker (Shadow Mode)**: Post-response validation system for consistency and logical contradictions.
- **Spreadsheet/Financial Integration**: Auto-detects, processes, and extracts financial metrics from spreadsheets.
- **Stale Request Auto-Recovery**: Automatically recovers stuck extraction requests.
- **Parallel Extraction Workers**: Uses `ThreadPoolExecutor` for increased throughput.
- **Tri-Memory Precedence Pipeline**: Implements "Symbolic > Semantic > Episodic" precedence hierarchy.
- **Symbolic Override Engine**: Rule-based system to override, augment, constrain, or prohibit semantic answers.
- **Data Gates ("Refuse to Hallucinate")**: Three-level validation system detecting entity not found, no relevant chunks, and ungrounded answers.
- **Test Runner Dashboard**: Provides a web UI (`/test-runner`) for monitoring automated tests, including vault selection, a 5-stage pipeline visualization, and persistent test runs.
- **Multi-Model Extraction Pipeline**:
    - **Ontology Schema**: Defines 16 entity types and 20+ relationship types with validation.
    - **Multi-Model Extraction**: Dual-model extraction using GPT-4o-mini and Claude Sonnet for redundant entity/relationship extraction with consensus building.
    - **Partial Parse Recovery & Document Truncation**: Fallback regex parsing for incomplete JSON and truncation of large documents.
    - **Entity Resolution**: Multi-model consensus building with name normalization, fuzzy matching, and confidence boosting.
    - **Validation & Conflict Resolution**: Validates consensus against ontology constraints and auto-resolves conflicts.
    - **Extraction Auto-Trigger**: Automatically detects and queues unextracted documents.
    - **Vault-Centric Extraction Workflow**: Multi-model extraction script directly integrated with existing vaults.
- **Retrieval Robustness Improvements**:
    - **Per-Question Trace Logging**: Captures retrieved files, scores, and query types for debugging.
    - **Keyword+Semantic Fusion**: Applies canonical term boosting when semantic scores are low.
    - **Folder Weighting & Authority Config**: Source priority scoring and fact type authorities integrated into document ranking.
    - **Person-Role/Org-Unit Query Routing Override**: Prioritizes Knowledge Graph routing for specific query types.
- **Systematic Failure Analysis Infrastructure**:
    - **FailureAnalyzer**: 7-layer failure tracing, pattern classification, and fix plan generation.
    - **TargetedExtractor**: Specialized prompts for various failure categories.
    - **FixApplier**: Applies targeted extraction results to KG.
    - **ImprovementLoop**: Orchestrates analyze → extract → apply → test cycle for iterative accuracy improvement.
- **Relationship-First Retrieval Architecture**:
    - **AnchorResolver**: Auto-detects primary organization for each vault using graph centrality. Looks up entity by name from `primary_organization_name` column.
    - **RelationshipFirstRetriever**: Traverses graph edges from anchor organization to find connected entities.
    - **Stage 0 Role Resolution**: Highest priority lookup stage for role resolution.
    - **Edge-Rank Prioritization**: Ranking system for relationship types to select the best match.
    - **Cross-Organization Contamination Prevention**: RoleResolver and DirectedGraphRetriever both apply anchor organization filtering to prevent returning entities from unrelated organizations (e.g., wrong CFO from different company).
- **Supplier Query Lookup**:
    - **Specialized Detection**: Detects supplier-related queries using keywords (supplier, supplies, provides, vendor, manufacturer, etc.).
    - **Entity Extraction from Query**: Uses regex patterns to extract entity names from queries (e.g., "Falcon X" from "Who provides flight computers for Falcon X?").
    - **SUPPLIER_OF Relationship Traversal**: Queries SUPPLIER_OF, SUPPLIES_TO, PROVIDES, MANUFACTURES relationships from the knowledge graph.
    - **Prioritized Results**: Prepends supplier entities and relationships in context so they appear first in LLM synthesis.
    - **Increased Context Limits**: Entity limit (15) and relationship limit (25) for supplier queries to include all relevant suppliers.
- **Corpus Maker (Phase 1.5)**:
    - **Web UI**: Full-featured UI for uploading, registering, and validating corpora at `/corpus-maker`.
    - **Selective Folder Upload**: Single parent folder selection with checkbox UI for subfolder inclusion/exclusion.
    - **Auto-Exclude Metadata**: Automatically excludes questions.json, manifest.json, readme.md, hidden files.
    - **Core Modules**: Handles uploading, validation, normalization, manifests, and registry.
    - **Document Categorization**: Standard categories (strategy, projects, financials, compliance, hr, technical, legal) with auto-detection.
    - **Manifest Tracking**: SHA256 checksums for document integrity.
    - **Multi-Vault Support**: Create multiple vaults from the same corpus via `/api/corpus/create-vault`.
    - **Corpus Cards**: Registered Corpora tab shows cards with vault associations, file counts, and Create Vault buttons.
    - **Test Runner Integration**: Direct link to create new vaults from Test Runner interface.
    - **API Endpoints & CLI Support**: Provides programmatic and command-line interfaces.

## Mandatory Testing Rule

**After EVERY code change, run:**
```bash
python cf_integration_tests.py --all
```

If tests fail, the change is NOT complete. Fix and rerun.

Include test output in your response to prove it passed.

## External Dependencies
- **Database:** PostgreSQL (with pgvector)
- **LLM:** OpenAI `gpt-4o-mini`
- **Vision LLM:** Anthropic Claude Sonnet 4
- **Vector Embeddings:** `text-embedding-3-small`
- **Web Framework:** Flask
- **Deployment:** Gunicorn
- **Authentication:** Magic Link, API Keys, JWT Sessions, Google OAuth

## Known Bugs

### BUG-001: Dashboard shows "complete" during active re-extraction (2026-01-28)
**Severity:** Medium  
**Status:** Open  
**Description:** When re-triggering extraction on a vault that already has completed extraction data, the dashboard continues to show "100% complete" with the old document count instead of reflecting the new in-progress extraction.

**Steps to Reproduce:**
1. Complete extraction on a vault (e.g., 104 documents)
2. Clear and re-trigger extraction on the same vault
3. Dashboard still shows "complete" and "100%" with old count (104/104)
4. Meanwhile, extraction logs show active progress (e.g., [16/100])

**Expected Behavior:** Dashboard should show extraction in-progress status with current progress (e.g., "16/100 - 16%")

**Root Cause (Suspected):** The `/api/extraction/overview` endpoint likely queries completed extraction records without checking for active extraction jobs in progress. Need to cross-reference `extraction_jobs` table status when determining vault extraction state.

**Fix Plan:**
1. In extraction overview API, check `extraction_jobs` table for any jobs with status != 'COMPLETE' for the vault
2. If active jobs exist, calculate progress from job counts vs total documents
3. Only show "complete" when all jobs are finished AND no new extraction is queued