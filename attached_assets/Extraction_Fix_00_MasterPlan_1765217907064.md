# Extraction Enhancement - Master Plan

## Overview

Fixing the 25% recall problem in Context Foundry entity extraction through 6 phased improvements.

**Target:** 25% recall → 70-85% recall

---

## Phase Summary

| Phase | Focus | Est. Effort | Impact |
|-------|-------|-------------|--------|
| **Phase 1** | Fix DOCX extraction | 30 min | +10% recall |
| **Phase 2** | Add Core few-shot examples | 30 min | +40% recall |
| **Phase 3** | Rewrite extraction prompt | 30 min | +15% recall |
| **Phase 4** | **TEST** | 15 min | Validate |
| **Phase 5** | Add 6 domain-specific examples | 1 hour | +5% recall |
| **Phase 6** | Multi-pass gap-check | 45 min | +10% recall |

---

## Implementation Order

```
Phase 1 (DOCX) → Phase 2 (Examples) → Phase 3 (Prompt)
                                            ↓
                                      Phase 4 (TEST)
                                            ↓
                            [If test passes, continue]
                                            ↓
                    Phase 5 (Domains) → Phase 6 (Gap-Check)
```

**STOP at Phase 4 if test fails.** Debug before continuing.

---

## Files Created

| File | Description |
|------|-------------|
| `Extraction_Fix_Phase1_DOCX.md` | Fix DOCX text extraction |
| `Extraction_Fix_Phase2_FewShot.md` | Create Core few-shot examples |
| `Extraction_Fix_Phase3_Prompt.md` | Rewrite extraction prompt |
| `Extraction_Fix_Phase4_Test.md` | Test phases 1-3 |
| `Extraction_Fix_Phase5_Domains.md` | 6 domain-specific example sets |
| `Extraction_Fix_Phase6_GapCheck.md` | Multi-pass extraction |

---

## Root Causes Being Fixed

| Problem | Root Cause | Phase |
|---------|------------|-------|
| Missing "Federated Data Catalog" | DOCX only reads paragraphs | Phase 1 |
| Only 12 entities extracted | No few-shot examples | Phase 2 |
| Conservative extraction | "ONLY extract EXPLICITLY" prompt | Phase 3 |
| LOCATION/ORGANIZATION confusion | Ambiguous type definitions | Phase 3 |
| Domain-specific entities missed | Generic examples | Phase 5 |
| Edge cases missed | Single-pass extraction | Phase 6 |

---

## Success Metrics

### After Phase 4 (minimum viable):

- [ ] Entity count ≥ 30 (up from 12)
- [ ] "Federated Data Catalog" extracted as CONCEPT
- [ ] "Corporate Holding Company" typed as ORGANIZATION
- [ ] "Government" typed as ORGANIZATION

### After Phase 6 (full implementation):

- [ ] Entity count ≥ 45
- [ ] All section headers captured
- [ ] Domain-specific entities recognized
- [ ] Type accuracy > 90%

---

## Notes for Replit

1. **Do one phase at a time** - don't try to implement everything at once
2. **Test after each phase** - verify it works before continuing
3. **Share results** - show entity counts and key extractions
4. **Ask questions** - if anything is unclear, ask before implementing

---

## Model Consideration (Optional)

Current: GPT-4o-mini (21% entity omission rate)

Options to test:
- GPT-4o (better accuracy, 33x more expensive)
- Claude Sonnet 4 (consolidate with Vision pipeline)
- DeepSeek-V3 (cheap, surprisingly good)

Run a comparison test after Phase 4 passes to inform model selection.
