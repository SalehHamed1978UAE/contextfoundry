# Context Foundry Ontology Architecture Standard

**Version:** 1.0  
**Date:** 2025-12-06  
**Status:** MANDATORY - All domain ontologies must conform before loading

---

## 1. Problem Statement

Initial ontology drafts from multiple LLMs revealed architectural inconsistencies that would cause systemic problems if built upon:

| Problem | Impact |
|---------|--------|
| Flat hierarchies (all types inherit directly from Layer 1) | Cannot query across related types ("show all facilities") |
| Asset-centric relationships | Loses temporal context (when, how long, what triggered) |
| Duplicate entity definitions across domains | Same concept (Shipment, Facility) defined differently, breaks cross-company queries |
| Inconsistent naming | `Product` vs `Good` vs `FinishedProduct` for same concept |

**If we build on inconsistent foundations, refactoring later requires re-extraction of every document and migration of every entity.**

---

## 2. Architectural Principles

### 2.1 Hierarchical Depth

**Rule:** Layer 2 domain templates MUST include intermediate abstract types between Layer 1 and concrete types.

**Minimum hierarchy depth:** 3 levels (Layer 1 → Abstract → Concrete)

**Bad (flat):**
```
Asset (L1)
  ├── PowerPlant (L2)
  ├── Port (L2)
  ├── Airport (L2)
  └── RailwayLine (L2)
```

**Good (hierarchical):**
```
Asset (L1)
  ├── Facility (L2 abstract)
  │     ├── ProductionFacility (L2 abstract)
  │     │     ├── PowerPlant (L2 concrete)
  │     │     └── DesalinationPlant (L2 concrete)
  │     ├── TransportFacility (L2 abstract)
  │     │     ├── Port (L2 concrete)
  │     │     └── Airport (L2 concrete)
  │     └── ProcessingFacility (L2 abstract)
  │           └── WasteProcessingFacility (L2 concrete)
  └── LinearAsset (L2 abstract)
        ├── TransmissionLine (L2 concrete)
        ├── Pipeline (L2 concrete)
        └── RailwayLine (L2 concrete)
```

**Why:** Enables queries like "show me all TransportFacilities with incidents this month" without enumerating every concrete type.

---

### 2.2 Event-Centric Relationships

**Rule:** Operational relationships MUST be modeled through Event entities, not direct Asset-to-Asset links.

**Bad (asset-centric):**
```
Vessel --DOCKS_AT--> Berth
```

**Good (event-centric):**
```
VesselCall (Event)
  --FOR_VESSEL--> Vessel
  --AT_BERTH--> Berth
  --AT_PORT--> Port
  
Properties on VesselCall: eta, ata, etd, atd, cargo_type, cargo_volume
```

**Why:** 
- Captures temporal context (when, how long)
- Enables time-series analysis
- Allows multiple calls at same berth
- Supports provenance (which document mentioned this call)

**Apply event-centric modeling for:**
- Maintenance activities → MaintenanceEvent
- Inspections → InspectionEvent
- Shipments → ShipmentEvent
- Production runs → ProductionEvent
- Outages → OutageEvent
- Transactions → TransactionEvent

---

### 2.3 Canonical Shared Types

**Rule:** Types that appear in multiple domains MUST use the canonical definition from the Core Ontology extension.

The following types are defined ONCE and shared across all domain templates:

#### 2.3.1 Canonical Facility Hierarchy

```sql
-- Defined in: shared_ontology.sql
-- UUID prefix: 20000000-0000-xxxx (shared namespace)

Facility (20000000-0000-0001-0000-000000000001)
  parent: Asset (L1)
  description: "Physical location where operations occur"
  
ProductionFacility (20000000-0000-0001-0000-000000000002)
  parent: Facility
  description: "Facility that produces goods, energy, or services"
  
ProcessingFacility (20000000-0000-0001-0000-000000000003)
  parent: Facility
  description: "Facility that transforms inputs into outputs"
  
StorageFacility (20000000-0000-0001-0000-000000000004)
  parent: Facility
  description: "Facility for storing goods, materials, or equipment"
  
TransportFacility (20000000-0000-0001-0000-000000000005)
  parent: Facility
  description: "Facility for movement of goods or people"
```

#### 2.3.2 Canonical Good Hierarchy

