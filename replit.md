# Context Foundry - Tri-Memory Cognitive Architecture MVP

## Overview
Context Foundry is a proof-of-concept for a tri-memory cognitive architecture (Semantic/Episodic/Symbolic) designed for multi-hop reasoning. Its core purpose is to provide detailed, reliable responses with full provenance tracking and confidence scoring for domain-agnostic reasoning. The project aims to outperform baseline systems in complex domains like IT operations and organizational charting, providing a robust solution for knowledge management and intelligent querying.

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
1.  **Semantic Memory (Knowledge Graph)**: Stores entities and relationships with lifecycle states, provenance, and confidence scores using PostgreSQL.
2.  **Episodic Memory (Vector Search)**: Stores document embeddings for similarity-based retrieval using PostgreSQL with pgvector.
3.  **Symbolic Memory (Rules Engine)**: Employs business rules with priority ordering for response validation.

### Agent Pipeline
-   **Retrieval Agent**: Gathers information from all three memory layers.
-   **Reasoning Agent**: Generates responses using an LLM.
-   **Validation Agent**: Validates generated responses against symbolic rules.
-   **Graph Builder Agent**: Ingests documents, extracts entities/relationships using schema-driven LLM prompts, and writes to a STAGING area with full provenance.
-   **Staging Validator Agent**: Validates STAGING data against schema rules, detects conflicts, and creates review items.
-   **Identity Resolution Agent**: Detects and manages duplicate entities using weighted similarity signals.
-   **Gardener Agent**: An autonomous agent that runs periodically to maintain graph health through decay, promotion, conflict resolution, demotion, and cleanup passes.

### Domain-Agnostic Schema System
The knowledge graph schema (entity types, relationship types, cardinality rules, validation rules) is fully configurable via YAML files, allowing for adaptability across different domains (e.g., IT Operations, Fiction & Literature, Investment Portfolio). Both the ingestion AND query pipelines are fully domain-agnostic, dynamically adapting prompts and searches based on the active schema.
Available Domain Schemas:
- `config/domain_schema.yaml` - IT Operations
- `config/fiction_schema.yaml` - Fiction & Literature
- `config/investment_schema.yaml` - Investment Portfolio

### UI/UX Decisions
The web interface features a "Cybernetic Operations" HUD-style theme with a deep slate background, electric cyan accents, scanline animations, and tech corner visuals. It includes an animated confidence ring and color-coded evidence chains. Frontier detection in the UI highlights knowledge boundaries.

### Technical Implementations & Design Choices
-   **Lifecycle States**: Data transitions from STAGING to TRUSTED.
-   **Confidence Scoring & Provenance**: Every piece of data includes a confidence score and full provenance.
-   **Temporal Tracking**: Entities and relationships have `valid_from`, `valid_to`, `superseded_by`, and `change_reason` for full temporal history, supporting "as of when?" queries.
-   **Query Handling**: Includes query classification, impact analysis, hallucination prevention, and detection of analysis/trend queries and ordered sequence requests.
-   **Schema-Driven Multi-Mode Traversal**: Relationship traversal is fully configurable via YAML schema.
-   **Deterministic Impact Queries**: LLM calls use `temperature=0.0`. Impact/blast-radius queries use exhaustive graph traversal (BFS with max_depth=10) driven by schema semantics.
-   **Frontier Detection (Multi-Tier Traversal)**: Graph traversal explicitly identifies where knowledge ends, capturing `FrontierNode` data with classified reasons for stoppage.
-   **Speculative Inference Layer**: Extends beyond confirmed knowledge using 3 schema-driven inference rules and vector similarity search to suggest potential connections (Transitive Dependency, Co-occurrence, Shared Dependency).
-   **Three-Tier Query Response Pipeline**: Query responses are structured into three confidence tiers: CONFIRMED, INFERRED, and KNOWLEDGE BOUNDARY, with corresponding UI visuals.
-   **Timeline Slider**: Filters the graph by date.
-   **Property-Aware Retrieval**: Supports querying entities by JSON properties.
-   **Evaluation Framework**: Automated evaluation against baselines, A/B testing, and metrics dashboard.
-   **Data Model**: Utilizes SQLAlchemy for Entity, Relationship, and Document models.
-   **Identity Resolution**: Employs 7 weighted similarity signals and specific merge policies.
-   **Ontology Architecture (6-Week Rebuild)**: Migration to a database-backed ontology for dynamic schema management, including:
    - Shadow mode infrastructure and database-backed ontology foundation (`entities_v2`, `ontology_types`, `ontology_relations`).
    - Constrained extraction pipeline with dynamic `SchemaPromptGenerator` and Pydantic models.
    - `GardenerAgent` with type-weighted promotion thresholds from the database.
    - Data cleanup scripts for orphans and stale staging, supporting infrastructure domain templates and risk-based threshold seeding.

## External Dependencies
-   **Database**: PostgreSQL (specifically Neon for Replit deployment).
-   **LLM**: OpenAI (gpt-4o-mini for reasoning via Replit AI Integrations, direct OpenAI API for embeddings).
-   **Vector Embeddings**: pgvector with OpenAI `text-embedding-3-small`.
-   **Web Framework**: Flask.
-   **Deployment**: Gunicorn.