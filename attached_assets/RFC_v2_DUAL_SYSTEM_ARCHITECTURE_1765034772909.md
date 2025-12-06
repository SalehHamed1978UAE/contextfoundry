# RFC v2: Dual-System Cognitive Architecture for Knowledge Graph Governance

**Status:** REVISED - Critical Gaps Addressed  
**Version:** 2.0  
**Author:** QData / ADQ  
**Date:** 2025-12-06  
**Previous Version:** RFC v1.0 (2025-12-06)  
**Reviewers:** ChatGPT, Gemini, Perplexity, Manus  
**Decision:** Build custom (PostgreSQL), adopt SHACL-inspired validation syntax

---

## Revision Summary

This revision addresses all critical gaps identified by four independent reviewers:

| Gap | Section | Resolution |
|-----|---------|------------|
| Bootstrap paradox | §3 | Immutable Layer 0 meta-ontology defined |
| Confidence calibration | §5 | Compositional formula + calibration protocol |
| Orphan threshold arbitrary | §6 | Domain-adaptive formula with sensitivity bounds |
| Deprecation handling | §7 | Three-action model with migration procedures |
| Schema versioning | §8 | Bi-temporal model with query translation |
| Agent coordination | §9 | Message bus protocol with orchestration order |
| Human-in-the-loop | §10 | Decision matrix with escalation paths |
| Storage strategy | §11 | Single PostgreSQL with logical separation |

---

## 1. Architecture Overview

### 1.1 Two Subsystems

```
┌─────────────────────────────────────────────────────────────────┐
│                     ONTOLOGY FOUNDRY                            │
│                   (Schema Governance)                           │
│                                                                 │
│  Governs: What TYPES of things can exist                        │
│  Cadence: Weekly/Monthly                                        │
│  Confidence: 0.90+ (calibrated, see §5)                         │
│  Storage: ontology_* tables                                     │
│                                                                 │
│  Agents: TypeValidator, CollisionDetector, HierarchyEnforcer,   │
│          NamespaceGuard, SchemaPromoter, DeprecationAgent       │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ CONSTRAINS (types must be ACTIVE)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     CONTEXT FOUNDRY                             │
│                   (Knowledge Governance)                        │
│                                                                 │
│  Governs: What SPECIFIC things we know                          │
│  Cadence: Continuous (per document)                             │
│  Confidence: 0.70+ (calibrated, see §5)                         │
│  Storage: entity_*, relationship_* tables                       │
│                                                                 │
│  Agents: Extractor, Gardener, Resolver, QueryAgent,             │
│          OrphanDetector                                         │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          │ SURFACES (orphan patterns)
                          ▼
┌─────────────────────────────────────────────────────────────────┐
│                     FEEDBACK CHANNEL                            │
│  Structure: OrphanPattern entity (see §6.2)                     │
│  Threshold: Domain-adaptive (see §6.1)                          │
│  Latency SLA: 48 hours to surface, 7 days to decision           │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 Design Principles

1. **Schema stability over instance flexibility** - Types change rarely; instances change continuously
2. **One-way constraint** - Context cannot create types; Ontology constrains extraction
3. **Feedback with friction** - Patterns must prove value before becoming types
4. **Declarative validation** - Rules as data, not code (SHACL-inspired)
5. **Single database** - PostgreSQL for both systems, logical separation

---

## 2. Constraint Mechanism

### 2.1 How Ontology Constrains Context

```python
# Extraction pipeline constraint
def extract_entities(document, ontology_version):
    active_types = get_active_types(ontology_version)
    
    for candidate in llm_extract(document):
        if candidate.type_id in active_types:
            yield Entity(candidate, status='STAGING')
        else:
            yield OrphanPattern(candidate)  # Feedback channel
```

**Rules:**
- Context Foundry can ONLY create entities of types with status = `ACTIVE`
- Extraction attempts for non-ACTIVE types are routed to OrphanDetector
- Relationship extraction is constrained by valid relationship types
- Property values are validated against type's JSON schema

### 2.2 What Cannot Be Extracted Without Active Type

| Scenario | Behavior |
|----------|----------|
| Type is PROPOSED | Extraction blocked, pattern logged |
| Type is APPROVED (not yet ACTIVE) | Extraction blocked, pattern logged |
| Type is DEPRECATED | Extraction blocked, existing instances preserved |
| Type doesn't exist | Extraction blocked, pattern logged as orphan |

---

## 3. Layer 0: Immutable Meta-Ontology

**This section resolves the bootstrap paradox.**

### 3.1 Definition

Layer 0 is a minimal, immutable set of types that define what the system can reason about. It is:
- **Hand-coded** in SQL migration
- **Never modified** through Ontology Foundry governance
- **Versioned separately** via database migrations only
- **The axioms** upon which all other types depend

### 3.2 Layer 0 Schema

```sql
-- =============================================================================
-- LAYER 0: META-ONTOLOGY (IMMUTABLE)
-- =============================================================================
-- These types define the governance substrate itself.
-- DO NOT MODIFY through Ontology Foundry. Migration-only changes.
-- =============================================================================

CREATE TABLE meta_ontology (
    id UUID PRIMARY KEY,
    meta_type VARCHAR(50) NOT NULL,
    meta_name VARCHAR(100) NOT NULL,
    definition JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    -- No updated_at - these are immutable
    CONSTRAINT immutable_check CHECK (meta_type IN (
        'META_TYPE',
        'META_RELATION', 
        'META_RULE',
        'META_VERSION',
        'META_LIFECYCLE'
    ))
);

