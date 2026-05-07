# Nexus Industries 72/100 — Per-Question Diagnosis of the 12 NOT_FOUND Failures

Vault: `176a4fb2-0bb4-4da3-9068-0e26268fca71`
Test result: `test_results/claudecode_nexus_industries_20260507_084232.json`
Audit date: 2026-05-07

## Headline finding

The dominant root cause is **edge-extraction failure on a small set of high-value documents**, not retrieval and not promotion gating. Three documents that source ≥ 6 of the 12 failures produced almost zero relationships:

| Source document | Entities | Relationships | Failures it should have answered |
|---|---:|---:|---|
| `02_organizational_announcement.md` | **0** | **0** | Q1, Q3, Q14, Q38, Q61, Q75 |
| `06_solid_state_battery_design.md` | 140 | **0** | Q25, Q67 |
| `04_greenhydrogen_initiative.md` | 41 | **0** | Q18, Q37 |
| `03_desert_sun_solar_farm.md` | 60 | **1** | Q46 |
| `10_first_solar_supplier.md` | 35 | 8 (none to Desert Sun) | Q46 |

`02_organizational_announcement.md` is in the vault but produced **no entities or edges at all** — this is a hard extraction failure on the single document that contains the org-chart deltas the test asks about. The two specification documents (`06_solid_state_battery_design.md`, `04_greenhydrogen_initiative.md`) have entities-without-edges, meaning extraction harvested values like `400 Wh/kg` as standalone `SPECIFICATION` nodes but never tied them to `BatteryTech` / `Solid-State Battery`.

---

## Per-question table

Categories used:
- **A: Edge present, retrieval missed it** (graph is right, query path is wrong)
- **B: Wrong/conflicting edge wins** (graph has bad data overriding good data)
- **C: Source doc not extracted at all** (doc → 0 ents, 0 rels)
- **D: Entities present, no connecting edge** (extraction harvested both sides but never wrote the relation)
- **E: Expected fact not in source corpus** (test data error)

