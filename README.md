# Context Foundry

[![Tests](https://img.shields.io/badge/tests-100%20passing-brightgreen)](docs/testing.md)
[![Python](https://img.shields.io/badge/python-3.11-blue)](https://python.org)
[![License](https://img.shields.io/badge/license-proprietary-lightgrey)]()

**Enterprise Knowledge Graph Governance System**

Context Foundry implements a dual-system cognitive architecture for enterprise knowledge graph governance. It separates Ontology Foundry (schema governance) from Context Foundry (instance governance) to allow for different governance cadences, confidence thresholds, and agent responsibilities.

## Features

- **Dual Governance Architecture**: Separate schema and instance governance with different confidence thresholds
- **Tri-Memory System**: Semantic, Episodic, and Symbolic memory layers
- **Multi-Tenant Isolation**: Row-Level Security with defense-in-depth protection
- **Query Classification**: Smart routing for dependency, impact, and ownership queries
- **Hallucination Guards**: Structured truth delivery with confidence scoring
- **RLM Integration**: Recursive Language Model for complex multi-hop queries

## Stabilization Status

The project has completed a 5-week stabilization program:

| Week | Focus | Status |
|------|-------|--------|
| Week 1 | Component Contracts | Complete |
| Week 2 | E2E Test Suite | Complete |
| Week 3 | Schema Consolidation | Complete |
| Week 4 | Bug Fixes | Complete |
| Week 5 | CI/CD + Documentation | Complete |

### Test Summary

| Category | Tests | Status |
|----------|-------|--------|
| Contract Tests | 88 | Passing |
| E2E Tests | 12 | Passing |
| Total | 100 | Passing |

## Quick Start

### Prerequisites

- Python 3.11+
- PostgreSQL with pgvector extension
- OpenAI API key (for LLM features)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd context-foundry

# Install dependencies
pip install -r requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
export OPENAI_API_KEY="your-key"

# Run the application
python -m gunicorn --bind 0.0.0.0:5000 main:app
```

### Running Tests

```bash
# Quick test run (contract tests only)
python -m pytest tests/contracts/ -q

# Full test suite
python -m pytest tests/contracts/ tests/integration/ tests/e2e/test_tenant_isolation.py -v
```

See [docs/testing.md](docs/testing.md) for detailed testing documentation.

## Architecture

### Core Components

```
src/context_foundry/
├── agents/              # Query and reasoning agents
│   ├── retrieval.py     # Context bundle builder
│   ├── reasoning.py     # Response generation
│   └── tier1_resolver.py # Simple query resolution
├── contracts/           # Component contracts
│   ├── query_parser.py  # Query intent classification
│   ├── entity_resolver.py # Entity matching
│   └── memory.py        # Memory layer contracts
├── memory/              # Tri-memory implementation
│   ├── semantic.py      # Knowledge graph memory
│   ├── episodic.py      # Document memory
│   └── symbolic.py      # Rule memory
├── ontology_foundry/    # Schema governance
│   └── schema_service.py # Ontology table loader
└── rlm/                 # Recursive Language Model
    ├── executor.py      # Multi-turn LLM orchestration
    └── memory_apis/     # Memory wrappers for RLM
```

### Database Schema

- **ontology**: Schema governance (types, relations, validation rules)
- **context**: Instance governance (entities, relationships, documents)
- **platform**: Multi-tenancy, users, API keys

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## API Reference

See [docs/API.md](docs/API.md) for the complete API reference.

### Query Examples

```python
# Dependency query
"What does Payment Service depend on?"
# -> Returns upstream dependencies

# Impact query
"What was affected by the database outage?"
# -> Returns blast radius (downstream impact)

# Ownership query
"Who owns the API Gateway?"
# -> Returns team ownership
```

## Development

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

### CI Pipeline

The GitHub Actions workflow runs on every push:

1. Contract tests
2. Integration tests
3. E2E tests
4. Lint checks
5. Security scans

See [.github/workflows/ci.yml](.github/workflows/ci.yml) for details.

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md)
- [API Reference](docs/API.md)
- [Testing Guide](docs/testing.md)
- [RLM Implementation](docs/RLM_IMPLEMENTATION_PLAN.md)

## Known Limitations

1. **E2E Tests with LLM Calls**: Some E2E tests require actual LLM API access. Use mock fixtures for deterministic testing.

2. **RLS Test Skips**: 4 tests skip when Row-Level Security prevents test data seeding.

## License

Proprietary. All rights reserved.
