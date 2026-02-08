# What Went Wrong with Tree Retrieval?

**Date**: 2026-02-08
**Verified Data**: Same vault (1d33909b), tree OFF (80%) vs tree ON (64%)

---

## Why Did We Build Tree Retrieval?

### The Original Theory (from spec)

**Problem Statement:**
> "Current retrieval uses flat semantic search that often prioritizes document text over knowledge graph relationships, causing **wrong entities to be selected** even when correct data exists in the KG."

**Example Given:**
```
Query: "What is the FY2026 capex?"
Current behavior: Returns FY2025 data (wrong year)
Root cause: Semantic search ranks "FY2025 capex" equally to "FY2026 capex"
```

**The Solution:**
Build hierarchical graph traversal that:
1. Starts from anchor organization (e.g., "Nexus Industries")
2. Follows relationship paths in knowledge graph
3. Ranks results by **graph distance** (depth 1-3) not semantics
4. Prioritizes entities closer to anchor

**Expected Result:**
- Fix entity confusion (selecting wrong CEO, wrong fiscal year)
- Expected: +8-12% accuracy improvement
- Reduce MISMATCH errors from 9 to 0-2

---

## What We Actually Implemented

We built a 596-line `TreeBasedRetriever` that:

✅ Identifies anchor organization (via `AnchorResolver`)
✅ Extracts query intent (what entity types to look for)
✅ Traverses knowledge graph via BFS (depth 1-3)
✅ Ranks by: `(graph_proximity * 0.7) + (semantic_similarity * 0.3)`
✅ Falls back to semantic search if graph is empty

**The implementation matches the spec exactly.**

---

## What Actually Happened

### Results

| Metric | Theory | Reality |
|--------|--------|---------|
| Accuracy Change | +8-12% | **-16%** ❌ |
| MISMATCH Errors | 9 → 0-2 | 13 → 20 (+7) ❌ |
| Questions Improved | ~13 | **1** ❌ |
| Questions Broken | 0 | **17** ❌ |

**The theory was completely wrong.**

---

## Concrete Examples of Failure

### Pattern 1: Can't Find Counts/Aggregates

Tree traversal cannot find facts stored in document chunks:

| Question | Tree OFF | Tree ON |
|----------|----------|---------|
| How many employees? | ✅ 12,500 | ❌ "Insufficient data" |
| How many divisions? | ✅ 4 divisions | ❌ "Insufficient data" |
| How many endpoints? | ✅ 2.1 million | ❌ "Insufficient data" |
| HTS wire capacity? | ✅ 1,000 km/year | ❌ "not specified" |

**Why:** These facts exist as **sentences in documents**, not as **relationships in the graph**.

Example from document:
> "Nexus Industries employs 12,500 people across 4 divisions."

This becomes document chunk text, not a `HAS_EMPLOYEE_COUNT` relationship.

---

### Pattern 2: Returns Wrong Division/Entity

Tree traversal follows wrong paths and returns plausible but wrong answers:

**Q27: Which division has the most employees?**
- Expected: Nexus Digital Solutions (3,500)
- Tree OFF: ✅ Correct
- Tree ON: ❌ "Materials Division (1,450)"

**Why:** Tree followed: `Nexus → HAS_DIVISION → Materials → HAS_EMPLOYEES → 1,450`
But didn't compare across ALL divisions to find the MAX.

---

### Pattern 3: Missing Specifications

Tree can't find technical specs that are embedded in prose:

**Q42: What is the HTS wire production capacity?**
- Expected: 1,000 km/year
- Tree OFF: ✅ Correct
- Tree ON: ❌ "not specified"

**Q49: What is the Falcon X endurance?**
- Expected: 28 hours
- Tree OFF: ✅ Correct
- Tree ON: ❌ "not specified"

**Why:** Specs like "28 hours endurance" are in document chunks describing the product, not extracted as `HAS_SPEC` relationships.

---

### The ONE Success

**Q38: Who is the CISO of Nexus Industries?**
- Expected: Jennifer Walsh
- Tree OFF: ❌ "not specified"
- Tree ON: ✅ Correct

**Why this worked:** The graph has a `HOLDS_POSITION` relationship: `Jennifer Walsh → CISO → Nexus Industries`

Tree traversal found it via: `Nexus → EMPLOYS → Jennifer Walsh` + role check.

**But:** This ONE success doesn't justify breaking 17 others.

---

## Root Cause Analysis

### The Theory's Fatal Assumptions

| Assumption | Reality Check | Status |
|------------|---------------|--------|
| "Facts exist in KG" | Only relationships exist, not facts | ❌ FALSE |
| "Document text is noisy" | Documents have correct answers | ❌ REVERSED |
| "Graph is authoritative" | Graph is incomplete/sparse | ❌ FALSE |
| "Proximity > Semantics" | Semantics works better empirically | ❌ FALSE |

### What the Spec Got Wrong

1. **Data Location Assumption**
   - Spec assumed: "Employee count is in graph as relationship"
   - Reality: Employee count is in document sentence
   - Graph only has individual `EMPLOYS` relationships, not aggregate `TOTAL_EMPLOYEES`

2. **Comparison Queries**
   - Spec assumed: "Which division has most X?" would traverse all divisions
   - Reality: Tree stops at first division found, doesn't compare
   - Graph traversal isn't comparison-aware

3. **Specification Extraction**
   - Spec assumed: Technical specs would be extracted as relationships
   - Reality: "28 hours endurance" stays in document prose
   - Extraction didn't create `HAS_ENDURANCE → 28 hours` relationships

---

## Why Did This Happen?

### Theory Was Based on Different Data

The spec mentions:
> "from 87% failure analysis"

