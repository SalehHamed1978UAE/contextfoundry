# Context Foundry 100-Query Evaluation Report

**Generated:** 2025-12-10 15:26:19 UTC  
**Total Queries:** 100  
**Evaluation Date:** December 10, 2025

---

## Executive Summary

| Category | Count | Percentage |
|----------|-------|------------|
| **ACCURATE** | 23 | 23.0% :white_check_mark: |
| **PARTIAL** | 54 | 54.0% |
| **LOW_CONFIDENCE** | 1 | 1.0% |
| **NOT_FOUND** | 19 | 19.0% :grey_question: |
| **HALLUCINATED** | 3 | 3.0% :x: |
| **ERROR** | 0 | 0.0% |

## Key Metrics

| Metric | Value | Assessment |
|--------|-------|------------|
| **Hallucination Rate** | 3.0% (1.0% corrected*) | PASS |
| **Accuracy Rate** | 23.0% | MODERATE |
| **Guard Trigger Rate** | 19.0% | Entity guard working correctly |
| **Response Rate** | 81.0% | System provides answers |

*Note: 2 of 3 "hallucinated" responses actually contain correct refusals - see Hallucination Analysis section

---

## Results by Query Category

### Complex Flow (10 queries)

| Result | Count | Percentage |
|--------|-------|------------|
| PARTIAL | 7 | 70% |
| ACCURATE | 2 | 20% |
| LOW_CONFIDENCE | 1 | 10% |

### Dependencies (20 queries)

| Result | Count | Percentage |
|--------|-------|------------|
| PARTIAL | 14 | 70% |
| ACCURATE | 3 | 15% |
| NOT_FOUND | 3 | 15% |

### Escalation (20 queries)

| Result | Count | Percentage |
|--------|-------|------------|
| PARTIAL | 15 | 75% |
| NOT_FOUND | 3 | 15% |
| ACCURATE | 2 | 10% |

### Hallucination Test (10 queries)

| Result | Count | Percentage |
|--------|-------|------------|
| NOT_FOUND | 4 | 40% |
| ACCURATE | 3 | 30% |
| HALLUCINATED | 3 | 30% |

### Impact Analysis (20 queries)

| Result | Count | Percentage |
|--------|-------|------------|
| ACCURATE | 12 | 60% |
| NOT_FOUND | 5 | 25% |
| PARTIAL | 3 | 15% |

### Ownership (20 queries)

| Result | Count | Percentage |
|--------|-------|------------|
| PARTIAL | 15 | 75% |
| NOT_FOUND | 4 | 20% |
| ACCURATE | 1 | 5% |

---

## Hallucination Analysis

The system was tested with 10 hallucination test queries (HA-001 to HA-010) designed to trigger hallucination:

| Query Type | Expected Behavior | Actual Behavior |
|------------|-------------------|-----------------|
| Fake entities (FakeService123, MagicAPI, etc.) | Refuse/Low confidence | Mostly correct |
| General knowledge (Capital of France, CEO of Apple) | Refuse/Low confidence | Mixed |
| Non-existent services (QuantumService, SkynetService) | Refuse | Correct |

### Hallucinated Responses Analysis

**TRUE HALLUCINATION (1 query - 1%):**

#### HA-004: "Who should I escalate to for issues with the QuantumService?"
- **Confidence:** 0.95
- **Response excerpt:** For issues with the QuantumService, you should escalate to Mia White, who is the VP of Engineering and the escalation point for SEV1 incidents....
- **Issue:** System fabricated an answer about a non-existent "QuantumService" by borrowing escalation info from other services

**FALSE POSITIVES (2 queries - correctly refused but miscategorized):**

#### HA-006: "Who is the CEO of Apple?"
- **Confidence:** 0.45
- **Response excerpt:** No entities are documented as the CEO of Apple in the knowledge graph....
- **Assessment:** This is actually CORRECT behavior - system refused to answer general knowledge question

#### HA-009: "What are the dependencies of the XYZ123 Platform?"
- **Confidence:** 0.50
- **Response excerpt:** No services are documented as depending on the XYZ123 Platform in the knowledge graph....
- **Assessment:** This is actually CORRECT behavior - system stated it has no information about non-existent entity

**CORRECTED HALLUCINATION RATE: 1.0%** (1 true hallucination out of 100 queries)

---

## Detailed Results Table

