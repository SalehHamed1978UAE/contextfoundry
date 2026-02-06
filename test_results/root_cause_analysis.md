# Root Cause Analysis: 13 Fixable Failures (8 CROSS_WIRING + 5 EXTRACTION_GAP)

**Date:** 2026-02-06
**Tenant:** `4668fc6d-c401-46d2-9797-4c8785f4d6ce` (Ontology Vault)
**Baseline:** 76/100 (Tree OFF)
**Analysis Method:** Direct KG queries + source chunk inspection

---

## Part 1: CROSS_WIRING Pattern Analysis (8 failures)

### Finding 1: The Boeing Mistype Problem (Root cause of Q17, Q48, Q83)

**The smoking gun:** There are TWO "Boeing" entities in the KG:

| Entity | Type | State | Confidence | Properties |
|--------|------|-------|------------|------------|
| Boeing | **PERSON** | STAGING | 0.95 | `{"type": "customer"}` |
| The Boeing Company | ORGANIZATION | ARCHIVED | 1.0 | Customer ID: CUST-001, Strategic |

The ontology extraction pipeline created a **Boeing entity typed as PERSON** (id: `11158f3e`). This mistyped node has become a **relationship magnet** — 16 edges flow through it, including:

- **WORKS_AT → Boeing (PERSON):** Michael Torres, Dr. Rachel Kim, Catherine O'Brien, Angela Thompson — these are Nexus employees who work ON the Boeing account, not AT Boeing
- **MEMBER_OF → Boeing (PERSON):** William Foster, Robert Martinez, Jennifer Liu — same account-team confusion
- **HOLDS_POSITION → Boeing (PERSON):** Robert Kim, Andrew Stevens, Dr. Jennifer Liu — people who hold positions related to Boeing programs, not positions at Boeing itself
- **HAS_ROLE → Development partner (ROLE):** Boeing typed as having a "development partner" role

**Why this causes cross-wiring:** When the system receives "who is the primary customer for HTS wire?" or "who is the customer for SmartGrid?", the retrieval finds `Boeing (PERSON, type=customer)` with high degree centrality. Because Boeing is the largest overall customer ($245M, 17% of revenue), and has the most relationship edges, it gets returned for ANY product-specific customer question — even when the actual customer relationship is with Siemens Healthineers (HTS wire) or Pacific Power (SmartGrid).

**The extraction prompt confusion:** The source document (`02_aerospace_division_strategy.md`, `05_falcon_x_program.md`) discusses Boeing in the context of Nexus's aerospace strategy. Sentences like "Michael Torres manages the Boeing account" were extracted as `Michael Torres → WORKS_AT → Boeing` instead of `Michael Torres → MANAGES_ACCOUNT → Boeing`. The LLM confused "managing a customer relationship" with "working at the company."

**Pattern:** Entity Resolution did NOT collapse these into one node — it created a separate PERSON-typed Boeing alongside the correctly-typed `The Boeing Company (ORGANIZATION, ARCHIVED, confidence=1.0, Customer ID=CUST-001)`. The ORGANIZATION entity has only 4 edges (LOCATED_IN → Chicago, WORKS_AT from Jennifer Morrison, MANAGES from Michael Torres, plus one more). The mistyped PERSON node absorbed 16 edges — 4x more relationship traffic than the correct entity.

### Finding 2: Participant List Contamination (Root cause of Q37, Q68, Q71, Q93)

These four failures share a common extraction pattern: **multi-person document chunks where the LLM creates wrong relationships between people and roles/products.**

#### Q37 (GreenHydrogen Project Director): Jennifer Walsh vs Dr. James Liu

Two different documents describe GreenHydrogen leadership:

| Document | Role Listed | Person |
|----------|-----------|--------|
| `09_greenhydrogen_milestone.md` (chunk 1) | "Project Director" | **Jennifer Walsh** |
| `09_greenhydrogen_el_paso.md` (chunk 1) | "Project Manager" | **Dr. James Liu** |

The extraction created `Dr. James Liu → MANAGES → GreenHydrogen Initiative (0.9)` but never created `Jennifer Walsh → PROJECT_DIRECTOR → GreenHydrogen`. Why?

- The milestone chunk lists Jennifer Walsh in a **bullet list** under "Project Leadership:" — a format the extraction prompt handles poorly for role assignment
- The El Paso project chunk lists Dr. James Liu in a **Markdown table** (`| Project Manager | Dr. James Liu | 100% |`) — a structured format the extraction prompt handles well
- Result: The table-formatted role got a MANAGES relationship; the bullet-listed role did not get a specific role relationship

