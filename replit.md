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
-   **Retrieval Agent**: Gathers information from all three memory layers to form a `ContextBundle`.
-   **Reasoning Agent**: Generates responses using an LLM (OpenAI gpt-4o-mini).
-   **Validation Agent**: Validates generated responses against symbolic rules.
-   **Graph Builder Agent**: Ingests documents, extracts entities/relationships using schema-driven LLM prompts, and writes to a STAGING area with full provenance. Configurable via YAML schema.
-   **Staging Validator Agent**: Validates STAGING data against schema rules (cardinality, types, required fields), detects conflicts, and creates review items.
-   **Identity Resolution Agent**: Detects and manages duplicate entities using weighted similarity signals, handling auto-merges and flagging for human review.
-   **Gardener Agent**: An autonomous agent that runs periodically to maintain graph health through decay, promotion, conflict resolution, demotion, and cleanup passes, ensuring data quality and relevance.

### Domain-Agnostic Schema System
The knowledge graph schema (entity types, relationship types, cardinality rules, validation rules) is fully configurable via YAML files, allowing for adaptability across different domains (e.g., IT Operations, Fiction & Literature, Investment Portfolio). Both the ingestion AND query pipelines are fully domain-agnostic:
- Entity Extractor builds dynamic prompts from active schema entity types and descriptions
- Relation Extractor builds dynamic prompts with source/target type constraints from schema
- Retrieval Agent dynamically searches all entity types from the current schema
- Reasoning Agent adapts its system prompt to include domain name and available types
- Property query analyzer generates schemas from current domain's property definitions
- `/api/examples` endpoint loads example queries from the active schema YAML
- Schema hot-reload via `/api/schema/reload` propagates to all components within the same process

### Available Domain Schemas
- `config/domain_schema.yaml` - IT Operations (SERVICE, COMPONENT, TEAM, PERSON, DATABASE, INCIDENT)
- `config/fiction_schema.yaml` - Fiction & Literature (CHARACTER, CREATURE, LOCATION, OBJECT, EVENT)
- `config/investment_schema.yaml` - Investment Portfolio (COMPANY, SECTOR, FUND, ANALYST, THESIS)

### UI/UX Decisions
The web interface features a "Cybernetic Operations" HUD-style theme with a deep slate background, electric cyan accents, scanline animations, and tech corner visuals. It includes an animated confidence ring and color-coded evidence chains for enhanced data visualization.

### Technical Implementations & Design Choices
-   **Type Storage**: Entity and relationship types are stored as VARCHAR and validated against the loaded YAML schema.
-   **Lifecycle States**: Data transitions from STAGING to TRUSTED.
-   **Validation Status**: Facts in STAGING are marked PENDING, VALID, INVALID, or CONFLICT.
-   **Confidence Scoring & Provenance**: Every piece of data includes a confidence score and full provenance tracing.
-   **Temporal Tracking**: Entities and relationships have `valid_from`, `valid_to`, `superseded_by`, and `change_reason` columns for full temporal history. Supports "as of when?" queries via `as_of_date` parameter and diff analysis between dates.
-   **Query Handling**: Includes query classification, impact analysis for `DEPENDS_ON` relationships, hallucination prevention through entity verification, detection of analysis/trend queries, and handling of ordered sequence requests.
-   **Property-Aware Retrieval**: Supports querying entities by JSON properties.
-   **Evaluation Framework**: Automated evaluation against baselines, A/B testing, and metrics dashboard.
-   **Data Model**: Utilizes SQLAlchemy for Entity, Relationship, and Document models.
-   **Configurable Schema**: All schema elements are loaded from YAML at runtime.
-   **Identity Resolution**: Employs 7 weighted similarity signals and specific merge policies (e.g., PERSON entities always require human review). Merges now create temporal history chains.
-   **SQLAlchemy JSON Mutations**: Requires explicit flagging for JSON column modifications to ensure persistence.

## Gardener Agent (Autonomous Graph Health)
The Gardener Agent runs every 5 minutes to maintain graph health through 5 autonomous passes:
1. **Decay Pass**: Type-specific confidence decay (OWNS: 0.02/wk, DEPENDS_ON: 0.01/wk)
2. **Promotion Pass**: Moves VALID facts from STAGING→TRUSTED (confidence≥0.75, dwell≥1hr)
3. **Conflict Resolution**: Strategy per type (higher_confidence_wins, newer_wins, rule_determined)
4. **Demotion Pass**: Archives low-confidence (<0.4) or superseded facts
5. **Cleanup Pass**: Removes stale STAGING (>30d), old resolved conflicts (>90d)