| Q# | Question | Expected | Entity in graph? | Relation in graph? | Source doc | Doc extraction | Category | Root cause |
|---|---|---|---|---|---|---|---|---|
| 1 | CEO of Nexus Industries | Dr. Victoria Chen | ✅ `Dr. Victoria Chen` (PERSON, STAGING) | ✅ `Dr. Victoria Chen --[HOLDS_POSITION]--> CEO` (STAGING) — appears 2× | `01_executive_team.md` plus `02_org_announce.md` | OK | **A** | Edge exists in STAGING but `CEO` ROLE node is **ARCHIVED** while edge is STAGING; competing edge `Dr. Robert Martinez --[HOLDS_POSITION]--> CEO` muddies retrieval. RoleResolver picked up "various positions" instead of disambiguating to Victoria Chen. |
| 3 | President of NDS | Robert Kim | ✅ `Robert Kim`, `Dr. Robert Kim` (PERSON, STAGING) | ❌ Only `Robert Kim --[HOLDS_POSITION]--> CFO` exists. **No PRESIDENT_OF / HOLDS_POSITION→President edge.** | `02_organizational_announcement.md` (line 15: "appointed President of Nexus Digital Solutions") + `00_CORPUS_MANIFEST.json` | **0 ents / 0 rels from 02_org_announce** | **C** | Single-document extraction failure. The president fact lives only in this announcement; doc was ingested but extracted to nothing. |
| 14 | When was Robert Kim appointed President of Digital Solutions | January 2026 (effective Jan 15, 2026) | ✅ Robert Kim | ❌ No appointment date qualifier on any Robert Kim edge | Same as Q3 | **0 ents / 0 rels** | **C** | Same extraction failure as Q3. Even if the President edge existed, the temporal qualifier (`effective January 15, 2026`) is not captured anywhere. |
| 18 | Which company has a green hydrogen offtake agreement with Nexus | Shell | ✅ `Shell`, `Shell plc` (ORGANIZATION, STAGING) | ❌ Shell has only LOCATED_IN, MEMBER_OF, PRODUCES, SUPPLIES (Technical Advisory) edges. No OFFTAKE / SUPPLIES_TO / HAS_AGREEMENT edge linking Shell to GreenHydrogen | `projects/04_greenhydrogen_initiative.md` line 128 (`\| Shell \| Offtake partner \| Revenue share \|`) and `stakeholders/13_shell_partner.md` | **04_greenhydrogen: 41 ents / 0 rels.** 13_shell_partner: 51 ents / 21 rels but no Shell→GreenHydrogen edge | **C/D** | The offtake fact is in a markdown table row in `04_greenhydrogen_initiative.md`, which extracted entities but **zero relationships**. `Toyota Offtake Agreement` was correctly captured (a different doc), so the OFFTAKE relation type isn't the blocker — table-row extraction is. |
| 25 | Target energy density for the solid-state battery | 400 Wh/kg | ✅ `400 Wh/kg` (SPECIFICATION), `400 Wh/kg Target` (MILESTONE), `Solid-State Batteries` (PROJECT), `BatteryTech Solid State` | ❌ **No HAS_SPEC / TARGETS edge from any battery entity to `400 Wh/kg`.** | `technical/06_solid_state_battery_design.md` (table row: `Energy Density \| 400 Wh/kg`) | **140 ents / 0 rels** | **D** | Both endpoints exist as separate entities; the edge between them was never created. Same 0-edge pattern across the entire spec doc. |
| 37 | Project Director for the GreenHydrogen Initiative | Jennifer Walsh | ✅ `Jennifer Walsh` (PERSON) | ✅ `Jennifer Walsh --[HOLDS_POSITION]--> Project Director` exists (STAGING). ❌ But **no edge connects Jennifer Walsh OR `Project Director` to `GreenHydrogen` / `Green Hydrogen` projects**. (15 hydrogen-related entities exist; only 4 incoming edges, none from Walsh.) | `02_greenhydrogen_process_specification.md` line 402: "Approved By: Jennifer Walsh, Project Director" | 04_greenhydrogen: 41 ents / 0 rels | **D** | Two-hop fact: `(Walsh)-[Director_of]->(GreenHydrogen)` requires either a single edge or a 2-hop join through the role. Neither exists. The `Project Director` node is unanchored — it has no `OF` relationship to any project. |
| 38 | CISO of Nexus Industries | Jennifer Walsh (appointed Jan 2026, formerly Robert Kim) | ✅ `Jennifer Walsh`, `Maria Santos`, `Robert Kim`; ✅ `CISO` (ROLE, STAGING) and `Chief Information Security Officer` (ROLE, STAGING) | ❌ Only edge to `CISO` is `Maria Santos --[HOLDS_POSITION]--> CISO` — **wrong person**. No edge to `Chief Information Security Officer`. The `Jennifer Walsh→CISO` and `Robert Kim→CISO` (formerly) facts are missing. | `communications/02_organizational_announcement.md` line 34: "CISO (New) \| Jennifer Walsh"; line 17: Robert Kim "served as Chief Information Security Officer since 2021" | **0 ents / 0 rels** | **B + C** | The correct CISO appointment fact is in the un-extracted org-announcement doc. Meanwhile a wrong/stale fact (Maria Santos as CISO) extracted from another doc wins by default. This is the cleanest example of an extraction gap producing a wrong answer (rather than NOT_FOUND). |
| 46 | Who supplies solar panels for the Desert Sun project | First Solar | ✅ `First Solar`, `First Solar, Inc.` (ORGANIZATION); ✅ many `Desert Sun*` entities | ❌ **`Desert Sun*` has 0 incoming edges.** First Solar has 5 SUPPLIES edges but to {Canadian Solar, LONGi, Qcells, Nexus Energy, JinkoSolar} — none to Desert Sun. | `projects/03_desert_sun_solar_farm.md` and `suppliers/10_first_solar_supplier.md` | 03_desert_sun: 60 ents / **1 rel**; 10_first_solar: 35 ents / 8 rels (all wrong direction or wrong target) | **D** | Both endpoints exist; the cross-document `First Solar SUPPLIES Desert Sun` link was never extracted. Extraction in `10_first_solar_supplier.md` confused First Solar's competitors (Canadian Solar, LONGi, Qcells, JinkoSolar) as things First Solar "supplies" — a serious extraction quality bug. |
| 61 | Who replaced Thomas Anderson as Digital President | Robert Kim | ✅ `Thomas Anderson` (PERSON, STAGING, **0 edges**), ✅ `Robert Kim` | ❌ No `SUCCEEDED_BY` / `REPLACED` edge. No `Anderson--PRESIDENT_OF--NDS` edge either. | `02_organizational_announcement.md` line 15: "Robert succeeds Thomas Anderson" | **0 ents / 0 rels** | **C** | Same root cause as Q3/Q14. Anderson exists in graph as an orphan (extracted from a different doc) but the succession fact is locked inside the un-extracted announcement. |
| 67 | Operating temperature range solid-state battery supports | -30°C to 60°C | ❌ No `-30°C to 60°C` entity (only `-30°C` as part of larger strings) | ❌ No HAS_SPEC edge | `technical/06_solid_state_battery_design.md` line 37: "Operating Temp \| -30 to 60°C" | 140 ents / 0 rels | **D** (with partial entity miss) | Same 0-edge pattern as Q25. Additionally the range "-30°C to 60°C" was not normalized into a single SPECIFICATION entity. |
| 75 | VP of Engineering for Nexus Digital Solutions | Dr. Alan Chen | ✅ `Dr. Alan Chen` (PERSON, STAGING) — but **0 outgoing edges** | ❌ `VP Engineering` (ROLE) exists with 0 incoming edges | Source has 4 separate mentions: `02_organizational_announcement.md` line 30, `meetings/11_product_launch_planning.md` line 18, `technical/03_nexusconnect_api_specification.md` lines 8 + 709, `technical/04_cybershield_architecture.md` line 429 | 02_org_announce: 0/0; others: not specifically audited | **C/D** | Despite 5 source mentions across 4 docs, no extractor produced an edge. Alan Chen is in the graph as an orphan PERSON. The strongest signal (the org-announcement table row) was lost with the rest of that doc. |
| 76 | Total patent portfolio size | 2,412 patents | ❌ No `2,412` / `2412` entity exists. Existing patent ents are: `Patent Portfolio` (PROJECT), `Patents Filed` (BUDGET), `Active Patent Portfolio = 650`, `Patent Portfolio = 100+ new/year` | ❌ — | Source corpus: best matches are `strategy/08_innovation_strategy.md` line 27 ("Active Patent Portfolio \| 650") and `strategy/01_corporate_strategy_2026_2030.md` line 57 ("Patent Portfolio \| 100+ new/year"). **No occurrence of "2,412" or "2412" anywhere in the corpus.** | n/a | **E** | The expected answer `2,412 patents` does not appear in any source document. This is a test-data issue: the question expects a number the corpus does not contain. The graph is correctly returning NOT_FOUND. |