-- Seed Layer 0 (run once, never again)
INSERT INTO meta_ontology (id, meta_type, meta_name, definition) VALUES

-- What is a Type?
('00000000-0000-0000-0000-000000000001', 'META_TYPE', 'OntologyType',
 '{
    "description": "Definition of an entity type in the ontology",
    "required_properties": ["type_name", "layer", "parent_type_id", "properties_schema"],
    "lifecycle_states": ["PROPOSED", "VALIDATING", "CONTESTED", "APPROVED", "ACTIVE", "DEPRECATED"],
    "governance": "ontology_foundry"
 }'),

-- What is a Relation?
('00000000-0000-0000-0000-000000000002', 'META_RELATION', 'OntologyRelation',
 '{
    "description": "Definition of a relationship type between entity types",
    "required_properties": ["relation_type", "source_type_id", "target_type_id", "cardinality"],
    "lifecycle_states": ["PROPOSED", "APPROVED", "ACTIVE", "DEPRECATED"],
    "governance": "ontology_foundry"
 }'),

-- What is a Rule?
('00000000-0000-0000-0000-000000000003', 'META_RULE', 'ValidationRule',
 '{
    "description": "Constraint rule for validating types or instances",
    "rule_types": ["HIERARCHY", "PROPERTY", "NAMING", "NAMESPACE", "CARDINALITY"],
    "severity_levels": ["ERROR", "WARNING", "INFO"],
    "governance": "ontology_foundry"
 }'),

-- What is a Version?
('00000000-0000-0000-0000-000000000004', 'META_VERSION', 'OntologyVersion',
 '{
    "description": "Versioned snapshot of the ontology at a point in time",
    "versioning": "semantic",
    "format": "major.minor.patch",
    "governance": "ontology_foundry"
 }'),

-- What are Lifecycle States?
('00000000-0000-0000-0000-000000000005', 'META_LIFECYCLE', 'LifecycleState',
 '{
    "description": "Valid states for governed entities",
    "ontology_states": ["PROPOSED", "VALIDATING", "CONTESTED", "APPROVED", "ACTIVE", "DEPRECATED"],
    "context_states": ["STAGING", "CORROBORATED", "TRUSTED", "CONTESTED", "RETRACTED"],
    "governance": "system"
 }');
```

### 3.3 Layer 0 Versioning

Layer 0 changes are **database migrations only**, not governed through the system:

```
migrations/
  001_create_meta_ontology.sql      -- Initial Layer 0
  002_add_meta_constraint.sql       -- Future: add new meta-type
  ...
```

**Change protocol:**
1. Propose change in code review (human)
2. Review impact on existing types (human)
3. Deploy migration in maintenance window
4. No rollback once deployed (breaking change)

---

## 4. Lifecycle States

### 4.1 Ontology Foundry States

```
┌──────────┐     validate      ┌────────────┐
│ PROPOSED │ ─────────────────▶│ VALIDATING │
└──────────┘                   └─────┬──────┘
     │                               │
     │ reject                        │ pass
     ▼                               ▼
┌──────────┐                   ┌──────────┐     human approve    ┌────────┐
│ REJECTED │                   │ APPROVED │ ───────────────────▶ │ ACTIVE │
└──────────┘                   └──────────┘                      └───┬────┘
                                    │                                │
                                    │ collision detected             │ deprecate
                                    ▼                                ▼
                              ┌───────────┐                    ┌────────────┐
                              │ CONTESTED │                    │ DEPRECATED │
                              └───────────┘                    └────────────┘
```

| State | Meaning | Who Can Transition | Extraction Allowed |
|-------|---------|-------------------|-------------------|
| PROPOSED | LLM-generated or human-submitted | Anyone | No |
| VALIDATING | Under rule evaluation | TypeValidator agent | No |
| CONTESTED | Conflicts detected | CollisionDetector agent | No |
| APPROVED | Passed validation | Validation agents | No |
| ACTIVE | In production | Human (or auto for low-risk) | **Yes** |
| DEPRECATED | Marked for removal | Human only | No (existing preserved) |

### 4.2 Context Foundry States

```
┌─────────┐     corroborate     ┌──────────────┐     promote     ┌─────────┐
│ STAGING │ ───────────────────▶│ CORROBORATED │ ──────────────▶ │ TRUSTED │
└─────────┘                     └──────────────┘                 └────┬────┘
     │                                │                               │
     │ contradict                     │ contradict                    │ contradict
     ▼                                ▼                               ▼
┌───────────┐                   ┌───────────┐                   ┌───────────┐
│ CONTESTED │ ◀─────────────────│ CONTESTED │                   │ CONTESTED │
└─────┬─────┘                   └───────────┘                   └───────────┘
      │
      │ disprove
      ▼
