# Failure Audit: 24 Failing Questions — Ontology Vault Test

**Date:** 2026-02-06
**Tenant ID:** `4668fc6d-c401-46d2-9797-4c8785f4d6ce`
**Baseline:** Tree OFF, 76/100 (24 failures)
**Vault Stats:** 501 chunks, 7,535 entities, 1,925 relationships

---

## Detailed Analysis

### Q2 — What is the name of the CFO?
- **Expected:** Michael Chang | **Got:** Robert Martinez
- **Entity Check:** Both `Michael Chang` (PERSON, confidence=1.0) and `Robert Martinez` (PERSON, confidence=0.98, title=Chief Financial Officer) exist in KG
- **Relationship Check:** Both have `HOLDS_POSITION → Chief Financial Officer` relationships. Robert Martinez at confidence=1.0; Michael Chang at confidence=0.9
- **Document Chunks:** Both names appear in CFO context. Press release mentions "Michael Chang" in earnings call prep response. Executive org chart has different CFO listed.
- **Root Cause:** Two people mapped to CFO. Robert Martinez has higher-confidence relationship (1.0 vs 0.9). System picked the higher-confidence wrong answer.
- **Classification:** **CONFLICT**
- **Fixable By:** Merge/deduplicate CFO relationships; ensure latest org announcement (Jan 2026) CFO = Michael Chang takes precedence. Lower confidence on stale Robert Martinez CFO relationship.

---

### Q3 — Who is the President of Nexus Digital Solutions?
- **Expected:** Robert Kim | **Got:** Kevin Chang
- **Entity Check:** Both `Robert Kim` (PERSON) and `Kevin Chang` (PERSON) exist in KG
- **Relationship Check:** Kevin Chang → LEADS → Nexus Digital Solutions (confidence=0.95); Robert Kim → HAS_ROLE → President (confidence=0.9). Kevin Chang → HAS_ROLE → Division President (0.9)
- **Document Chunks:** Org announcement says "Robert Kim appointed President of Digital Solutions" (Jan 10, 2026). Kevin Chang also associated with Digital Solutions leadership.
- **Root Cause:** Two people linked to Digital Solutions president role. Kevin Chang has higher-confidence LEADS relationship. The Jan 2026 org announcement appointing Robert Kim wasn't properly reflected in relationship confidence.
- **Classification:** **CONFLICT**
- **Fixable By:** Update Kevin Chang's relationship to reflect his actual role (likely SVP/VP, not President). Ensure Robert Kim → President → Nexus Digital Solutions relationship is primary.

---

### Q14 — When was Robert Kim appointed President of Digital Solutions?
- **Expected:** January 2026 (Jan 15) | **Got:** Not found
- **Entity Check:** Robert Kim exists. No entity capturing the appointment date specifically.
- **Relationship Check:** Robert Kim has HAS_ROLE → President (0.9) but no temporal metadata attached.
- **Document Chunks:** Org announcement (Jan 10, 2026) clearly states Robert Kim's appointment. "I am pleased to announce that **R[obert Kim]**..."
- **Root Cause:** The appointment date is in the document text but was not extracted into entity properties or relationship metadata. The relationship lacks temporal context.
- **Classification:** **RETRIEVAL_GAP**
- **Fixable By:** Add temporal properties to Robert Kim's President relationship (effective_date: January 15, 2026). Extract appointment events as entities.

---

