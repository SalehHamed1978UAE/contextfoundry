# MVP 2 Week 6: DEDUPLICATION, ENTITY MERGING & SCALE

**Date:** 2025-12-09
**Status:** Code complete, pending integration test with Docker

---

## Objectives

1. Build entity deduplication and merging for overlapping chunk extractions
2. Scale test data from 1 document to 6 documents
3. Improve extraction recall (fix 500-char truncation bug)
4. Implement evidence-based STAGING → TRUSTED promotion
5. Add relationship endpoint validation
6. Add batch extraction pipeline

---

## Completed Deliverables

### 1. Entity Deduplication & Merging Module

**File:** `src/agents/dedup.py` — `DeduplicationAgent`

**Two-level dedup:**

1. **In-memory dedup** (before DB insertion):
   - Groups entities by `canonical_name + entity_type`
   - Keeps highest-confidence version, merges provenance into a list
   - Tracks `extraction_count` for evidence-based promotion
   - Same logic for relationships (`source + target + type`)

2. **Database-level dedup** (after insertion, across documents):
   - Finds duplicate entries in STAGING by canonical_name + entity_type
   - Survivor selection: highest confidence wins
   - Confidence boost: +0.05 per additional extraction (capped at +0.10)
   - Re-points all relationships from duplicates to survivor
   - Archives duplicates (not deleted — audit trail preserved)
   - Merges nodes in Apache AGE graph

3. **Cross-document entity resolution:**
   - Matches STAGING entities against existing TRUSTED entities
   - Boosts TRUSTED confidence (+0.03 per new evidence)
   - Re-points relationships and archives the STAGING duplicate

### 2. Extraction Recall Fix

**Problem:** `text[:500]` in extraction prompts was truncating input, causing the LLM to miss entities appearing after the first 500 characters. This resulted in only 2 entities extracted per chunk (payment-api and payments-db).

**Fix:**
- Increased text window from 500 to 2000 characters
- Rewrote entity extraction prompt with clearer type definitions
- Added Component type (for gateways, load balancers)
- Added Incident type (for INC-xxx references)
- Expanded relationship prompt to include all 7 relationship types (was only 4)
- Better instructions for confidence scoring

**Expected improvement:** From ~2 entities/chunk to 6-10+ entities/chunk

### 3. Data Model Fix — canonical_name Storage

**Bug:** `canonical_name` was being stored in the `source_sentence` column (line 431 of extraction.py). The actual source sentence evidence was lost.

**Fix:**
- `canonical_name` → stored in `extracted_text` column
- `source_sentence` → now stores the actual evidence sentence
- `_find_entity_id_by_name` updated to search both columns (backward compatible)
- Dedup queries updated to use `COALESCE(extracted_text, source_sentence)`
- Staging summary updated to display canonical names correctly

### 4. Test Document Corpus (6 documents)

**Directory:** `test_data/`

| Document | Type | Entities Expected | Key Coverage |
|----------|------|-------------------|-------------|
| `runbook_payment_api_recovery.md` | Runbook | ~15 | payment-api, payments-db, payments-team |
| `runbook_user_service_auth.md` | Runbook | ~12 | user-service, session-cache, platform-team |
| `runbook_notification_service.md` | Runbook | ~14 | notification-service, messaging-team, queues |
| `runbook_database_operations.md` | Runbook | ~18 | All databases, database-team, all DBAs |
| `incident_report_INC003.md` | Incident | ~12 | INC-003, payment-api outage, cascading |
| `incident_report_INC004_cascading.md` | Incident | ~15 | INC-004, session-cache OOM, cascading auth |

**Cross-document entity overlap** (validates dedup):
- `payment-api` appears in 4 documents
- `Bob Martinez` appears in 4 documents
- `payments-team` appears in 3 documents
- `user-service` appears in 3 documents
- `platform-team` appears in 4 documents
- `notification-service` appears in 3 documents

### 5. Evidence-Based Promotion

**File:** `src/agents/gardener.py` — `promote_with_evidence()`

**Promotion criteria:**
- Confidence >= threshold (default 0.70)
- Entity must appear in >= N distinct source documents (configurable, default 1)
- Relationships only promoted when both endpoints are TRUSTED

