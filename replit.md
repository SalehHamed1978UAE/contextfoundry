# Context Foundry - Dual-System Cognitive Architecture

## Overview
Context Foundry implements a dual-system cognitive architecture for enterprise knowledge graph governance. It separates Ontology Foundry (schema governance) from Context Foundry (instance governance) to allow for different governance cadences, confidence thresholds, and agent responsibilities. The project provides a robust framework for managing knowledge graphs, emphasizing structured truth delivery and a cognitive cycle approach to information processing, enabling multi-tenancy and advanced knowledge extraction capabilities with a focus on structured truth delivery and preventing hallucinations.

## User Preferences
- Iterative development with detailed explanations
- Ask before making major changes
- Comprehensive logging at every step
- Prevent silent failures and "confident wrong answer" hallucinations
- Provide human review workflow for conflicts and duplicates
- Ensure resilient database error handling with session rollback

## System Architecture

### Core Architecture
The system is divided into two main services: Platform Foundation (handles multi-tenancy, user management, authentication, document management, usage metering, external AI integrations) and Brain (manages knowledge extraction, ontology governance, entity/relationship management, tri-memory architecture, query/reasoning agents). Communication uses HTTP with shared Pydantic types.

### Governance Separation
- **Ontology Foundry (Schema Governance)**: Manages types of entities and relationships with high confidence and a slower cadence, defining schemas and validation rules.
- **Context Foundry (Knowledge Governance)**: Manages instances of entities and relationships with continuous cadence and configurable confidence, handling entities, relationships, documents, and embeddings.

### Database Schema Structure
Three logical schemas: `ontology` (schema governance), `context` (instance governance), and `platform` (Platform Foundation components). A `shared` schema exists for cross-system components.

### Key Features
- **Immutable Meta-Ontology (Layer 0)**: Defines foundational types and rules.
- **SHACL-Inspired Validation Rules**: Enforce schema quality and consistency.
- **Approval Workflow**: Manages type approval with confidence-based routing.
- **Message Bus**: PostgreSQL-backed for agent coordination with exactly-once semantics.
- **Context Bundle API**: Public API for structured truth delivery.
- **Schema Versioning & Deprecation**: Manages type evolution with audit trails.
- **UI/UX**: Single Page Application (SPA) with Flask/Jinja2, AJAX, SVG graph visualization.
- **Corpus Stats Dashboard**: Displays real-time document processing statistics.
- **OCR Support**: Integrates Tesseract OCR with Claude Vision fallback for visually complex PDFs.
- **Tenant Isolation**: Multi-layer security architecture including PostgreSQL Row-Level Security (RLS) and application-level filtering.
- **Document Management**: Supports upload, versioning, re-queue, and status tracking.
- **Bulk Ingestion System**: Multi-file/ZIP uploads, S3/Google Drive connectors, and content deduplication.
- **Automatic Domain Detection**: Semantic routing classifies documents for domain-specific extraction.
- **Chunked Extraction**: Splits documents into overlapping chunks to prevent LLM output saturation.
- **Query/Reasoning System**: Provides GROUNDED, GAP, and INFERRED responses with hallucination guards, using a 4-AI consensus design.
- **EntityResolver**: Multi-stage pipeline (exact, alias, normalized, semantic, fuzzy match) with disambiguation for robust entity matching. Entity name embeddings are stored in `entities.name_embedding`. Includes intelligent plural/singular normalization (via `inflect` library) and abbreviation expansion (auth→authentication, cdn→content delivery network, etc.).
- **RLM Integration (Recursive Language Model)**: For complex multi-hop queries, including a `QueryComplexityRouter`, specialized `Memory APIs` for tri-memory, a `REPLSandbox` for secure Python execution, an `RLMExecutor`, and a `SubQueryAPI`.

## External Dependencies
- **Database**: PostgreSQL (with pgvector for embeddings)
- **LLM**: OpenAI `gpt-4o-mini`
- **Vision LLM**: Anthropic Claude Sonnet 4
- **Vector Embeddings**: `text-embedding-3-small`
- **Web Framework**: Flask
- **Deployment**: Gunicorn
- **Authentication**: Magic Link, API Keys, JWT Sessions, Google OAuth

## Recent Changes (January 2026)