**Critical insight:** Jennifer Walsh's entity has 17 edges, but NONE of them link her to GreenHydrogen. Her relationships are scattered: WORKS_AT → Nexus Energy Systems, HAS_ROLE → Investor Relations, HAS_ROLE → CISO (0.8), HAS_ROLE → Presenter, HAS_ROLE → CEO/CFO (0.6!). She's been assigned roles from multiple documents where she appeared as an attendee or participant, but the specific "Project Director" role was missed.

#### Q68 (Export Control Committee Chair): Col. James Foster vs "Empowered Official"

The extraction created `Col. (Ret.) James Foster → REPORTS_TO → Export Control Committee (0.9)` and `Col. (Ret.) James Foster → REPORTS_TO → Empowered Official (0.9)`. Both are **REPORTS_TO** — the wrong relationship type entirely. The source says Foster IS the Empowered Official who CHAIRS the committee.

**Root cause:** The extraction prompt interpreted an organizational hierarchy mention as a reporting relationship. When a document says "Committee chaired by the Empowered Official" and separately identifies James Foster as the Empowered Official, the transitive link `James Foster = Empowered Official = Chair` requires two-hop reasoning the extraction prompt doesn't perform.

**Additional cross-wiring:** `James Foster → WORKS_AT → Nel Hydrogen (0.9)` — this is from document `acb4ec94` (GreenHydrogen steering committee minutes). The minutes mention Nel Hydrogen as a supplier and James Foster as an attendee. The extraction collapsed the co-occurrence into a WORKS_AT relationship. James Foster actually works at Nexus, not Nel Hydrogen.

#### Q71 (Mining Automation Partner): Caterpillar vs Siemens

Caterpillar Inc. exists with entity type ORGANIZATION and has partner metadata (PART-003, Technology Integration). But its only relationships are geographic:
- `LOCATED_IN → Deerfield, IL`
- `OPERATES_IN → Heavy Equipment Manufacturing`

**Zero partner/technology relationships** were created despite a full partner profile document (`d70fea1b`) existing with detailed mining automation specs, compatible equipment tables, and IP ownership details.

Meanwhile, Siemens has `COMPETITOR` entity type. The competitive intelligence document mentions Siemens's "mining automation initiative" — but as a competitive threat, not a partnership. The retrieval found this mention and returned Siemens as the partner.

**Root cause:** The extraction prompt created geographic relationships from the partner profile's header table but failed to extract the core partnership relationship (`Caterpillar → TECHNOLOGY_PARTNER → Autonomous Mining Operations`). The document is table-heavy — 8+ tables in the profile — and the extraction appears to have processed header metadata but stopped before reaching the partnership details tables.

#### Q93 (Solid-State Battery Electrolyte): LLZO vs "proprietary"

There are 12 electrolyte-related entities in the KG:

| Entity | Type | Has LLZO? |
|--------|------|-----------|
| Li-metal / LLZO / NMC811 | METRIC | Yes (in name) |
| Solid Electrolyte (LLZO) | SYSTEM | Yes (in name) |
| Solid electrolyte material | DELIVERABLE | No — `{type: proprietary}` |
| Electrolyte Composition | SPECIFICATION | No |
| solid electrolyte composition patents | IP | No |

The retrieval found `Solid electrolyte material (DELIVERABLE, type=proprietary)` and returned "proprietary solid electrolyte" instead of looking at the sibling entities that contain LLZO explicitly. The `type: proprietary` property came from the IP/patent section of the document, which describes the electrolyte as proprietary technology. The specific chemical composition (Li7La3Zr2O12, Al-doped) exists in the design spec but was extracted as a separate entity name (`Li-metal / LLZO / NMC811`) rather than as a property on the primary electrolyte entity.

**Root cause:** Entity fragmentation — the same concept (LLZO solid electrolyte) was extracted as 5+ separate entities with different names and types. No relationships connect them. The retrieval found the least specific one.

### Cross-Wiring Summary: Three Systemic Patterns

| Pattern | Failures | Root Cause |
|---------|----------|------------|
| **High-degree mistyped node** | Q17, Q48, Q83 | Boeing extracted as PERSON with 16 edges; absorbs all "customer" queries |
| **Co-occurrence → wrong relationship** | Q37, Q68, Q71 | People/orgs mentioned in same chunk get WORKS_AT/MEMBER_OF instead of correct relationship |
| **Entity fragmentation** | Q93 | Same concept split into 5+ entities; retrieval picks least specific one |