┌───────────┐
│ RETRACTED │
└───────────┘
```

| State | Meaning | Transition Criteria |
|-------|---------|---------------------|
| STAGING | Newly extracted | Initial extraction |
| CORROBORATED | Multiple sources agree | N sources confirm (N from threshold table) |
| TRUSTED | High confidence | Gardener promotion |
| CONTESTED | Conflicting evidence | Contradiction detected |
| RETRACTED | Proven false | Human or agent retraction |

---

## 5. Confidence Calibration

**This section resolves the arbitrary threshold criticism.**

### 5.1 Compositional Confidence Formula

Confidence is not a single LLM logit. It is a weighted composite:

```python
def compute_confidence(entity_or_type, context):
    """
    Compute calibrated confidence score.
    
    Components:
    - extraction_confidence: LLM's raw confidence (calibrated)
    - corroboration_score: Agreement across sources
    - hierarchy_alignment: Fit with existing ontology structure
    - human_review_score: Human validation (if applicable)
    """
    
    weights = get_weights_for_domain(context.domain)
    
    # Base extraction confidence (calibrated from LLM logits)
    extraction = calibrate_llm_confidence(
        raw_confidence=entity_or_type.llm_confidence,
        model=context.extraction_model,
        domain=context.domain
    )
    
    # Corroboration: how many independent sources agree?
    corroboration = compute_corroboration(
        entity_or_type,
        min_sources=2,
        decay_factor=0.9  # Recent sources weighted higher
    )
    
    # Hierarchy alignment: does this fit the ontology structure?
    hierarchy = compute_hierarchy_fit(
        entity_or_type,
        parent_type=entity_or_type.parent,
        sibling_types=get_siblings(entity_or_type.parent)
    )
    
    # Human review (1.0 if approved, 0.5 if pending, 0.0 if rejected)
    human = get_human_review_score(entity_or_type)
    
    # Weighted composite
    confidence = (
        weights.extraction * extraction +
        weights.corroboration * corroboration +
        weights.hierarchy * hierarchy +
        weights.human * human
    )
    
    return min(1.0, max(0.0, confidence))
```

### 5.2 Default Weights by System

| Component | Ontology Foundry | Context Foundry |
|-----------|------------------|-----------------|
| extraction_confidence | 0.20 | 0.40 |
| corroboration_score | 0.30 | 0.35 |
| hierarchy_alignment | 0.25 | 0.15 |
| human_review_score | 0.25 | 0.10 |

### 5.3 Calibration Protocol

Thresholds must be empirically calibrated, not guessed:

```python
# Initial (conservative) thresholds
ONTOLOGY_THRESHOLD = 0.90  # Strict for schema
CONTEXT_THRESHOLD = 0.70   # Flexible for instances

# Calibration procedure (run quarterly)
def calibrate_thresholds(domain, labeled_sample):
    """
    1. Sample 200 entities/types with known ground truth
    2. Compute confidence scores using current formula
    3. Find threshold that achieves target precision/recall
    4. Update threshold table
    """
    
    # Target metrics
    ONTOLOGY_TARGET_PRECISION = 0.95  # Few false positives
    CONTEXT_TARGET_RECALL = 0.85      # Few false negatives
    
    # Find optimal thresholds
    ontology_threshold = find_threshold_for_precision(
        labeled_sample.types,
        target=ONTOLOGY_TARGET_PRECISION
    )
    
    context_threshold = find_threshold_for_recall(
        labeled_sample.entities,
        target=CONTEXT_TARGET_RECALL
    )
    
    # Store calibrated thresholds
    update_threshold_table(domain, ontology_threshold, context_threshold)
    
    # Log calibration metrics
    log_calibration_report(domain, metrics)
```

### 5.4 Threshold Table Schema

```sql
CREATE TABLE confidence_thresholds (
    domain_id VARCHAR(4) PRIMARY KEY,
    domain_name VARCHAR(50) NOT NULL,
    
    -- Ontology Foundry thresholds
    type_promotion_threshold DECIMAL(3,2) DEFAULT 0.90,
    type_auto_approve_threshold DECIMAL(3,2) DEFAULT 0.98,
    
    -- Context Foundry thresholds  
    entity_staging_threshold DECIMAL(3,2) DEFAULT 0.50,
    entity_corroboration_threshold DECIMAL(3,2) DEFAULT 0.70,
    entity_promotion_threshold DECIMAL(3,2) DEFAULT 0.85,
    
    -- Calibration metadata
    last_calibrated_at TIMESTAMP,
    calibration_sample_size INTEGER,
    calibration_precision DECIMAL(3,2),
    calibration_recall DECIMAL(3,2),
    
    -- Version
    updated_at TIMESTAMP DEFAULT NOW()
);
```

---

## 6. Orphan Pattern Detection

**This section resolves the arbitrary threshold criticism.**

### 6.1 Domain-Adaptive Threshold Formula

```python
def compute_orphan_threshold(domain):
    """
    Threshold scales with document corpus size.
    
    Formula (from Manus review):
    - occurrence_threshold = max(10, 0.05 * total_documents)
    - document_threshold = max(5, 0.10 * total_documents)
    
    Bounds:
    - Minimum: 10 occurrences across 5 documents (small corpus)
    - Maximum: 500 occurrences across 100 documents (huge corpus)
    """
    
    total_docs = count_documents_in_domain(domain)
    
    occurrence_threshold = max(10, min(500, int(0.05 * total_docs)))
    document_threshold = max(5, min(100, int(0.10 * total_docs)))
    
    return OrphanThreshold(
        occurrences=occurrence_threshold,
        documents=document_threshold,
        domain=domain,
        computed_at=now()
    )