| # | Query ID | Category | Confidence | Result |
|---|----------|----------|------------|--------|
| 1 | IA-001 | impact_analysis | 0.77 | ACCURATE |
| 2 | IA-002 | impact_analysis | 0.77 | ACCURATE |
| 3 | IA-003 | impact_analysis | 0.77 | ACCURATE |
| 4 | IA-004 | impact_analysis | 0.77 | ACCURATE |
| 5 | IA-005 | impact_analysis | 0.77 | ACCURATE |
| 6 | IA-006 | impact_analysis | 0.77 | ACCURATE |
| 7 | IA-007 | impact_analysis | 0.50 | PARTIAL |
| 8 | IA-008 | impact_analysis | 0.45 | PARTIAL |
| 9 | IA-009 | impact_analysis | 0.77 | ACCURATE |
| 10 | IA-010 | impact_analysis | 0.77 | ACCURATE |
| 11 | IA-011 | impact_analysis | 0.00 | NOT_FOUND |
| 12 | IA-012 | impact_analysis | 0.00 | NOT_FOUND |
| 13 | IA-013 | impact_analysis | 0.77 | ACCURATE |
| 14 | IA-014 | impact_analysis | 0.00 | NOT_FOUND |
| 15 | IA-015 | impact_analysis | 0.00 | NOT_FOUND |
| 16 | IA-016 | impact_analysis | 0.77 | ACCURATE |
| 17 | IA-017 | impact_analysis | 0.77 | ACCURATE |
| 18 | IA-018 | impact_analysis | 0.50 | PARTIAL |
| 19 | IA-019 | impact_analysis | 0.00 | NOT_FOUND |
| 20 | IA-020 | impact_analysis | 0.77 | ACCURATE |
| 21 | ES-001 | escalation | 0.95 | PARTIAL |
| 22 | ES-002 | escalation | 0.95 | PARTIAL |
| 23 | ES-003 | escalation | 0.50 | PARTIAL |
| 24 | ES-004 | escalation | 0.77 | ACCURATE |
| 25 | ES-005 | escalation | 0.95 | PARTIAL |
| 26 | ES-006 | escalation | 0.50 | PARTIAL |
| 27 | ES-007 | escalation | 0.50 | PARTIAL |
| 28 | ES-008 | escalation | 0.45 | PARTIAL |
| 29 | ES-009 | escalation | 0.50 | PARTIAL |
| 30 | ES-010 | escalation | 0.00 | NOT_FOUND |
| 31 | ES-011 | escalation | 0.00 | NOT_FOUND |
| 32 | ES-012 | escalation | 0.50 | PARTIAL |
| 33 | ES-013 | escalation | 0.00 | NOT_FOUND |
| 34 | ES-014 | escalation | 0.41 | PARTIAL |
| 35 | ES-015 | escalation | 0.45 | PARTIAL |
| 36 | ES-016 | escalation | 0.50 | PARTIAL |
| 37 | ES-017 | escalation | 0.50 | PARTIAL |
| 38 | ES-018 | escalation | 0.77 | ACCURATE |
| 39 | ES-019 | escalation | 0.50 | PARTIAL |
| 40 | ES-020 | escalation | 0.45 | PARTIAL |
| 41 | OW-001 | ownership | 0.50 | PARTIAL |
| 42 | OW-002 | ownership | 0.95 | PARTIAL |
| 43 | OW-003 | ownership | 0.95 | ACCURATE |
| 44 | OW-004 | ownership | 0.45 | PARTIAL |
| 45 | OW-005 | ownership | 0.50 | PARTIAL |
| 46 | OW-006 | ownership | 0.00 | NOT_FOUND |
| 47 | OW-007 | ownership | 0.41 | PARTIAL |
| 48 | OW-008 | ownership | 0.50 | PARTIAL |
| 49 | OW-009 | ownership | 0.77 | PARTIAL |
| 50 | OW-010 | ownership | 0.50 | PARTIAL |
| 51 | OW-011 | ownership | 0.00 | NOT_FOUND |
| 52 | OW-012 | ownership | 0.50 | PARTIAL |
| 53 | OW-013 | ownership | 0.50 | PARTIAL |
| 54 | OW-014 | ownership | 0.95 | PARTIAL |
| 55 | OW-015 | ownership | 0.00 | NOT_FOUND |
| 56 | OW-016 | ownership | 0.50 | PARTIAL |
| 57 | OW-017 | ownership | 0.00 | NOT_FOUND |
| 58 | OW-018 | ownership | 0.45 | PARTIAL |
| 59 | OW-019 | ownership | 0.50 | PARTIAL |
| 60 | OW-020 | ownership | 0.50 | PARTIAL |
| 61 | DEP-001 | dependencies | 0.95 | ACCURATE |
| 62 | DEP-002 | dependencies | 0.77 | ACCURATE |
| 63 | DEP-003 | dependencies | 0.50 | PARTIAL |
| 64 | DEP-004 | dependencies | 0.50 | PARTIAL |
| 65 | DEP-005 | dependencies | 0.50 | PARTIAL |
| 66 | DEP-006 | dependencies | 0.50 | PARTIAL |
| 67 | DEP-007 | dependencies | 0.00 | NOT_FOUND |
| 68 | DEP-008 | dependencies | 0.45 | PARTIAL |
| 69 | DEP-009 | dependencies | 0.45 | PARTIAL |
| 70 | DEP-010 | dependencies | 0.00 | NOT_FOUND |
| 71 | DEP-011 | dependencies | 0.50 | PARTIAL |
| 72 | DEP-012 | dependencies | 0.50 | PARTIAL |
| 73 | DEP-013 | dependencies | 0.45 | PARTIAL |
| 74 | DEP-014 | dependencies | 0.00 | NOT_FOUND |
| 75 | DEP-015 | dependencies | 0.50 | PARTIAL |
| 76 | DEP-016 | dependencies | 0.64 | PARTIAL |
| 77 | DEP-017 | dependencies | 0.41 | PARTIAL |
| 78 | DEP-018 | dependencies | 0.50 | PARTIAL |
| 79 | DEP-019 | dependencies | 0.77 | ACCURATE |
| 80 | DEP-020 | dependencies | 0.77 | PARTIAL |
| 81 | HA-001 | hallucination_test | 0.45 | ACCURATE |
| 82 | HA-002 | hallucination_test | 0.00 | NOT_FOUND |
| 83 | HA-003 | hallucination_test | 0.00 | NOT_FOUND |
| 84 | HA-004 | hallucination_test | 0.95 | HALLUCINATED |
| 85 | HA-005 | hallucination_test | 0.10 | ACCURATE |
| 86 | HA-006 | hallucination_test | 0.45 | HALLUCINATED |
| 87 | HA-007 | hallucination_test | 0.10 | ACCURATE |
| 88 | HA-008 | hallucination_test | 0.00 | NOT_FOUND |
| 89 | HA-009 | hallucination_test | 0.50 | HALLUCINATED |
| 90 | HA-010 | hallucination_test | 0.00 | NOT_FOUND |
| 91 | CF-001 | complex_flow | 0.77 | ACCURATE |
| 92 | CF-002 | complex_flow | 0.77 | ACCURATE |
| 93 | CF-003 | complex_flow | 0.45 | PARTIAL |
| 94 | CF-004 | complex_flow | 0.50 | PARTIAL |
| 95 | CF-005 | complex_flow | 0.10 | LOW_CONFIDENCE |
| 96 | CF-006 | complex_flow | 0.77 | PARTIAL |
| 97 | CF-007 | complex_flow | 0.50 | PARTIAL |
| 98 | CF-008 | complex_flow | 0.50 | PARTIAL |
| 99 | CF-009 | complex_flow | 0.50 | PARTIAL |
| 100 | CF-010 | complex_flow | 0.50 | PARTIAL |

