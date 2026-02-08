# Tree Retrieval Postmortem: Theory vs Reality

**Date**: 2026-02-08
**Status**: FAILED - Feature produces worse results than baseline

---

## TL;DR

**Theory**: Tree retrieval would fix entity confusion by prioritizing graph proximity over semantic similarity. Expected +8-12% improvement.

**Reality**: Tree retrieval produces -12% worse results. It hallucinates wrong entities and misses basic facts.

**Verdict**: Either the implementation is fundamentally broken, OR the theory is wrong for this data structure.

---

## The Original Theory (from TREE_BASED_RETRIEVAL_SPEC.md)

### Problem Statement

> "Current retrieval uses flat semantic search that often prioritizes document text over knowledge graph relationships, causing wrong entities to be selected even when correct data exists in the KG."

### Example Given
```
Query: "What is the FY2026 capex?"

Problem: Wrong fiscal year data or wrong organization data retrieved
Root Cause: Semantic similarity ranks similar text equally regardless of org mismatch
```

### Proposed Solution

**Hierarchical Graph Traversal**
- Treat KG as a tree rooted at anchor organization
- Rank by **graph distance** (depth 1-3) not just semantics
- Traverse relationships: anchor → LEADS → person, anchor → HAS_PROJECT → project

### Expected Results

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Overall Accuracy | 87% | 96-100% | +9-13 points |
| MISMATCH Failures | 9 | 0-2 | -7-9 |
| Graph Traversal Used | 20% | 80%+ | +60 points |

**Expected**: Fix 13 failing questions, achieve 95%+ accuracy

---

## What Actually Happened

### Actual Results

| Metric | Tree OFF | Tree ON | Change |
|--------|----------|---------|--------|
| Overall Accuracy | 80% | 68% | **-12 points** ❌ |
| Questions Helped | N/A | 1 | Only 1/100 |
| Questions Hurt | N/A | 13 | Made worse |
| MISMATCH Failures | 12 | 19 | **+7** ❌ |

**Opposite of predicted**: Tree retrieval INCREASED mismatches instead of reducing them!

---

## Critical Failures

### 1. Hallucinated Wrong People (MISMATCH)

| Question | Expected | Tree OFF | Tree ON |
|----------|----------|----------|---------|
| Who is the CEO? | Dr. Victoria Chen | ✅ Correct | ❌ Dr. Sarah Thompson |
| Who is the CFO? | Michael Chang | ❌ "Hedging Policy" | ❌ Dr. Robert Kim |
| Who is President of Digital? | Robert Kim | ✅ Correct | ❌ Kevin Chang |
| Primary customer for HTS wire? | Siemens | ✅ Correct | ❌ Boeing |

**Pattern**: Tree retrieval returns WRONG entities with high confidence. This is worse than saying "I don't know".

**Question**: Where is "Dr. Sarah Thompson" even coming from? Is this entity in the graph? Or is it being invented?

---

### 2. Missing Basic Aggregates (NO_DATA)

| Question | Expected | Tree OFF | Tree ON |
|----------|----------|----------|---------|
| How many employees? | 12,500 | ✅ Correct | ❌ "Insufficient data" |
| How many divisions? | 4 | ✅ Correct | ❌ "Insufficient data" |
| How many satellites? | 48 | ✅ Correct | ❌ "Insufficient data" |
| How many endpoints? | 2.1M | ✅ Correct | ❌ "Insufficient data" |

**Pattern**: Tree traversal cannot find count/aggregate facts that are likely stored in document chunks, not as graph relationships.

**Theory Failure**: The spec assumes aggregates would be in the graph. They're not.

---

### 3. The ONE Success

**Q76: What is the total patent portfolio size?**
- Expected: 2,412 patents
- Tree OFF: ❌ "insufficient data"
- Tree ON: ✅ Correct

This is the ONLY question (1/100) where tree retrieval helped.

---

## Root Cause Analysis

### Hypothesis 1: Implementation Bugs

**Possible Issues:**
1. Graph traversal following wrong relationship types
2. Entity matching logic is broken (matching wrong PERSON entities)
3. Anchor resolution returning wrong starting point
4. Ranking algorithm prioritizing wrong results

**Evidence**:
- Hallucinating "Dr. Sarah Thompson" suggests wrong entity traversal
- Multiple PERSON confusion errors (CEO, CFO, President)
- Pattern: Similar roles being confused