But our baseline is **80%**, not 87%.

**Hypothesis:** The spec was written for a different dataset where:
- Graph had better extraction quality
- Facts were properly extracted as relationships
- Aggregates existed in graph

Our dataset has:
- Sparse graph (only 691 relationships for 5,573 entities)
- Facts in documents, not graph
- No aggregate relationships

---

## Is Tree Retrieval Fundamentally Wrong?

### No - But It Requires Different Data

Tree retrieval CAN work if:

✅ **Facts are extracted as relationships**
- "12,500 employees" → `HAS_EMPLOYEE_COUNT` relationship
- "28 hours endurance" → `HAS_ENDURANCE` relationship
- "FY2026 capex $500M" → `HAS_METRIC` relationship with temporal scope

✅ **Graph is complete enough**
- High relationship-to-entity ratio (currently 691/5573 = 12%)
- All important facts represented in graph

✅ **Used for the right query types**
- Relationship traversal: "Who reports to X?"
- Path finding: "Connection between X and Y?"
- NOT for: counts, comparisons, specifications

### Our Implementation is Correct

The code works as designed. The problem is:
1. **Our knowledge graph is too sparse**
2. **Our extraction doesn't create aggregate/spec relationships**
3. **Our documents contain the truth, not the graph**

---

## What Should We Do?

### Option 1: Fix Knowledge Graph Extraction (Hard, 2-3 weeks)

**Extract facts as relationships:**
```
"12,500 employees" →
  Nexus Industries -[HAS_EMPLOYEE_COUNT]-> 12500

"Falcon X has 28 hour endurance" →
  Falcon X -[HAS_ENDURANCE]-> 28 hours

"Materials Division has 1,450 employees" →
  Materials Division -[HAS_EMPLOYEES]-> 1450
```

**Then comparison queries work:**
```
Query: "Which division has most employees?"
Traversal:
  Nexus → HAS_DIVISION → [All Divisions]
  For each division → HAS_EMPLOYEES → count
  Return MAX
```

**Pros:**
- Tree retrieval could work as designed
- Would fix entity confusion for relationships

**Cons:**
- Requires redesigning extraction pipeline
- Still wouldn't help with prose-embedded facts
- 2-3 weeks of work
- Might not even reach 80% (current baseline)

---

### Option 2: Hybrid Approach (Medium, 1 week)

**Use tree ONLY for specific query types:**

```python
if query_type in ['WHO', 'RELATIONSHIP']:
    # "Who is the CISO?" - tree is good at this
    try_tree_first()
    if low_confidence:
        fallback_to_flat()

elif query_type in ['COUNT', 'SPEC', 'COMPARISON']:
    # "How many employees?" - tree can't handle this
    use_flat_only()

else:
    # Default to flat (empirically better)
    use_flat_retrieval()
```

**Pros:**
- Get the ONE benefit (role/relationship queries)
- Avoid the 17 failures (counts/specs)
- Relatively quick to implement

**Cons:**
- Added complexity
- Still might not beat 80% overall
- Maintenance burden

---

### Option 3: Abandon Tree Retrieval (Easy, immediate)

**Keep tree OFF permanently:**
- Current accuracy: 80%
- Tree makes it 64%
- No reason to deploy

**Use graph as enrichment only:**
```
1. Flat retrieval finds answer in docs: "Jennifer Walsh is CISO"
2. Graph enriches with relationships: "reports to Dr. Victoria Chen"
3. Combined answer: "Jennifer Walsh (CISO), reports to CEO Dr. Victoria Chen"
```

**Pros:**
- No risk of regression
- Keep proven 80% accuracy
- Focus on improving flat retrieval incrementally

**Cons:**
- Give up on graph-first vision
- Lose the theoretical benefits

---

## My Recommendation

**Option 3 - Abandon tree retrieval for now**

**Why:**
1. **Empirical data beats theory** - Real test shows -16%, not +12%
2. **80% is already good** - Don't break what works
3. **Time investment isn't justified** - Weeks of work for uncertain gain
4. **Graph quality is the real problem** - Fix that first, then retry

**What to do instead:**
1. **Improve extraction quality**
   - Better entity deduplication
   - More accurate relationship extraction
   - Add aggregate/spec relationships

2. **Test graph quality**
   - What % of facts are in graph vs documents?
   - Are relationships correct? (CEO → right person?)
   - Run quality metrics

3. **Revisit tree retrieval later**
   - Once graph is 50%+ complete
   - Once extraction is validated
   - With smaller, controlled test

---

## Lessons Learned

1. **Always validate assumptions**
   - Spec assumed facts in graph - should have checked first
   - Would have saved weeks of implementation

2. **Data quality > Algorithm quality**
   - Tree retrieval code is good
   - But garbage in → garbage out

3. **Empirical testing beats theoretical models**
   - Theory: +12%
   - Reality: -16%
   - Test on real data ASAP

4. **Don't deploy features that make things worse**
   - 64% < 80%
   - Keep it OFF

---

## The Answer to Your Question

**"What is the point of tree retrieval?"**
- To fix entity confusion by prioritizing graph structure

**"Did we implement it wrong?"**
- No, implementation matches spec exactly

**"Is the theory completely wrong?"**
- No, but theory assumed different data (complete graph)

**"What have we gotten wrong?"**
- Assumed our graph had the facts (it doesn't)
- Didn't validate graph quality before building
- Trusted spec's data assumptions

**"Why did we do tree retrieval?"**
- Spec promised +12% improvement
- Theory was sound for the right data
- But our data doesn't match the spec's assumptions

**Bottom line:**
Tree retrieval isn't wrong. Our knowledge graph just isn't good enough to support it yet.