```

### 6.2 OrphanPattern Entity Structure

```sql
CREATE TABLE orphan_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Pattern identification
    pattern_text VARCHAR(255) NOT NULL,           -- "Certificate of Origin"
    normalized_text VARCHAR(255) NOT NULL,        -- "certificate_of_origin"
    suggested_type_name VARCHAR(100),             -- LLM suggestion
    suggested_parent_type_id UUID,                -- Where it might fit
    
    -- Evidence
    occurrence_count INTEGER DEFAULT 1,
    document_ids UUID[] NOT NULL,                 -- Which docs mentioned it
    extraction_contexts JSONB,                    -- Surrounding text samples
    first_seen_at TIMESTAMP DEFAULT NOW(),
    last_seen_at TIMESTAMP DEFAULT NOW(),
    
    -- Confidence
    avg_extraction_confidence DECIMAL(3,2),
    pattern_coherence_score DECIMAL(3,2),         -- How consistent are mentions?
    
    -- Lifecycle
    status VARCHAR(20) DEFAULT 'ACCUMULATING',    -- ACCUMULATING, SURFACED, REVIEWING, PROMOTED, REJECTED
    surfaced_at TIMESTAMP,
    surfaced_to_user_id UUID,
    decision VARCHAR(20),                         -- PROMOTE, REJECT, MERGE
    decision_at TIMESTAMP,
    decision_by_user_id UUID,
    decision_notes TEXT,
    
    -- If promoted, link to new type
    promoted_to_type_id UUID REFERENCES ontology_types(id),
    
    -- Domain
    domain_id VARCHAR(4) NOT NULL,
    
    CONSTRAINT valid_status CHECK (status IN (
        'ACCUMULATING', 'SURFACED', 'REVIEWING', 'PROMOTED', 'REJECTED', 'MERGED'
    ))
);

CREATE INDEX idx_orphan_patterns_domain_status ON orphan_patterns(domain_id, status);
CREATE INDEX idx_orphan_patterns_occurrence ON orphan_patterns(occurrence_count DESC);
```

### 6.3 Orphan Detection Agent

```python
class OrphanDetector:
    """
    Runs on schedule (hourly) to:
    1. Aggregate new orphan mentions
    2. Check if any patterns exceed threshold
    3. Surface patterns that exceed threshold
    """
    
    def run(self, domain):
        threshold = compute_orphan_threshold(domain)
        
        # Find patterns exceeding threshold
        ready_patterns = self.db.query("""
            SELECT * FROM orphan_patterns
            WHERE domain_id = :domain
              AND status = 'ACCUMULATING'
              AND occurrence_count >= :occurrences
              AND array_length(document_ids, 1) >= :documents
        """, domain=domain, 
             occurrences=threshold.occurrences,
             documents=threshold.documents)
        
        for pattern in ready_patterns:
            self.surface_pattern(pattern)
    
    def surface_pattern(self, pattern):
        """
        Move pattern to SURFACED status and notify reviewers.
        """
        # Generate LLM suggestion for type definition
        suggestion = self.llm.suggest_type_definition(
            pattern_text=pattern.pattern_text,
            extraction_contexts=pattern.extraction_contexts,
            existing_hierarchy=self.get_relevant_hierarchy(pattern)
        )
        
        pattern.suggested_type_name = suggestion.type_name
        pattern.suggested_parent_type_id = suggestion.parent_type_id
        pattern.status = 'SURFACED'
        pattern.surfaced_at = now()
        
        # Notify via message bus
        self.bus.publish('orphan.surfaced', {
            'pattern_id': pattern.id,
            'pattern_text': pattern.pattern_text,
            'occurrence_count': pattern.occurrence_count,
            'document_count': len(pattern.document_ids),
            'suggestion': suggestion.to_dict()
        })
```

### 6.4 Latency SLA

| Stage | SLA | Enforcement |
|-------|-----|-------------|
| Pattern accumulation → Surface | 48 hours max after threshold met | OrphanDetector runs hourly |
| Surface → Human review | 7 days | Escalation to domain lead |
| Review → Decision | 3 days | Auto-reject if no response |
| Decision → Active (if promoted) | 24 hours | Automated deployment |

---

## 7. Deprecation Handling

**This section resolves the deprecation gap.**

### 7.1 Three-Action Model

When a type is deprecated, exactly ONE action must be specified:

```sql
CREATE TYPE deprecation_action AS ENUM ('MIGRATE', 'ARCHIVE', 'DELETE');

