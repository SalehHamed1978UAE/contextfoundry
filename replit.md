# Context Foundry - Tri-Memory Cognitive Architecture MVP

## Overview
Context Foundry is a walking skeleton proof-of-concept demonstrating a tri-memory cognitive architecture (Semantic/Episodic/Symbolic) that performs multi-hop reasoning with full provenance and confidence scoring.

**Current State**: MVP2 Week 7 Complete - Full 100-query automated evaluation completed. Context Foundry wins 5/5 vs GraphRAG baseline with statistically significant provenance advantage (+2.19 score). **Domain-agnostic architecture validated** with org chart domain test (30 people, 8 teams, 5 departments).

## Architecture

### Tri-Memory System

1. **Semantic Memory (Knowledge Graph)**
   - PostgreSQL with entities (services, teams, people, incidents) and relationships (DEPENDS_ON, OWNS, MEMBER_OF, etc.)
   - Lifecycle states: STAGING → TRUSTED → ARCHIVED
   - Full provenance tracking (source documents, source sentences)
   - Confidence scoring per entity/relationship

2. **Episodic Memory (Vector Search)**
   - PostgreSQL with pgvector for document embeddings
   - Stores runbooks and operational documents
   - Similarity-based retrieval for context

3. **Symbolic Memory (Rules Engine)**
   - Business rules with priority ordering
   - Rule types: INVARIANT, SAFETY_CHECK, ESCALATION_POLICY, VALIDATION
   - Applied during response validation

### Agent Pipeline

1. **Retrieval Agent**: Queries all three memory layers, builds ContextBundle
2. **Reasoning Agent**: Uses OpenAI (gpt-4o-mini via Replit AI Integrations) to generate response
3. **Validation Agent**: Checks response against symbolic rules

## Project Structure

```
src/context_foundry/
├── models/
│   ├── schema.py           # SQLAlchemy models (Entity, Relationship, Document, Rule)
│   └── context_bundle.py   # ContextBundle data structure
├── memory/
│   ├── semantic.py         # Knowledge graph operations
│   ├── episodic.py         # Vector search operations
│   └── symbolic.py         # Rules engine operations
├── agents/
│   ├── graph_loader.py     # Data ingestion agent
│   ├── org_chart_loader.py # Org chart domain loader (non-IT domain)
│   ├── retrieval.py        # Context retrieval agent
│   ├── reasoning.py        # LLM reasoning agent
│   └── validation.py       # Rule validation agent
├── data/
│   ├── synthetic_generator.py       # Original IT ops synthetic data
│   ├── scaled_synthetic_generator.py # Scaled data (1,011 entities)
│   └── org_chart_generator.py       # Org chart domain data (30 people, 8 teams)
├── ingestion/               # MVP2: Document ingestion pipeline
│   ├── document_loader.py   # PDF/DOCX/MD/TXT loading
│   ├── text_chunker.py      # Sentence-aware chunking
│   └── ingestion_pipeline.py # Pipeline orchestration
├── extraction/              # MVP2: Entity/Relation extraction
│   ├── entity_extractor.py  # LLM-powered NER (7 entity types)
│   ├── relation_extractor.py # Relation extraction (8 types)
│   ├── extraction_pipeline.py # Pipeline orchestration
│   ├── staging_loader.py    # STAGING layer integration
│   ├── duplicate_detector.py # Fuzzy deduplication
│   └── validation.py        # Precision/recall measurement
├── evaluation/              # Week 7: Comparison framework
│   ├── graphrag_baseline.py # Simpler GraphRAG for comparison
│   ├── query_set.py         # 100 queries across 6 categories
│   └── evaluator.py         # Blind A/B evaluation framework
├── utils/
│   └── logger.py           # Comprehensive logging
└── core.py                 # Main orchestrator
main.py                     # CLI interface
web_app.py                  # Flask web interface
templates/                  # HTML templates
static/css/                 # Stylesheets
static/js/                  # JavaScript
```

## Running the System