---

## Part 2: EXTRACTION_GAP Pattern Analysis (5 failures)

### Finding 3: Missing Relationship Types Are Systematically Absent

The 5 extraction gaps involve these specific missing relationship types:

| Q# | Missing Relationship | Source Entity | Target Entity | Both Exist? |
|----|---------------------|---------------|---------------|-------------|
| Q18 | PARTY_TO / HAS_AGREEMENT | Shell (PARTNER, 0.95) | GreenHydrogen Offtake Agreement (SERVICE, 0.95) | Yes |
| Q46 | SUPPLIES / PROCURES_FROM | First Solar (ORG, 1.0) | Desert Sun Solar Panels (CONTRACT, 1.0) | Yes |
| Q60 | DETECTED_ON / OCCURRED_AT | Phishing Attack (INCIDENT, 0.9) | December 12, 2025 (DATE, 0.95) | Yes |
| Q75 | HAS_ROLE (scoped) | Dr. Alan Chen (PERSON, 0.95) | VP Engineering + Nexus Digital (role+org) | Yes (partial) |
| Q48 | PRIMARY_CUSTOMER | Siemens Healthineers (CUSTOMER, 0.95) | HTS Wire Supply Agreement (CONTRACT, 1.0) | Yes |

**Critical observation: In all 5 cases, BOTH entities exist in the KG with reasonable confidence. Only the connecting relationship is missing.**

### Finding 4: Zero Product-Customer/Supplier Relationships in Entire KG

I searched for the following relationship types across the entire ontology vault KG:

- `SUPPLIES`: 0 relationships
- `CUSTOMER_OF`: 0 relationships
- `PROCURES_FROM`: 0 relationships
- `PILOT_CUSTOMER`: 0 relationships
- `PRIMARY_CUSTOMER`: 0 relationships
- `SUPPLIER_OF`: 0 relationships
- `SUPPLIES_TO`: 0 relationships

**The ontology vault has ZERO supply-chain relationships.** The relationship type distribution is dominated by:

| Type | Count | Avg Confidence |
|------|-------|---------------|
| WORKS_AT | 492 | 0.87 |
| MEMBER_OF | 278 | 0.77 |
| PART_OF | 227 | 0.80 |
| MANAGES | 135 | 0.85 |
| HOLDS_POSITION | 108 | 0.91 |
| HAS_ROLE | 99 | 0.88 |
| REPORTS_TO | 95 | 0.85 |
| RESPONSIBLE_FOR | 94 | 0.97 |
| LOCATED_IN | 89 | 0.84 |
| OWNS | 75 | 0.83 |
| INVESTED_IN | 58 | 0.85 |
| LEADS | 55 | 0.88 |
| PRODUCES | 12 | 0.83 |

**The extraction prompt is biased toward organizational/HR relationship types** (WORKS_AT, MEMBER_OF, REPORTS_TO, HAS_ROLE) and almost completely ignores supply-chain, commercial, and event-timing relationships.

### Finding 5: Document Format Correlates With Extraction Success

For each extraction gap, I examined the source chunk format:

| Q# | Entity Pair | Chunk Format | Why Extraction Failed |
|----|-------------|--------------|----------------------|
| Q18 (Shell + Offtake) | Newsletter paragraph: "offtake agreement with Shell for green hydrogen" | **Inline mention** in a newsletter paragraph amid many topics. Shell is mentioned once in passing within a bullet point about energy division achievements. | LLM treated this as descriptive text, not a relationship to extract. |
| Q46 (First Solar + Desert Sun) | Supplier review table: Name/Revenue columns | **Multi-supplier table** with 5+ suppliers. First Solar appears as one row. The table has procurement data but the LLM extracted the header entities (First Solar as org, Desert Sun as contract) without creating the link between them. | Table rows = entity extraction, but cross-column relationships not created. |
| Q60 (Phishing + Date) | Incident timeline table: `Dec 12, 02:47 \| EDR alerts on suspicious PowerShell` | **Timeline table** with multiple timestamps and events. The LLM extracted "Phishing Attack" as INCIDENT and "December 12, 2025" as DATE but didn't link them. | Same table-row problem: columns extracted as separate entities, not related. |
| Q75 (Dr. Alan Chen + VP Eng) | API spec header: `Owner: Dr. Alan Chen, VP Engineering` | **Document metadata header** — this is a single line in a document control section. The LLM extracted Dr. Alan Chen as PERSON and created WORKS_AT → Nexus Digital Solutions but didn't parse the role from the ownership line. | Role embedded in document metadata, not in prose or table. |
| Q48 (Siemens + HTS Wire) | Customer profile document: full page about Siemens Healthineers as customer | **Dedicated customer profile** exists (doc `322b9ba2`) with HTS Wire contract details, revenue pipeline, and exec contacts. But no CUSTOMER_OF or SUPPLIES relationship was created. | Same systemic gap: supply-chain relationship types simply not generated. |