### Value Demo (6/6 queries working)
- **Demo Script**: `scripts/value_demo.py`
- **Demo Tenant**: 8eee325b-ba3b-447e-9ee7-6d66085ead5f
- **Query Results**:
  1. Blast Radius (0.77) - "If Auth Service goes down, what services are affected?"
  2. Dependency Chain (0.95) - "What does Order Service depend on?"
  3. Ownership (0.50) - "Who manages the Payment Service?"
  4. Incident Impact (0.59) - "What was affected by incident INC-2025-1201?"
  5. Cross-Document Reasoning (0.77) - "Which team should be paged if Orders Database fails?"
  6. Gap Identification (0.50) - "What services have no documented disaster recovery?"
- **Verdict**: CONTEXT FOUNDRY PROVIDES SIGNIFICANT VALUE

### Alias Intelligence System (January 2026)
- **entity_aliases Table**: Stores acronym/synonym mappings with RLS (alias_text, alias_type, source, entity_id)
- **EntityResolver._alias_match()**: Checks entity_aliases before semantic/fuzzy search
- **GraphBuilder Integration**: Extracts aliases from patterns like "Full Name (ABBR)" during ingestion
- **Retrieval Agent Integration**: _verify_target_entity_exists() uses alias resolution
- **Backfill Script**: scripts/backfill_aliases.py extracts aliases from existing entity names
- **Result**: EHR → "Electronic Health Record (EHR)" resolved at 0.77 confidence

### Test 2 Results - Al Shifa Healthcare (6/6 queries working)
- **Demo Tenant**: 7031800f-06ef-4858-b9e8-a22174bfbdae
- **Query Results**:
  1. Blast Radius (0.77) - "If Patient Identity Service goes down..."
  2. Dependency Chain (0.77) - "What does the EHR depend on?" (uses alias)
  3. Ownership (0.95) - "Who manages the Lab System?"
  4. Incident Impact (0.45) - "What was affected by incident INC-2025-0892?"
  5. Cross-Document (0.50) - "Which team should be paged if Master Patient Index fails?"
  6. Gap Identification (0.50) - "What systems have no documented disaster recovery?"

### Bug Fixes (Demo Debugging)
- **RLS Tenant Context Reset**: Fixed `session.commit()` resetting PostgreSQL `SET app.current_tenant_id`
- **EntityResolver UUID Conversion**: Added UUID conversion in `EntityResolver.__init__()`
- **RLM Memory APIs UUID Conversion**: Fixed SemanticMemoryAPI and EpisodicMemoryAPI
- **Query Parser Incident ID Handling**: Fixed extraction of incident IDs like "INC-2025-1201"
- **Retrieval Agent "affected by" Pattern**: Added patterns for incident impact queries
- **A/B Evaluation Tenant Isolation**: Fixed BlindEvaluator not setting RLS tenant context on its session. ContextFoundry relies on RLS while GraphRAGBaseline uses explicit filters. Added `session.execute(text("SELECT platform.set_current_tenant(:tid)"))` in BlindEvaluator.__init__. Web routes now pass g.tenant_id to all evaluators.

### Critical A/B Evaluation Bug Fixes (January 2026)
**Three critical bugs fixed that caused ContextFoundry to return 0 relationships:**

1. **SemanticMemory RLS Context Fix**: Added RLS tenant context setting in `SemanticMemory.__init__()`:
   ```python
   self.session.execute(text("SELECT platform.set_current_tenant(:tid)"), {'tid': tenant_id})
   ```
   Without this, RLS policies blocked all entity/relationship queries.

2. **Flat Dict Structure Fix**: Changed `get_entity_relationships()` to return a flat dict with `relationship_type`, `source_name`, `target_name` at the top level. Previously these were nested under `relationship` key, causing consumers to get `None` values.

3. **Traversal Fallback for Missing Semantics**: Added fallback logic in `traverse_from_entity_with_relationships()` and `traverse_with_frontier_detection()` to traverse bidirectionally when no semantics are defined in schema:
   ```python
   if rel_type_def and rel_type_def.semantics:
       # Use schema rules
   else:
       # FALLBACK: Traverse in both directions
       if rel.source_id == current_id:
           neighbor_id = rel.target_id
       elif rel.target_id == current_id:
           neighbor_id = rel.source_id
   ```