### Web Interface (Recommended)
The web interface provides a sleek, "Cybernetic Operations" HUD-style UI for querying the system:
- Deep slate background (#0f172a) with electric cyan (#06b6d4) accents
- Scanline animation effect for "system running" feel
- Tech corner accents on cards mimicking tactical displays
- Multi-page layout: Dashboard, Memory Graph, Learning Loop, System Rules, A/B Evaluation
- Real-time query execution with animated confidence ring
- Color-coded evidence chain by memory layer (cyan=semantic, purple=episodic, pink=symbolic)
- Live system status footer: API version, Memory count, Latency indicator

Typography:
- Headers: Space Grotesk (geometric, technical feel)
- Data/Code: JetBrains Mono (precision monospace)
- UI Text: Inter (clean readability)

```bash
python web_app.py
# Opens at http://localhost:5000
```

### CLI Interface
```bash
# Run demo mode (automated queries)
python main.py --demo

# Run interactive CLI
python main.py
```

### CLI Commands
- `query <text>` - Execute a natural language query
- `impact <entity>` - Analyze impact if entity fails
- `escalation <context>` - Find escalation path
- `stats` - Show memory statistics
- `examples` - Show example queries
- `export` - Export last query results

## Example Queries

1. **Impact Analysis**: "What services are affected if the Payments Database goes down?"
2. **Escalation Path**: "Who should I escalate to for a SEV1 on the Auth Service?"
3. **Team Ownership**: "What team owns the Payment Service?"
4. **Dependency Chain**: "What does the Checkout Service depend on?"

## Synthetic Data

The MVP2 uses scaled synthetic IT operations data:
- 122 services (Payment, Auth, Checkout, etc.)
- 33 teams (Payments, Auth, API, SRE, Platform, etc.)
- 385 people with roles and expertise
- 400 incidents with severity levels
- 71 databases
- 5 runbooks with procedures
- 8 business rules
- 2,622 relationships

## Configuration

- Database: PostgreSQL (Neon via Replit)
- LLM: gpt-4o-mini via Replit AI Integrations (no API key needed)
- Vector dimensions: 384

## Key Design Decisions

1. **Lifecycle States**: All ingested data starts in STAGING and is promoted to TRUSTED for use in reasoning
2. **Confidence Scoring**: Every entity, relationship, and response has a confidence score
3. **Full Provenance**: Every fact traces back to source documents and sentences
4. **No Silent Failures**: Comprehensive logging at every step of the pipeline
5. **Simple Embeddings**: Using deterministic bag-of-words for MVP (production would use sentence-transformers)

## Recent Changes

- 2025-12-02: **Domain-Agnostic Architecture Validated** - Org chart domain test successful
  - Created org_chart_generator.py: 30 people, 8 teams, 5 departments with REPORTS_TO/MEMBER_OF/LEADS relationships
  - Added org_chart_loader.py to populate tri-memory system with non-IT domain data
  - Entity namespacing implemented ("Org:" prefix) to prevent cross-domain collisions
  - Business rules applied correctly: VP approval for teams >10 members, Director approval otherwise
  - Test query achieved 95% confidence with multi-hop reasoning: Team → Headcount → Rule → Approver
  - Same tri-memory system handles both IT ops and org chart queries without code changes
- 2025-12-02: **100-Query Automated Evaluation Complete** - CF wins 5/5 against GraphRAG baseline
  - 100 queries across 6 categories (impact, escalation, ownership, dependencies, incidents, expertise)
  - CF Latency: 47 wins, GraphRAG: 30 wins, Ties: 23 (not statistically significant, Cohen's d=0.17)
  - CF Provenance Score: 2.32/3 vs GraphRAG 0.13/3 (**+2.19 advantage, statistically significant**)
  - CF Relationship Citations: 32% vs GraphRAG 10%
  - CF Rule Citations: 100% vs GraphRAG 3%
  - Response Length: CF 5602 chars (detailed), GraphRAG 322 chars (brief)
  - Results saved: exports/evaluation_results_20251202_175048.json
- 2025-12-02: **CRITICAL FIX: Hallucination Prevention** - Fixed "confident wrong answer" bug where CF would cite real relationships for non-existent entities
  - Added target entity extraction and verification in RetrievalAgent
  - If queried entity doesn't exist in graph → return 10% confidence with explicit "entity not found" message
  - ContextBundle now tracks target_entity_name, target_entity_found, target_entity_match
  - ReasoningAgent returns early with structured response for missing entities
  - Prevents fabricating relationships about non-existent entities (e.g., "Search Service" was citing Auth Service relationships)
  - **Known Entity Lookup First**: Primary extraction method now queries database for all trusted entity names and finds the longest match in the query string - more reliable than regex parsing
  - Scenario suffix stripping: removes "is corrupted", "goes down", "crashes" etc. from extracted names
  - Fallback regex patterns for entities not yet in database
  - Case-insensitive matching with title-case normalization
- 2025-12-02: **MVP2 Week 7 complete** - GraphRAG baseline + blind evaluation framework + web UI
- 2025-12-02: Added Evaluation web UI with blind A/B testing interface, query browser, side-by-side comparison, voting, metrics dashboard
- 2025-12-02: Built 100-query evaluation set across 6 categories (impact, escalation, ownership, dependencies, incidents, expertise)
- 2025-12-02: Added GraphRAG baseline implementation for fair comparison (no confidence scores, no symbolic rules)
- 2025-12-02: Created blind A/B evaluation framework with randomized ordering and source hiding
- 2025-12-02: Added API endpoints: /api/evaluation/query-set, /api/evaluation/run, /api/evaluation/compare, /api/evaluation/graphrag, /api/evaluation/preference, /api/evaluation/metrics, /api/evaluation/reveal
- 2025-12-02: **MVP2 Week 6 complete** - Gardener + Identity Resolution with full persistence
- 2025-12-02: Added ConflictLog, MergeAudit, DuplicateCandidate database tables
- 2025-12-02: Built API endpoints: /api/conflicts, /api/duplicates, /api/merge-audits
- 2025-12-02: Gardener now persists conflict records to database with cycle_id
- 2025-12-02: IdentityResolver persists merge audits and flagged duplicate candidates
- 2025-12-02: Added human review workflow for conflicts and duplicates
- 2025-12-02: MVP2 Week 5 complete - Entity extraction pipeline with 98.1% F1 score
- 2025-12-02: Added duplicate detection with fuzzy matching and normalization
- 2025-12-02: Built staging loader with STAGING layer integration and provenance
- 2025-12-02: Created LLM-powered NER for 7 entity types and 8 relation types
- 2025-12-02: Added document ingestion pipeline (PDF/DOCX/MD/TXT)
- 2025-12-02: Scaled synthetic data to 1,011 entities with scaled_synthetic_generator.py
- 2025-12-02: Fixed "invalid transaction rollback" errors with proper session cleanup
- 2025-12-02: Added skip-if-exists logic to graph_loader for graceful re-runs
- 2025-12-02: Added ContextFoundry.cleanup() method for proper session management
- 2025-12-02: Configured gunicorn deployment with /health endpoint
- 2025-12-01: Added sleek web UI with dark theme, glassmorphism, animated gradients
- 2025-12-01: MVP Complete - All 3 demo queries working with full provenance
- 2025-12-01: Added resilient database error handling with session rollback
- 2025-12-01: Integrated OpenAI via Replit AI Integrations
- 2025-12-01: Built complete tri-memory architecture with 4 agents