```sql
Good (20000000-0000-0002-0000-000000000001)
  parent: Asset (L1)
  description: "Tangible item that can be produced, traded, or consumed"

Commodity (20000000-0000-0002-0000-000000000002)
  parent: Good
  description: "Raw or semi-processed tradeable material"

FinishedProduct (20000000-0000-0002-0000-000000000003)
  parent: Good
  description: "Manufactured item ready for sale or use"

UtilityProduct (20000000-0000-0002-0000-000000000004)
  parent: Good
  description: "Electricity, water, gas, or similar utility output"
```

#### 2.3.3 Canonical Shipment

```sql
Shipment (20000000-0000-0003-0000-000000000001)
  parent: Event (L0)
  description: "Movement of goods from origin to destination"
  properties:
    - origin_location
    - destination_location
    - departure_time
    - arrival_time
    - carrier
    - tracking_id
    - status
```

#### 2.3.4 Canonical Agent Hierarchy

```sql
OperationalTeam (20000000-0000-0004-0000-000000000001)
  parent: Organization (L1)
  description: "Team responsible for operational activities"

MaintenanceTeam (20000000-0000-0004-0000-000000000002)
  parent: OperationalTeam
  description: "Team responsible for maintenance activities"

OperationsTeam (20000000-0000-0004-0000-000000000003)
  parent: OperationalTeam
  description: "Team responsible for day-to-day operations"
```

**Domain templates extend these, they do not redefine them.**

---

### 2.4 Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Entity types | PascalCase, singular noun | `PowerPlant`, `VesselCall` |
| Relationship types | UPPER_SNAKE_CASE, verb phrase | `OPERATES_AT`, `TRIGGERED_BY` |
| Properties | snake_case | `capacity_mw`, `departure_time` |
| Abstract types | Suffix with domain or role | `ProductionFacility`, `LinearAsset` |
| Event types | Suffix with `Event` or action noun | `MaintenanceEvent`, `Inspection` |

---

### 2.5 Relationship Direction Standards

**Rule:** Relationships flow from specific to general, from event to participant, from dependent to dependency.

| Pattern | Direction | Example |
|---------|-----------|---------|
| Event → Participant | Event is source | `MaintenanceEvent --ON_ASSET--> PowerPlant` |
| Child → Parent | Child is source | `Terminal --PART_OF--> Port` |
| Dependent → Dependency | Dependent is source | `Service --DEPENDS_ON--> Database` |
| Actor → Action Target | Actor is source | `MaintenanceTeam --PERFORMS--> MaintenanceEvent` |

---

## 3. Required Ontology Structure

Every domain ontology SQL file MUST include:

### 3.1 Header Comment
```sql
-- =============================================================================
-- Context Foundry: [Domain Name] Domain Template
-- =============================================================================
-- Archetype: [CODE] (ID: [XX])
-- Conforms to: Ontology Architecture Standard v1.0
-- Author: [LLM Name]
-- Date: [YYYY-MM-DD]
-- =============================================================================
```

### 3.2 Shared Type References
```sql
-- =============================================================================
-- SHARED TYPE REFERENCES (from shared_ontology.sql)
-- These types are NOT defined here, only referenced
-- =============================================================================
-- Facility: 20000000-0000-0001-0000-000000000001
-- ProductionFacility: 20000000-0000-0001-0000-000000000002
-- Good: 20000000-0000-0002-0000-000000000001
-- Shipment: 20000000-0000-0003-0000-000000000001
```

### 3.3 Abstract Types Section
```sql
-- =============================================================================
-- ABSTRACT TYPES (intermediate hierarchy)
-- =============================================================================
```

### 3.4 Concrete Types Section
```sql
-- =============================================================================
-- CONCRETE TYPES (extractable entities)
-- =============================================================================
```

### 3.5 Event Types Section
```sql
-- =============================================================================
-- EVENT TYPES (temporal occurrences)
-- =============================================================================
```

### 3.6 Relationship Types Section
```sql
-- =============================================================================
-- RELATIONSHIP TYPES
-- =============================================================================
```

---

## 4. UUID Allocation

### 4.1 Shared Namespace (Cross-Domain)
```
20000000-0000-XXXX-0000-00000000000Y
         ^^^^
         0000 = shared namespace

XXXX ranges:
  0001 = Facility hierarchy
  0002 = Good hierarchy
  0003 = Shipment and logistics
  0004 = Agent hierarchy
  0005 = Document hierarchy
  0006-000F = Reserved for future shared types
```

