# Tree Retrieval vs Flat Retrieval - Comparative Analysis

**Date**: 2026-02-08
**Test Dataset**: Nexus Industries (100 questions)
**Vault**: 4668fc6d (501 chunks, 6025 entities, 1025 relationships)

---

## Executive Summary

**Tree Retrieval OFF**: 80% accuracy (80/100)
**Tree Retrieval ON**: 68% accuracy (68/100)
**Net Impact**: -12% (Tree retrieval performs WORSE)

### Key Findings

1. **Tree ON only helped 1 question** (patent portfolio count)
2. **Tree ON hurt 13 questions** (made correct → wrong)
3. **Both agreed on 67 questions** (both correct)
4. **Both failed 19 questions** (both wrong)

---

## Pattern Analysis: Where Tree Retrieval Fails

### 1. Count/Aggregation Questions (6 failures)

Tree retrieval **cannot find counts** that flat retrieval finds easily:

| Q# | Question | Tree OFF | Tree ON |
|----|----------|----------|---------|
| Q7 | How many employees does Nexus Industries have? | ✅ 12,500 | ❌ "Insufficient data" |
| Q26 | How many business divisions does Nexus Industries have? | ✅ 4 divisions | ❌ "Insufficient data" |
| Q41 | How many endpoints does CyberShield protect? | ✅ 2.1 million | ❌ "Insufficient data" |
| Q51 | How many satellites are in the Orbital Constellation project? | ✅ 48 satellites | ❌ "Insufficient data" |
| Q59 | How many global locations does Nexus have? | ✅ Correct | ❌ "Insufficient data" |

**Pattern**: Tree retrieval struggles with **aggregation/counting questions**. It's too focused on graph traversal and misses document-level aggregate facts.

---

### 2. Person/Role Questions (4 hallucinations!)

Tree retrieval **hallucinates wrong people**:

| Q# | Question | Expected | Tree OFF | Tree ON |
|----|----------|----------|----------|---------|
| Q1 | Who is the CEO of Nexus Industries? | Dr. Victoria Chen | ✅ Correct | ❌ **Dr. Sarah Thompson** |
| Q3 | Who is the President of Nexus Digital Solutions? | Robert Kim | ✅ Correct | ❌ **Kevin Chang** |
| Q29 | Who are the members of the Executive Leadership Team? | 9 people | ✅ Correct | ❌ Wrong list |
| Q48 | Who is the primary customer for HTS superconducting wire? | Siemens Healthineers | ✅ Correct | ❌ **Boeing** |

**Pattern**: Tree retrieval **confuses entities** with similar relationship types. It follows the wrong path in the knowledge graph and returns plausible but WRONG people.

**This is VERY BAD** - hallucinating facts is worse than saying "I don't know".

---

### 3. Technical Specifications (2 failures)

| Q# | Question | Tree OFF | Tree ON |
|----|----------|----------|---------|
| Q25 | What is the target energy density for the solid-state battery? | ✅ 400 Wh/kg | ❌ "not specified" |
| Q99 | How does Nexus's operating margin compare to target? | ✅ Correct | ❌ Wrong |

**Pattern**: Tree retrieval misses **numeric specifications** that are likely in document chunks, not graph relationships.

---

## The ONE Case Where Tree Retrieval Helped

**Q76: What is the total patent portfolio size?**
- Expected: 2,412 patents
- Tree OFF: ❌ "insufficient data"
- Tree ON: ✅ **Correct!**

**Why it worked**: This is an aggregation question where the graph might have counted PATENT relationships more effectively than document search.

**But**: This is only 1/100 questions, and tree retrieval failed 5 other count questions, so this isn't a reliable pattern.

---

## Questions Both Strategies Failed (19 questions)

Some questions are hard for BOTH approaches. Interestingly, they sometimes give **different wrong answers**:

### Different Hallucinations

| Q# | Question | Tree OFF Wrong Answer | Tree ON Wrong Answer |
|----|----------|----------------------|---------------------|
| Q2 | What is the name of the CFO? | "Hedging Policy" (!) | "Dr. Robert Kim" |
| Q37 | Who is the Project Director for GreenHydrogen? | "not specified" | "Dr. James Liu" |
| Q40 | What is the total company backlog? | $11.5 billion | $11.5 billion |
| Q45 | When was Dr. Victoria Chen appointed CEO? | March 2018 | March 2018 |