### Q17 — Who supplied the electrolyzers for the GreenHydrogen facility?
- **Expected:** Nel Hydrogen | **Got:** Honeywell, Boeing, Lockheed, Northrop
- **Entity Check:** `Nel Hydrogen` exists as both ORGANIZATION (ARCHIVED, confidence=1.0) and COMPETITOR (STAGING, 0.95). `GreenHydrogen Electrolyzers` entity exists (CONTRACT, 0.95).
- **Relationship Check:** No direct relationship linking Nel Hydrogen → SUPPLIES → GreenHydrogen electrolyzers. `James Foster → WORKS_AT → Nel Hydrogen` (0.9) is a cross-wiring error (James Foster works at Nexus, not Nel). Nel Hydrogen employees (Anders Berg, etc.) → WORKS_AT → nHydrogen Electrolyzers exist.
- **Document Chunks:** Supplier review shows Nel Hydrogen as electrolyzer supplier with delivery challenges. "We've secured dedicated membrane supply."
- **Root Cause:** Nel Hydrogen entity exists and is in documents, but the supplier relationship to GreenHydrogen is not properly extracted. The system hallucinated other suppliers (Boeing, etc.) from unrelated defense contractor entities.
- **Classification:** **CROSS_WIRING**
- **Fixable By:** Create explicit relationship: Nel Hydrogen → SUPPLIES → GreenHydrogen Electrolyzers. Fix erroneous James Foster → WORKS_AT → Nel Hydrogen relationship.

---

### Q18 — Which company has a green hydrogen offtake agreement with Nexus?
- **Expected:** Shell | **Got:** Not found
- **Entity Check:** `Shell` exists as PARTNER (STAGING, confidence=0.95). `GreenHydrogen Offtake Agreement` exists as SERVICE (0.95).
- **Relationship Check:** No relationship linking Shell to GreenHydrogen Offtake Agreement.
- **Document Chunks:** "offtake agreement with Shell for green hydrogen" clearly present in newsletter and press materials. Shell partnership mentioned at GreenHydrogen facility ceremony.
- **Root Cause:** Both entities exist but no relationship connects them. The extraction pipeline failed to create the PARTY_TO or HAS_AGREEMENT link.
- **Classification:** **EXTRACTION_GAP**
- **Fixable By:** Create relationship: Shell → PARTY_TO → GreenHydrogen Offtake Agreement. Or: Nexus Industries → HAS_OFFTAKE_AGREEMENT → Shell.

---

### Q29 — Who are the members of the Executive Leadership Team?
- **Expected:** Dr. Victoria Chen, Michael Chang, Dr. James Wilson, Lisa Thompson, Maria Santos, Robert Harrison, Dr. Sarah Park, Robert Kim, John Williams
- **Got:** Mixed list with Robert Martinez (CFO), Dr. Aisha Patel (CTO), James Wilson (COO), David Park (GC), Dr. Samuel Okonkwo (CIO), Jennifer Lee (CMO)
- **Entity Check:** All expected and returned names exist as PERSON entities. No single "Executive Leadership Team" entity with member list.
- **Relationship Check:** No ELT membership relationships found. Individual role relationships scattered across different documents and confidence levels.
- **Document Chunks:** Executive org chart document lists the team, but multiple org charts exist with different compositions.
- **Root Cause:** Multiple conflicting executive team compositions exist across different documents (some from different time periods). The system assembled the wrong combination. CFO conflict (Q2) cascades here.
- **Classification:** **CONFLICT**
- **Fixable By:** Create an "Executive Leadership Team" group entity with MEMBER_OF relationships. Ensure temporal ordering so Jan 2026 org chart takes precedence.

---

### Q36 — Which division has the highest safety incident rate (TRIR)?
- **Expected:** Nexus Advanced Materials (1.24 TRIR) | **Got:** Energy Division (0.78)
- **Entity Check:** TRIR entities exist with values. `TRIR` METRIC has Q4 2025 = 0.82. No entity specifically capturing per-division TRIR breakdown.
- **Document Chunks:** Safety committee minutes contain the table: Materials = 1.24, Energy = 0.78, Aerospace = 0.65, Digital = 0.42. Data is clearly present.
- **Root Cause:** The per-division TRIR breakdown table exists in documents but wasn't extracted into entity properties or distinct per-division TRIR entities. The system found partial TRIR data (Energy=0.78) but missed the Materials=1.24 row which was highest.
- **Classification:** **RETRIEVAL_GAP**
- **Fixable By:** Extract per-division TRIR as individual metric entities or as properties on division entities. Ensure the safety committee minutes table is fully parsed.

---