### 4.2 Domain Namespaces
```
20000000-00XX-0000-0000-00000000000Y
           ^^
           Domain ID

01 = INFRA (Infrastructure)
02 = SUPPLY (Supply Chain)
03 = HEALTH (Healthcare)
04 = MFG (Manufacturing)
05 = AVIATION (Aviation & Mobility)
06 = FINANCE (Financial Services)
07 = CONSTRUCT (Construction)
```

### 4.3 Relationship Namespace
```
30000000-00XX-0000-0000-00000000000Y
           ^^
           Domain ID (same as entity domain)
           
30000000-0000-XXXX = Shared relationships
```

---

## 5. Validation Checklist

Before any ontology is loaded into the database:

### 5.1 Structural Validation
- [ ] Hierarchy depth ≥ 3 for all concrete types
- [ ] Abstract intermediate types defined
- [ ] No concrete type inherits directly from Layer 1 (except via shared types)

### 5.2 Event-Centric Validation
- [ ] Operational activities modeled as Events
- [ ] Events have temporal properties (start_time, end_time or timestamp)
- [ ] Asset-to-Asset relationships are structural only (PART_OF, CONTAINS)

### 5.3 Shared Type Validation
- [ ] Uses canonical Facility hierarchy (not custom Facility)
- [ ] Uses canonical Good hierarchy (not custom Product)
- [ ] Uses canonical Shipment (not domain-specific shipment)
- [ ] References shared UUIDs correctly

### 5.4 Consistency Validation
- [ ] No orphan entity types
- [ ] All UUIDs unique within file
- [ ] No UUID collision with shared namespace
- [ ] Valid JSON schemas
- [ ] Executable SQL

### 5.5 Cross-Domain Validation
- [ ] No duplicate type names across domains
- [ ] Shared types not redefined
- [ ] Cross-domain relationships use shared types as junction points

---

## 6. Refactoring Requirements

### 6.1 INFRA Ontology Refactoring

**Current state:** 29 entity types, flat hierarchy, asset-centric

**Required changes:**

1. **Add abstract types:**
   - `InfrastructureFacility` (parent: ProductionFacility) 
   - `UtilityPlant` (parent: InfrastructureFacility) → parent for PowerPlant, DesalinationPlant
   - `TransportHub` (parent: TransportFacility) → parent for Port, Airport, Station
   - `LinearAsset` (parent: Asset) → parent for TransmissionLine, Pipeline, RailwayLine

2. **Make event-centric:**
   - Keep `VesselCall` as event, add relationships to Vessel, Berth, Port
   - Keep `MaintenanceEvent`, add relationships to Asset, Team
   - Keep `Outage`, add relationships to Asset, Cause
   - Keep `Inspection`, add relationships to Asset, Inspector, Findings

3. **Use shared types:**
   - Replace any `Product` with `UtilityProduct` from shared
   - Use `Shipment` from shared for cargo movements

### 6.2 MFG Ontology Refactoring

**Current state:** 15 entity types, partially hierarchical

**Required changes:**

1. **Add abstract types:**
   - Use `ProcessingFacility` from shared as parent for ManufacturingPlant
   - Add `QualityFacility` (parent: Facility) for QCLab

2. **Use shared types:**
   - Remove `Shipment`, use shared `Shipment`
   - Make `RawMaterial` inherit from `Commodity` (shared)
   - Make `FinishedProduct` inherit from shared `FinishedProduct`

3. **Role-based agents:**
   - Change `Operator` from Person to OperationalTeam
   - Change `QCInspector` from Person to OperationalTeam
   - Link Person to Team via `MEMBER_OF` relationship

### 6.3 SUPPLY Ontology Refactoring

**Current state:** Best structured, but has JSON syntax errors

**Required changes:**

1. **Fix JSON syntax errors** (per validation report)
2. **Export shared types** to shared_ontology.sql
3. **Verify Port** inherits from TransportFacility (shared)

---

## 7. Implementation Sequence

1. **Create shared_ontology.sql** with canonical shared types
2. **Load shared_ontology.sql** into database first
3. **Refactor each domain ontology** to conform to this standard
4. **Cross-validate** all ontologies for consistency
5. **Load domain ontologies** in any order (they depend only on shared)

---

## 8. Approval

This standard must be acknowledged by all LLMs before ontology refactoring begins.

| LLM | Domain(s) | Acknowledged |
|-----|-----------|--------------|
| Claude | INFRA | Pending |
| Manus | SUPPLY, CONSTRUCT | Pending |
| ChatGPT | HEALTH, AVIATION | Pending |
| Perplexity | MFG, FINANCE | Pending |
| Gemini | CONSTRUCT | Pending |

---

**End of Standard**
