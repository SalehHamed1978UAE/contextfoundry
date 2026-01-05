# Context Foundry Testing Guide

This document describes how to run tests for the Context Foundry project.

## Test Structure

```
tests/
├── contracts/           # Component contract tests (fast, deterministic)
│   ├── test_query_parser_contract.py    # 37 tests
│   ├── test_entity_resolver_contract.py # 17 tests
│   ├── test_memory_parity.py            # 18 tests
│   └── test_ontology_fallback.py        # 14 tests
├── integration/         # Integration tests
│   └── test_rlm_parity.py               # 2 tests
├── e2e/                 # End-to-end tests
│   ├── test_tenant_isolation.py         # 12 tests
│   ├── test_dependency_queries.py       # 18 tests
│   ├── test_impact_queries.py           # 14 tests
│   └── test_management_queries.py       # 14 tests
└── fixtures/            # Test fixtures and mocks
    ├── knowledge_graph.py               # Canonical test data
    ├── seed_test_data.py                # Database seeding
    └── mock_llm.py                      # Mock LLM client
```

## Running Tests

### Quick Test Run (Contract Tests Only)

```bash
python -m pytest tests/contracts/ -q
```

Expected output: `88 passed` (includes ontology fallback tests)

### Full Test Suite

```bash
python -m pytest tests/contracts/ tests/integration/ tests/e2e/test_tenant_isolation.py -v
```

Expected output: `100 passed, 4 skipped`

### Individual Test Categories

```bash
# Contract tests (fast, no external dependencies)
python -m pytest tests/contracts/ -v

# Integration tests
python -m pytest tests/integration/ -v

# E2E tenant isolation tests
python -m pytest tests/e2e/test_tenant_isolation.py -v

# All E2E tests (requires LLM API access)
python -m pytest tests/e2e/ -v
```

### Running Specific Test Files

```bash
# Query parser tests
python -m pytest tests/contracts/test_query_parser_contract.py -v

# Memory parity tests (RLM bug detection)
python -m pytest tests/contracts/test_memory_parity.py -v

# Ontology fallback tests
python -m pytest tests/contracts/test_ontology_fallback.py -v
```

## Test Categories

### Contract Tests

Contract tests verify that components satisfy their interface contracts without requiring external services. They are fast and deterministic.

| Test File | Tests | Purpose |
|-----------|-------|---------|
| `test_query_parser_contract.py` | 37 | Query intent classification |
| `test_entity_resolver_contract.py` | 17 | Entity resolution thresholds |
| `test_memory_parity.py` | 18 | RLM/SemanticMemory parity |
| `test_ontology_fallback.py` | 14 | YAML fallback behavior |

### Integration Tests

Integration tests verify that components work together correctly.

| Test File | Tests | Purpose |
|-----------|-------|---------|
| `test_rlm_parity.py` | 2 | RLM API integration |

### E2E Tests

End-to-end tests exercise the full query pipeline.

| Test File | Tests | Purpose |
|-----------|-------|---------|
| `test_tenant_isolation.py` | 12 | Multi-tenant data isolation |
| `test_dependency_queries.py` | 18 | "What does X depend on?" |
| `test_impact_queries.py` | 14 | Blast radius queries |
| `test_management_queries.py` | 14 | Ownership queries |

## Test Fixtures

### Mock LLM Client

For deterministic testing without LLM API calls:

```python
from tests.fixtures.mock_llm import MockLLMClient

def test_with_mock_llm(mock_openai):
    # mock_openai fixture provides MockLLMClient
    # All OpenAI calls return canned responses
    pass
```

### Canonical Test Data

```python
from tests.fixtures.knowledge_graph import (
    CANONICAL_ENTITIES,
    CANONICAL_RELATIONSHIPS,
    TEST_TENANT_ID,
)
```

### Database Seeding

```python
from tests.fixtures.seed_test_data import seed_canonical_test_data

def test_with_seeded_data(seeded_test_data):
    # seeded_test_data contains entities and relationships
    entities = seeded_test_data["entities"]
    relationships = seeded_test_data["relationships"]
```

## Known Test Behaviors

### Skipped Tests (4)

Four integration tests skip when Row-Level Security (RLS) prevents test data seeding:

- `test_rlm_parity.py::test_parity_*` - Requires valid tenant context

These tests pass in environments with proper tenant configuration.

### E2E Tests with LLM Calls

Some E2E tests (dependency, impact, management queries) require actual LLM API calls. Use mock fixtures for faster, deterministic execution:

```python
def test_dependency_query(mock_openai, mock_embeddings):
    # Uses mock LLM instead of real API
    pass
```

## Coverage

To generate a coverage report:

```bash
python -m pytest tests/contracts/ tests/integration/ --cov=src/context_foundry --cov-report=html
```

Open `htmlcov/index.html` to view the report.

## Pre-commit Hooks

Contract tests run automatically before each commit. To install:

```bash
pip install pre-commit
pre-commit install
```

To run manually:

```bash
pre-commit run --all-files
```

## CI Pipeline

The GitHub Actions workflow runs:

1. **Contract Tests** - All contract tests must pass
2. **Integration Tests** - Integration tests run
3. **E2E Tests** - Tenant isolation tests run
4. **Lint Check** - Ruff linter
5. **Security Scan** - Bandit security analysis

See `.github/workflows/ci.yml` for details.

## Troubleshooting

### Database Connection Errors

Ensure `DATABASE_URL` environment variable is set:

```bash
export DATABASE_URL="postgresql://user:pass@host:5432/dbname"
```

### RLS Skipped Tests

If tests skip due to RLS, ensure you have a valid tenant context or run tests with RLS disabled for development.

### LLM API Timeouts

E2E tests with real LLM calls may timeout. Use mock fixtures or increase the timeout:

```bash
python -m pytest tests/e2e/ --timeout=300
```