**What to Check**:
```sql
-- Does "Dr. Sarah Thompson" even exist in the graph?
SELECT * FROM entities
WHERE name LIKE '%Sarah Thompson%'
AND tenant_id = '4668fc6d-c401-46d2-9797-4c8785f4d6ce';

-- What CEO relationships exist?
SELECT e.name, r.relationship_type, r.target_entity_name
FROM relationships r
JOIN entities e ON r.source_id = e.id
WHERE r.relationship_type IN ('CEO_OF', 'LEADS')
AND r.tenant_id = '4668fc6d-c401-46d2-9797-4c8785f4d6ce';
```

---

### Hypothesis 2: Knowledge Graph Quality Issues

**Possible Issues:**
1. **Wrong relationships extracted** - CEO relationship points to wrong person
2. **Duplicate entities** - Multiple "Robert Kim" entities confused
3. **Missing relationships** - Aggregates (employee count) not stored as relationships
4. **Relationship direction confusion** - Traversing in wrong direction

**Evidence**:
- Tree retrieval can't find counts → counts not in graph
- Person confusion → multiple similar entities or wrong relationships
- Q2: CFO query returns "Hedging Policy" → relationship labels corrupted?

**What to Check**:
```sql
-- How many PERSON entities exist?
SELECT entity_type, COUNT(*)
FROM entities
WHERE tenant_id = '4668fc6d-c401-46d2-9797-4c8785f4d6ce'
GROUP BY entity_type;

-- Are there duplicate people?
SELECT name, COUNT(*)
FROM entities
WHERE entity_type = 'PERSON'
AND tenant_id = '4668fc6d-c401-46d2-9797-4c8785f4d6ce'
GROUP BY name
HAVING COUNT(*) > 1;

-- Check for aggregate-type relationships
SELECT relationship_type, COUNT(*)
FROM relationships
WHERE tenant_id = '4668fc6d-c401-46d2-9797-4c8785f4d6ce'
AND relationship_type LIKE '%COUNT%' OR relationship_type LIKE '%TOTAL%'
GROUP BY relationship_type;
```

---

### Hypothesis 3: Theory is Wrong for This Data

**Possible Issues:**
1. **Document chunks contain truth, graph doesn't** - Facts are in prose, not extracted as relationships
2. **Graph extraction quality too low** - Extraction created wrong/noisy relationships
3. **Anchor-centric view is wrong** - Some facts aren't connected to anchor org
4. **Semantic search actually works better** - For this dataset, similarity > structure

**Evidence**:
- Flat retrieval finds counts easily → they're in document chunks
- Tree retrieval misses specs/numbers → not extracted as relationships
- Only 1/100 improvement → graph doesn't add value

**Implication**: Maybe the knowledge graph is **supplementary context**, not the **primary retrieval source**.

---

## Comparison: Spec Assumptions vs Reality

| Spec Assumption | Reality Check | Status |
|-----------------|---------------|--------|
| "Correct data exists in KG" | Counts/aggregates NOT in KG | ❌ FALSE |
| "Document text prioritized wrong" | Document text has correct answers | ❌ REVERSED |
| "Graph proximity > semantics" | Semantics performs better | ❌ FALSE |
| "Anchor resolution works" | Might be resolving to wrong entities | ❓ UNKNOWN |
| "Relationships are reliable" | CEO pointing to wrong person? | ❌ FALSE |

---

## What Should We Do?

### Option 1: Fix the Implementation (Optimistic View)

**Assumption**: The theory is sound, but implementation has bugs.

**Action Plan**:
1. **Investigate hallucinations**
   - Query graph for "Dr. Sarah Thompson", "Kevin Chang", etc.
   - Trace what relationship path led to these wrong answers
   - Check if entities are duplicated or relationships are mislabeled

2. **Fix anchor resolution**
   - Verify anchor is correctly identified (should be "Nexus Industries")
   - Check if wrong anchor → wrong entity selection

3. **Fix relationship traversal**
   - Add logging to show exact path: anchor → rel → entity
   - Verify relationship types are correct
   - Check if depth limits are working

4. **Add document fallback**
   - When graph returns empty, fall back to document chunks
   - This should fix the "insufficient data" for counts

**Timeline**: 1-2 weeks of debugging

**Risk**: Might discover the graph quality is too poor to fix easily

---

### Option 2: Fix the Knowledge Graph (Medium Effort)

**Assumption**: Implementation is correct, but graph extraction created bad data.

**Action Plan**:
1. **Re-extract with better prompts**
   - Fix entity deduplication (Robert Kim vs Robert Kim)
   - Improve relationship extraction (ensure CEO → correct person)
   - Extract aggregate facts as relationships (TOTAL_EMPLOYEES → 12500)

2. **Validate extraction quality**
   - Manual review of top 50 entities
   - Check CEO/CFO/executive relationships are correct
   - Verify no hallucinated entities