ALTER TABLE ontology_types ADD COLUMN deprecation_action deprecation_action;
ALTER TABLE ontology_types ADD COLUMN deprecation_target_type_id UUID;
ALTER TABLE ontology_types ADD COLUMN deprecation_reason TEXT;
ALTER TABLE ontology_types ADD COLUMN deprecated_at TIMESTAMP;
ALTER TABLE ontology_types ADD COLUMN deprecated_by_user_id UUID;
```

| Action | Meaning | Instance Behavior | Query Behavior |
|--------|---------|-------------------|----------------|
| MIGRATE | Replace with successor type | Auto-retype to target | Transparently rewritten |
| ARCHIVE | Preserve but hide | Marked `archived=true` | Excluded unless `include_archived=true` |
| DELETE | Remove entirely | Hard deleted | Returns nothing |

### 7.2 Deprecation Procedure

```python
class DeprecationAgent:
    
    def deprecate_type(self, type_id, action, target_type_id=None, reason=None):
        """
        Deprecate a type with specified action.
        
        Requires:
        - action must be specified
        - MIGRATE requires target_type_id
        - Human approval required
        """
        
        type_record = self.get_type(type_id)
        instance_count = self.count_instances(type_id)
        
        # Validation
        if action == 'MIGRATE' and not target_type_id:
            raise ValueError("MIGRATE requires target_type_id")
        
        if action == 'DELETE' and instance_count > 0:
            raise ValueError(f"Cannot DELETE type with {instance_count} instances. Use MIGRATE or ARCHIVE.")
        
        # Require human approval for types with instances
        if instance_count > 0:
            approval = self.request_human_approval(
                type_record, action, instance_count, target_type_id, reason
            )
            if not approval.granted:
                raise PermissionError("Human approval denied")
        
        # Execute deprecation
        with self.db.transaction():
            # Update type status
            type_record.status = 'DEPRECATED'
            type_record.deprecation_action = action
            type_record.deprecation_target_type_id = target_type_id
            type_record.deprecation_reason = reason
            type_record.deprecated_at = now()
            
            # Handle instances based on action
            if action == 'MIGRATE':
                self.migrate_instances(type_id, target_type_id)
            elif action == 'ARCHIVE':
                self.archive_instances(type_id)
            elif action == 'DELETE':
                pass  # No instances to handle
            
            # Update query translation map
            self.update_migration_map(type_id, action, target_type_id)
    
    def migrate_instances(self, from_type_id, to_type_id):
        """
        Retype all instances from old type to new type.
        Preserves instance IDs, updates type reference.
        """
        self.db.execute("""
            UPDATE entities
            SET type_id = :to_type_id,
                migration_source_type_id = :from_type_id,
                migrated_at = NOW()
            WHERE type_id = :from_type_id
        """, from_type_id=from_type_id, to_type_id=to_type_id)
    
    def archive_instances(self, type_id):
        """
        Mark all instances as archived.
        They remain in DB but are excluded from default queries.
        """
        self.db.execute("""
            UPDATE entities
            SET archived = true,
                archived_at = NOW(),
                archive_reason = 'type_deprecated'
            WHERE type_id = :type_id
        """, type_id=type_id)
```

### 7.3 Migration Map

```sql
CREATE TABLE type_migration_map (
    old_type_id UUID NOT NULL,
    old_type_name VARCHAR(100) NOT NULL,
    new_type_id UUID,                    -- NULL if ARCHIVE or DELETE
    new_type_name VARCHAR(100),
    action deprecation_action NOT NULL,
    migrated_at TIMESTAMP DEFAULT NOW(),
    
    PRIMARY KEY (old_type_id)
);
```

---

## 8. Schema Versioning

**This section resolves the query compatibility gap.**

### 8.1 Bi-Temporal Model

Every ontology change is tracked with two timestamps:
- **valid_time**: When the change is semantically true
- **transaction_time**: When the change was recorded in the system

```sql
CREATE TABLE ontology_versions (
    version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    version_number VARCHAR(20) NOT NULL,  -- Semantic: "2.1.0"
    
    -- What changed
    change_type VARCHAR(20) NOT NULL,     -- TYPE_ADDED, TYPE_DEPRECATED, RELATION_ADDED, etc.
    change_target_id UUID NOT NULL,       -- ID of changed type/relation
    change_payload JSONB NOT NULL,        -- Full change details
    
    -- Bi-temporal tracking
    valid_from TIMESTAMP NOT NULL,        -- When change takes effect
    valid_to TIMESTAMP,                   -- NULL = still valid
    transaction_time TIMESTAMP DEFAULT NOW(),
    
    -- Governance
    approved_by_user_id UUID,
    change_reason TEXT,
    
    CONSTRAINT valid_change_type CHECK (change_type IN (
        'TYPE_ADDED', 'TYPE_MODIFIED', 'TYPE_DEPRECATED',
        'RELATION_ADDED', 'RELATION_MODIFIED', 'RELATION_DEPRECATED',
        'RULE_ADDED', 'RULE_MODIFIED', 'RULE_DEPRECATED'
    ))
);

CREATE INDEX idx_ontology_versions_number ON ontology_versions(version_number);
CREATE INDEX idx_ontology_versions_valid ON ontology_versions(valid_from, valid_to);
```

### 8.2 Version Numbering

```
MAJOR.MINOR.PATCH

MAJOR: Breaking changes (type removed, incompatible schema change)
MINOR: Backward-compatible additions (new type, new optional property)
PATCH: Non-functional changes (description update, hint improvement)
```

### 8.3 Query Translation

Queries can target a specific ontology version:

```python
class QueryTranslator:
    """
    Translates queries written against old ontology versions
    to work with current version.
    """
    
    def translate(self, query, source_version, target_version=None):
        """
        Rewrite query from source_version to target_version (default: current).
        
        Uses migration_map to substitute deprecated types.
        """
        target_version = target_version or self.get_current_version()
        
        if source_version == target_version:
            return query  # No translation needed
        
        # Get all migrations between versions
        migrations = self.get_migrations_between(source_version, target_version)
        
        # Apply substitutions
        translated = query
        for migration in migrations:
            if migration.action == 'MIGRATE':
                translated = translated.replace(
                    migration.old_type_name,
                    migration.new_type_name
                )
            elif migration.action == 'ARCHIVE':
                # Add filter to exclude archived
                translated = self.add_archive_filter(translated, migration.old_type_name)
        
        return translated
```

### 8.4 Historical Queries

```python
# Query current state (default)
results = context.query("SELECT * FROM PowerPlant WHERE capacity_mw > 100")

# Query as of specific ontology version
results = context.query(
    "SELECT * FROM PowerPlant WHERE capacity_mw > 100",
    ontology_version="1.2.0"
)

