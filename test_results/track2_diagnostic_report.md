# Track 2 Retrieval Pipeline Diagnostic Report (Final)

**Date:** January 21, 2026  
**Vault:** Manus Healthtec (e13cb452-118e-4cf6-8e80-8502ce4742fa)  
**Chunks:** 116 (all with embeddings)

---

## Executive Summary

| Question | Expected Answer | Source File | Failure Stage | Root Cause |
|----------|-----------------|-------------|---------------|------------|
| Q14 | $165 million | company_profile.md | **INGESTION** | File at corpus root excluded by upload_rules |
| Q16 | 2022 | company_profile.md | **INGESTION** | File at corpus root excluded by upload_rules |
| Q55 | Salesforce | vendor_list.md | **EMBEDDING** | Chunk exists but not in top-50 semantic results |
| Q56 | Slack | vendor_list.md | **EMBEDDING** | Chunk exists but not in top-50 semantic results |
| Q183 | Ride-sharing | hr_policies.md | **EMBEDDING** | Chunk exists with full content but not in top-50 |

---

## Root Cause Analysis

### 1. INGESTION ISSUE (Q14, Q16)

**Evidence:**
- Upload rules: `include_folders: ['documents', 'excel_data']`
- Root-level files in corpus: `['ambiguity_log.md', 'company_profile.md', ...]`
- company_profile.md is at corpus ROOT, not in `documents/` folder
- No chunk contains "Total Funding" or "Company Profile"

**Fix:** Config change - add root-level files to upload_rules OR move company_profile.md to documents/

---

### 2. EMBEDDING ISSUE (Q55, Q56, Q183)

**Evidence:**
All three chunks EXIST with correct content:

| Question | Chunk Content | Has Embedding | Rank in Top-50 |
|----------|--------------|---------------|----------------|
| Q55 | "Salesforce \| CRM \| $150K/year" | Yes | NOT FOUND |
| Q56 | "Slack \| Team communication \| $50K/year" | Yes | NOT FOUND |
| Q183 | "Use of ride-sharing services (Uber, Lyft)" | Yes | NOT FOUND |

**Similarity Scores for Q183 search:**
- Query: "What is the preferred ground transportation method for local travel?"
- Top result: 0.30 (very low)
- HR Policies chunk (with ride-sharing): Not in top-50

**Root Cause:**
The embedding model (text-embedding-3-small) is not capturing semantic relationships between:
1. Natural language queries → Markdown table rows (Q55, Q56)
2. Business question → Policy document section (Q183)

**The fundamental issue:** Default top-K of 5 is insufficient when relevant chunks score below 0.5 similarity.

---

## Recommended Fixes

### Immediate (Config Changes):
1. **Ingestion:** Update upload_rules to include root-level .md files
2. **Retrieval:** Increase default document search limit from 5 to 15-20

### Short-term (Code Changes):
3. Add **keyword fallback** when semantic scores < 0.5
4. Add **hybrid search** combining BM25 + semantic

### Medium-term (Architecture):
5. Pre-process Markdown tables into natural language during chunking
6. Consider larger embedding model (text-embedding-3-large) for better semantic matching

---

## Summary

| Failure Stage | Questions | Fix Complexity | Impact |
|--------------|-----------|----------------|--------|
| **INGESTION** | Q14, Q16 | Low (config) | +2 questions |
| **EMBEDDING** | Q55, Q56, Q183 | Medium (hybrid search) | +3 questions |

**Total potential improvement:** +5 questions if fixes applied