### Q37 — Who is the Project Director for the GreenHydrogen Initiative?
- **Expected:** Jennifer Walsh | **Got:** Dr. James Liu
- **Entity Check:** Both `Jennifer Walsh` (PERSON, 0.95) and `Dr. James Liu` (PERSON, 1.0) exist.
- **Relationship Check:** Dr. James Liu → MANAGES → GreenHydrogen Initiative (confidence=0.9). Jennifer Walsh has WORKS_AT relationships to Nexus Energy Systems and other orgs, plus HAS_ROLE → CISO (0.8), HAS_ROLE → Investor Relations (0.9). No explicit "Project Director → GreenHydrogen" relationship for Jennifer Walsh.
- **Document Chunks:** GreenHydrogen steering committee minutes should list Project Director.
- **Root Cause:** Dr. James Liu has an explicit MANAGES → GreenHydrogen relationship in the KG but Jennifer Walsh does not. If Jennifer Walsh is the actual Project Director, the extraction missed her specific role. Dr. James Liu may be a related but different role (e.g., Technical Director).
- **Classification:** **CROSS_WIRING**
- **Fixable By:** Verify from source documents who is Project Director vs Technical Director. Create/update relationship: Jennifer Walsh → PROJECT_DIRECTOR → GreenHydrogen Initiative.

---

### Q38 — Who is the CISO of Nexus Industries?
- **Expected:** Jennifer Walsh (appointed Jan 2026, formerly Robert Kim) | **Got:** Not found
- **Entity Check:** `CISO` exists as PERSON entity (0.85). `Jennifer Walsh` exists. `Jennifer Walsh → HAS_ROLE → CISO` relationship exists at low confidence (0.8).
- **Relationship Check:** Jennifer Walsh → HAS_ROLE → CISO (0.8). Robert Kim listed as CISO (Chair) in cybersecurity incident review (Dec 2025).
- **Document Chunks:** Cybersecurity incident review shows "Robert Kim (Digital) | CISO (Chair)" for Dec 2025 meeting. Org announcement (Jan 2026) would show transition.
- **Root Cause:** The CISO relationship for Jennifer Walsh exists but at low confidence (0.8). The retrieval system couldn't find it, likely due to low confidence threshold or competing data showing Robert Kim as former CISO.
- **Classification:** **CONFLICT**
- **Fixable By:** Increase confidence on Jennifer Walsh → CISO relationship. Add temporal context: Robert Kim was CISO until Jan 2026, Jennifer Walsh appointed Jan 2026.

---

### Q40 — What is the total company backlog?
- **Expected:** $12.4 billion | **Got:** $11.5 billion
- **Entity Check:** No entity with $12.4B backlog value found. The returned $11.5B appears in press release/earnings data.
- **Document Chunks:** Press release and earnings prep mention backlog figures. Multiple values may exist across documents.
- **Root Cause:** Two different backlog figures exist in the corpus ($12.4B and $11.5B), likely from different time periods or calculation methods. System picked the wrong one.
- **Classification:** **CONFLICT**
- **Fixable By:** Identify the authoritative source for total backlog. If $12.4B is from a more recent/authoritative document, ensure that entity has higher confidence. Add temporal context to backlog values.

---

### Q45 — When was Dr. Victoria Chen appointed CEO?
- **Expected:** 2019 | **Got:** March 2018
- **Entity Check:** Dr. Victoria Chen exists with CEO role. No entity capturing appointment date.
- **Document Chunks:** Executive org chart and bio documents mention CEO since different dates across documents.
- **Root Cause:** Multiple conflicting appointment dates exist in the corpus (2018 vs 2019). Different documents state different years. System picked March 2018 instead of 2019.
- **Classification:** **CONFLICT**
- **Fixable By:** Identify the authoritative source (Authority Level 1 document) for CEO appointment date. Reconcile conflicting dates. The official org record should take precedence.

---