## Complete API Reference

### Core Query & Stats
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/query` | POST | Query knowledge graph with natural language. Returns response with confidence, provenance, evidence chain. Body: `{"query": "...", "as_of_date": "2024-01-01"}` (as_of_date optional for temporal queries) |
| `/api/stats` | GET | System statistics: entity counts, relationship counts, lifecycle distribution |
| `/api/examples` | GET | Example queries for the UI |
| `/api/graph/visualization` | GET | Live graph data for visualization. Query params: `lifecycle_state` (STAGING/TRUSTED/ARCHIVED/all), `entity_type`, `limit`. Returns nodes and edges with lifecycle states and confidence scores. |
| `/api/graph/search` | GET | Search entities by name. Query params: `q` (search term), `lifecycle_state`, `limit`. Returns matching entities for search-first exploration. |
| `/api/graph/expand/<entity_id>` | GET | Get entity with 1-hop neighbors (progressive disclosure). Query params: `lifecycle_state`. Returns center node, neighbors, and edges respecting lifecycle filter. |
| `/api/graph/entity/<entity_id>` | GET | Full entity details for side panel. Returns entity info, properties, incoming/outgoing relationships with names. |

### Temporal Tracking & History
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/entities/<id>/history` | GET | Get temporal history for an entity - all versions over time with superseded_by chains and change_reasons |
| `/api/knowledge/diff` | GET | Get differences in knowledge graph between two dates. Query params: `from_date`, `to_date` (required), `entity_type` (optional). Returns added/removed/modified entities and relationships |

### Document Ingestion & Schema
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/ingest` | POST | Ingest document. Extracts entities/relationships to STAGING, auto-runs validation and identity resolution. Body: `{"text": "...", "title": "..."}` |
| `/api/schema` | GET | Current domain schema (entity types, relationship types, cardinality rules) |
| `/api/schema/reload` | POST | Reload schema from config file |
| `/api/validate` | POST | Validate all STAGING data against schema rules |
| `/api/review-queue` | GET | Pending review items (conflicts, duplicates) |

### Gardener (Graph Health)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/gardener/status` | GET | Scheduler status: running, cycle count, cumulative stats |
| `/api/gardener/run` | POST | Trigger immediate Gardener cycle |
| `/api/gardener/history` | GET | Recent Gardener cycle history |

### Identity Resolution & Duplicates
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/resolve-duplicates` | POST | Run identity resolution to detect/merge duplicates |
| `/api/duplicates` | GET | Pending duplicate candidates for human review |
| `/api/duplicates/<id>/review` | POST | Resolve duplicate. Body: `{"decision": "merge|reject|skip"}` |
| `/api/merge-audits` | GET | Merge audit trail |

### Conflicts
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/conflicts` | GET | Unresolved conflicts from validation |
| `/api/conflicts/<id>/resolve` | POST | Resolve conflict. Body: `{"resolution": "keep_existing|keep_new"}` |

### Evaluation & A/B Testing
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/evaluation/query-set` | GET | Evaluation query set for A/B testing |
| `/api/evaluation/run` | POST | Run automated evaluation against baseline |
| `/api/evaluation/compare` | POST | Compare Context Foundry vs GraphRAG |
| `/api/evaluation/graphrag` | POST | Query GraphRAG baseline directly |
| `/api/evaluation/preference` | POST | Submit human preference vote |
| `/api/evaluation/metrics` | GET | Evaluation metrics and results |
| `/api/evaluation/reveal` | POST | Reveal which response is CF vs baseline |

### Feedback (Learning Loop)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/feedback` | POST | Submit feedback for query response |
| `/api/feedback/stats` | GET | Feedback statistics |
| `/api/feedback/recent` | GET | Recent feedback entries |

## External Dependencies
-   **Database**: PostgreSQL (specifically Neon for Replit deployment).
-   **LLM**: OpenAI (gpt-4o-mini for reasoning via Replit AI Integrations, direct OpenAI API for embeddings).
-   **Vector Embeddings**: pgvector with OpenAI `text-embedding-3-small` (1536 dimensions).
-   **Web Framework**: Flask.
-   **Deployment**: Gunicorn.