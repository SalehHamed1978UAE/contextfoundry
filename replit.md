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
-   **Graph Loader**: Handles structured data ingestion.
-   **Graph Builder Agent**: Perception layer that ingests documents, extracts entities/relationships using schema-driven LLM prompts, and writes to STAGING with full provenance. Now fully configurable via YAML schema.
-   **Staging Validator Agent**: Validates STAGING data against schema rules (cardinality, source/target types, required fields). Detects conflicts and creates review items.

### Domain-Agnostic Schema System (NEW)
Context Foundry is now truly domain-agnostic. The knowledge graph schema (entity types, relationship types, cardinality rules, validation rules) is fully configurable via YAML configuration files.

**Key Files:**
-   `config/domain_schema.yaml` - Default IT Operations schema
-   `config/examples/investment_portfolio.yaml` - Example Investment Portfolio schema
-   `src/context_foundry/config/domain_schema.py` - DomainSchemaLoader class

**How to add a new domain:**
1.  Create a new YAML file in `config/` or `config/examples/`
2.  Define entity_types with name, description, required_fields, optional_fields
3.  Define relationship_types with source_types, target_types, cardinality (many-to-one or many-to-many)
4.  Optionally add validation_rules
5.  Pass `schema_config_path` to API endpoints or agents

**API Endpoints:**
-   `GET /api/schema` - Get current schema configuration
-   `POST /api/schema/reload` - Reload schema from config file
-   `POST /api/ingest` - Ingest document with optional `schema_config_path`
-   `POST /api/validate` - Validate STAGING data against current schema
-   `GET /api/review-queue` - Get pending review items

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
-   **Configurable Schema**: Entity types, relationship types, cardinality rules, and validation rules are all loaded from YAML configuration at runtime.

## Example Domain Schemas

### IT Operations (Default)
```yaml
domain: "IT Operations"
entity_types:
  - SERVICE, COMPONENT, TEAM, PERSON, DATABASE, INCIDENT
relationship_types:
  - DEPENDS_ON (many-to-many)
  - OWNS (many-to-one: only one owner per entity)
  - SUPPORTS (many-to-many)
  - MEMBER_OF (many-to-many)
  - AFFECTS (many-to-many)
  - CAUSED_BY (many-to-one: only one root cause)
```

### Investment Portfolio (Example)
```yaml
domain: "Investment Portfolio"
entity_types:
  - FUND, COMPANY, SECTOR, ANALYST, HOLDING, REPORT
relationship_types:
  - HOLDS (many-to-many: funds hold multiple companies)
  - COVERS (many-to-many: analysts cover multiple sectors)
  - BELONGS_TO (many-to-one: company belongs to one sector)
  - MANAGES (many-to-one: one manager per fund)
  - AUTHORED (many-to-many)
  - ABOUT (many-to-one: report about one company)
```

## External Dependencies
-   **Database**: PostgreSQL (Neon via Replit).
-   **LLM**: OpenAI (gpt-4o-mini via Replit AI Integrations for reasoning, direct OpenAI API for embeddings).
-   **Vector Embeddings**: pgvector with OpenAI text-embedding-3-small (1536 dimensions).
-   **Web Framework**: Flask.
-   **Deployment**: Gunicorn.