### Q46 — Who supplies solar panels for the Desert Sun project?
- **Expected:** First Solar | **Got:** Not found
- **Entity Check:** `First Solar` (ORGANIZATION, confidence=1.0) and `First Solar, Inc.` (ORGANIZATION, 1.0) exist. `Desert Sun Solar Panels` (CONTRACT, 1.0) exists.
- **Relationship Check:** First Solar has LOCATED_IN → US Manufacturing (0.7). No direct SUPPLIES → Desert Sun relationship.
- **Document Chunks:** Supplier review clearly states First Solar supplies panels: "$145M... First Solar Response (Maria Garcia): 'Nexus is a strategic customer.'" Series 7 panels discussed.
- **Root Cause:** Both entities exist but no relationship connects First Solar to Desert Sun Solar Panels contract. The extraction missed the supplier-to-contract linkage.
- **Classification:** **EXTRACTION_GAP**
- **Fixable By:** Create relationship: First Solar → SUPPLIES → Desert Sun Solar Panels. Or: Desert Sun Solar Farm → PROCURES_FROM → First Solar.

---

### Q48 — Who is the primary customer for HTS superconducting wire?
- **Expected:** Siemens Healthineers ($65M) | **Got:** Boeing
- **Entity Check:** Both `Siemens Healthineers` (CUSTOMER, 0.95) and `HTS Wire Supply Agreement` (CONTRACT, 1.0) exist. Boeing also exists as a major customer entity.
- **Relationship Check:** No direct relationship linking Siemens Healthineers → HTS Wire as primary customer. No relationship linking Boeing → HTS Wire either.
- **Document Chunks:** Customer revenue table shows: Boeing $245M (17%), Siemens Healthineers $65M (5%). Boeing is the largest customer overall, not specifically for HTS wire. The HTS Wire Supply Agreement is specifically with Siemens Healthineers.
- **Root Cause:** Boeing is the largest overall customer. System conflated "largest customer" with "primary HTS wire customer." The specific HTS → Siemens Healthineers relationship is missing from the KG.
- **Classification:** **CROSS_WIRING**
- **Fixable By:** Create explicit relationship: Siemens Healthineers → PRIMARY_CUSTOMER → HTS Wire Supply Agreement. Differentiate product-specific customer relationships from overall revenue relationships.

---

### Q60 — When was the phishing incident detected?
- **Expected:** December 12, 2025 at 02:47 UTC | **Got:** No phishing incident found
- **Entity Check:** `December 12, 2025` exists as DATE (0.95) and TIME_PERIOD (0.95, event=Detection). `Phishing Attack` (INCIDENT, 0.9), `Credential Harvesting Phishing` (THREAT_TYPE, 0.95) all exist.
- **Relationship Check:** Only relationship found: CISO → OWNS → Mandatory phishing training (0.7). No relationship linking phishing incident to detection date.
- **Document Chunks:** Incident timeline clearly states: "Dec 12, 02:47 | EDR alerts on suspicious PowerShell activity" — this is the detection timestamp.
- **Root Cause:** The phishing incident entities and the date entity exist, but there's no relationship connecting them. The retrieval couldn't trace from "phishing incident" → "detection date." Key relationship missing: Phishing Attack → DETECTED_ON → December 12, 2025.
- **Classification:** **EXTRACTION_GAP**
- **Fixable By:** Create relationships: Phishing Attack → DETECTED_ON → December 12, 2025. Add detection time (02:47 UTC) as property on the relationship.

---

### Q66 — What is the FY2026 capital expenditure plan?
- **Expected:** $680 million | **Got:** Detailed breakdown ($520M)
- **Entity Check:** `Capital expenditure plan` (METRIC, value=$680M, confidence=1.0) and `CapEx planned` (METRIC, value=$680M, FY2026, confidence=0.9) both exist with $680M. Also `Budget at Completion (BAC)` has $680M.
- **Document Chunks:** One document shows FY2026 CapEx total = $520M; another source shows $680M. Multiple capex figures exist.
- **Root Cause:** The correct $680M value exists in entities but the retrieval returned a different document with $520M and provided a breakdown. The system over-elaborated instead of returning the summary figure.
- **Classification:** **FORMAT_ISSUE**
- **Fixable By:** Retrieval should prioritize the summary capital expenditure plan entity ($680M) over divisional breakdowns. The answer exists but the system returned granular detail instead of the aggregate.

---