**Result**: ContextFoundry now **outperforms** GraphRAG Baseline:
- ContextFoundry: 134 entities, 134 relationships
- GraphRAG: 18 entities, 54 relationships

### EntityResolver Normalization Enhancement (January 2026)
**Problem**: EntityResolver was too strict - "User Database" wouldn't match "Users Database", "Auth Service" wouldn't match "Authentication Service".

**Solution**: Added intelligent normalization using the `inflect` library:
- **normalize_for_matching()**: Converts entity names to a canonical form by singularizing plurals, expanding abbreviations, and sorting tokens
- **_normalized_match() stage**: Inserted between contains_match and semantic_search for fast matching
- **ABBREVIATION_MAP**: 30+ common IT abbreviations (auth→authentication, cdn→content delivery network, lb→load balancer, etc.)

**Test Results**:
- "API Gateways" → "API Gateway": MATCH
- "Auth Services" → "Auth Service": MATCH
- "Authentication Service" → "Auth Service": MATCH
- "CDN Edge" → "Content Delivery Network Edge": MATCH
- "LB Service" → "Load Balancer Service": MATCH

### 3-Step Query Pipeline (January 2026)
**Problem**: Query interpretation was tightly coupled with retrieval. Blast radius queries might return all relationships instead of filtering by direction.

**Solution**: Separate query interpretation from retrieval with a 3-step pipeline:

1. **Step 1 - Query Interpretation (LLM)**: `QueryInterpreter` parses natural language into structured `QueryIntent`:
   ```json
   {"entity": "API Gateway", "direction": "inbound", "relationship_types": ["DEPENDS_ON", "CALLS"], "depth": 2}
   ```

2. **Step 2 - Directed Retrieval (Code)**: `DirectedGraphRetriever` executes EXACTLY what was asked - precise SQL filtering by direction and relationship types.

3. **Step 3 - Answer Synthesis (LLM)**: Format retrieved results into natural language answer.

**Direction Mapping**:
| Query Type | Direction | Relationship Types |
|------------|-----------|-------------------|
| Blast radius if X fails | inbound | DEPENDS_ON, CALLS |
| What does X depend on | outbound | DEPENDS_ON |
| What services does X call | outbound | CALLS |
| Who manages X | inbound | MANAGES, OWNS |
| What was affected by incident X | outbound | AFFECTS |

**Files**:
- `src/context_foundry/agents/query_interpreter.py` - Step 1
- `src/context_foundry/agents/directed_retriever.py` - Step 2
- `src/context_foundry/agents/query_pipeline.py` - Orchestrator
- `scripts/test_query_pipeline.py` - Test script

**Test Results** (5/5 interpretation tests passing):
- Blast radius query: 8 inbound relationships, 0 outbound ✓
- Dependency query: 5 outbound relationships, 0 inbound ✓

### 3-Step Pipeline Integration (January 2026)
**Problem**: Old blast radius code returned 64 services instead of the correct 19 from database truth. The schema-driven traversal was too permissive, including all relationship types.

**Solution**: Integrated 3-step pipeline into `ContextFoundry.query()` via auto-detection:
- `_is_impact_query()`: Regex patterns detect impact queries (blast radius, if X fails, cascade, etc.)
- `_query_with_3step_pipeline()`: Routes to 3-step pipeline for precise directional filtering

**CascadePath Tracking**: Added `CascadePath` dataclass in `directed_retriever.py` for impact chain visualization:
```python
@dataclass
class CascadePath:
    path: List[str]           # ["Auth Service", "API Gateway", "GraphQL Gateway"]
    depth: int                # 2
    relationship_types: List[str]  # ["DEPENDS_ON", "DEPENDS_ON"]
```

**Multi-Path Support**: Tracks ALL valid paths per entity via path signatures:
- "Order Service" has 5 different impact chains reaching it
- Uses `seen_path_signatures` set to avoid duplicates while allowing multiple routes

**Results** (Auth Service blast radius):
| Metric | Old (Broken) | New (3-Step) | Database Truth |
|--------|--------------|--------------|----------------|
| Depth 1 | (in 64) | 6 | 6 |
| Depth 2 | (in 64) | 11-13 | 11-13 |
| Total entities | 64 | 17 | 19 |
| Cascade paths | N/A | 29 | N/A |
| Confidence | ~0.50 | **0.93** | N/A |