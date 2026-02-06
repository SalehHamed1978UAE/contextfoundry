# Week 1 Implementation Guide: Conflict-Aware Retrieval

**Goal:** Improve accuracy from 74% → 81% (+7 questions) in ~12 hours of implementation

**Target failures:** Q3, Q14, Q25, Q51, Q100 + 2 persistent MISMATCH failures

---

## Implementation Tasks

### Task 1: SOURCE_TRUST Hierarchy (1 hour)

**File:** `src/context_foundry/resolution/source_trust.py` (NEW)

```python
"""Document authority weights for conflict resolution."""

from typing import Dict

# Based on document type reliability (research-backed)
SOURCE_TRUST: Dict[str, float] = {
    # High-trust sources (organizational authority)
    "annual_report": 0.95,
    "strategic_plan": 0.90,
    "organizational_chart": 0.95,
    "financial_statement": 0.95,

    # Medium-trust sources (operational documents)
    "project_plan": 0.75,
    "technical_spec": 0.85,
    "meeting_notes": 0.60,
    "email": 0.55,

    # Low-trust sources (generic extractions)
    "extraction_run": 0.50,  # Re-extraction gets lowest trust
    "unknown": 0.40,
}

def get_source_trust(document_type: str) -> float:
    """Get trust weight for document type."""
    return SOURCE_TRUST.get(document_type.lower(), SOURCE_TRUST["unknown"])
```

**Integration:**
- Add `document_type` field to evidence records table (migration)
- Populate document_type from document metadata during extraction

---

### Task 2: Cardinality Registry (2 hours)

**File:** `src/context_foundry/extraction/ontology_manager.py` (MODIFY)

Add cardinality field to relationship definitions:

```python
# In YAML schema (ontologies/*.yaml)
relationships:
  PRESIDENT_OF:
    description: "Person holds president role for organization"
    cardinality: "1-to-1"  # One president per org at a time
    from_types: [PERSON]
    to_types: [ORGANIZATION]

  HAS_ROLE:
    description: "Person has role at organization"
    cardinality: "N-to-1"  # Person has one role per org
    from_types: [PERSON]
    to_types: [ROLE]

  HAS_REVENUE:
    description: "Organization has revenue value"
    cardinality: "1-to-1"  # One revenue per org per period
    from_types: [ORGANIZATION]
    to_types: [METRIC]

  HAS_CUSTOMER:
    description: "Organization has customer relationship"
    cardinality: "1-to-N"  # Org can have many customers
    from_types: [ORGANIZATION]
    to_types: [ORGANIZATION]

  HAS_ENERGY_DENSITY:
    description: "Product has target energy density"
    cardinality: "1-to-1"  # One target per product
    from_types: [PRODUCT]
    to_types: [METRIC]
```

**Code changes:**

```python
# In OntologyManager class
def get_cardinality(self, relationship_type: str) -> str:
    """Get cardinality constraint for relationship type.

    Returns:
        "1-to-1" | "1-to-N" | "N-to-1" | "N-to-N"
    """
    rel_def = self.schema.get("relationships", {}).get(relationship_type, {})
    return rel_def.get("cardinality", "N-to-N")  # Default to most permissive

def is_functional(self, relationship_type: str) -> bool:
    """Check if relationship has functional dependency (1-to-1 or N-to-1)."""
    cardinality = self.get_cardinality(relationship_type)
    return cardinality in ["1-to-1", "N-to-1"]
```

---

### Task 3: CRH Evidence-Weighted Scorer (3 hours)

**File:** `src/context_foundry/resolution/conflict_resolver.py` (NEW)

