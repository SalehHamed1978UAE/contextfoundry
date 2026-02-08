# Extraction Validation: 5-Document Slice Selection

**Date**: 2026-02-08
**Phase**: 1.1 - Document Selection for Extraction Validation
**Authority**: Context Foundry Agent Directive v2
**Source Directory**: `/Users/salehyahyahamed/Desktop/All docs/slice docs/`

---

## Selection Criteria

Per the Agent Directive, the 5-document slice must test:
1. Supply-chain relationships (customer/supplier/partner)
2. Co-occurrence guardrail (companies mentioned together ≠ relationship)
3. Well-known entity names (test for entity confusion)
4. Bidirectional relationships (A supplies to B, B is customer of A)
5. Authority levels and relationship validation

---

## Selected Documents

### Document 1: Boeing Customer Profile
**File**: `01_boeing_customer_profile.md`
**Purpose**: Customer relationship validation

**Key Relationships to Extract**:
- Boeing IS_CUSTOMER_OF Nexus Industries
- Boeing PURCHASES_FROM Nexus Aerospace
- Boeing PURCHASES_FROM Nexus Advanced Materials
- Revenue: $730M (FY2025)

**Key People**:
- Kelly Ortberg (CEO, Boeing)
- Brian West (CFO, Boeing)
- Ted Colbert (President, Defense, Boeing)
- Sarah Thompson (VP Supplier Management, Boeing)
- Jennifer Morrison (Account Manager, Nexus)
- Michael Torres (Division President, Nexus)

**Test Cases**:
- ✅ Extraction should create `Boeing CUSTOMER_OF Nexus`
- ❌ Should NOT create reverse `Nexus SUPPLIER_OF Boeing` unless explicitly stated
- ✅ Boeing contacts (Sarah Thompson, Kelly Ortberg) should be linked to Boeing, not Nexus
- ✅ Nexus contacts (Jennifer Morrison, Michael Torres) should be linked to Nexus
- ✅ Revenue $730M should be attributed correctly

---

### Document 2: Lockheed Martin Customer Profile
**File**: `14_lockheed_martin_customer.md`
**Purpose**: Another customer relationship + entity confusion test

**Key Relationships to Extract**:
- Lockheed Martin IS_CUSTOMER_OF Nexus Industries
- Lockheed Martin PURCHASES_FROM Nexus Aerospace
- Lockheed Martin PURCHASES_FROM Nexus Advanced Materials
- Revenue: $180M (FY2025)

**Key People**:
- James Taiclet (CEO, Lockheed Martin)
- Sarah Chen (VP Supplier Management, Lockheed Martin)
- Col. (Ret.) James Foster (Account Manager, Nexus)

**CRITICAL TEST - Name Confusion**:
- **James Foster** appears in TWO documents:
  - Document 2 (this doc): Col. James Foster works for Nexus (Account Manager)
  - Document 5 (Supplier Review): James Foster works for Nel Hydrogen (Account Director)
- These are **DIFFERENT PEOPLE** with the same name
- Extraction must NOT merge them into one entity
- Must use context (company affiliation) to distinguish

**Test Cases**:
- ✅ Create two separate PERSON entities for James Foster
- ✅ Col. James Foster WORKS_FOR Nexus Industries
- ✅ James Foster (Nel) WORKS_FOR Nel Hydrogen
- ❌ Should NOT merge these into one person

---

### Document 3: Nel Hydrogen Supplier Profile
**File**: `09_nel_hydrogen_supplier.md`
**Purpose**: Supplier relationship (OPPOSITE direction from customers)

**Key Relationships to Extract**:
- Nel Hydrogen IS_SUPPLIER_TO Nexus Industries
- Nel Hydrogen SUPPLIES Electrolyzers TO Nexus Energy Systems
- Nexus PROCURES_FROM Nel Hydrogen
- Spend: $95M (FY2025-2027)

**Key People**:
- Hakon Volldal (CEO, Nel)
- Filip Smeets (President, Nel Electrolyser)
- Anders Berg (Project Manager, Nel)
- Michelle Thompson (Commodity Manager, Nexus)

**Test Cases**:
- ✅ **Bidirectional validation**: Nel supplies TO Nexus (opposite of Boeing/Lockheed)
- ✅ Entity: Nel ASA vs Nel Hydrogen (name variations - should be same entity)
- ✅ Nel employees linked to Nel, not Nexus
- ❌ Payment terms should NOT create relationships

---

### Document 4: First Solar Supplier Profile
**File**: `10_first_solar_supplier.md`
**Purpose**: Another supplier relationship

**Key Relationships to Extract**:
- First Solar IS_SUPPLIER_TO Nexus Industries
- First Solar SUPPLIES Solar Panels TO Nexus Energy Systems
- Spend: $148M (FY2025)