# Query as of specific point in time
results = context.query(
    "SELECT * FROM PowerPlant WHERE capacity_mw > 100",
    as_of="2025-06-01T00:00:00Z"
)
```

---

## 9. Agent Coordination

**This section resolves the agent orchestration gap.**

### 9.1 Message Bus Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      MESSAGE BUS (PostgreSQL LISTEN/NOTIFY)     │
│                                                                 │
│  Channels:                                                      │
│  - ontology.type.proposed     - ontology.type.validated         │
│  - ontology.type.approved     - ontology.type.activated         │
│  - ontology.type.deprecated   - ontology.collision.detected     │
│  - context.entity.staged      - context.entity.promoted         │
│  - context.orphan.detected    - context.orphan.surfaced         │
│  - governance.approval.needed - governance.approval.granted     │
└─────────────────────────────────────────────────────────────────┘
```

### 9.2 Orchestration Order

**Ontology Foundry Pipeline:**

```
1. TypeProposer (human or LLM)
   └─▶ publishes: ontology.type.proposed
   
2. TypeValidator (agent)
   ├─▶ subscribes: ontology.type.proposed
   ├─▶ validates: JSON schema, required fields, naming conventions
   └─▶ publishes: ontology.type.validated OR ontology.type.rejected

3. CollisionDetector (agent)
   ├─▶ subscribes: ontology.type.validated
   ├─▶ checks: name collisions, UUID collisions, semantic duplicates
   └─▶ publishes: ontology.type.cleared OR ontology.collision.detected

4. HierarchyEnforcer (agent)
   ├─▶ subscribes: ontology.type.cleared
   ├─▶ validates: depth ≥ 3, no Layer 1 direct inheritance, valid parent
   └─▶ publishes: ontology.type.approved OR ontology.type.rejected

5. SchemaPromoter (agent)
   ├─▶ subscribes: ontology.type.approved
   ├─▶ checks: confidence threshold, human approval (if required)
   └─▶ publishes: ontology.type.activated

6. ConstraintPublisher (agent)
   ├─▶ subscribes: ontology.type.activated
   └─▶ updates: Context Foundry's active type cache
```

**Context Foundry Pipeline:**

```
1. Extractor (agent)
   ├─▶ input: document
   ├─▶ constraint: only extract types in active_types cache
   └─▶ publishes: context.entity.staged, context.orphan.detected

2. Corroborator (agent)
   ├─▶ subscribes: context.entity.staged
   ├─▶ compares: against existing entities, other documents
   └─▶ publishes: context.entity.corroborated OR context.entity.contested

3. Gardener (agent)
   ├─▶ subscribes: context.entity.corroborated
   ├─▶ evaluates: confidence threshold, promotion criteria
   └─▶ publishes: context.entity.promoted

4. OrphanDetector (agent)
   ├─▶ subscribes: context.orphan.detected
   ├─▶ aggregates: occurrence counts, document lists
   └─▶ publishes: context.orphan.surfaced (when threshold met)
```

### 9.3 Failure Handling

```python
class AgentRunner:
    """
    Wraps agent execution with retry, timeout, and dead-letter handling.
    """
    
    MAX_RETRIES = 3
    TIMEOUT_SECONDS = 30
    
    async def run_agent(self, agent, message):
        for attempt in range(self.MAX_RETRIES):
            try:
                async with timeout(self.TIMEOUT_SECONDS):
                    result = await agent.process(message)
                    return result
            except TimeoutError:
                self.log.warning(f"Agent {agent.name} timed out, attempt {attempt + 1}")
            except Exception as e:
                self.log.error(f"Agent {agent.name} failed: {e}")
        
        # All retries exhausted - send to dead letter queue
        self.dead_letter_queue.put({
            'agent': agent.name,
            'message': message,
            'error': str(e),
            'timestamp': now()
        })
```

---

## 10. Human-in-the-Loop Governance

**This section resolves the approval workflow gap.**

### 10.1 Decision Matrix

| Action | Confidence ≥ 0.98 | Confidence 0.90-0.98 | Confidence < 0.90 |
|--------|-------------------|---------------------|-------------------|
| New concrete type (under approved abstract) | Auto-approve | Domain lead | Skip (reject) |
| New abstract type | Domain lead | Architecture team | Skip (reject) |
| Type deprecation | Architecture team | Architecture team | N/A |
| Cross-domain type merge | Architecture team | Architecture team | N/A |
| New relationship type | Auto-approve | Domain lead | Skip (reject) |
| Rule modification | Architecture team | Architecture team | N/A |

### 10.2 Escalation Path

```
Level 1: Domain Lead (e.g., AVIATION lead)
  └─▶ Can approve: concrete types, relationships within domain
  └─▶ SLA: 3 business days
  └─▶ Escalates to: Level 2 if no response

Level 2: Architecture Team (QData architects)
  └─▶ Can approve: abstract types, cross-domain, deprecations
  └─▶ SLA: 5 business days
  └─▶ Escalates to: Level 3 if no response

Level 3: Head of QData (Saleh)
  └─▶ Can approve: anything
  └─▶ Final authority
```

### 10.3 Approval Request Schema