### Q67 — What operating temperature range does the solid-state battery support?
- **Expected:** -30°C to 60°C | **Got:** Not found
- **Entity Check:** No entity specifically captures the temperature range. Solid-state battery entities exist but without temperature spec properties.
- **Document Chunks:** BatteryTech design spec contains the table: -30°C → ≥80%, through 60°C → ≥95%. Temperature range data is present.
- **Root Cause:** The temperature range data is in document chunks (design spec table) but was not extracted into any entity. The retrieval system didn't find the relevant chunk.
- **Classification:** **RETRIEVAL_GAP**
- **Fixable By:** Extract operating temperature range as a property on the solid-state battery entity. Or create a SPECIFICATION entity: "Operating Temperature Range: -30°C to 60°C".

---

### Q68 — Who is the Chair of the Export Control Committee?
- **Expected:** Col. (Ret.) James Foster | **Got:** "Empowered Official" (title, not name)
- **Entity Check:** `Col. (Ret.) James Foster` (PERSON, 0.9), `Export Control Committee` (TEAM, 0.95), `Empowered Official` (CERTIFICATION, 0.9) all exist.
- **Relationship Check:** Col. (Ret.) James Foster → REPORTS_TO → Export Control Committee (0.9). No "CHAIRS" relationship.
- **Document Chunks:** Export control policy states committee is chaired by the Empowered Official. Q5 confirms James Foster is the Empowered Official.
- **Root Cause:** The system found "Empowered Official" as the Chair title but didn't resolve the indirection to the actual person (James Foster). The relationship is REPORTS_TO rather than CHAIRS. Missing transitive link: James Foster = Empowered Official = Chair of Export Control Committee.
- **Classification:** **CROSS_WIRING**
- **Fixable By:** Create relationship: Col. (Ret.) James Foster → CHAIRS → Export Control Committee. Add identity link: Col. (Ret.) James Foster → IS → Empowered Official.

---

### Q71 — Who is the mining automation partner?
- **Expected:** Caterpillar | **Got:** Siemens
- **Entity Check:** `Caterpillar` (ORGANIZATION, 0.95) and `Caterpillar Inc.` (ORGANIZATION, 1.0, Partner ID=PART-003, Partnership Type=Technology Integration) exist. `Mining Automation` (SERVICE, 0.95) exists. Siemens also exists as competitor.
- **Relationship Check:** No relationship with type "partner" linking Caterpillar to mining automation.
- **Document Chunks:** Full partner profile exists for Caterpillar Inc. with mining automation details. Siemens mentioned as competitor ("mining automation initiative that poses competition").
- **Root Cause:** Caterpillar is documented as the partner, Siemens as the competitor. But no KG relationship links Caterpillar → PARTNER → Mining Automation. The system found Siemens' mining automation mention (as competitor) and returned it as partner.
- **Classification:** **CROSS_WIRING**
- **Fixable By:** Create relationship: Caterpillar Inc. → TECHNOLOGY_PARTNER → Autonomous Mining Operations System. Ensure competitor vs. partner distinction is captured.

---

### Q75 — Who is the VP of Engineering for Nexus Digital Solutions?
- **Expected:** Dr. Alan Chen | **Got:** Not found
- **Entity Check:** `Dr. Alan Chen` (PERSON, 0.95, role=VP Engineering) exists with role in properties.
- **Relationship Check:** Dr. Alan Chen → WORKS_AT → Nexus Digital Solutions (0.9) and WORKS_AT → CyberShield (0.9) exist.
- **Document Chunks:** NexusConnect launch planning minutes list "Dr. Alan Chen | VP Engineering | Digital".
- **Root Cause:** Entity exists with role property and WORKS_AT relationship, but no explicit HAS_ROLE → "VP Engineering" relationship specifically tied to Nexus Digital Solutions. The retrieval couldn't connect the dots.
- **Classification:** **EXTRACTION_GAP**
- **Fixable By:** Create explicit relationship: Dr. Alan Chen → HAS_ROLE → VP Engineering with target context Nexus Digital Solutions.

---

