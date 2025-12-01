# Context Foundry - Tri-Memory Cognitive Architecture MVP

## Overview
Context Foundry is a walking skeleton proof-of-concept demonstrating a tri-memory cognitive architecture (Semantic/Episodic/Symbolic) that performs multi-hop reasoning with full provenance and confidence scoring.

**Current State**: MVP Complete - Successfully answering complex queries like "What services are affected if the payments database goes down?" by routing through all three memory layers and returning responses with complete evidence chains.

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
│   ├── retrieval.py        # Context retrieval agent
│   ├── reasoning.py        # LLM reasoning agent
│   └── validation.py       # Rule validation agent
├── data/
│   └── synthetic_generator.py  # IT ops synthetic data
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
The web interface provides a sleek, modern UI for querying the system:
- Dark theme with glassmorphism effects
- Real-time query execution with confidence meters
- Visual evidence chain with memory layer indicators
- Live statistics dashboard

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

The MVP uses synthetic IT operations data:
- 10 services (Payment, Auth, Checkout, etc.)
- 5 teams (Payments, Auth, API, SRE, Platform)
- 20 people with roles and expertise
- 20 incidents with severity levels
- 5 runbooks with procedures
- 8 business rules

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

- 2025-12-01: Added sleek web UI with dark theme, glassmorphism, animated gradients
- 2025-12-01: MVP Complete - All 3 demo queries working with full provenance
- 2025-12-01: Added resilient database error handling with session rollback
- 2025-12-01: Integrated OpenAI via Replit AI Integrations
- 2025-12-01: Built complete tri-memory architecture with 4 agents
