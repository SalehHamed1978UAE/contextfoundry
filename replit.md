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
-   **Reasoning Agent**: Generates responses using an LLM.
-   **Validation Agent**: Validates generated responses against symbolic rules.
-   **Graph Builder Agent**: Ingests documents, extracts entities/relationships using schema-driven LLM prompts, and writes to a STAGING area with full provenance. Configurable via YAML schema.
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
The web interface features a "Cybernetic Operations" HUD-style theme with a deep slate background, electric cyan accents, scanline animations, and tech corner visuals. It includes an animated confidence ring and color-coded evidence chains.
**Frontier Detection UI:**
- Frontier nodes in Memory Graph display with dashed amber borders and a "?" badge.
- Hover tooltips explain why traversal stopped.
- "Knowledge Frontier" panel shows knowledge boundaries and documentation gaps.

### Technical Implementations & Design Choices
-   **Type Storage**: Entity and relationship types are stored as VARCHAR and validated against loaded YAML schema.
-   **Lifecycle States**: Data transitions from STAGING to TRUSTED.
-   **Confidence Scoring & Provenance**: Every piece of data includes a confidence score and full provenance.
-   **Temporal Tracking**: Entities and relationships have `valid_from`, `valid_to`, `superseded_by`, and `change_reason` for full temporal history, supporting "as of when?" queries.
-   **Query Handling**: Includes query classification, impact analysis, hallucination prevention, and detection of analysis/trend queries and ordered sequence requests.
-   **Schema-Driven Multi-Mode Traversal**: Relationship traversal is fully configurable via YAML schema with `semantics.modes` and `TraversalRules`.
-   **Deterministic Impact Queries**: LLM calls use `temperature=0.0`. Impact/blast-radius queries use exhaustive graph traversal (BFS with max_depth=10) driven by schema semantics.
-   **Frontier Detection (Multi-Tier Traversal)**: Graph traversal explicitly identifies where knowledge ends, capturing `FrontierNode` data with classified reasons for stoppage.
-   **Speculative Inference Layer**: Extends beyond confirmed knowledge using 3 schema-driven inference rules and vector similarity search to suggest potential connections:
    - **Transitive Dependency**: Infers multi-hop dependencies (A→B→C ⇒ A→C) with 63% confidence
    - **Co-occurrence**: Detects entities mentioned together in 3+ documents with 36% confidence
    - **Shared Dependency**: Finds entities sharing common targets with 45% confidence
    - Isolated entities (no relationships) are treated as pseudo-frontiers for co-occurrence analysis
-   **Three-Tier Query Response Pipeline (Phase 3)**: Query responses are structured into three confidence tiers:
    - **CONFIRMED**: Direct relationships from the knowledge graph with high confidence
    - **INFERRED**: AI-analyzed connections from speculative inference rules with confidence percentages
    - **KNOWLEDGE BOUNDARY**: Explicit frontier nodes where traversal stopped, indicating knowledge gaps
    - UI displays tiered results summary with visual cards (green/purple/amber color coding)
    - API always returns `tiered_results` and `speculative_inferences` for consistent frontend rendering
-   **Timeline Slider**: Filters the graph by date, re-expanding the current entity with the new `as_of_date`.
-   **Property-Aware Retrieval**: Supports querying entities by JSON properties.
-   **Evaluation Framework**: Automated evaluation against baselines, A/B testing, and metrics dashboard.
-   **Data Model**: Utilizes SQLAlchemy for Entity, Relationship, and Document models.
-   **Identity Resolution**: Employs 7 weighted similarity signals and specific merge policies (e.g., PERSON entities always require human review).
-   **SQLAlchemy JSON Mutations**: Requires explicit flagging for JSON column modifications.

## 6-Week Rebuild Progress (Ontology Architecture)

### Session 1: Week 0-1 ✅ COMPLETE
**Objective**: Establish shadow mode infrastructure and database-backed ontology foundation

**Completed Components**:
1. **Feature Flags Module** (`src/context_foundry/config/feature_flags.py`)
   - ExtractionMode enum: LEGACY, SHADOW, CONSTRAINED
   - Helper functions: is_shadow_enabled(), is_constrained_enabled()
   
2. **Shadow Metrics Module** (`src/context_foundry/monitoring/shadow_metrics.py`)
   - Persistent JSONL logging for extraction comparison
   - Overlap/precision metrics computation
   
3. **Database Tables Created**:
   - `entities_v2`: Shadow table with new ontology columns (entity_type_id, corroboration_count, etc.)
   - `ontology_types`: 4-layer hierarchy with origin tracking
   - `ontology_relations`: Semantic relationship constraints with extraction_hints
   - `extraction_events`: Audit trail for extraction pipeline
   
4. **Seeded Ontology Data**:
   - Layer 0: 4 Meta-Core types (Entity, Event, Record, Relation)
   - Layer 1: 6 Common Core types (Asset, Agent, Location, Person, Organization, Document)
   - Layer 2: 10 IT Operations types + 13 relationships with semantics
   
5. **Validation Triggers**:
   - `validate_entity_type()`: Rejects unknown types (CREATURE test passed)
   - `validate_relationship()`: Manus SQL fix for source/target type constraints
   - `check_extension_name_collision()`: Layer 3 tenant extension guardrails
   
6. **RLS Policies**: Created but not yet enabled (staged rollout)

**Verification Passed**:
- Layer counts: 4/6/10 as expected
- 13 relationships with correct source/target type pairs
- CREATURE type correctly rejected by validation trigger

### Session 2: Week 2 (Next)
**Objective**: Build constrained extraction pipeline with dynamic SchemaPromptGenerator and Pydantic models

### Session 3: Week 3
**Objective**: Confidence & provenance system with corroboration scoring

### Session 4: Week 4
**Objective**: Data cleanup scripts (sequential to avoid FK violations)

### Session 5: Week 5
**Objective**: Staged cutover from YAML to database-backed ontology

### Session 6: Week 6
**Objective**: Production rollout with RLS enabled

## External Dependencies
-   **Database**: PostgreSQL (specifically Neon for Replit deployment).
-   **LLM**: OpenAI (gpt-4o-mini for reasoning via Replit AI Integrations, direct OpenAI API for embeddings).
-   **Vector Embeddings**: pgvector with OpenAI `text-embedding-3-small` (1536 dimensions).
-   **Web Framework**: Flask.
-   **Deployment**: Gunicorn.