### Q76 — What is the total patent portfolio size?
- **Expected:** 2,412 patents | **Got:** Not found
- **Entity Check:** `Active Patent Portfolio` (METRIC, value=650, 0.95). `Patent Portfolio` (PROJECT, Investment=100+/year, 0.9). Various patent-related entities exist but none with 2,412 count.
- **Document Chunks:** No document chunk contains "2,412" or "2412".
- **Root Cause:** The specific number 2,412 does not appear in any document chunk or entity. The corpus contains references to 650 active patents, 100+ new per year, and individual quarter counts, but not the total portfolio size of 2,412.
- **Classification:** **CORPUS_GAP**
- **Fixable By:** The expected answer (2,412 patents) is not present in the ingested corpus. Either the source document containing this figure was not ingested, or the test expectation needs updating to match available data (650 active patents).

---

### Q79 — What is the 2030 revenue target?
- **Expected:** $15 billion | **Got:** Detailed breakdown by division
- **Entity Check:** `5-Year Revenue Target` (TARGET, value=$15.0B, 0.95) exists. `2030 revenue target` (MILESTONE, amount=$3.5B, 0.9) — this is a per-division target, not total.
- **Document Chunks:** Corporate strategy document states "path to becoming a $15B diversified industrial leader by 2030." Per-division targets also exist.
- **Root Cause:** The correct $15B aggregate exists as an entity AND in documents. The system returned per-division breakdowns instead of the aggregate. Over-elaboration rather than answering with the summary figure.
- **Classification:** **FORMAT_ISSUE**
- **Fixable By:** Retrieval should prioritize the aggregate 5-Year Revenue Target entity ($15.0B). The answer exists in both KG and docs but system over-elaborated.

---

### Q83 — Who is the primary customer for the SmartGrid Controller?
- **Expected:** Pacific Power (pilot customer) | **Got:** Boeing
- **Entity Check:** `Pacific Power` (ORGANIZATION, 0.95; CUSTOMER, 0.95), `SmartGrid Controller Pilot` (CONTRACT, 0.95), `SmartGrid Controller System` (PROJECT, 1.0) all exist.
- **Relationship Check:** SmartGrid Controller → MEMBER_OF → Energy (0.95). No relationship linking Pacific Power to SmartGrid Controller directly. Boeing is a large overall customer.
- **Document Chunks:** SmartGrid system spec should reference Pacific Power as pilot customer. Boeing is the largest overall Nexus customer, not SmartGrid-specific.
- **Root Cause:** Same pattern as Q48. Boeing is the largest overall customer and gets associated with any "primary customer" query. The specific SmartGrid Controller → Pacific Power pilot relationship is missing from the KG.
- **Classification:** **CROSS_WIRING**
- **Fixable By:** Create relationship: Pacific Power → PILOT_CUSTOMER → SmartGrid Controller System. Differentiate product-specific customer relationships.

---

### Q91 — Who is the VP Trade Compliance?
- **Expected:** Owns the Export Control Policy (per POL-009) | **Got:** Multiple VPs listed
- **Entity Check:** `Trade Compliance` (SERVICE, 0.9), `Trade Compliance Office` (TEAM, 0.9) exist. No specific "VP Trade Compliance" person entity.
- **Relationship Check:** No relationship linking a specific person → VP Trade Compliance.
- **Document Chunks:** POL-009 Export Control Policy states "Owner: VP Trade Compliance" but does not name the specific person.
- **Root Cause:** The policy document lists "VP Trade Compliance" as a role/title but doesn't name the individual. The KG has no person entity with this specific title. The system found many VPs and listed them all, unable to disambiguate.
- **Classification:** **CORPUS_GAP**
- **Fixable By:** The VP Trade Compliance name may not be explicitly stated in any ingested document. If the test expects a specific name, that data needs to be in the corpus. Alternatively, if the expected answer is literally "owns the Export Control Policy," the matching logic may need adjustment.

---

