# Context Foundry - Tri-Memory Cognitive Architecture MVP

## Overview
Context Foundry is a proof-of-concept demonstrating a tri-memory cognitive architecture (Semantic/Episodic/Symbolic) for multi-hop reasoning with full provenance and confidence scoring. It provides domain-agnostic reasoning, validated in IT operations and organizational chart domains, outperforming baseline systems in provenance tracking and rule citation by offering detailed and reliable responses.

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
1.  **Semantic Memory (Knowledge Graph)**: PostgreSQL stores entities and relationships with lifecycle states, provenance tracking, and confidence scoring.
2.  **Episodic Memory (Vector Search)**: PostgreSQL with pgvector stores document embeddings for similarity-based retrieval.
3.  **Symbolic Memory (Rules Engine)**: Business rules with priority ordering for response validation.

### Agent Pipeline
-   **Retrieval Agent**: Queries all three memory layers to build a `ContextBundle`.
-   **Reasoning Agent**: Uses OpenAI (gpt-4o-mini) to generate responses.
-   **Validation Agent**: Checks responses against symbolic rules.
-   **Graph Loader**: Handles data ingestion.

### UI/UX Decisions (Web Interface)
-   **Theme**: "Cybernetic Operations" HUD-style with a deep slate background and electric cyan accents.
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

### Feature Specifications
-   **Core Queries**: Impact analysis, escalation path finding, team ownership, dependency chain.
-   **Synthetic Data**: Scaled IT operations data and org chart data for testing.

## External Dependencies
-   **Database**: PostgreSQL (Neon via Replit).
-   **LLM**: OpenAI (gpt-4o-mini via Replit AI Integrations).
-   **Vector Embeddings**: pgvector with OpenAI text-embedding-3-small (1536 dimensions).
-   **Web Framework**: Flask.
-   **Deployment**: Gunicorn.

## Required Environment Variables
-   **OPENAI_API_KEY**: Required for episodic memory embeddings (text-embedding-3-small). Note: Replit AI Integrations only supports chat completions, not embeddings endpoint, so a direct OpenAI API key is needed for document ingestion.

## Recent Changes (Dec 4, 2025)
-   Replaced simple_embedding() hash-based placeholders with real OpenAI text-embedding-3-small embeddings
-   Updated schema from Vector(384) to Vector(1536) for OpenAI embedding dimensions
-   Re-ingested all 231 synthetic documents with real embeddings
-   Retrieval quality improved: "cloud migration" queries now return 0.61-0.72 similarity (up from 0.09-0.17)

### Confidence Calibration System (Dec 4, 2025)
Implemented 3-phase confidence calibration to fix topic-centric query handling:

1. **Sufficiency Autorater** - LLM evaluates if context is SUFFICIENT/PARTIAL/INSUFFICIENT before synthesis
2. **Quadrant Confidence** - 4-quadrant scoring based on entity+docs presence:
   - Q1: Entity + Good docs → 0.90 base (best case)
   - Q2: Entity + No docs → 0.70 base (graph only)
   - Q3: No entity + Good docs → 0.65+ base (topic-centric - WAS BROKEN, NOW WORKS)
   - Q4: No entity + No docs → 0.10 base (correctly abstains)
3. **Entity Density Scoring** - Proxy grounding via known entity mentions in documents

**Results:**
| Query | Before | After |
|-------|--------|-------|
| "Mia White concerns" (entity exists) | 95% | 50% |
| "Cloud migration decisions" (topic with docs) | **10%** | **64%** |
| "Project Omega" (unknown topic) | 10% | 10% |

Key fix: Topic-centric queries now synthesize from documents even when no matching entity exists, enabling queries about projects, initiatives, and decisions.

### Autorater Context Visibility Fix (Dec 4, 2025)
Fixed issue where the Sufficiency Autorater couldn't see document evidence due to context truncation:

**Root Cause:** The Knowledge Graph section was ~9,500 chars, pushing documents beyond the autorater's 8,000 char window. The autorater was rating INSUFFICIENT even when docs contained clear evidence.

**Solution:**
1. **Reordered context sections** - Documents now come BEFORE Knowledge Graph (docs ~2,800 chars appear within 8K window)
2. **Increased doc snippets** - From 300 chars to 800 chars per document (5 docs × 800 = 4,000 chars, within budget)

**Results:**
| Query | Before Fix | After Fix |
|-------|------------|-----------|
| "Mia White concerns" | 50% (INSUFFICIENT) | **95%** (SUFFICIENT) |
| "Cloud migration decisions" | 64% (no change) | 64% (no regression) |

**Context Order:** Documents → Knowledge Graph → Rules → Uncertainty Report

### Regression Test Suite (Dec 4, 2025)
Created comprehensive test suite with 37 tests covering:

**Test Categories:**
- **Entity Queries (7 tests)**: Mia White concerns, Alex Rivera role, Auth Service ownership, team members, dependencies, escalation paths, service tiers
- **Topic Queries (6 tests)**: Cloud migration decisions, cost reduction, frontend framework, observability, Q4 budget, hiring plans
- **Impact Queries (4 tests)**: Auth Service failure cascade, Payment Service outage, API Gateway blast radius, Notification Service impact
- **Missing Entity Abstention (5 tests)**: Unknown services, persons, projects, teams, fictional topics
- **Contradiction Handling (3 tests)**: Vendor switches, cost target evolution, decision reversals
- **Temporal Reasoning (5 tests)**: Migration timelines, recent hires, Q4 initiatives, incident sequences, meeting decisions
- **Edge Cases (4 tests)**: Ambiguous names, partial matches, short queries, multi-hop reasoning
- **Confidence Calibration (3 tests)**: Q1/Q3/Q4 quadrant verification

**Test Assertions:**
- Confidence in expected range (varies by query type)
- Key facts present in answer
- No hallucinated content (forbidden terms check)
- Correct entity mentions

**Usage:**
```bash
python run_regression_tests.py           # Run all 37 tests
python run_regression_tests.py --quick   # Run 5 key tests (~1 min)
python run_regression_tests.py --smoke   # Run 2 smoke tests (~15 sec)
```