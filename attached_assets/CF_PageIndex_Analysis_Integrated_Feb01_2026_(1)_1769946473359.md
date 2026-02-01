# PageIndex Analysis for Context Foundry
**Date:** February 1, 2026
**For:** Context Foundry Development
**Source:** https://github.com/VectifyAI/PageIndex
**Contributors:** Claude (strategic analysis), Claude Code (architectural review), Codex (operational review), Riff (implementation analysis)

---

## Executive Summary

PageIndex is an open-source (MIT licensed), reasoning-based RAG framework that replaces vector similarity search with hierarchical tree indexing and LLM-driven tree traversal. It achieved 98.7% accuracy on FinanceBench, significantly outperforming vector-based approaches (~70-80%) on professional documents.

The core insight: **similarity ≠ relevance.** LLMs can reason about where to look, not just match embeddings.

**Bottom line for CF:** PageIndex solves a specific problem CF has — document retrieval quality — using a technique that is philosophically aligned with CF's vision but architecturally complementary, not competing. The tree indexing approach could significantly improve CF's document ingestion and retrieval stages without replacing CF's core knowledge graph, tri-memory, or entity/relationship architecture.

**Verdict:** 3 components are directly applicable and high-value. 3 are medium-value adaptations. 1 is exploratory. 3 should be skipped.

**⚠️ Critical prerequisite:** None of this can be validated until the test runner is fixed. The test infrastructure is currently broken — no corpus has ever had a verified clean run. Implementation without measurement is waste.

---

## 1. What PageIndex Actually Does

### The Core Idea

PageIndex transforms documents into a hierarchical JSON tree structure (like an intelligent table of contents), then uses LLM reasoning to traverse that tree during retrieval instead of using vector similarity search.

**Two-step process:**

1. **Indexing:** PDF → LLM analyzes structure → Hierarchical JSON tree with node IDs, page ranges, and summaries
2. **Retrieval:** Query → LLM reads tree → Reasons about which branch to explore → Fetches relevant sections → Iterates until answer found

No vectors, no chunking. Documents stay semantically coherent.

### The Tree Structure

Each document becomes a nested JSON tree. The tree lives in the LLM's context window, not a separate vector DB:

```json
{
  "title": "Financial Stability",
  "node_id": "0006",
  "start_index": 21,
  "end_index": 22,
  "summary": "The Federal Reserve ...",
  "nodes": [
    {
      "title": "Monitoring Financial Vulnerabilities",
      "node_id": "0007",
      "start_index": 22,
      "end_index": 28,
      "summary": "The Federal Reserve's monitoring ..."
    }
  ]
}
```

### Why It Works Better Than Vector RAG

PageIndex's core argument — and the evidence supports it:

- **Similarity ≠ Relevance.** Vector search finds text that *sounds like* the query. Reasoning finds text that *answers* the query. These are different things.
- **No chunking artifacts.** Documents split naturally at section boundaries, not arbitrary 512-token windows.
- **Cross-references work.** When a document says "see Appendix G," the LLM can follow that reference through the tree. Vector search cannot.
- **Context-aware retrieval.** Multi-turn conversations inform which branches to explore next. Vector search treats each query independently.
- **Explainable.** You can trace exactly why a section was retrieved (the LLM's reasoning path through the tree), unlike opaque vector similarity scores.

### How the Processing Pipeline Works

**PDF Processing (5 phases):**
1. Page extraction and token counting
2. Table of contents detection (3 fallback modes: TOC with page numbers → TOC without page numbers → generate from content)
3. Tree structure generation via `meta_processor` with accuracy-based fallbacks
4. Recursive node subdivision for large sections (configurable max pages/tokens per node)
5. Tree assembly and enrichment (node IDs, summaries, document description)

**Markdown Processing (4 phases):**
1. Header extraction (uses `#` levels for hierarchy)
2. Text extraction and level detection
3. Optional tree thinning (merges small nodes)
4. Stack-based tree construction

**Enrichment (both paths):**
- Sequential node ID assignment (depth-first)
- LLM-generated summaries (leaf nodes get full summaries, parent nodes get prefix summaries)
- Document-level description generation

### What's Not Novel (Just Good Prompt Engineering)

- **ToC detection**: "Is there a table of contents on this page?" — standard LLM prompting
- **Title appearance checking**: Fuzzy matching via LLM — could be done with embeddings too
- **Page number extraction**: Regex + LLM cleanup — nothing special

The novel part is the **architectural decision** to use tree traversal instead of vector search, not the individual prompts.

---

## 2. Relevance to Context Foundry's Known Problems

### Problem 1: Spreadsheet Row-Level Extraction (Biggest Failure Category)

**CF's issue:** 15 of 37 failures in the Jan 20 test were spreadsheet/row-level data (employee directories, sales pipelines, expense reports, customer metrics).

**PageIndex relevance:** Moderate. PageIndex's vision-based RAG mode works directly from PDF page images without OCR, which could handle tabular layouts better than text extraction. However, PageIndex doesn't specifically solve structured data extraction — it's designed for navigating long narrative documents.

**Verdict:** Not a direct fix, but the vision RAG approach is worth exploring for table-heavy documents. This is CF's biggest failure category — can't ignore it.

### Problem 2: Retrieval Quality for Complex Queries

**CF's issue:** Comparison queries returning wrong results ("highest ACV deal" returning the wrong deal), multi-hop questions failing.

**PageIndex relevance:** High. This is exactly what PageIndex is built for. The reasoning-based tree traversal can follow relationships across document sections, backtrack when information is insufficient, and aggregate from multiple sections — something vector retrieval fundamentally cannot do.

**Verdict:** Strong fit. The iterative reasoning loop (read TOC → select section → extract → sufficient? → if no, try another section) is precisely what CF needs for complex queries.

**Note:** Some failures in this category (Q16/Q31/Q82) are actually retrieval *pattern* issues, not complex query issues — the existing search patterns in `document_searcher.py` are too restrictive, missing relevant documents entirely. Current local fixes (pending merge) prove this: loosening patterns recovers the right results without any architectural change. PageIndex would help with genuinely complex queries; pattern fixes handle the rest.

### Problem 3: "I Don't Know" Detection (Data Gates)

**CF's issue:** Q196-200 should return "not in documents" but the system guesses or hangs.

**PageIndex relevance:** Moderate. Because PageIndex's retrieval is reasoning-based, the LLM can determine "I've searched the relevant sections and this information isn't here" more reliably than vector search, which always returns *something* even if nothing is relevant.

**Verdict:** The tree traversal approach naturally supports "I searched everywhere relevant and found nothing" — a better foundation for Data Gates than similarity scores.

### Problem 4: Temporal/Date Queries

**CF's issue:** Date-bound queries partially broken.

**PageIndex relevance:** Low. PageIndex doesn't specifically handle temporal reasoning. This remains a CF-specific challenge at the knowledge graph level.

---

## 3. What CF Should Adopt

### A. Hierarchical Document Indexing — HIGH VALUE ✅

**What:** During document ingestion, generate a PageIndex-style tree structure alongside entity/relationship extraction.

**Why:** CF currently chunks documents for vector storage. Adding a hierarchical tree index preserves document structure and enables structured navigation during retrieval.

**How it fits CF's architecture:**
- Tree index stored as metadata alongside the document in the vault
- Knowledge graph (entities/relationships) remains CF's primary knowledge structure
- Tree index becomes a secondary retrieval path for document-level questions
- The tree feeds INTO entity extraction (better section boundaries = better extraction)

**CF-specific type definition:**
```typescript
interface CFEntityNode {
  node_id: string;           // entity_id from Neo4j
  name: string;              // entity name
  summary: string;           // LLM-generated summary
  confidence: number;        // resolution confidence
  metadata: {
    type: string;            // "SERVICE" | "TEAM" | "METRIC"
    source_doc?: string;     // originating document
    start_index: number;     // page/section start
    end_index: number;       // page/section end
  };
  relationships: CFEntityNode[];  // child nodes
}
```

**Implementation:** PageIndex is MIT licensed. The `page_index.py` and `page_index_md.py` modules can be adapted directly.

**Effort:** 2-3 days | **Validates:** Validation 3 (better retrieval)

### B. Reasoning-Based Retrieval Loop — HIGH VALUE ✅

**What:** Add tree-search retrieval as an alternative or complement to CF's current semantic search + graph traversal. The key pattern is iterative: read ToC → select section → extract → check sufficiency → loop or answer.

**Why:** CF's query pipeline currently does: intent classification → semantic search → graph traversal → coherence check → answer. Adding a tree-search stage improves retrieval for document-structure-dependent questions.

**Current CF flow:**
```
Query → Entity Resolution → Return grounded facts
```

**Enhanced CF flow:**
```
Query → Intent Classification → [Tree Search + Graph Traversal + Semantic Search]
                                         ↓
                              Merge & Rank Results
                                         ↓
                              Coherence Check → Answer
```

The tree search, graph traversal, and semantic search run in parallel. Results are merged and ranked before the answer stage.

**Routing clarity (Claude Code):** "Find CEO" → knowledge graph. "Find CEO's 2030 strategy statement" → tree search → section → extract. The query type determines which retrieval path leads.

**Core loop pattern (from PageIndex, adapted for CF):**
```python
def reasoning_retrieval(query, tree_index):
    context = []
    while not is_sufficient(context, query):
        section = llm_select_section(tree_index, query, context)
        content = fetch_section(section)
        context.append(content)
        if max_iterations_reached():
            break
    return generate_answer(query, context)
```

**Effort:** 3-5 days | **Validates:** Validation 3, Validation 6

### C. Entity Summary Caching — HIGH VALUE ✅

**What:** Each entity/tree node gets an LLM-generated summary for quick navigation without full relationship traversal.

**Why:** Pre-computed summaries enable faster reasoning during retrieval. Instead of traversing the full knowledge graph for every query, the LLM can scan summaries to decide where to drill deeper.

**Implementation:**
```typescript
async function generateEntitySummary(entity: Entity): Promise<string> {
  const relationships = await getRelationships(entity.id);
  const prompt = `Summarize this entity's role in the system:
    Name: ${entity.name}
    Type: ${entity.type}
    Dependencies: ${relationships.map(r => r.target.name).join(', ')}`;
  return await llm.generate(prompt);
}
```

**Effort:** 3-5 days | **Validates:** Validation 3 (faster retrieval), Validation 6 (richer context)

### D. Natural Section Boundaries for Extraction — MEDIUM VALUE 🔶

**What:** Use PageIndex's tree structure to define extraction boundaries instead of arbitrary chunking.

**Why:** CF currently chunks documents into fixed-size pieces for entity extraction. If a chunk boundary cuts through a sentence about a relationship ("Dr. Chen reports to | the CEO of MedSync"), the extraction fails. PageIndex's natural section boundaries solve this. This is directly what improved CF's entity count from 12 to 55 when chunking was fixed in December.

**How:** Run PageIndex tree generation as a pre-processing step before entity extraction. Each tree node becomes an extraction unit instead of arbitrary chunks.

**Effort:** 2-3 days | **Validates:** Validation 3 (better extraction)

### E. Selective Re-Extraction via Tree Branches — MEDIUM VALUE 🔶

**What:** When a document is updated, use the tree structure to identify which sections changed and re-extract only those branches.

**Why:** Currently, updating a document means re-ingesting the entire thing — re-chunking, re-extracting all entities, re-embedding. With a tree index, you can diff the old and new trees, identify changed nodes, and re-extract only those sections. Everything else stays intact.

**How:** Compare old tree and new tree node-by-node (title + content hash). Changed or new nodes get re-processed through entity extraction. Unchanged branches keep their existing entities and relationships.

**Impact:** Faster incremental updates, less LLM cost, and — critically — unchanged knowledge stays stable instead of being subject to extraction variance on every re-run.

**Effort:** 2-3 days | **Validates:** Validation 8 (completeness)

### F. Tree Metadata for the Evidence Layer — MEDIUM VALUE 🔶

**What:** Store PageIndex node summaries and tree position alongside entity mentions in CF's Evidence Layer.

**Why:** CF's planned Evidence Layer (Phase 2 on the architecture roadmap) stores immutable mentions — what documents actually say, with full provenance. PageIndex tree metadata enriches this: each entity mention can carry not just "document X, page Y" but "document X, section 'Financial Stability > Monitoring Vulnerabilities', pages 22-28, node summary: 'The Federal Reserve's monitoring...'"

**How:** When entity extraction runs against tree-defined sections, the tree node metadata (node_id, title, summary, page range) gets attached to every entity_mention and relation_mention record. This gives the Evidence Layer structural context, not just page numbers.

**Impact:** Better provenance, better audit trails, and richer context for the Canonical Layer to work with when aggregating confidence.

**Effort:** 1-2 days | **Validates:** Validation 6, Validation 8

### G. Vision-Based Document Processing — EXPLORATORY 🔬

**What:** PageIndex's vision RAG mode processes PDF pages as images, bypassing OCR entirely.

**Why:** Could improve handling of tables, charts, and complex layouts that CF currently struggles with. This is CF's biggest failure category (15 of 37 failures were spreadsheet/row-level data). Can't write it off.

**Caveat:** Requires multimodal LLM (GPT-4V or similar), adds cost per page. Worth experimenting with but not a primary integration path.

**Effort:** 3-5 days | **Validates:** Validation 8 (completeness)

---

## 4. What CF Should NOT Adopt

### Replacing the Knowledge Graph ❌

PageIndex is a document retrieval system. CF is a cognitive middleware layer. PageIndex finds the right section of a document. CF understands entities, relationships, and reasons across multiple documents. These are different layers — PageIndex should feed into CF, not replace any part of CF's core architecture.

### Abandoning Vector Search Entirely ❌

PageIndex markets itself as "vectorless." CF should not follow this path. Vector search remains useful for cross-document semantic queries ("find everything related to revenue growth"). The tree index is better for within-document navigation. CF should use both.

### PageIndex's Cloud Service ❌

PageIndex offers a hosted API. CF should not depend on an external service for its core document processing. Use the open-source library directly.

### ToC Extraction Pipeline ❌

Heavily PDF-specific in its implementation (PyMuPDF, physical page detection, LLM-based ToC parsing). CF should use the tree generation concept but not port the PDF-specific parsing code unless PDF ingestion becomes a primary path. The markdown processing pipeline is more relevant to CF's current document formats.

---

## 5. Integration Architecture

```
CURRENT CF PIPELINE:
Document → Chunking → Entity Extraction → Knowledge Graph
                  ↓
         Vector Embedding → Vector Store
                  ↓
Query → Semantic Search + Graph Traversal → Answer

PROPOSED CF PIPELINE (WITH PAGEINDEX):
Document → PageIndex Tree Generation → Tree Index (stored per document)
                  ↓
         Section-Based Entity Extraction → Knowledge Graph
                  ↓                              ↓
         Entity Summary Generation       Vector Embedding (by section)
                  ↓                              ↓
         Summary Cache                   Vector Store
                  ↓
Query → Intent Classification
         ├── Tree Search (document-level questions)
         ├── Semantic Search (cross-document questions)  
         └── Graph Traversal (relationship questions)
                  ↓
         Merge & Rank → Coherence Check → Answer
```

### Key Design Decisions

**Consolidate, don't add.** CF already has two detection systems: `document_searcher.py` and `retrieval_router.py`. PageIndex integration should replace or unify these into a single tree-aware retrieval path — not add a third system alongside them. The tree index gives both systems what they're trying to approximate with pattern matching.

**Tree index is per-document, stored in the vault.** Each document gets its own tree. The tree is generated once during ingestion and stored alongside the document metadata.

**Entity extraction uses tree sections, not arbitrary chunks.** Better section boundaries = better entity extraction = better knowledge graph.

**Retrieval is hybrid.** Tree search, vector search, and graph traversal all contribute to the answer. The query pipeline decides which paths to use based on intent classification.

**Tree search is optional per query.** Simple factual lookups ("who is the CEO?") go straight to graph traversal. Document-structure questions ("what does section 3.2 say about liabilities?") use tree search. Complex questions use all three.

**Routing examples (Claude Code):**
- "Find CEO" → Graph traversal
- "Find CEO's 2030 strategy statement" → Tree search → section → extract
- "Compare revenue across divisions" → Tree search + semantic search
- "How does team A relate to team B?" → Graph traversal
- "What does the annual report say about risk?" → Tree search

---

## 6. Reference Code

### Tree Node Type Definition
```typescript
// From PageIndex — adapt for CF
interface PageIndexNode {
  node_id: string;
  title: string;
  start_index: number;
  end_index: number;
  summary?: string;
  sub_nodes?: PageIndexNode[];
}
```

### CF Entity Node (Extended)
```typescript
interface CFEntityNode {
  node_id: string;
  name: string;
  summary: string;
  confidence: number;
  metadata: {
    type: string;
    source_doc?: string;
    start_index: number;
    end_index: number;
  };
  relationships: CFEntityNode[];
}
```

### Reasoning Retrieval Loop
```python
# Core pattern from PageIndex — the iterative loop
def reasoning_retrieval(query, tree_index):
    context = []
    while not is_sufficient(context, query):
        section = llm_select_section(tree_index, query, context)
        content = fetch_section(section)
        context.append(content)
        if max_iterations_reached():
            break
    return generate_answer(query, context)
```

### Entity Summary Generation
```typescript
async function generateEntitySummary(entity: Entity): Promise<string> {
  const relationships = await getRelationships(entity.id);
  const prompt = `Summarize this entity's role in the system:
    Name: ${entity.name}
    Type: ${entity.type}
    Dependencies: ${relationships.map(r => r.target.name).join(', ')}`;
  return await llm.generate(prompt);
}
```

---

## 7. Implementation Effort

| Task | Effort | Priority | Validates |
|------|--------|----------|-----------|
| **Fix test runner (PREREQUISITE)** | **???** | **BLOCKING** | **Everything** |
| **Test tree retrieval on failure set (Q24/Q66/Q79)** | **1 day** | **High** | **Validation 3 (targeted proof)** |
| Integrate tree generation into ingestion | 2-3 days | High | Validation 3 |
| Add tree search as query pipeline stage | 3-5 days | High | Validation 3, 6 |
| Entity summary caching | 3-5 days | High | Validation 3, 6 |
| Replace chunk boundaries with tree sections | 2-3 days | Medium | Validation 3 |
| Test on existing corpora (Manus, MedSync, NexaTech) | 1-2 days | High | Validation 3, 5 |
| Implement selective re-extraction via tree diff | 2-3 days | Medium | Validation 8 |
| Attach tree metadata to Evidence Layer mentions | 1-2 days | Medium | Validation 6, 8 |
| Add navigation path caching for common queries | 1-2 days | Low | Validation 3 |
| Vision RAG exploration for tables | 3-5 days | Low | Validation 8 |

**Total: ~2-3 weeks of focused work** (after test runner is fixed).

**Dependencies:**
- OpenAI API key (PageIndex uses GPT-4o for tree generation)
- Can be adapted to use Anthropic API instead (prompt modifications needed)
- MIT license — no legal barriers

---

## 8. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| LLM cost for tree generation | Medium | Medium | Generate once per document, cache tree index |
| Tree quality varies by document type | Medium | Low | Fallback to current chunking if tree generation fails |
| **Poor structure documents (OCR, unformatted)** | **High** | **Medium** | **Automatic fallback: if tree confidence low, silently use chunking** |
| Added complexity to ingestion pipeline | High | Medium | Make tree generation optional, flag-controlled |
| Dependency on external LLM for indexing | High | Low | Already dependent on LLM for entity extraction |
| Token cost per query (multiple LLM calls) | Medium | Medium | Cache tree structures; limit iteration depth |
| Latency (ToC read → select → extract → verify) | Medium | Low | Parallel execution with other retrieval paths |
| Cold start (need tree before querying) | Low | Low | Generate during ingestion, not at query time |

---

## 9. Recommendation

**Adopt PageIndex's tree indexing and reasoning-based retrieval as a complementary layer in CF.**

This is not a pivot. It's an enhancement to CF's document processing that directly addresses known weaknesses (complex query retrieval, section-boundary chunking, "I don't know" detection) while staying fully aligned with CF's cognitive middleware vision.

**The tree index becomes CF's "document memory."** The knowledge graph remains CF's "understanding." Together, they give CF both structural navigation and semantic reasoning — which is what the tri-memory architecture promises.

### Validation Sequence

**Step 0: Fix the test runner.** Nothing else matters until you can measure. No corpus has ever had a verified clean run. Every recommendation below requires clean measurement.

**Step 1: Run Claude Code's manual section-aware routing fixes.** Claude Code has written section-aware routing (JV/partnership detection, company overview detection) and loosened `document_searcher.py` patterns as manual retrieval fixes. These are essentially a hand-coded prototype of what PageIndex automates. However, these changes are not yet deployed — there's a push conflict pending, and the pattern fixes are sitting in a local commit waiting for Replit's current test to complete before merge. Once merged, if they improve accuracy on Q16/Q31/Q77/Q82, that validates structure-aware retrieval with zero new dependencies.

**Step 2: Get a clean baseline.** Run the full 235 questions with manual fixes. Record accuracy. This is the number to beat.

**Step 3: Test tree-guided retrieval on the failure set.** Before full integration, test tree-guided retrieval specifically against known failures (Q24, Q66, Q79 and the comparison/multi-hop failures from the Jan 20 run). If tree search resolves even half of those, the case for wider adoption is proven with minimal effort.

**Step 4: Integrate PageIndex for full automation.** If both Step 1 and Step 3 show improvement, invest in the full integration.

**Step 5: Comparative test.** Run the same 235 questions with and without tree-augmented retrieval. This directly advances Validation 3.

### Design Principle to Reinforce

CF's entity resolution already embodies the "reasoning over structure" philosophy — it resolves to a specific entity, not "similar" ones. PageIndex validates this approach with independent evidence. Double down on it:
- Add confidence thresholds for disambiguation
- Build explicit navigation paths for common query patterns
- Cache frequently-traversed paths
- Use page offset logic for precise document section → entity mapping

---

*This analysis integrates strategic review (Claude), architectural review (Claude Code), operational review (Codex), and implementation analysis (Riff). Based on PageIndex's open-source repository (MIT license), published documentation, and DeepWiki code analysis.*