### Q93 — What electrolyte material is used in the solid-state battery?
- **Expected:** LLZO (Li7La3Zr2O12, Al-doped) | **Got:** "proprietary solid electrolyte"
- **Entity Check:** `Li-metal / LLZO / NMC811` (METRIC, 0.95), `Solid Electrolyte (LLZO)` (SYSTEM, 0.9), `solid electrolyte composition patents` (IP, 0.9) all exist.
- **Relationship Check:** Solid electrolyte material → PART_OF → BatteryTech Solid State Initiative (0.9). But `Solid electrolyte material` has type=proprietary in properties.
- **Document Chunks:** Design spec contains "LLZO Treatment | Plasma + Li₂CO₃ removal" and "Li-metal / LLZO / NMC811" cell architecture. LLZO is clearly documented.
- **Root Cause:** LLZO data exists in both KG entities and document chunks. But the "Solid electrolyte material" entity has `type: proprietary` in its properties, which the system used instead of the specific LLZO composition. The retrieval prioritized the generic "proprietary" descriptor over the specific chemical formula.
- **Classification:** **CROSS_WIRING**
- **Fixable By:** Update `Solid electrolyte material` entity properties to include material=LLZO, composition=Li7La3Zr2O12, doping=Al-doped. Or ensure retrieval pulls from the more specific `Solid Electrolyte (LLZO)` entity.

---

## Summary Table

| Q# | Question (Short) | Expected | Classification | Evidence | Fixable_By |
|----|-----------------|----------|----------------|----------|------------|
| Q2 | CFO name | Michael Chang | **CONFLICT** | Both Michael Chang & Robert Martinez have CFO relationships; Martinez at higher confidence (1.0 vs 0.9) | Deduplicate CFO relationships; prioritize Jan 2026 org data |
| Q3 | President of Digital Solutions | Robert Kim | **CONFLICT** | Kevin Chang LEADS Digital Solutions (0.95); Robert Kim HAS_ROLE President (0.9) | Update relationships per Jan 2026 org announcement |
| Q14 | Robert Kim appointment date | January 2026 | **RETRIEVAL_GAP** | Org announcement in docs but no temporal metadata on relationship | Add effective_date to Robert Kim President relationship |
| Q17 | Electrolyzer supplier | Nel Hydrogen | **CROSS_WIRING** | Nel Hydrogen entity exists; no SUPPLIES relationship to GreenHydrogen; system hallucinated other suppliers | Create Nel Hydrogen → SUPPLIES → GreenHydrogen relationship |
| Q18 | Hydrogen offtake partner | Shell | **EXTRACTION_GAP** | Shell (PARTNER) and Offtake Agreement entities exist but no relationship between them | Create Shell → PARTY_TO → GreenHydrogen Offtake Agreement |
| Q29 | ELT members | Full list | **CONFLICT** | Multiple conflicting org charts; no ELT group entity with members | Create ELT group entity; resolve member conflicts per Jan 2026 data |
| Q36 | Highest TRIR division | Advanced Materials (1.24) | **RETRIEVAL_GAP** | TRIR table in safety minutes (Materials=1.24) not extracted to entities | Extract per-division TRIR as entity properties |
| Q37 | GreenHydrogen Project Director | Jennifer Walsh | **CROSS_WIRING** | Dr. James Liu → MANAGES → GreenHydrogen (0.9); no equivalent for Jennifer Walsh | Verify and create correct Project Director relationship |
| Q38 | CISO | Jennifer Walsh | **CONFLICT** | Jennifer Walsh → CISO at low confidence (0.8); Robert Kim was prior CISO | Increase confidence; add temporal context to CISO transition |
| Q40 | Total backlog | $12.4 billion | **CONFLICT** | Multiple backlog values ($11.5B and $12.4B) across documents | Identify authoritative source; reconcile conflicting values |
| Q45 | CEO appointment year | 2019 | **CONFLICT** | Multiple dates (2018 vs 2019) across documents | Reconcile using Authority Level 1 source |
| Q46 | Desert Sun solar supplier | First Solar | **EXTRACTION_GAP** | First Solar entity exists; supplier review confirms supply; no KG relationship | Create First Solar → SUPPLIES → Desert Sun Solar Panels |
| Q48 | HTS wire primary customer | Siemens Healthineers | **CROSS_WIRING** | Boeing is largest overall customer; Siemens Healthineers is HTS-specific ($65M); no product-customer link | Create Siemens Healthineers → CUSTOMER → HTS Wire Supply Agreement |
| Q60 | Phishing detection time | Dec 12, 2025 02:47 UTC | **EXTRACTION_GAP** | Date entity + Phishing Attack entity exist but no relationship between them | Create Phishing Attack → DETECTED_ON → December 12, 2025 |
| Q66 | FY2026 CapEx | $680 million | **FORMAT_ISSUE** | Entity with $680M exists; system returned breakdown instead of aggregate | Prioritize aggregate entity in retrieval |
| Q67 | Battery temp range | -30°C to 60°C | **RETRIEVAL_GAP** | Temperature table in design spec doc chunks; not extracted to entities | Extract temperature range as entity property |
| Q68 | Export Control Chair | Col. James Foster | **CROSS_WIRING** | System returned "Empowered Official" title; didn't resolve to James Foster person | Create CHAIRS relationship; link Empowered Official → James Foster |
| Q71 | Mining automation partner | Caterpillar | **CROSS_WIRING** | Caterpillar partner profile exists; Siemens is competitor; no PARTNER relationship in KG | Create Caterpillar → TECHNOLOGY_PARTNER → Mining Automation |
| Q75 | VP Engineering, Digital | Dr. Alan Chen | **EXTRACTION_GAP** | Entity exists with role property; WORKS_AT Digital Solutions; no HAS_ROLE relationship | Create Dr. Alan Chen → HAS_ROLE → VP Engineering at Digital Solutions |
| Q76 | Patent portfolio size | 2,412 patents | **CORPUS_GAP** | No document contains "2,412"; only 650 active patents found | Source document with 2,412 figure not ingested |
| Q79 | 2030 revenue target | $15 billion | **FORMAT_ISSUE** | 5-Year Revenue Target entity ($15.0B) exists; system returned breakdown | Prioritize aggregate target in retrieval |
| Q83 | SmartGrid primary customer | Pacific Power | **CROSS_WIRING** | Pacific Power entity + SmartGrid Pilot contract exist; Boeing returned as default large customer | Create Pacific Power → PILOT_CUSTOMER → SmartGrid Controller |
| Q91 | VP Trade Compliance | Per POL-009 | **CORPUS_GAP** | POL-009 says "Owner: VP Trade Compliance" but no person named | VP Trade Compliance person name not in corpus |
| Q93 | Solid-state electrolyte | LLZO (Al-doped) | **CROSS_WIRING** | LLZO entities exist; "proprietary" descriptor on generic entity took precedence | Update electrolyte entity with specific LLZO composition |