**Key People**:
- Mark Widmar (CEO, First Solar)
- Maria Garcia (VP Sales, First Solar) - **NOTE: Also appears in Doc 5**
- Jason Dymbort (VP Sales, First Solar)
- Timothy Reynolds (Procurement Lead, Nexus)

**Test Cases**:
- ✅ First Solar SUPPLIER_TO Nexus
- ✅ First Solar employees linked to First Solar
- ✅ Maria Garcia works for First Solar (important for Doc 5 test)

---

### Document 5: Supplier Performance Review
**File**: `12_supplier_performance_review.md`
**Purpose**: CO-OCCURRENCE GUARDRAIL STRESS TEST

**Companies Mentioned Together**:
- Nel Hydrogen (supplier to Nexus)
- First Solar (supplier to Nexus)
- Honeywell (supplier to Nexus)
- General Atomics (supplier to Nexus)
- Boeing (supplier to Nexus in this context!)

**People Mentioned as Guests**:
- James Foster, Account Director, Nel Hydrogen
- Maria Garcia, VP Sales, First Solar
- Thomas Mitchell, Program Manager, Honeywell

**CRITICAL TESTS**:

1. **Co-occurrence Guardrail**:
   - ❌ Should NOT create: `Nel Hydrogen PARTNER_OF First Solar`
   - ❌ Should NOT create: `First Solar WORKS_WITH Honeywell`
   - ❌ Should NOT create: `General Atomics PARTNER_OF Boeing`
   - ✅ Should create: `Nel Hydrogen SUPPLIER_TO Nexus`
   - ✅ Should create: `First Solar SUPPLIER_TO Nexus`
   - ✅ Should create: `Honeywell SUPPLIER_TO Nexus`
   - ✅ Should create: `General Atomics SUPPLIER_TO Nexus`

2. **Person Attribution**:
   - ✅ James Foster (Nel) attending meeting as guest - still works for Nel
   - ✅ Maria Garcia (First Solar) attending meeting as guest - still works for First Solar
   - ❌ Should NOT create: James Foster WORKS_FOR Nexus
   - ❌ Should NOT create: Maria Garcia WORKS_FOR Nexus

3. **Boeing Role Reversal**:
   - In Document 1: Boeing is a CUSTOMER of Nexus
   - In Document 5 (Section 5): Boeing is a SUPPLIER to Nexus (composite structures)
   - ✅ Both relationships are correct - bidirectional business relationship
   - ✅ Should create: `Boeing CUSTOMER_OF Nexus` (from Doc 1)
   - ✅ Should create: `Boeing SUPPLIER_TO Nexus` (from Doc 5)

4. **Name Collision - James Foster**:
   - Document 2: Col. James Foster, Account Manager at Nexus (manages Lockheed Martin account)
   - Document 5: James Foster, Account Director at Nel Hydrogen (guest at supplier review)
   - ✅ Must create TWO separate PERSON entities
   - ✅ Use context clues: "Guest" + "Nel Hydrogen" vs "Nexus" + "Account Manager"

**Rationale**: Companies mentioned in same document are NOT automatically related to each other. They are only related through Nexus as common customer.

---

## Expected Extraction Outcomes

### Entities to Extract (Minimum)

**Organizations**:
- Nexus Industries (anchor)
- Boeing / The Boeing Company
- Lockheed Martin Corporation
- Nel Hydrogen / Nel ASA
- First Solar, Inc.
- Honeywell
- General Atomics

**People**:
- Dr. Victoria Chen (Nexus CEO)
- Robert Kim (Nexus CFO)
- Kelly Ortberg (Boeing CEO)
- Sarah Thompson (Boeing VP Supplier Management)
- James Taiclet (Lockheed Martin CEO)
- Sarah Chen (Lockheed Martin VP Supplier Management)
- **Col. James Foster (Nexus Account Manager)** - Person 1
- **James Foster (Nel Hydrogen Account Director)** - Person 2 (DIFFERENT PERSON!)
- Mark Widmar (First Solar CEO)
- Maria Garcia (First Solar VP Sales)
- Hakon Volldal (Nel CEO)

### Relationships to Extract

**Customer Relationships** (Document 1, 2):
- Boeing IS_CUSTOMER_OF Nexus Industries
- Lockheed Martin IS_CUSTOMER_OF Nexus Industries

**Supplier Relationships** (Document 3, 4, 5):
- Nel Hydrogen IS_SUPPLIER_TO Nexus Industries
- First Solar IS_SUPPLIER_TO Nexus Industries
- Honeywell IS_SUPPLIER_TO Nexus Industries (from Doc 5)
- General Atomics IS_SUPPLIER_TO Nexus Industries (from Doc 5)
- Boeing IS_SUPPLIER_TO Nexus Industries (from Doc 5, Section 5)

