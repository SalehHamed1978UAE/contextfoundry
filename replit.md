# Context Foundry - Tri-Memory Cognitive Architecture MVP

## Overview
Context Foundry is a walking skeleton proof-of-concept demonstrating a tri-memory cognitive architecture (Semantic/Episodic/Symbolic) that performs multi-hop reasoning with full provenance and confidence scoring. The project aims to provide domain-agnostic reasoning capabilities, validated by successful application in both IT operations and organizational chart domains. It significantly outperforms baseline systems in provenance tracking and rule citation, offering detailed and reliable responses.

## User Preferences
- I want iterative development.
- I prefer detailed explanations.
- Ask before making major changes.
- Ensure comprehensive logging at every step of the pipeline.
- Prevent silent failures.
- The system should detect when queries ask for ordered sequences vs single facts.
- Rules should resolve person references via the semantic graph.
- Rule queries should be correctly classified and not misclassified as entity lookups.
- Impact queries should correctly traverse incoming DEPENDS_ON edges to identify downstream cascades.
- Prevent "confident wrong answer" hallucinations by verifying queried entities exist in the graph before citing relationships.
- Prioritize known entity lookup from the database, using longest match and scenario suffix stripping.
- Provide a human review workflow for conflicts and duplicates.
- Ensure resilient database error handling with session rollback.
- Implement graceful re-runs for data loaders.
- Ensure proper session management and cleanup.

## System Architecture

### Tri-Memory System
1.  **Semantic Memory (Knowledge Graph)**: PostgreSQL stores entities (services, teams, people, incidents) and relationships (DEPENDS_ON, OWNS, MEMBER_OF) with lifecycle states (STAGING → TRUSTED → ARCHIVED), full provenance tracking, and confidence scoring.
2.  **Episodic Memory (Vector Search)**: PostgreSQL with pgvector stores document embeddings (runbooks, operational documents) for similarity-based retrieval.
3.  **Symbolic Memory (Rules Engine)**: Business rules with priority ordering (INVARIANT, SAFETY_CHECK, ESCALATION_POLICY, VALIDATION) applied during response validation.

### Agent Pipeline
-   **Retrieval Agent**: Queries all three memory layers to build a `ContextBundle`.
-   **Reasoning Agent**: Uses OpenAI (gpt-4o-mini) to generate responses.
-   **Validation Agent**: Checks responses against symbolic rules.
-   **Graph Loader**: Handles data ingestion.
-   **Org Chart Loader**: Specific loader for the organizational chart domain.

### UI/UX Decisions (Web Interface)
-   **Theme**: Sleek "Cybernetic Operations" HUD-style, deep slate background (#0f172a), electric cyan (#06b6d4) accents.
-   **Visuals**: Scanline animation, tech corner accents on cards, animated confidence ring, color-coded evidence chain (cyan=semantic, purple=episodic, pink=symbolic).
-   **Layout**: Multi-page (Dashboard, Memory Graph, Learning Loop, System Rules, A/B Evaluation).
-   **Typography**: Headers: Space Grotesk; Data/Code: JetBrains Mono; UI Text: Inter.

### Technical Implementations & Design Choices
-   **Lifecycle States**: Data progresses from STAGING to TRUSTED.
-   **Confidence Scoring**: Every entity, relationship, and response includes a confidence score.
-   **Full Provenance**: Facts trace back to source documents and sentences.
-   **Entity Resolution**: Rule queries resolve person references via the semantic graph.
-   **Query Classification**: Queries are classified into types ('entity', 'rule', 'impact', 'analysis', 'general') to ensure correct processing.
-   **Impact Queries**: Correctly traverse incoming `DEPENDS_ON` edges for blast radius analysis.
-   **Hallucination Prevention**: Verifies entity existence in the graph, returning low confidence for non-existent entities.
-   **Analysis Query Detection**: Detects pattern/trend/aggregation queries and returns honest limitation (0% confidence) instead of hallucinating patterns from partial data.
-   **Sequence Detection**: Detects and handles queries asking for ordered sequences, adjusting confidence if multi-step evidence is missing.
-   **Data Ingestion**: Document loader (PDF/DOCX/MD/TXT), sentence-aware chunking, LLM-powered entity and relation extraction, fuzzy deduplication, staging layer integration.
-   **Evaluation Framework**: Automated evaluation against baseline (GraphRAG) with blind A/B testing, metrics dashboard, and comparison features.
-   **Data Model**: SQLAlchemy models for Entity, Relationship, Document, Rule.

### Feature Specifications
-   **Core Queries**: Impact analysis, escalation path finding, team ownership, dependency chain.
-   **Synthetic Data**: Scaled IT operations data (1,011 entities) and org chart data (30 people, 8 teams).

## External Dependencies
-   **Database**: PostgreSQL (Neon via Replit).
-   **LLM**: OpenAI (gpt-4o-mini via Replit AI Integrations).
-   **Vector Embeddings**: pgvector (for Episodic Memory).
-   **Web Framework**: Flask.
-   **Deployment**: Gunicorn.

## Recent Changes

### 2025-12-03: Analysis Query Classification
The system now detects pattern/trend/aggregation queries and returns honest limitation responses at 0% confidence instead of hallucinating patterns from partial data.

**Implementation Details:**
- Added `_is_analysis_query()` using regex patterns for pattern/trend/aggregation keywords (patterns, trends, common issues, most frequent, how many, recurring, summary, statistics, aggregate)
- New 'analysis' query type in `_classify_query_type()` - checked before impact and rule detection
- Analysis queries skip entity extraction entirely and set `is_analysis_query=True` on ContextBundle
- Also excluded from potential entity name detection (prevents false "entity not found" responses)
- `calculate_uncertainty()` returns 0% confidence with recommendation="analysis_not_supported"
- `to_llm_context()` adds explicit guidance: "Pattern/trend analysis requires aggregation capabilities beyond my current scope"

**Test Results:**
- Query: "What patterns do you see in recent incidents?" → 0% confidence, honest limitation response
- Query: "What are the most common issues causing outages?" → 0% confidence, honest limitation response
- Control: "What teams own the Payment Service?" → 95% confidence, correct answer

### 2025-12-03: Query-Structure-Aware Sequence Detection
The system now detects when queries ask for ordered sequences vs single facts and calibrates confidence accordingly.

**Implementation Details:**
- Added `_detect_sequence_intent()` using linguistic patterns (path, chain, workflow, steps, order) and ordinal markers (first, next, then)
- ContextBundle now tracks `sequence_intent`, `sequence_intent_reason`, `has_multi_step_evidence`
- Added `_check_multi_step_evidence()` to detect numbered lists, bullets, arrows in TOPICALLY RELEVANT documents
  - Separates structural keywords (procedure, path, steps) from topic keywords (escalation, approval, sev1)
  - Requires title match OR 3+ topic keyword matches to consider document relevant
  - Prevents false positives from unrelated numbered lists
- Confidence capped at 45% when sequence_intent=True but no relevant multi-step evidence found
- LLM prompt enriched with sequence guidance (look for ordered steps, avoid single-fact answers)
- Fixed document retrieval: "Escalation Procedures" runbook now correctly retrieved for path queries
- Updated `_get_rule_document_keywords()` to prioritize 'procedure', 'path', 'steps' for sequence queries

**Test Result:**
- Query: "What's the escalation path for a SEV1?"
- Answer: Full 4-step path (Team Lead → Director → VP → Executive) with 95% confidence
- Evidence: Correctly cites "Escalation Procedures" runbook and resolves Mia White as VP of Engineering