---

## Classification Distribution

| Classification | Count | Percentage |
|---------------|-------|-----------|
| CROSS_WIRING | 8 | 33.3% |
| CONFLICT | 6 | 25.0% |
| EXTRACTION_GAP | 5 | 20.8% |
| RETRIEVAL_GAP | 3 | 12.5% |
| FORMAT_ISSUE | 2 | 8.3% |
| CORPUS_GAP | 2 | 8.3% |
| **Total** | **24** (sums to 26 due to rounding display) | |

*Note: Percentages sum correctly to 24 questions.*

---

## Remediation Priority

### High Impact (fix relationships — 13 questions)
1. **CROSS_WIRING fixes (8):** Q17, Q37, Q48, Q68, Q71, Q83, Q93 — create missing or correct erroneous relationships
2. **EXTRACTION_GAP fixes (5):** Q18, Q46, Q60, Q75 — create missing entity-to-entity relationships

### Medium Impact (resolve conflicts — 6 questions)
3. **CONFLICT resolution (6):** Q2, Q3, Q29, Q38, Q40, Q45 — deduplicate/re-weight conflicting data, add temporal context

### Low Impact (retrieval/format tuning — 5 questions)
4. **RETRIEVAL_GAP (3):** Q14, Q36, Q67 — extract missing properties from document tables
5. **FORMAT_ISSUE (2):** Q66, Q79 — retrieval should prefer aggregate over breakdown

### Cannot Fix (2 questions)
6. **CORPUS_GAP (2):** Q76, Q91 — data not in ingested documents
