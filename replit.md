# Context Foundry - Tri-Memory Cognitive Architecture MVP

## Overview
Context Foundry is a proof-of-concept for a tri-memory cognitive architecture (Semantic/Episodic/Symbolic) designed for multi-hop reasoning. It provides full provenance tracking and confidence scoring for domain-agnostic reasoning. The project aims to deliver detailed, reliable responses, outperforming baseline systems in IT operations and organizational chart domains.

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
1.  **Semantic Memory (Knowledge Graph)**: PostgreSQL stores entities and relationships with lifecycle states, provenance, and confidence scores.
2.  **Episodic Memory (Vector Search)**: PostgreSQL with pgvector stores document embeddings for similarity-based retrieval.
3.  **Symbolic Memory (Rules Engine)**: Business rules with priority ordering for response validation.

### Agent Pipeline
-   **Retrieval Agent**: Queries all three memory layers to build a `ContextBundle`.
-   **Reasoning Agent**: Uses OpenAI (gpt-4o-mini) to generate responses.
-   **Validation Agent**: Checks responses against symbolic rules.
-   **Graph Loader**: Handles data ingestion.

### UI/UX Decisions (Web Interface)
-   **Theme**: "Cybernetic Operations" HUD-style with deep slate background and electric cyan accents.
-   **Visuals**: Scanline animation, tech corner accents, animated confidence ring, color-coded evidence chain.
-   **Layout**: Multi-page (Dashboard, Memory Graph, Learning Loop, System Rules, A/B Evaluation).
-   **Typography**: Headers: Space Grotesk; Data/Code: JetBrains Mono; UI Text: Inter.

### Technical Implementations & Design Choices
-   **Lifecycle States**: Data progresses from STAGING to TRUSTED.
-   **Confidence Scoring**: Every entity, relationship, and response includes a confidence score.
-   **Full Provenance**: Facts trace back to source documents.
-   **Entity Resolution**: Rule queries resolve person references via the semantic graph.
-   **Query Classification**: Queries are classified into types ('entity', 'rule', 'impact', 'analysis', 'general').
-   **Impact Queries**: Traverse incoming `DEPENDS_ON` edges for blast radius analysis and include all cascade services.
-   **Hallucination Prevention**: Verifies entity existence; returns low confidence for non-existent entities.
-   **Analysis Query Detection**: Detects pattern/trend/aggregation queries and returns 0% confidence with honest limitations.
-   **Sequence Detection**: Detects and handles queries asking for ordered sequences, adjusting confidence if multi-step evidence is missing.
-   **Property-Aware Retrieval**: Supports querying entities by their JSON properties using an LLM query analyzer and PostgreSQL JSON operators.
-   **Data Ingestion**: Document loader with sentence-aware chunking, LLM-powered entity/relation extraction, fuzzy deduplication, and staging layer integration.
-   **Evaluation Framework**: Automated evaluation against baseline with A/B testing and metrics dashboard.
-   **Data Model**: SQLAlchemy models for Entity, Relationship, Document, Rule.
-   **Feature Specifications**: Core queries include impact analysis, escalation path finding, team ownership, and dependency chain. Synthetic data is used for testing.
-   **Confidence Calibration System**: Implemented a 3-phase system (Sufficiency Autorater, Quadrant Confidence, Entity Density Scoring) to improve handling of topic-centric queries.
-   **Cognitive Loop**: Infrastructure added for continuous ingestion, validation, and learning with `conflicts`, `review_queue`, and `gardener_logs` tables.

## External Dependencies
-   **Database**: PostgreSQL (Neon via Replit).
-   **LLM**: OpenAI (gpt-4o-mini via Replit AI Integrations for reasoning, direct OpenAI API for embeddings).
-   **Vector Embeddings**: pgvector with OpenAI text-embedding-3-small (1536 dimensions).
-   **Web Framework**: Flask.
-   **Deployment**: Gunicorn.