**CLI:** `python -m src.cli promote-evidence [min_confidence] [min_sources]`

### 6. Relationship Validation

**File:** `src/agents/extraction.py` — `validate_relationships_against_entities()`

- Pre-insertion check: both endpoints must exist in extracted entity set
- Self-loop detection: source != target
- Orphaned relationships logged and dropped with warning
- Integrated into pipeline between dedup and insertion

### 7. Batch Extraction Pipeline

**File:** `src/utils/extraction_pipeline.py` — `run_batch_extraction()`

- Process multiple documents sequentially
- Per-document dedup + cross-document resolution after each
- Aggregate statistics across batch
- CLI: `python -m src.cli extract-all [directory]`

---

## New CLI Commands

```bash
python -m src.cli extract <file>              # Extract from single document
python -m src.cli extract-all [directory]      # Extract from all .md files
python -m src.cli dedup                        # Run dedup on STAGING
python -m src.cli promote-evidence [conf] [n]  # Evidence-based promotion
```

---

## Files Created

| File | Lines | Purpose |
|------|-------|---------|
| `src/agents/dedup.py` | ~280 | Deduplication & entity merging |
| `test_data/runbook_user_service_auth.md` | ~95 | User service auth runbook |
| `test_data/incident_report_INC003.md` | ~95 | Payment outage incident |
| `test_data/architecture_order_system.md` | ~110 | Order system architecture |
| `test_data/runbook_notification_service.md` | ~115 | Notification service runbook |
| `test_data/runbook_database_operations.md` | ~120 | Database operations runbook |
| `test_data/incident_report_INC004_cascading.md` | ~115 | Cascading auth failure incident |

## Files Modified

| File | Changes |
|------|---------|
| `src/agents/extraction.py` | Improved prompts (2000 char window), fixed canonical_name storage, added relationship validation, expanded entity/relationship types |
| `src/agents/gardener.py` | Added `promote_with_evidence()` method |
| `src/utils/extraction_pipeline.py` | Integrated dedup, relationship validation, cross-doc resolution, batch mode |
| `src/cli.py` | Added extract, extract-all, dedup, promote-evidence commands |

---

## Architecture: Updated Pipeline Flow

```
Document (MD/PDF/DOCX)
  │
  ▼
STEP 1: Ingest (sentence-aware chunking)
  │
  ▼
STEP 2: Extract (LLM-based, per chunk)
  │  entities + relationships
  ▼
STEP 3: Deduplicate (in-memory)
  │  merge by canonical_name + entity_type
  │  merge by source + target + relationship_type
  ▼
STEP 3b: Validate relationships
  │  drop orphans (missing endpoints)
  │  drop self-loops
  ▼
STEP 4: Insert into STAGING
  │  entities → graph_lifecycle + AGE
  │  relationships → relationship_metadata + AGE
  ▼
STEP 5: DB-level dedup
  │  merge STAGING duplicates across chunks
  │  confidence boost for multiple extractions
  ▼
STEP 6: Cross-document resolution
  │  match STAGING against TRUSTED
  │  boost TRUSTED confidence, archive STAGING dups
  ▼
STEP 7: Summary report
```

---

## Next Steps (MVP 2 Week 7)

- [ ] Spin up Docker, run batch extraction on all 6 documents
- [ ] Measure extraction recall (target: 80%+ of entities captured)
- [ ] Run evidence-based promotion with min_sources=2
- [ ] Verify cross-document entity resolution works
- [ ] Measure end-to-end query accuracy with populated graph
- [ ] Consider GPU acceleration for Ollama (currently ~2 min/chunk on CPU)

---

## Key Decisions

1. **Archive, don't delete** — Merged duplicates go to ARCHIVED state with audit trail (conflicts JSONB tracks what was merged into what)
2. **Confidence boost for evidence** — Each additional independent extraction adds +0.05 confidence (capped at +0.10). Cross-document matches add +0.03.
3. **Backward compatible** — New `extracted_text` column for canonical names, queries fall back to `source_sentence` for legacy data
4. **Batch before promote** — Run all documents through extraction before promotion so cross-document evidence is available