**Insight**: When both are wrong, tree sometimes gives a different (also wrong) answer. This suggests they're retrieving different context.

---

## Root Cause Analysis

### Why Tree Retrieval Underperforms

1. **Graph Traversal Too Narrow**
   - Follows relationships in knowledge graph
   - Misses document chunks that have the complete answer
   - Example: Employee count is probably in a single document chunk, not aggregated in graph

2. **Entity Confusion**
   - Knowledge graph has many PERSON entities
   - Tree traversal follows wrong relationship path
   - Returns a person with similar role/relationship type
   - Example: Asking for CEO, returns another executive

3. **Missing Aggregates**
   - Graph stores individual relationships
   - Doesn't have pre-computed aggregates (total employees, total satellites, etc.)
   - Document chunks often contain these summary statistics

4. **Hallucination Risk**
   - When tree retrieval "finds" something via graph traversal, it's confident even if wrong
   - Flat retrieval more likely to say "insufficient data" when unsure

---

## Recommendations

### Immediate Action: Keep Tree Retrieval OFF

For this dataset, **flat/semantic retrieval is clearly superior** (80% vs 68%).

### Future: Hybrid Approach

The data suggests a potential **two-pass hybrid strategy**:

#### Strategy A: Question-Type Routing
```
IF question_type == "aggregation/count":
    USE flat_retrieval  # Better at finding aggregate stats
ELIF question_type == "person/role":
    USE flat_retrieval  # Tree hallucinates wrong people
ELSE:
    TRY tree_retrieval FIRST
    IF confidence < threshold:
        FALLBACK to flat_retrieval
```

#### Strategy B: Dual-Pass Verification
```
1. Run BOTH tree and flat retrieval
2. If answers match → high confidence
3. If answers differ → use the one with higher confidence score
4. If both have low confidence → say "insufficient data"
```

#### Strategy C: Selective Tree Use
Only use tree retrieval for:
- Relationship traversal questions ("Who reports to X?")
- Path-finding questions ("What's the connection between X and Y?")
- NOT for: counts, specifications, person identification

---

## Testing Recommendations

### Next Experiments

1. **Test with different question sets**
   - Does tree retrieval perform better on relationship-heavy datasets?
   - Test on queries that require multi-hop reasoning

2. **Analyze tree retrieval confidence scores**
   - Are hallucinations correlated with low confidence?
   - Can we detect when tree is going wrong?

3. **Test hybrid approach**
   - Implement Strategy C above
   - Measure accuracy improvement

4. **Investigate hallucination root cause**
   - Why does tree retrieval return "Dr. Sarah Thompson" for CEO?
   - Is this entity even in the knowledge graph?
   - Are relationship types mislabeled?

---

## Technical Deep Dive Needed

### Questions to Answer

1. **Where is "Dr. Sarah Thompson" coming from?**
   - Query the knowledge graph for this entity
   - Check if CEO relationship is mislabeled
   - Verify entity extraction quality

2. **Why can't tree retrieval find counts?**
   - Are aggregate facts stored as relationships?
   - Check if "HAS_EMPLOYEE_COUNT" relationships exist
   - May need to enhance extraction to create these

3. **Can we improve tree query mapping?**
   - File: `retrieval_router.py:1865` (`_map_classification_to_tree_query_type`)
   - Current mapping may be wrong for certain question types
   - Test different query type classifications

---

## Conclusion

**Tree retrieval is currently harmful** for this dataset:
- ❌ Worse accuracy (68% vs 80%)
- ❌ Hallucinates wrong information
- ❌ Misses basic facts (counts, specifications)
- ✅ Only helped 1 out of 100 questions

**Keep it OFF** until we understand and fix the root causes.

**Next Steps**:
1. Investigate hallucination sources
2. Design question-type routing strategy
3. Test hybrid approach on subset
4. Consider improving knowledge graph extraction quality