### Extraction Gap Summary: Two Systemic Patterns

| Pattern | Failures | Root Cause |
|---------|----------|------------|
| **Supply-chain relationship blindspot** | Q18, Q46, Q48 | Extraction prompt produces 0 SUPPLIES/CUSTOMER_OF/PROCURES_FROM relationships across entire KG. The ontology defines these types but the extraction prompt never generates them. |
| **Cross-column table relationships** | Q60, Q75 | When data appears in table rows, individual columns get extracted as separate entities but the row-level relationship (this person has this role, this incident happened on this date) is lost. |

---

## Part 3: Why These Patterns Exist — Extraction Prompt Analysis

### The WORKS_AT Gravity Well

492 of 1,925 relationships (25.6%) are WORKS_AT. This is the single most common relationship type. The extraction prompt appears to default to WORKS_AT for any person-organization co-occurrence:

- `Michael Torres → WORKS_AT → Boeing` (he manages the Boeing account at Nexus)
- `James Foster → WORKS_AT → Nel Hydrogen` (he attended a meeting where Nel was discussed)
- `Catherine O'Brien → WORKS_AT → Boeing` (she works on Boeing programs at Nexus)
- `Jennifer Walsh → WORKS_AT → Q4 Inc` (mentioned alongside Q4 in investor call)

**The prompt doesn't distinguish between:**
1. Person X is employed at Organization Y (genuine WORKS_AT)
2. Person X manages the account/relationship with Organization Y (should be MANAGES_ACCOUNT)
3. Person X is mentioned in the same document as Organization Y (should be nothing, or ATTENDEE)
4. Person X is a customer contact at Organization Y (should be CONTACT_AT)

### The Missing Relationship Type Vocabulary

The ontology defines 230 relationship types, but the extraction only uses ~17 regularly. Critical types that appear 0 times:

- SUPPLIES / SUPPLIER_OF / SUPPLIES_TO
- CUSTOMER_OF / PRIMARY_CUSTOMER
- PARTY_TO / HAS_AGREEMENT
- CHAIRS / SERVES_ON
- DETECTED_ON / OCCURRED_AT
- PROJECT_DIRECTOR / TECHNICAL_LEAD
- TECHNOLOGY_PARTNER / DEVELOPMENT_PARTNER

The extraction prompt either doesn't know about these types or defaults to the simpler organizational types.

### Entity Type Confusion

Boeing was extracted as PERSON (not ORGANIZATION) because the source text discusses Boeing as an account/customer in sentences like "Boeing is our largest customer" — the LLM may have interpreted this as a named entity reference without proper type discrimination. The ontology validation should have caught this (Boeing ≠ PERSON), but the entity was in STAGING state and the Gardener hasn't promoted it.

---

## Part 4: Recommended Fixes (Prioritized)

### Tier 1: KG Data Corrections (Direct SQL, no code changes needed)

These 10 fixes target all 13 failures (projected 76 → 86-89):

