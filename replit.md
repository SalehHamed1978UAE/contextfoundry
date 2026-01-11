# Context Foundry - Cognitive Operating System for the Enterprise

## Overview

Context Foundry is a **Cognitive Operating System for the Enterprise** designed to provide AI systems with a coherent, evolving understanding of organizational reality. It aims to build a dynamic "World Model" that compounds knowledge over time, is grounded in verifiable sources, and remains trustworthy by admitting uncertainty. The project's vision is to create a domain-agnostic, single substrate that serves all enterprise AI applications, moving beyond static knowledge representations to a system that learns and adapts. Key capabilities include a Tri-Memory System (Semantic, Episodic, Symbolic), a robust Fact Lifecycle (Staging, Trusted, Archived), and Context-Attached Knowledge, ensuring relationships carry rich metadata like temporal validity and provenance. The ultimate goal is to enable AI to reason over structured truth, eliminating hallucination and providing reliable, context-aware answers.

## User Preferences

- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

## System Architecture

Context Foundry is built around a **Tri-Memory System** comprising Semantic Memory (knowledge graph of entities, relationships, topology), Episodic Memory (event timelines, incident patterns), and Symbolic Memory (rules, constraints, safety invariants). Each fact within the system follows a **Fact Lifecycle**: STAGING (newly extracted facts), TRUSTED (validated facts used for reasoning), and ARCHIVED (superseded or stale facts). Facts include `_layer`, `_confidence`, `_sources`, and `_lifecycle` metadata.

A core architectural principle is **Context-Attached Knowledge**, where relationships are enriched with metadata such as `valid_from`, `valid_to`, `provenance_text`, `event_context`, and `qualifiers`. The system assembles a **Context Bundle** for AI applications, which is a structured package containing focal entities, relationships with their context, dependency paths, applicable rules, and a confidence summary.

The system employs several key agents:
- **GraphBuilderAgent**: Extracts entities and context-attached relationships from documents.
- **RetrievalAgent**: Assembles the Context Bundle from the tri-memory system.
- **ReasoningAgent**: Utilizes LLMs to reason over the Context Bundle.
- **ValidationAgent**: Applies symbolic rules and adjusts confidence.
- **GardenerAgent**: Maintains the quality of the knowledge graph (deduplication, promotion, pruning).
- **QueryTimeSemanticAgent**: Parses user queries, resolves entities, and orchestrates retrieval and reasoning.

The **Query Flow** involves parsing, entity resolution, context bundle retrieval, a sufficiency check, reasoning by an LLM, validation against symbolic rules, response generation (with confidence and provenance), and an asynchronous learning step to identify and address knowledge gaps.

Key architectural features include:
- **Tenant Context and RLS**: Enhanced `TenantSession` with failure tracking and `ensure_tenant_context()` helper for Row-Level Security.
- **Query Pipeline**: Features `QueryClassifier` for LLM-based query classification, `RoleResolver` for resolving roles (e.g., CEO) to individuals, and `RetrievalRouter` for intelligent routing to `GRAPH_ONLY`, `DOCS_ONLY`, or `HYBRID` strategies, with automatic fallback for list queries.
- **Role Resolution (3-Stage)**: Enhanced `RoleResolver` with fallback stages:
  - Stage 1: Exact relationship lookup (HOLDS_POSITION, HAS_POSITION, HOLD_POSITION relationships in KG)
  - Stage 2: Fuzzy property matching (word-boundary regex on position/role/title/job_title fields)
  - Stage 3: Document chunk search (pattern matching for "Name, Role" in text)
  - `resolve_all()`: Dual-source lookup combining entity properties AND relationship-based matches
- **Implicit Role Extraction**: `GraphBuilder` automatically creates HOLDS_POSITION relationships from entity properties (position/title/role fields) during ingestion.
- **Relationship Type Standard**: Supports multiple position relationship types: `HOLDS_POSITION`, `HAS_POSITION`, `HOLD_POSITION`, `HELD_POSITION`, `HAS_ROLE`, `HAS_TITLE`.
- **QA Verifier**: A two-layer verification system (Structural rules + LLM semantic check) to ensure answer quality, rejecting unsupported or off-topic responses and providing detailed verdicts.
- **Dynamic Confidence Scoring**: Replaces hardcoded confidence with computed scores based on answer quality and evidence.
- **Source Attribution**: Extracts and displays sources from various tool types, with a user-friendly frontend display.
- **Deterministic Document Fallback**: Automatically triggers document search when the knowledge graph lacks specific data, ensuring comprehensive factual queries.
- **Context Injection**: Passes `vault_context` to the `ToolAgent` and `QueryPipeline` for target entity resolution when no explicit entity is in the query.
- **QA Evidence Alignment**: `AnswerVerifierAgent` combines pre-fetched pipeline data with tool call results for robust verification.
- **Shared Response Helpers**: Centralized functions in `src/context_foundry/utils/response_helpers.py` ensure consistent evidence gathering, confidence calculation, and response formatting across CLI and Web interfaces. Key components:
  - `QAEvidence` dataclass: Unified evidence structure from pipeline + tool calls
  - `build_qa_evidence()`: Combines retrieval results and tool call data
  - `calculate_confidence()`: Single formula for confidence scoring based on QA verdict and evidence
  - `build_response()`: Consistent response dictionary format for all code paths
- **Ambiguity Detection & Disambiguation**: Generalized pattern for handling queries that match multiple entities:
  - `AmbiguityResult` dataclass: Query-agnostic structure for ambiguous results (roles, entities, departments, projects, locations, metrics)
  - `RoleResolver.resolve_all()`: Finds all people holding a role across the vault (accepts vault_context for org prioritization)
  - `RetrievalResult.needs_disambiguation`: Property to detect when disambiguation is needed
  - `DisambiguationReasoner`: LLM-based reasoning to determine best match:
    - Fast path: Single match → use directly
    - Fast path: Exact vault context match → use matching entity
    - LLM fallback: Reason about which match(es) best answer user's intent
  - Response format: Primary answer + "Note: Your documents also mention..." for alternatives
  - When no clear primary match, asks user to clarify

## External Dependencies

- **Database:** PostgreSQL (with pgvector for embeddings)
- **LLM:** OpenAI `gpt-4o-mini`
- **Vision LLM:** Anthropic Claude Sonnet 4
- **Vector Embeddings:** `text-embedding-3-small`
- **Web Framework:** Flask
- **Deployment:** Gunicorn
- **Authentication:** Magic Link, API Keys, JWT Sessions, Google OAuth