---

## Failure breakdown by category

| Category | Count | Questions |
|---|---:|---|
| **A** — Retrieval miss on present edge | **1** | Q1 |
| **B** — Wrong edge wins (combined with C) | 1 (Q38, also C) | Q38 |
| **C** — Source doc produced 0 extractions | **5** | Q3, Q14, Q38, Q61, Q75 |
| **D** — Both endpoints present, no edge | **5** | Q18, Q25, Q37, Q46, Q67 |
| **E** — Fact not in corpus (test-data issue) | **1** | Q76 |

**~10 of 12 failures share one upstream cause: the extractor failed to produce relationships from specific documents.** Of those, the single highest-leverage doc is `02_organizational_announcement.md` (drives Q3, Q14, Q38, Q61, and contributes to Q1 and Q75).

## Specific actionable findings

1. **Re-extract `02_organizational_announcement.md`.** It is in the vault with 0 entities and 0 relationships. The doc is well-structured and contains the announcement narrative plus a leadership table — both of which the ontology pipeline normally handles. Investigate why this single document silently produced nothing (likely candidates: empty chunk because of frontmatter delimiter, an exception swallowed during a single-doc extraction, or a content-type filter rejecting `.md` with embedded HTML).

2. **Specification documents are dropping all relationships.** `06_solid_state_battery_design.md` (140 ents / 0 rels) and `04_greenhydrogen_initiative.md` (41 ents / 0 rels) are extracting entities from markdown tables but never emitting `HAS_SPEC` / `TARGETS` / `SUPPLIES` edges between table rows and the row's subject. This affects more than just Q25/Q67/Q18; it likely depresses any spec/agreement question that depends on a table.

3. **Q46 reveals a directional-extraction bug.** From `10_first_solar_supplier.md`, the extractor produced `First Solar --[SUPPLIES]--> Canadian Solar/LONGi/Qcells/JinkoSolar` — these are First Solar's **competitors**, not its customers. The extractor confused "compared to" / "vs" language for "supplies". Worth a focused regex/prompt fix.

4. **Q1 (CEO) is the only true retrieval failure** of the 12. The correct edge is in STAGING but the role-resolver returned a vague answer. The combination of an ARCHIVED `CEO` ROLE node, a noisy second `Dr. Robert Martinez --[HOLDS_POSITION]--> CEO` edge, and STAGING lifecycle on the correct edge suggests retrieval is not handling the multi-edge / lifecycle disambiguation cleanly. Worth a closer look in `RoleResolver`.

5. **Q76 is a test-data error.** The number "2,412" is not in the corpus. Recommend flagging in the question set rather than chasing it as an extraction defect.

## What this implies for the 72→? roadmap

The 12 NOT_FOUND failures can plausibly be cut to ≤ 3 by:
- Re-running extraction on the 3 named source docs and verifying edges land (estimated +5 questions: Q3, Q14, Q37, Q61, Q75; possibly Q1 and Q38).
- Fixing the spec-table edge emission in the ontology pipeline (+2: Q25, Q67).
- Fixing First-Solar directional extraction OR seeding the Desert Sun supplier edge (+1: Q46).
- Adding the Shell offtake edge from the GreenHydrogen doc (+1: Q18).
- Excluding/correcting Q76.

This points to extraction quality (specifically: silent per-document extraction failures and table-row relationship emission) as the dominant blocker — not retrieval, not promotion gating, not ontology coverage.