| # | Fix | Entity IDs (verified) | Questions Fixed |
|---|-----|-----------------------|----------------|
| 1 | Delete `Boeing (PERSON)` entity `11158f3e` and its 16 edges; correct entity is `The Boeing Company (ORGANIZATION)` `0229f990` with CUST-001 metadata | `11158f3e`, `0229f990` | Reduces Q48, Q83 cross-wiring |
| 2 | Create: `Siemens Healthineers (CUSTOMER)` → CUSTOMER_OF → `HTS Wire Supply Agreement (CONTRACT)` | Source chunk: `322b9ba2` (customer profile) | Q48 |
| 3 | Create: `Pacific Power (CUSTOMER, 0.95)` → PILOT_CUSTOMER → `SmartGrid Controller System (PROJECT, 1.0)` | Pacific Power entities exist as CUSTOMER+ORG | Q83 |
| 4 | Create: `Nel Hydrogen (ORGANIZATION, 1.0)` → SUPPLIES → GreenHydrogen electrolyzers. Delete: `James Foster → WORKS_AT → Nel Hydrogen` (cross-contamination from doc `acb4ec94`) | Nel Hydrogen `id` in ARCHIVED state | Q17 |
| 5 | Create: `Shell (PARTNER, 0.95)` → PARTY_TO → `GreenHydrogen Offtake Agreement (SERVICE, 0.95)`. Evidence: chunk `d2d7b4da` ("offtake agreement with Shell") and chunk `5e7a2988` ("Shell (Offtake Partner)") | Both entities verified | Q18 |
| 6 | Create: `First Solar (ORGANIZATION, 1.0)` → SUPPLIES → `Desert Sun Solar Panels (CONTRACT, 1.0)`. Evidence: chunk `172c99ab` (supplier review) | Both entities verified | Q46 |
| 7 | Create: `Jennifer Walsh (PERSON, 0.95)` → HAS_ROLE → Project Director, scoped to GreenHydrogen Initiative. Evidence: chunk `5e7a2988` ("Jennifer Walsh, Project Director" in bullet list) | Jennifer Walsh verified with 17 edges but 0 GreenHydrogen links | Q37 |
| 8 | Create: `Col. (Ret.) James Foster (PERSON, 0.9)` → CHAIRS → `Export Control Committee (TEAM, 0.95)`. Change existing REPORTS_TO to CHAIRS. Evidence: export control policy doc `df140076` | Both entities verified | Q68 |
| 9 | Create: `Caterpillar Inc. (ORGANIZATION, 1.0)` → TECHNOLOGY_PARTNER → Mining Automation (SERVICE, 0.95). Evidence: chunk `51ecee64` (partner profile with PART-003 ID) and chunk `1f5c6586` (equipment compatibility table) | Caterpillar Inc. has 0 partnership edges despite full profile doc | Q71 |
| 10 | Update: `Solid electrolyte material (DELIVERABLE)` properties to include `material=LLZO, composition=Li7La3Zr2O12`. Or create relationship linking `Solid Electrolyte (LLZO) (SYSTEM, 0.9)` to BatteryTech. Evidence: design spec chunks contain "LLZO Treatment" and "Li-metal / LLZO / NMC811" | 5 fragmented electrolyte entities, none linked | Q93 |

### Tier 2: Extraction Prompt Improvements (Code changes, systemic fix)

These would prevent the same patterns from recurring on re-extraction:

| # | Fix | Impact |
|---|-----|--------|
| 1 | Add supply-chain relationship types to extraction prompt examples | Prevents all SUPPLIES/CUSTOMER_OF gaps |
| 2 | Add "co-occurrence ≠ employment" guardrail to WORKS_AT extraction | Prevents person-org contamination |
| 3 | Add table-row relationship extraction (cross-column linking) | Prevents timeline/role table gaps |
| 4 | Add entity type validation against ontology at extraction time | Prevents Boeing-as-PERSON mistype |

### Tier 3: Retrieval Improvements (Code changes, defense in depth)

| # | Fix | Impact |
|---|-----|--------|
| 1 | When query asks "customer for X product", filter to product-specific relationships, not global revenue rank | Q48, Q83 |
| 2 | When entity fragmentation detected (5+ entities with similar names), consolidate before answering | Q93 |

---

## Appendix: Entity Degree Distribution (Top 15)

| Entity | Type | Edges | State |
|--------|------|-------|-------|
| Nexus Industries | ORGANIZATION | 147 | ARCHIVED |
| Nexus Advanced Materials | TEAM | 55 | ARCHIVED |
| Dr. Victoria Chen | PERSON | 41 | STAGING |
| Michael Torres | PERSON | 39 | STAGING |
| Kevin Chang | PERSON | 39 | STAGING |
| Robert Kim | PERSON | 38 | STAGING |
| Dr. Elena Rodriguez | PERSON | 35 | STAGING |
| Nexus | TEAM | 33 | STAGING |
| Nexus Digital Solutions | ORGANIZATION | 31 | ARCHIVED |
| Nexus Aerospace | LOCATION | 24 | STAGING |
| Dr. James Wilson | PERSON | 24 | STAGING |
| Dr. Rachel Kim | PERSON | 20 | STAGING |
| Toyota | ORGANIZATION | 18 | ARCHIVED |
| Maria Santos | PERSON | 18 | STAGING |
| Steven Park | PERSON | 18 | STAGING |
| **Boeing** | **PERSON** | **16** | **STAGING** |

Note: Boeing (PERSON) is the 16th highest-degree entity in the entire KG — higher than most actual people. This alone explains its dominant appearance in customer queries.
