# Conflict-Aware Retrieval Plan

## Problem Statement

The ontology re-extraction revealed a **system capability gap**: the retrieval pipeline cannot handle conflicting knowledge graph data. When multiple entities/relationships conflict (e.g., "Kevin Chang" vs "Robert Kim" for President of Digital Solutions), the system randomly picks one without evidence weighting.

**Current behavior:**
- `tool_agent.py:1111` → `_synthesize_direct_answer()` takes `pipeline_result.entities` **as-is**
- No conflict detection or resolution
- LLM sees ALL conflicting data, picks arbitrarily
- Result: Wrong answers when KG has conflicts

**Goal:** Make the system **robust to conflicting evidence** by implementing evidence-weighted resolution.

## Architecture Design

### Component 1: ConflictResolver

**Location:** `src/context_foundry/resolution/conflict_resolver.py` (new file)

**Purpose:** Detect and resolve conflicts in entity/relationship lists using evidence weighting.

**Key Methods:**

```python
class ConflictResolver:
    """
    Evidence-weighted conflict resolution for knowledge graph data.

    When multiple entities/relationships conflict, rank by:
    1. Evidence count (how many source chunks support this fact)
    2. Extraction confidence
    3. Recency (newer extractions preferred)
    4. Lifecycle state (TRUSTED > STAGING > ARCHIVED)
    """

    def resolve_entity_conflicts(
        self,
        entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect entity conflicts and return highest-ranked candidates.

        Conflict detection:
        - Same entity_type + similar name (fuzzy match > 0.85)
        - Same role in organization (e.g., both are "President of Digital Solutions")

        Ranking criteria:
        1. evidence_count (from evidence_records table)
        2. confidence score
        3. updated_at timestamp
        4. lifecycle_state: TRUSTED (1.0) > STAGING (0.8) > ARCHIVED (0.5)

        Args:
            entities: List of entity dicts from tree retrieval

        Returns:
            Deduplicated list with highest-ranked entity per conflict group
        """

    def resolve_relationship_conflicts(
        self,
        relationships: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect relationship conflicts and return highest-ranked candidates.

        Conflict detection:
        - Same relationship_type + source + target entities
        - Contradictory property values (e.g., different dates for same event)

        Ranking criteria:
        1. evidence_count
        2. confidence score
        3. updated_at timestamp

        Returns:
            Deduplicated list with highest-ranked relationship per conflict group
        """

    def _get_evidence_count(self, fact_type: str, fact_id: str) -> int:
        """
        Query evidence_records table for provenance count.

        SELECT COUNT(*) FROM evidence_records
        WHERE fact_type = :fact_type AND fact_id = :fact_id
        """

    def _calculate_evidence_score(self, entity: Dict) -> float:
        """
        Calculate composite evidence score (0-1).

        Score = weighted_average(
            evidence_count * 0.4,    # Most important: how many sources
            confidence * 0.3,         # Extraction confidence
            recency * 0.2,           # Newer = better
            lifecycle_state * 0.1    # TRUSTED > STAGING > ARCHIVED
        )
        """
```

### Component 2: Integration Point in ToolAgent

**Location:** `src/context_foundry/agents/tool_agent.py:1047-1111`

**Implementation:**

```python
# BEFORE (current code - line 1047):
pipeline_result = self.query_pipeline.process(question, vault_context=vault_context)

# AFTER (new conflict-aware code):
pipeline_result = self.query_pipeline.process(question, vault_context=vault_context)

# NEW: Conflict resolution before answer synthesis
if pipeline_result and (pipeline_result.entities or pipeline_result.relationships):
    from ..resolution.conflict_resolver import ConflictResolver

    resolver = ConflictResolver(self.session, self.tenant_id)

    # Resolve entity conflicts (e.g., Kevin Chang vs Robert Kim)
    if pipeline_result.entities:
        original_count = len(pipeline_result.entities)
        pipeline_result.entities = resolver.resolve_entity_conflicts(pipeline_result.entities)

        if len(pipeline_result.entities) < original_count:
            logger.info(f"[CONFLICT] Resolved {original_count - len(pipeline_result.entities)} "
                       f"entity conflicts via evidence weighting")

    # Resolve relationship conflicts (e.g., conflicting appointment dates)
    if pipeline_result.relationships:
        original_count = len(pipeline_result.relationships)
        pipeline_result.relationships = resolver.resolve_relationship_conflicts(pipeline_result.relationships)

        if len(pipeline_result.relationships) < original_count:
            logger.info(f"[CONFLICT] Resolved {original_count - len(pipeline_result.relationships)} "
                       f"relationship conflicts via evidence weighting")

# Continue with existing direct answer logic (line 1109)
if pipeline_result and self._can_answer_directly(pipeline_result):
    answer = self._synthesize_direct_answer(question, pipeline_result, intent)
    ...
```

### Component 3: Evidence Counting Enhancement

**Problem:** The current extraction pipeline doesn't populate `evidence_records` table consistently.

**Location:** `src/context_foundry/extraction/kg_ingestor.py`

**Enhancement:** When staging entities/relationships, ensure evidence_records are created:

```python
# In kg_ingestor.py: _insert_evidence_records()
# ENSURE this is called for EVERY entity/relationship insertion

def _insert_evidence_records(
    self,
    fact_type: str,
    fact_id: str,
    evidence_text: str,
    source_document_id: str,
    chunk_id: str
):
    """
    Create evidence_record linking fact to source.

    This enables conflict resolution to count provenance.
    """
    evidence_record = EvidenceRecord(
        tenant_id=self.tenant_id,
        fact_type=FactType.ENTITY if fact_type == 'ENTITY' else FactType.RELATIONSHIP,
        fact_id=fact_id,
        evidence_text=evidence_text,
        source_document_id=source_document_id,
        chunk_id=chunk_id
    )
    self.session.add(evidence_record)
```

## Implementation Steps

### Phase 1: Basic Conflict Detection (1 hour)

1. Create `src/context_foundry/resolution/conflict_resolver.py`
2. Implement `_detect_entity_conflicts()` using fuzzy name matching
3. Implement `_get_evidence_count()` to query evidence_records table
4. Add basic ranking by evidence_count

### Phase 2: Evidence-Weighted Scoring (2 hours)

1. Implement `_calculate_evidence_score()` with weighted formula
2. Add recency scoring (newer extractions preferred)
3. Add lifecycle_state weighting (TRUSTED > STAGING > ARCHIVED)
4. Test with Kevin Chang vs Robert Kim case

### Phase 3: Integration (1 hour)

1. Add conflict resolver to `tool_agent.py:1047-1111`
2. Add logging for conflict resolution diagnostics
3. Test end-to-end with conflicting KG data

### Phase 4: Validation (2 hours)

1. Re-run 100Q test on ontology vault
2. Verify Q3, Q14, Q51 regressions are fixed
3. Measure impact on overall accuracy
4. Add conflict resolution metrics to test results

## Expected Results

**Before conflict resolution:**
- Q3: FAIL - "Kevin Chang" (wrong, from conflicting KG data)
- Q14: FAIL - Robert Kim appointment date not found
- Q51: FAIL - Wrong satellite count (24 instead of 48)
- **Overall: 74%**

**After conflict resolution:**
- Q3: PASS - "Robert Kim" (correct, higher evidence count)
- Q14: PASS - Appointment date from correct Robert Kim entity
- Q51: PASS - Correct satellite count (conflicting data filtered)
- **Expected: 77%+** (restore baseline + potential improvements)

## Success Metrics

1. **Conflict Detection Rate:** % of queries where conflicts are detected
2. **Resolution Accuracy:** % of conflicts correctly resolved (human validation)
3. **System Robustness:** Accuracy on test set WITH vs WITHOUT conflicting KG data
4. **Evidence Utilization:** % of entities/relationships with evidence_records

## Future Enhancements (Post-MVP)

1. **Cross-document verification:** When KG conflicts, fetch source documents and re-verify
2. **Confidence downgrade:** When evidence is split 50/50, return "uncertain" response
3. **Active learning:** Flag conflicts for human review, learn from resolutions
4. **Temporal conflict resolution:** Prefer most recent facts for time-sensitive data

## Files to Create/Modify

**New files:**
- `src/context_foundry/resolution/__init__.py`
- `src/context_foundry/resolution/conflict_resolver.py`
- `tests/test_conflict_resolver.py`

**Modified files:**
- `src/context_foundry/agents/tool_agent.py` (add conflict resolution at line 1047)
- `src/context_foundry/extraction/kg_ingestor.py` (ensure evidence_records populated)

## Testing Plan

**Unit tests:**
```python
def test_detect_entity_conflict_same_role():
    # Kevin Chang vs Robert Kim for same role
    entities = [
        {"name": "Kevin Chang", "type": "PERSON", "confidence": 0.8, "evidence_count": 1},
        {"name": "Robert Kim", "type": "PERSON", "confidence": 0.9, "evidence_count": 5}
    ]

    resolver = ConflictResolver(session, tenant_id)
    resolved = resolver.resolve_entity_conflicts(entities)

    # Should keep Robert Kim (higher evidence count)
    assert len(resolved) == 1
    assert resolved[0]["name"] == "Robert Kim"

def test_resolve_relationship_conflict_different_dates():
    # Same person, same role, different appointment dates
    relationships = [
        {"type": "APPOINTED_ON", "source": "Robert Kim", "target": "2024-01-15", "evidence_count": 2},
        {"type": "APPOINTED_ON", "source": "Robert Kim", "target": "2024-03-01", "evidence_count": 1}
    ]

    resolver = ConflictResolver(session, tenant_id)
    resolved = resolver.resolve_relationship_conflicts(relationships)

    # Should keep 2024-01-15 (higher evidence count)
    assert len(resolved) == 1
    assert resolved[0]["target"] == "2024-01-15"
```

**Integration tests:**
```python
def test_conflict_resolution_in_query_pipeline():
    # Create conflicting entities in KG
    # Run query that would hit conflict
    # Verify conflict resolver selected correct entity
    pass
```

**End-to-end test:**
- Re-run Q3, Q14, Q51 from 100Q test
- Verify answers are now correct
- Check logs for "[CONFLICT] Resolved X conflicts" messages

---

**Ready for implementation:** This plan provides concrete code structure, integration points, and validation steps for building conflict-aware retrieval capability.