---

## Category Definitions

| Category | Definition |
|----------|------------|
| **ACCURATE** | Response is grounded in knowledge graph, confidence >= 0.7 |
| **PARTIAL** | Response has some grounding, confidence 0.4-0.7 |
| **LOW_CONFIDENCE** | Response exists but confidence < 0.4 |
| **NOT_FOUND** | Entity guard triggered - entity not in knowledge graph |
| **HALLUCINATED** | System provided answer for non-existent entity with high confidence |
| **ERROR** | System error during query processing |

---

## Conclusions

### What's Working Well

1. **Entity Guard**: The entity-not-found guard correctly prevents most hallucinations
   - 19 queries correctly refused due to missing entities
   - System says "I don't know" instead of making things up

2. **Impact Analysis**: Strong performance on blast radius queries (60%+ accurate)
   - "What services are affected if X goes down?" works reliably
   - Correct traversal direction (downstream dependents)

3. **Confidence Calibration**: Scores correlate with response quality
   - 0.77+ for grounded answers
   - 0.45-0.50 for partial information
   - 0.00 when entity doesn't exist

### Areas for Improvement

1. **Hallucination on General Knowledge**: 3 queries (3%) still hallucinated
   - HA-004: Escalation for QuantumService (0.95 confidence)
   - HA-006: CEO of Apple (0.45 confidence)
   - HA-009: XYZ123 Platform dependencies (0.50 confidence)

2. **Knowledge Graph Coverage**: Many PARTIAL results indicate incomplete data
   - Add more entities and relationships to improve accuracy
   - Consider auto-suggesting similar entities when exact match fails

3. **Escalation Queries**: Lower accuracy than impact analysis
   - Need more OWNS/RESPONSIBLE_FOR relationships in graph

---

## Recommendations

1. **Tighten General Knowledge Guard**: Detect and refuse general knowledge questions
2. **Expand Knowledge Graph**: Add missing entities (CDN, Logging Service, etc.)
3. **Improve Entity Matching**: Use embedding similarity for near-matches
4. **Monitor Hallucination Rate**: Target < 1% for production

---

## Raw Evidence

Full evidence with SQL verification available in: `outputs/CF_Evaluation_Evidence.json`

Each entry contains:
- Query ID and text
- Full response
- Confidence score
- Category classification
- Entity verifications (when applicable)

---

*Report generated by Context Foundry Evaluation System*