```python
"""
Conflict-aware retrieval using CRH (Credible Ranking with Hints).

Based on Li et al., SIGMOD 2014: "Truth Discovery on Structured Data"
"""

from dataclasses import dataclass
from typing import List, Optional, Dict
import math

from src.context_foundry.extraction.ontology_manager import OntologyManager
from src.context_foundry.resolution.source_trust import get_source_trust


@dataclass
class EnrichedFact:
    """Fact with conflict resolution metadata."""
    fact_id: str
    fact_type: str  # "ENTITY" | "RELATIONSHIP"
    entity_id: Optional[str]
    relationship_id: Optional[str]
    value: str  # The claimed value (e.g., "Robert Kim", "$2.3B")

    # Evidence metadata
    evidence_count: int
    confidence: float
    source_document_types: List[str]  # e.g., ["org_chart", "email"]

    # Computed scores
    source_trust_score: float = 0.0
    crh_score: float = 0.0


@dataclass
class ConflictGroup:
    """Group of conflicting facts for same entity/relationship."""
    conflict_key: str  # e.g., "PRESIDENT_OF:Nexus Digital Solutions"
    cardinality: str  # "1-to-1" | "N-to-1" | etc.
    facts: List[EnrichedFact]
    resolved_fact: Optional[EnrichedFact] = None


class ConflictResolver:
    """Resolves conflicts using functional dependencies and evidence weighting."""

    def __init__(self, ontology_manager: OntologyManager):
        self.ontology = ontology_manager

    def detect_conflicts(
        self,
        facts: List[EnrichedFact],
        relationship_type: str
    ) -> List[ConflictGroup]:
        """Detect conflicts using cardinality constraints.

        Args:
            facts: List of facts to check for conflicts
            relationship_type: Type of relationship (e.g., "PRESIDENT_OF")

        Returns:
            List of conflict groups where resolution is needed
        """
        cardinality = self.ontology.get_cardinality(relationship_type)

        # No conflicts for N-to-N relationships
        if cardinality == "N-to-N":
            return []

        # Group facts by conflict key
        groups: Dict[str, List[EnrichedFact]] = {}

        for fact in facts:
            if cardinality == "1-to-1":
                # Conflict if multiple facts claim same relationship
                key = f"{relationship_type}:{fact.entity_id}"
            elif cardinality == "N-to-1":
                # Conflict if entity has multiple values for same relationship
                key = f"{relationship_type}:{fact.entity_id}"
            elif cardinality == "1-to-N":
                # Conflict if target has multiple sources
                key = f"{relationship_type}:{fact.value}"
            else:
                continue

            if key not in groups:
                groups[key] = []
            groups[key].append(fact)

        # Only create conflict groups for keys with multiple facts
        conflicts = []
        for key, group_facts in groups.items():
            if len(group_facts) > 1:
                conflicts.append(ConflictGroup(
                    conflict_key=key,
                    cardinality=cardinality,
                    facts=group_facts
                ))

        return conflicts

    def compute_crh_score(self, fact: EnrichedFact) -> float:
        """
        Compute Credible Ranking with Hints (CRH) score.

        Formula (from Li et al., SIGMOD 2014):
        CRH = α * source_trust + β * confidence + γ * log(evidence_count + 1)

        Weights tuned for our domain:
        - source_trust (α=0.4): Document authority is primary signal
        - confidence (β=0.3): LLM confidence is secondary
        - evidence_count (γ=0.3): Multiple mentions provide support
        """
        α, β, γ = 0.4, 0.3, 0.3

        # Average source trust across all evidence documents
        avg_source_trust = sum(
            get_source_trust(doc_type)
            for doc_type in fact.source_document_types
        ) / len(fact.source_document_types) if fact.source_document_types else 0.0

        # Logarithmic evidence count (diminishing returns)
        evidence_score = math.log(fact.evidence_count + 1) / math.log(10)  # Normalize to ~[0, 1]

        crh_score = (
            α * avg_source_trust +
            β * fact.confidence +
            γ * evidence_score
        )

        return crh_score

    def resolve_conflict(self, conflict_group: ConflictGroup) -> EnrichedFact:
        """Resolve conflict by selecting highest-scored fact.

        Args:
            conflict_group: Group of conflicting facts

        Returns:
            The winning fact after CRH scoring
        """
        # Compute CRH scores for all facts
        for fact in conflict_group.facts:
            fact.source_trust_score = sum(
                get_source_trust(doc_type)
                for doc_type in fact.source_document_types
            ) / len(fact.source_document_types) if fact.source_document_types else 0.0

            fact.crh_score = self.compute_crh_score(fact)

        # Select fact with highest CRH score
        winner = max(conflict_group.facts, key=lambda f: f.crh_score)
        conflict_group.resolved_fact = winner

        return winner

    def resolve_all(
        self,
        facts: List[EnrichedFact],
        relationship_type: str
    ) -> List[EnrichedFact]:
        """Detect and resolve all conflicts for a relationship type.

        Returns:
            List of facts with conflicts resolved (winning facts only)
        """
        conflicts = self.detect_conflicts(facts, relationship_type)

        # Track which facts are winners
        resolved_fact_ids = set()

        for conflict in conflicts:
            winner = self.resolve_conflict(conflict)
            resolved_fact_ids.add(winner.fact_id)

        # Return all non-conflicting facts + winning facts
        result = []
        conflict_keys = {c.conflict_key for c in conflicts}

        for fact in facts:
            # If fact was in a conflict, only include if it won
            if any(fact in c.facts for c in conflicts):
                if fact.fact_id in resolved_fact_ids:
                    result.append(fact)
            else:
                # No conflict, include as-is
                result.append(fact)

        return result
```