**Employment Relationships**:
- Kelly Ortberg WORKS_FOR Boeing (CEO)
- Sarah Thompson WORKS_FOR Boeing (VP)
- James Taiclet WORKS_FOR Lockheed Martin (CEO)
- Col. James Foster WORKS_FOR Nexus Industries (Account Manager)
- James Foster (Nel) WORKS_FOR Nel Hydrogen (Account Director)
- Maria Garcia WORKS_FOR First Solar (VP Sales)
- Mark Widmar WORKS_FOR First Solar (CEO)

### Relationships to NOT Extract (Validation Failures)

❌ **From Document 5** (Co-occurrence):
- Nel Hydrogen PARTNER_OF First Solar
- First Solar WORKS_WITH Honeywell
- Honeywell COLLABORATES_WITH General Atomics
- General Atomics PARTNER_OF Boeing
- Any relationship between suppliers (they're just mentioned together)

❌ **Entity Confusion**:
- Sarah Thompson WORKS_FOR Nexus (she works for Boeing!)
- Sarah Chen WORKS_FOR Nexus (she works for Lockheed!)
- James Foster (Nel) merged with Col. James Foster (Nexus)

❌ **Direction Errors**:
- Nexus CUSTOMER_OF Boeing (wrong direction - Boeing is customer)
- Nexus SUPPLIER_TO Nel Hydrogen (wrong direction - Nel supplies to Nexus)

---

## Validation Criteria

### Phase 1.2 Success Metrics

After re-extraction with improved prompts:

1. **Customer Relationships**: 2/2 correct (Boeing, Lockheed Martin)
2. **Supplier Relationships**: 5/5 correct (Nel, First Solar, Honeywell, General Atomics, Boeing)
3. **Bidirectional Relationship**: Boeing is both customer AND supplier (2 relationships)
4. **Entity Deduplication**: James Foster appears as 2 separate people
5. **Co-occurrence Guardrail**: 0 false relationships between suppliers
6. **Person-Organization Attribution**: 100% correct (no Boeing/Lockheed employees → Nexus)
7. **Authority Level**: All extracted facts must cite source document

### Red Flags (Immediate Failure)

If extraction produces ANY of these, it fails:
- Nel Hydrogen PARTNER_OF First Solar
- Sarah Thompson WORKS_FOR Nexus Industries
- Sarah Chen WORKS_FOR Nexus Industries
- James Foster (Nel) merged with Col. James Foster (Nexus) as one person
- Boeing CUSTOMER_OF Nexus but missing Boeing SUPPLIER_TO Nexus (both should exist)
- Honeywell PARTNER_OF General Atomics

---

## Phase 1.3 Verification Process

Once extraction completes:

### 1. Query relationships
```sql
SELECT source_entity_name, relationship_type, target_entity_name, metadata
FROM relationships
WHERE tenant_id = '4668fc6d-c401-46d2-9797-4c8785f4d6ce'
AND source_entity_name IN (
  'Boeing', 'The Boeing Company',
  'Lockheed Martin', 'Lockheed Martin Corporation',
  'Nel Hydrogen', 'Nel ASA',
  'First Solar',
  'Honeywell',
  'General Atomics'
)
ORDER BY source_entity_name, relationship_type;
```

### 2. Check for false positives (Co-occurrence violations)
```sql
SELECT source_entity_name, relationship_type, target_entity_name
FROM relationships
WHERE tenant_id = '4668fc6d-c401-46d2-9797-4c8785f4d6ce'
AND (
  (source_entity_name IN ('Nel Hydrogen', 'Nel ASA') AND target_entity_name LIKE '%First Solar%')
  OR (source_entity_name LIKE '%First Solar%' AND target_entity_name IN ('Honeywell'))
  OR (source_entity_name IN ('General Atomics') AND target_entity_name LIKE '%Boeing%')
  OR (source_entity_name IN ('Honeywell') AND target_entity_name IN ('General Atomics'))
);
```
Expected: **0 rows** (any result = failure)

### 3. Verify James Foster name collision handling
```sql
SELECT id, name, entity_type, metadata
FROM entities
WHERE tenant_id = '4668fc6d-c401-46d2-9797-4c8785f4d6ce'
AND name ILIKE '%James Foster%';
```
Expected: **2 separate entities** (one for Nexus, one for Nel)

### 4. Check person-organization attribution
```sql
SELECT e.name as person_name, r.relationship_type, r.target_entity_name as company
FROM entities e
JOIN relationships r ON e.id = r.source_id
WHERE e.tenant_id = '4668fc6d-c401-46d2-9797-4c8785f4d6ce'
AND e.entity_type = 'PERSON'
AND e.name IN ('Sarah Thompson', 'Sarah Chen', 'Maria Garcia')
AND r.relationship_type = 'WORKS_FOR';
```
Expected:
- Sarah Thompson WORKS_FOR Boeing (NOT Nexus)
- Sarah Chen WORKS_FOR Lockheed Martin (NOT Nexus)
- Maria Garcia WORKS_FOR First Solar (NOT Nexus)

### 5. Verify bidirectional Boeing relationship
```sql
SELECT relationship_type, target_entity_name
FROM relationships
WHERE tenant_id = '4668fc6d-c401-46d2-9797-4c8785f4d6ce'
AND source_entity_name ILIKE '%Boeing%'
AND target_entity_name ILIKE '%Nexus%';
```
Expected: At least 1 relationship showing Boeing as customer OR supplier

---

## Critical Test: Name Collision (James Foster)

This is the **hallucination test** that directly addresses the tree retrieval postmortem finding where it returned "Dr. Sarah Thompson" as CEO.

**The Problem**:
- Document 2: Col. (Ret.) James Foster - Account Manager at Nexus Industries
- Document 5: James Foster - Account Director at Nel Hydrogen

**Why This Matters**:
If extraction merges these into one person, it creates entity confusion that leads to hallucinations like:
- Q: "Who is the Account Manager for Lockheed Martin at Nexus?"
- Wrong Answer: "James Foster from Nel Hydrogen"

**How to Distinguish**:
1. **Context clues in Document 2**:
   - Listed in "Key Contacts" for Nexus side
   - Title: "Account Manager"
   - Executive Sponsor for Lockheed account

2. **Context clues in Document 5**:
   - Listed under "External (by invitation for their review segment)"
   - Explicitly: "Nel Hydrogen (James Foster, Account Director)"
   - He's a **guest** at the meeting, not a Nexus employee

**Correct Extraction**:
- Entity 1: `PERSON: Col. James Foster` with metadata: `{company: "Nexus Industries", title: "Account Manager"}`
- Entity 2: `PERSON: James Foster` with metadata: `{company: "Nel Hydrogen", title: "Account Director"}`

**Verification Query**:
```sql
SELECT e.name, r.target_entity_name as employer, e.metadata->>'title' as title
FROM entities e
JOIN relationships r ON e.id = r.source_id
WHERE e.name ILIKE '%James Foster%'
AND r.relationship_type = 'WORKS_FOR';
```
Expected result:
| name | employer | title |
|------|----------|-------|
| Col. James Foster | Nexus Industries | Account Manager |
| James Foster | Nel Hydrogen | Account Director |

---

## Next Steps

1. **Clear existing extraction** for tenant `4668fc6d-c401-46d2-9797-4c8785f4d6ce`
2. **Extract ONLY these 5 documents** from `/Users/salehyahyahamed/Desktop/All docs/slice docs/`
3. **Run validation queries** (Phase 1.3)
4. **Document results** in EXTRACTION_VALIDATION_RESULTS.md
5. **If pass**: Proceed to Phase 2 (Promotion-time verification)
6. **If fail**: Iterate on extraction prompts and repeat

---

## Document Paths

```
/Users/salehyahyahamed/Desktop/All docs/slice docs/01_boeing_customer_profile.md
/Users/salehyahyahamed/Desktop/All docs/slice docs/14_lockheed_martin_customer.md
/Users/salehyahyahamed/Desktop/All docs/slice docs/09_nel_hydrogen_supplier.md
/Users/salehyahyahamed/Desktop/All docs/slice docs/10_first_solar_supplier.md
/Users/salehyahyahamed/Desktop/All docs/slice docs/12_supplier_performance_review.md
```

---

## Why This Slice Addresses Tree Retrieval Failures

The tree retrieval postmortem identified these failure patterns:

1. **Hallucinating wrong people** (Q1: "Dr. Sarah Thompson" as CEO)
   - **Our test**: Sarah Thompson (Boeing), Sarah Chen (Lockheed) must NOT be linked to Nexus
   - **Our test**: James Foster name collision - must create 2 separate people

2. **Missing aggregates** (Q7: Employee count)
   - **Our test**: Revenue/spend numbers must be attributed correctly

3. **Entity confusion** (Q3: Wrong President)
   - **Our test**: Multiple "Sarah" names, two "James Foster" people
   - **Our test**: Boeing appears as both customer AND supplier

4. **Co-occurrence errors** (assuming companies mentioned together are partners)
   - **Our test**: Document 5 has 5 suppliers mentioned together
   - Must NOT create relationships between them

---

## Authority

This selection follows the Context Foundry Agent Directive v2:
- Tests supply-chain relationships (customer/supplier/bidirectional)
- Tests co-occurrence guardrail (Document 5 has multiple companies)
- Tests entity deduplication (James Foster name collision)
- Tests bidirectional relationships (Boeing as customer AND supplier)
- Provides verifiable ground truth for validation