```sql
CREATE TABLE approval_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- What needs approval
    request_type VARCHAR(50) NOT NULL,   -- TYPE_PROMOTION, DEPRECATION, etc.
    target_id UUID NOT NULL,             -- Type/relation being approved
    target_snapshot JSONB NOT NULL,      -- Full state at request time
    
    -- Routing
    assigned_level INTEGER NOT NULL,     -- 1, 2, or 3
    assigned_to_user_id UUID,
    assigned_to_role VARCHAR(50),
    
    -- Context for reviewer
    confidence_score DECIMAL(3,2),
    evidence_summary TEXT,
    llm_recommendation VARCHAR(20),      -- APPROVE, REJECT, NEEDS_INFO
    llm_reasoning TEXT,
    
    -- Lifecycle
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT NOW(),
    sla_deadline TIMESTAMP NOT NULL,
    
    -- Decision
    decision VARCHAR(20),                -- APPROVED, REJECTED, ESCALATED
    decision_at TIMESTAMP,
    decision_by_user_id UUID,
    decision_notes TEXT,
    
    CONSTRAINT valid_status CHECK (status IN ('PENDING', 'APPROVED', 'REJECTED', 'ESCALATED', 'EXPIRED'))
);
```

---

## 11. Storage Strategy

**This section resolves the storage architecture gap.**

### 11.1 Single Database, Logical Separation

Both systems share one PostgreSQL database with logical separation via schemas:

```sql
-- Ontology Foundry tables
CREATE SCHEMA ontology;
  ontology.meta_ontology          -- Layer 0 (immutable)
  ontology.types                  -- Type definitions
  ontology.relations              -- Relationship definitions
  ontology.rules                  -- Validation rules
  ontology.versions               -- Version history
  ontology.approval_requests      -- Governance queue

-- Context Foundry tables
CREATE SCHEMA context;
  context.entities                -- Entity instances
  context.relationships           -- Relationship instances
  context.documents               -- Source documents
  context.embeddings              -- Vector store (pgvector)
  context.orphan_patterns         -- Feedback channel

-- Shared tables
CREATE SCHEMA shared;
  shared.users                    -- User accounts
  shared.audit_log                -- All changes
  shared.message_queue            -- Agent coordination
  shared.confidence_thresholds    -- Calibration data
```

### 11.2 Cross-Schema Foreign Keys

```sql
-- Context entities reference Ontology types
ALTER TABLE context.entities
ADD CONSTRAINT fk_entity_type
FOREIGN KEY (type_id) REFERENCES ontology.types(id);

-- Only allow ACTIVE types
CREATE OR REPLACE FUNCTION check_type_active()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM ontology.types 
        WHERE id = NEW.type_id AND status = 'ACTIVE'
    ) THEN
        RAISE EXCEPTION 'Cannot create entity of non-ACTIVE type';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER enforce_active_type
BEFORE INSERT ON context.entities
FOR EACH ROW EXECUTE FUNCTION check_type_active();
```

### 11.3 Why Single Database?

| Factor | Single DB | Separate DBs |
|--------|-----------|--------------|
| Foreign key integrity | ✅ Native | ❌ Application-level |
| Transaction atomicity | ✅ Native | ❌ Distributed tx needed |
| Operational complexity | ✅ Simple | ❌ Two systems to manage |
| Vector search | ✅ pgvector | ✅ pgvector |
| Query across systems | ✅ JOIN | ❌ API calls |

---

## 12. SHACL-Inspired Validation Rules

**Adopted from reviewer recommendation: "steal from SHACL"**

### 12.1 Rule Schema

```sql
CREATE TABLE ontology.rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Rule identity
    rule_name VARCHAR(100) NOT NULL UNIQUE,
    rule_type VARCHAR(50) NOT NULL,
    
    -- What this rule validates
    target_type VARCHAR(50) NOT NULL,    -- 'TYPE', 'RELATION', 'ENTITY'
    target_filter JSONB,                  -- Optional: only apply to matching targets
    
    -- Rule definition (SHACL-inspired)
    constraint_definition JSONB NOT NULL,
    
    -- Severity
    severity VARCHAR(10) DEFAULT 'ERROR',
    
    -- Status
    status VARCHAR(20) DEFAULT 'ACTIVE',
    
    CONSTRAINT valid_rule_type CHECK (rule_type IN (
        'HIERARCHY_DEPTH', 'PROPERTY_REQUIRED', 'PROPERTY_TYPE',
        'NAMING_PATTERN', 'NAMESPACE_ALLOCATION', 'CARDINALITY',
        'NO_ORPHANS', 'NO_COLLISIONS', 'CUSTOM'
    )),
    CONSTRAINT valid_severity CHECK (severity IN ('ERROR', 'WARNING', 'INFO'))
);
```

### 12.2 Example Rules

```sql
INSERT INTO ontology.rules (rule_name, rule_type, target_type, constraint_definition, severity) VALUES

-- Hierarchy depth must be ≥ 3
('hierarchy_minimum_depth', 'HIERARCHY_DEPTH', 'TYPE',
 '{
    "constraint": "minDepth",
    "value": 3,
    "message": "Type must have hierarchy depth >= 3 (no direct Layer 1 inheritance)"
 }',
 'ERROR'),

-- Type names must be PascalCase
('type_naming_convention', 'NAMING_PATTERN', 'TYPE',
 '{
    "constraint": "pattern",
    "field": "type_name",
    "regex": "^[A-Z][a-zA-Z0-9]*$",
    "message": "Type name must be PascalCase"
 }',
 'ERROR'),

-- UUID must follow namespace allocation
('uuid_namespace_allocation', 'NAMESPACE_ALLOCATION', 'TYPE',
 '{
    "constraint": "uuidPattern",
    "pattern": "20000000-{domain_id}-*",
    "message": "UUID must follow domain namespace allocation"
 }',
 'ERROR'),

-- No orphan types (must have at least one relationship)
('no_orphan_types', 'NO_ORPHANS', 'TYPE',
 '{
    "constraint": "minRelationships",
    "value": 1,
    "message": "Type must participate in at least one relationship"
 }',
 'WARNING'),

-- Extraction hints required
('extraction_hints_required', 'PROPERTY_REQUIRED', 'TYPE',
 '{
    "constraint": "required",
    "field": "extraction_hints",
    "message": "Type must have extraction hints for NLP pipeline"
 }',
 'ERROR'),

-- Properties schema must be valid JSON Schema
('valid_properties_schema', 'PROPERTY_TYPE', 'TYPE',
 '{
    "constraint": "jsonSchema",
    "field": "properties_schema",
    "message": "properties_schema must be valid JSON Schema"
 }',
 'ERROR');
```

