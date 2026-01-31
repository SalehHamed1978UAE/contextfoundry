# Phase 4: Test Phases 1-3

**Goal:** Verify the fixes work before adding complexity.

---

## Test Document

Use: `Gemini_-_Consolidated_Critical_Success_Factors_for_Federated_Data_Catalogs.docx`

---

## Before/After Comparison

### Record BEFORE metrics (from previous run):

| Metric | Before |
|--------|--------|
| Characters extracted | 5,639 |
| Entities extracted | 12 |
| Key entities found | ❌ Missing "Federated Data Catalog" |
| Type accuracy | ❌ "Corporate Holding Company" → LOCATION (wrong) |

### Run extraction with new code and record AFTER:

| Metric | After |
|--------|-------|
| Characters extracted | _____ (should be higher) |
| Entities extracted | _____ (target: 40+) |
| Key entities found | Check list below |
| Type accuracy | Check list below |

---

## Checklist: Key Entities That MUST Be Extracted

| Entity | Expected Type | Found? |
|--------|---------------|--------|
| Federated Data Catalog | CONCEPT | ☐ |
| Hub-and-Spoke | CONCEPT | ☐ |
| Crawl, Walk, Run Approach | CONCEPT or PROCESS | ☐ |
| Corporate Holding Company | ORGANIZATION | ☐ |
| Government | ORGANIZATION | ☐ |
| Data Steward | ROLE | ☐ |
| Minimum Viable Metadata | CONCEPT | ☐ |
| Hybrid Governance Model | CONCEPT or PROCESS | ☐ |

---

## Checklist: Type Accuracy

| Entity | OLD Type | NEW Type | Correct? |
|--------|----------|----------|----------|
| Corporate Holding Company | LOCATION ❌ | ORGANIZATION | ☐ |
| Government | LOCATION ❌ | ORGANIZATION | ☐ |

---

## Success Criteria

✅ **Pass** if:
- Characters extracted increased (tables/headers captured)
- Entity count ≥ 30 (up from 12)
- "Federated Data Catalog" is extracted
- "Corporate Holding Company" typed as ORGANIZATION
- "Government" typed as ORGANIZATION

❌ **Fail** if:
- Entity count still < 20
- Key entities still missing
- Type confusion persists

---

## If Test Fails

1. Check DOCX extraction - is title/header text in the extracted content?
2. Check prompt - are few-shot examples included?
3. Check LLM response - is it returning valid JSON?
4. Check confidence threshold - are we filtering out low-confidence entities?

---

## Report Results

Share:
1. Full entity list (name, type, confidence)
2. Characters extracted count
3. Any errors or issues

---

**DO NOT proceed to Phase 5 until test passes.**
