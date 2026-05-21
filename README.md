# Context Foundry

> Tri-Memory Cognitive Architecture for Enterprise Operations

## Architecture

Context Foundry implements a tri-memory system designed to outperform GraphRAG on multi-hop reasoning:

1. **Semantic Memory** (Knowledge Graph)
   - Lifecycle: STAGING → TRUSTED → ARCHIVED
   - Apache AGE for graph storage
   - Confidence scoring per entity/relationship

2. **Episodic Memory** (Vector Search)
   - Corpus: Long-term document embeddings
   - Session: Short-term conversation context
   - pgvector for similarity search

3. **Symbolic Memory** (Rules Engine)
   - Invariants, safety checks, escalation policies
   - Priority-based conflict resolution

4. **Learning Loop**
   - Human feedback collection
   - Weekly calibration cycles
   - Confidence threshold adjustment

## Quick Start

### Prerequisites

- Docker & Docker Compose
- 16GB+ RAM
- (Optional) NVIDIA GPU for faster inference

### Setup

```bash
# Clone and navigate
cd contextfoundry

# Copy environment file
cp .env.example .env

# Start infrastructure
docker-compose up -d

# Wait for services to be healthy
docker-compose ps

# Initialize database schema
docker-compose exec postgres psql -U cf_user -d context_foundry -f /docker-entrypoint-initdb.d/schema.sql

# Pull Ollama models
docker-compose exec ollama ollama pull mistral:7b
docker-compose exec ollama ollama pull nomic-embed-text

# View logs
docker-compose logs -f app
```

### Test the API

```bash
# Health check
curl http://localhost:8000/health

# Submit a query (once implemented)
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What database does ServiceX use?"}'
```

## Development Roadmap

### Phase 1: Walking Skeleton (Current)
- [ ] Infrastructure setup
- [ ] Database schema
- [ ] Minimal synthetic data
- [ ] All 6 agents (basic implementation)
- [ ] End-to-end query flow

### Phase 2: Scale Up
- [ ] Full synthetic dataset (50 services, 200 incidents)
- [ ] Uncertainty surfacing
- [ ] Learning loop implementation

### Phase 3: Evaluation
- [ ] GraphRAG baseline
- [ ] 100 test queries
- [ ] Blind evaluation
- [ ] Go/no-go decision

## Project Structure

```
contextfoundry/
├── docker-compose.yml       # Infrastructure orchestration
├── Dockerfile               # Application container
├── requirements.txt         # Python dependencies
├── schema.sql              # Database schema
├── init-db.sql             # Database initialization
├── src/
│   ├── main.py             # FastAPI application
│   ├── config.py           # Configuration
│   ├── agents/             # Six agents
│   ├── models/             # Data models
│   ├── db/                 # Database utilities
│   └── utils/              # Helper functions
└── data/                   # Synthetic data (generated)
```

## Architecture Principles

1. **Uncertainty First**: Every response surfaces confidence and caveats
2. **No Silent Failures**: Explicit error modes with graceful degradation
3. **Provenance Always**: Sentence-level source tracking minimum
4. **Learning Built-In**: Feedback loop from Day 1, not deferred
5. **Local-First**: No external API dependencies, full sovereignty

## License

MIT (for MVP evaluation purposes)