### 12.3 Rule Executor

```python
class RuleExecutor:
    """
    Executes SHACL-inspired validation rules against types/entities.
    """
    
    def validate(self, target, rules=None):
        """
        Validate target against applicable rules.
        
        Returns:
        - ValidationResult with errors, warnings, info
        """
        rules = rules or self.get_rules_for_target(target)
        
        errors = []
        warnings = []
        info = []
        
        for rule in rules:
            result = self.execute_rule(rule, target)
            
            if not result.passed:
                if rule.severity == 'ERROR':
                    errors.append(result)
                elif rule.severity == 'WARNING':
                    warnings.append(result)
                else:
                    info.append(result)
        
        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            info=info
        )
    
    def execute_rule(self, rule, target):
        """
        Execute single rule against target.
        """
        constraint = rule.constraint_definition
        
        if rule.rule_type == 'HIERARCHY_DEPTH':
            depth = self.compute_hierarchy_depth(target)
            passed = depth >= constraint['value']
            
        elif rule.rule_type == 'NAMING_PATTERN':
            value = getattr(target, constraint['field'])
            passed = re.match(constraint['regex'], value) is not None
            
        elif rule.rule_type == 'PROPERTY_REQUIRED':
            value = getattr(target, constraint['field'], None)
            passed = value is not None and value != ''
            
        # ... other rule types
        
        return RuleResult(
            rule=rule,
            target=target,
            passed=passed,
            message=constraint['message'] if not passed else None
        )
```

---

## 13. Implementation Phases

### Phase 1: Foundation (Week 1)
- [ ] Create database schemas (ontology, context, shared)
- [ ] Seed Layer 0 meta-ontology
- [ ] Load existing 8 ontology files as ACTIVE types
- [ ] Implement confidence threshold table

### Phase 2: Ontology Foundry MVP (Week 2)
- [ ] Implement TypeValidator agent
- [ ] Implement CollisionDetector agent
- [ ] Implement HierarchyEnforcer agent
- [ ] Implement rule executor with 6 base rules
- [ ] Implement message bus (PostgreSQL LISTEN/NOTIFY)

### Phase 3: Governance Integration (Week 3)
- [ ] Implement approval_requests workflow
- [ ] Implement SchemaPromoter with human-in-the-loop
- [ ] Implement DeprecationAgent with three-action model
- [ ] Implement version tracking

### Phase 4: Feedback Channel (Week 4)
- [ ] Implement OrphanDetector agent
- [ ] Implement orphan_patterns table and aggregation
- [ ] Implement adaptive threshold computation
- [ ] Connect feedback channel to Ontology Foundry

### Phase 5: Calibration & Tuning (Ongoing)
- [ ] Collect labeled sample for threshold calibration
- [ ] Run initial calibration
- [ ] Monitor false positive/negative rates
- [ ] Adjust thresholds quarterly

---

## 14. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Schema stability | < 5 type changes/month | Count ACTIVE → DEPRECATED transitions |
| Orphan pattern detection | > 80% of valid patterns surfaced | Manual review of rejected patterns |
| False positive rate (types) | < 5% | Audit of ACTIVE types after 30 days |
| False negative rate (entities) | < 15% | Sample comparison against ground truth |
| Approval latency | < 5 days average | Time from PROPOSED to ACTIVE |
| Query compatibility | 100% for past 6 months | Automated test suite against historical queries |

---

## 15. Appendix: Glossary Updates

| Term | Definition |
|------|------------|
| Layer 0 | Immutable meta-ontology defining what types/relations/rules are |
| SHACL-inspired | Validation approach using declarative rules as data |
| Bi-temporal | Tracking both valid_time (semantic) and transaction_time (system) |
| Orphan pattern | Recurring extraction that doesn't match any ACTIVE type |
| Deprecation action | MIGRATE, ARCHIVE, or DELETE - required when deprecating a type |
| Confidence calibration | Empirical process of setting thresholds based on labeled data |

---

## 16. Sign-Off

**RFC v2 Status:** Ready for implementation

**Critical gaps addressed:** 5/5
- ✅ Bootstrap paradox (§3)
- ✅ Confidence calibration (§5)
- ✅ Orphan threshold (§6)
- ✅ Deprecation handling (§7)
- ✅ Schema versioning (§8)

**Additional specifications added:**
- ✅ Agent coordination (§9)
- ✅ Human-in-the-loop (§10)
- ✅ Storage strategy (§11)
- ✅ SHACL-inspired rules (§12)

**Decision adopted:** Build custom on PostgreSQL, steal validation patterns from SHACL

**Next step:** Send to Replit for Session 5 implementation

---

*End of RFC v2*