3. **Add aggregate extraction**
   - Extract: "12,500 employees" → HAS_EMPLOYEE_COUNT relationship
   - Extract: "4 divisions" → HAS_DIVISION_COUNT relationship
   - This should fix the count queries

**Timeline**: 2-3 weeks (extraction + validation)

**Risk**: Might require redesigning extraction pipeline

---

### Option 3: Abandon Tree Retrieval (Pessimistic View)

**Assumption**: The theory is fundamentally wrong for this dataset.

**Action Plan**:
1. **Keep tree retrieval OFF permanently**
2. **Use graph as supplementary context only**
   - Flat retrieval finds answer in docs
   - Graph enriches answer with relationships
   - Hybrid: "CFO is Michael Chang (from docs), reports to CEO (from graph)"

3. **Focus on improving flat retrieval**
   - Better chunk ranking
   - Better semantic embeddings
   - Add reranking step

**Timeline**: Immediate (just turn it off)

**Pro**: 80% accuracy is already decent, focus on incremental improvements

**Con**: Give up on the vision of graph-first retrieval

---

### Option 4: Hybrid Approach (Pragmatic View)

**Assumption**: Tree retrieval works for SOME queries, not all.

**Action Plan**:
1. **Question-type routing**
   ```python
   if query_type in ['AGGREGATION', 'COUNT']:
       use_flat_retrieval()  # Tree can't handle counts
   elif query_type == 'ROLE':
       try_tree_first()      # Tree good at relationships
       if low_confidence:
           fallback_to_flat()
   ```

2. **Dual-pass verification**
   - Run both tree and flat
   - If answers match → high confidence
   - If differ → use flat (empirically better)

3. **Selective tree use**
   - Only for relationship traversal ("Who reports to X?")
   - Not for facts/specs/counts

**Timeline**: 1 week to implement routing logic

**Pro**: Get benefits of both approaches

**Con**: Adds complexity, might still have hallucination issues

---

## Recommendations

### Immediate (This Week)

1. **Keep tree retrieval OFF** - 80% > 68%, don't deploy broken feature
2. **Run diagnostic queries** - Check if "Dr. Sarah Thompson" exists, verify relationships
3. **Create test suite** - Add unit tests for tree traversal with known-good graph data

### Short Term (1-2 Weeks)

**If diagnostics show implementation bugs:**
- Fix traversal logic
- Add fallback to documents
- Re-test on subset

**If diagnostics show graph quality issues:**
- Review extraction prompts
- Fix entity deduplication
- Add aggregate extraction

### Medium Term (1 Month)

**If bugs fixed:**
- Deploy hybrid approach (question-type routing)
- Monitor for hallucinations
- Gradually increase tree retrieval usage

**If not fixable:**
- Abandon tree-first retrieval
- Use graph as enrichment only
- Focus on improving flat retrieval quality

---

## Open Questions

1. **Where is "Dr. Sarah Thompson" coming from?**
   - Is this a real entity in the graph?
   - Or is tree retrieval inventing entities?

2. **Why can't tree find employee counts?**
   - Are counts stored as relationships?
   - Should we add TOTAL_EMPLOYEES relationship type?

3. **Are relationships bidirectional?**
   - If CEO → LEADS → Nexus, can we traverse Nexus → LEADS → CEO?
   - Or is directionality causing missed results?

4. **What's the graph coverage?**
   - What % of facts are in graph vs document chunks?
   - If <50%, graph-first will always fail

5. **Is the spec based on different data?**
   - Was spec written for a different dataset with better graph quality?
   - Our 80% baseline is already worse than spec's 87% baseline

---

## Lessons Learned

1. **Validate assumptions before building**
   - Spec assumed facts are in KG - they're not (for counts)
   - Should have checked graph coverage first

2. **Hallucinations are worse than "I don't know"**
   - Returning wrong CEO with confidence destroys trust
   - Better to say "insufficient data" than guess wrong

3. **Empirical testing beats theory**
   - Theory predicted +12%, reality is -12%
   - Real data always wins over theoretical models

4. **Graph quality is critical**
   - Tree retrieval amplifies graph errors
   - If extraction is noisy, graph-first fails

---

## Next Steps

**Your Decision**:
- [ ] **Option 1**: Debug implementation (1-2 weeks)
- [ ] **Option 2**: Fix knowledge graph (2-3 weeks)
- [ ] **Option 3**: Abandon tree retrieval (immediate)
- [ ] **Option 4**: Hybrid approach (1 week)

**My Recommendation**: Start with diagnostics (Option 1 investigation), then decide based on findings:
- If simple bugs → fix them
- If graph quality issues → consider Option 2 or 4
- If fundamental theory issues → Option 3

The good news: **Your toggle works perfectly**, so you can easily A/B test any improvements!