---

### Task 4: Integration Point (2 hours)

**File:** `src/context_foundry/agents/tool_agent.py` (MODIFY)

Insert conflict resolution between retrieval and synthesis:

```python
# Around line 1047 (after tree retrieval, before answer synthesis)

from src.context_foundry.resolution.conflict_resolver import (
    ConflictResolver,
    EnrichedFact
)

# Inside retrieve_and_synthesize or similar method:

# BEFORE (current code):
# tree_results = self.tree_retriever.retrieve(query)
# answer = self.synthesizer.generate(tree_results)

# AFTER (with conflict resolution):
tree_results = self.tree_retriever.retrieve(query)

# Convert results to EnrichedFacts
enriched_facts = []
for rel in tree_results.relationships:
    fact = EnrichedFact(
        fact_id=rel.id,
        fact_type="RELATIONSHIP",
        entity_id=rel.source_entity_id,
        relationship_id=rel.id,
        value=rel.target_entity_id,  # Or relationship properties
        evidence_count=len(rel.evidence_records),
        confidence=rel.confidence,
        source_document_types=[
            ev.source_document.document_type
            for ev in rel.evidence_records
            if ev.source_document
        ]
    )
    enriched_facts.append(fact)

# Resolve conflicts
resolver = ConflictResolver(self.ontology_manager)
resolved_facts = resolver.resolve_all(
    enriched_facts,
    relationship_type=query.relationship_type  # Extract from query
)

# Continue with synthesis using resolved facts
answer = self.synthesizer.generate(resolved_facts)
```

---

### Task 5: Testing (4 hours)

**Test plan:**

1. **Unit tests for ConflictResolver:**
   - Test cardinality detection (1-to-1, N-to-1, 1-to-N)
   - Test CRH scoring with known SOURCE_TRUST values
   - Test conflict resolution picks correct winner

2. **Integration tests for specific failures:**
   - Q3: Kevin Chang vs Robert Kim → verify org chart wins
   - Q51: 24 vs 48 satellites → verify higher confidence wins
   - Q100: $2.3B vs $1.8B Boeing → verify newer/higher-trust wins

3. **Golden test creation:**
```python
def test_q3_conflict_resolution():
    """Q3: President of Digital Solutions conflict."""
    facts = [
        EnrichedFact(
            fact_id="fact_1",
            value="Robert Kim",
            evidence_count=2,
            confidence=0.85,
            source_document_types=["organizational_chart"]
        ),
        EnrichedFact(
            fact_id="fact_2",
            value="Kevin Chang",
            evidence_count=1,
            confidence=0.75,
            source_document_types=["email"]
        ),
    ]

    resolver = ConflictResolver(ontology_manager)
    conflict = ConflictGroup(
        conflict_key="PRESIDENT_OF:Digital Solutions",
        cardinality="1-to-1",
        facts=facts
    )

    winner = resolver.resolve_conflict(conflict)

    # Org chart (0.95) should beat email (0.55)
    assert winner.value == "Robert Kim"
    assert winner.fact_id == "fact_1"
```

4. **Full vault test:**
   - Run: `pytest data/test-runner/run_test.py --vault-id <id>`
   - Expected: 77-81% accuracy (target: +7 questions from 74%)
   - Specific fixes expected: Q3, Q14 (cascading), Q51

---

## Success Criteria

**Must achieve:**
- ✅ Q3 passes (Robert Kim selected over Kevin Chang)
- ✅ Q51 passes (correct satellite count selected)
- ✅ Baseline maintained (Q41, Q75 still pass)

**Stretch goals:**
- ✅ Q100 passes (correct Boeing revenue selected)
- ✅ 81% overall accuracy (+7 questions)

**Validation:**
- No new failures introduced
- CRH scoring picks correct value in 100% of known conflicts
- SOURCE_TRUST hierarchy properly applied

---

## Next Steps After Week 1

**If 81% achieved:**
- Proceed to Week 2: Query routing with graph reliability detection
- Expected: +6 questions → 87%

**If 77% achieved:**
- Conflicts resolved, but extraction quality still an issue
- Proceed to Week 3: Metric extraction with typed schemas
- Expected: +5 questions → 82%

**If <77% achieved:**
- Debug CRH scoring formula
- Check SOURCE_TRUST weights
- Verify cardinality constraints are correct
