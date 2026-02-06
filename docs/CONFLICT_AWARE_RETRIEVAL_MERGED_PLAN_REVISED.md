# Conflict-Aware Retrieval: Final Plan

## Purpose
Build a system that outperforms competitors under noisy KG conditions, not a clean KG. The architecture must resolve conflicts at query time, prevent cross-wiring, extract and normalize metrics reliably, route retrieval based on conflict risk and evidence quality, and prefer NULL over wrong answers when confidence is low.

## Baseline Observations
1. Re-extraction increased conflicts and regressed accuracy (77% to 74%).
2. Tree retrieval helps role queries but fails for metric queries when graph edges are absent.
3. Passing multiple conflicting candidates to the LLM without arbitration causes wrong answers.
4. Some failures are NOT conflicts: wrong single facts due to cross-wiring or weak entity grounding.
5. Aggregation failures are both LLM math errors AND value selection errors (wrong inputs to computation). Structured compute fixes arithmetic; the conflict-vs-complement classifier fixes value selection.

## Design Principles
1. Query-time arbitration over KG cleaning.
2. Entity-grounded validation before synthesis.
3. Evidence-weighted truth selection with explicit conflict detection.
4. Metric normalization before aggregation or ranking.
5. Routing based on conflict risk and evidence reliability, not only query type.
6. Prefer NULL over wrong for low confidence or ungrounded results.
7. Always fall back gracefully to documents when KG is weak or inconsistent.
8. Classify first, then aggregate — never aggregate without determining whether values conflict or complement.

## Architecture Overview
Five layers before answer synthesis:
0. Entity-Grounded Retrieval Validation
1. Conflict Detector
2. Conflict Resolver
3. Metric Normalizer + Canonicalizer
4. Aggregation Planner + Structured Compute

Routing is updated with conflict risk, entity grounding, doc-level entropy, and entity-linking certainty.
For metric queries, normalization and canonicalization run before conflict detection; structured compute runs after resolution.
For aggregation queries, the router decomposes into sub-queries before entering the pipeline.

---

## Component 0: Entity-Grounded Retrieval Validation
Prevent cross-wiring (wrong facts attached to the wrong entity).

### Goal
Validate that retrieved candidates are connected to the query entity along the correct graph path.

### Two Validation Modes
Mode 1: Direct Path Validation (product/project queries)
- Query mentions a named entity (GreenHydrogen, SmartGrid Controller, HTS wire)
- Candidate must connect through that specific entity node, not through a parent/sibling
- Implementation: extract specific entity, resolve node ID, require candidate edge path to include that node

Mode 2: Scope Constraint Validation (division/business unit queries)
- Query mentions a division/business unit
- Candidate relationships must originate from nodes within that division subgraph
- Precompute division membership map; reject candidates outside scope

### Named-Group Membership Rule
For queries like "Executive Leadership Team members":
- Require direct HAS_MEMBER edges to the named group node
- Do not infer membership from title/role alone
- If group node absent, fallback to docs with exact group name

---

## Component 1: Conflict Detector
Detect conflicts when a relation should be functionally unique or when metric values collide within the same scope.

### 1.1 Cardinality Registry (Auto + Manual)
Manual registry for seed relations, and automatic constraint mining (PaTeCon) for scalability.

```
RELATION_CARDINALITY = {
  "PRESIDENT_OF": "1-to-1",
  "CEO_OF": "1-to-1",
  "CFO_OF": "1-to-1",
  "APPOINTED_ON": "1-to-1",
  "HAS_ENERGY_DENSITY": "1-to-1",
  "HAS_ASSET_COUNT": "1-to-1",
  "HAS_MEMBER": "N-to-N",
  "HAS_CUSTOMER": "1-to-N"
}
```

Auto-mined constraints update this table as the KG evolves.
Add cardinality exceptions for co-roles or interim roles when qualifiers indicate shared or temporary positions.

### 1.2 Conflict Rules
Detect conflicts when:
1. A 1-to-1 relation has more than one candidate.
2. Two facts overlap in **normalized** time period (see 3.1a) but disagree.
3. Two metrics share the same (entity, **canonical_metric**, normalized_period, unit) and differ materially.
4. Entity names are fuzzy-matched collisions within the same role or relationship.

Materiality thresholds for metric conflicts:
- Financial values: difference > 2% of larger value = material conflict
- Counts/integers: any difference = conflict
- Percentages: difference > 0.5 percentage points = conflict
Below threshold: treat as rounding variance, prefer higher-authority source.

**Important:** Conflict rule 1.2.3 operates on **canonical_metric** (output of 3.2a), not raw extracted metric strings. "Net sales" and "revenue" must both resolve to REVENUE before this rule can detect their conflict.

### 1.3 Entropy Signal (Doc-Level)
Compute entropy over document-level candidate answers, not KG-only.

- High entropy -> do not trust KG as sole source
- Require conflict-aware prompt or return NULL

---

## Component 2: Conflict Resolver

### 2.0 Document Authority Tiers (Source Trust Table)
Define source trust explicitly with tiers. This is required to compute source_trust_weight.

```
DOCUMENT_AUTHORITY_TIERS = {
  # Tier 1: Structural / Official
  "organizational_chart": 0.95,
  "annual_report": 0.95,
  "financial_statement": 0.95,
  "strategic_plan": 0.90,

  # Tier 2: Procedural / Operational
  "project_charter": 0.70,
  "meeting_notes": 0.60,

  # Tier 3: Communication
  "email": 0.40,
  "slack_message": 0.40,

  # Tier 4: Personal / Draft
  "draft": 0.15,
  "personal_notes": 0.15,
}
```

If a document type is unknown, default to 0.50.
Prerequisite: ensure ingestion/classification sets document_type. If not, add a lightweight classifier (filename heuristics or simple content rules) so source_trust_weight is not constant.

Score competing candidates and select a winner only when evidence separation is strong.

### 2.1 Evidence-Weighted Scoring (Normalized)
Scores must be normalized to 0..1, or use ratio-based thresholds.

```
score = 0.30 * source_trust_weight
      + 0.25 * extraction_confidence
      + 0.20 * recency_weight
      + 0.15 * lifecycle_weight
      + 0.10 * evidence_count
```

Evidence count must be independent-source count, not chunk frequency.

Source independence rule:
- If two evidence records share >70% n-gram overlap within 200 tokens around the value claim, count as one source
- Cap evidence contribution at 1 per document
- Cap evidence contribution at 2 per source_type (e.g., max 2 emails count, even if 5 exist)
- Rationale: sharing *false* values is strong evidence of copying; sharing *true* values is not (sources converge on correct numbers naturally)

### 2.1a CATD for Numerical Conflicts (Optional Enhancement)
For metric-type conflicts specifically, consider Confidence-Aware Truth Discovery (CATD) instead of or alongside the hand-tuned scoring formula. CATD models extraction errors as Gaussian and learns source reliability weights from data rather than requiring manual tuning.

```python
def catd_resolve(claims, alpha=0.05, max_iter=20):
    """CATD: Confidence-Aware Truth Discovery for numerical values."""
    values = [c.value for c in claims]
    truth = np.mean(values)  # Initialize
    for _ in range(max_iter):
        weights = []
        for c in claims:
            n = c.source.total_claims_count
            residual_sq = (c.value - truth) ** 2 + 1e-10
            chi2_val = scipy.stats.chi2.ppf(alpha / 2, max(n - 1, 1))
            weights.append(chi2_val / residual_sq)
        weights = np.array(weights) / sum(weights)
        new_truth = sum(w * v for w, v in zip(weights, values))
        if abs(new_truth - truth) < 1e-6:
            break
        truth = new_truth
    return truth
```

Use case: when 3+ sources provide numerical values for the same metric and hand-tuned weights aren't discriminating. Falls back to evidence-weighted scoring (2.1) for role/entity conflicts where Gaussian assumptions don't apply.

### 2.2 Decision Rule (Ratio-Based)
If top_score < 0.50: return NULL or doc fallback (no confident answer)
If top_score / runner_up_score > 1.25: select top
If > 1.10: select top but flag low confidence
Else: mark contested, return split evidence

### 2.3 Temporal Supersession Logic
Use valid_from, valid_to, superseded_by to treat non-overlapping facts as sequential, not conflicting.

**Important:** Temporal supersession operates on **normalized time periods** (output of 3.1a), not raw date strings.

### 2.4 Resolution Cascade (Ordered)
1. Score candidates using 2.1 (or 2.1a for numerical conflicts)
2. Apply ratio threshold from 2.2
3. If contested: check temporal supersession (2.3)
4. If still contested on a 1-to-1 relation: apply IAR -> return NULL + doc fallback
5. If still contested on an N-to-N relation: return all candidates with scores

---

## Component 3: Metric Normalizer + Canonicalizer
Handle numeric facts with structured schema, verification, canonicalization, and hierarchy-aware classification.

### 3.1 Schema-Guided Extraction (Pydantic + Verification)
Add a typed schema for metrics:
- value (numeric)
- unit (normalized: B, M, K, %, count)
- currency (ISO 4217)
- time_period (normalized — see 3.1a)
- source_date (when the document was published)
- reporting_period (what the metric measures — this is what conflict detection compares)
- scope (entity, division, segment, geography)
- measurement_basis (annual, quarterly, lifetime, per-unit, cumulative)
- target_vs_actual

Run a second-pass verification agent to validate units and scalar values.
Conflict detection and temporal supersession compare **reporting_period**, not source_date.

### 3.1a Temporal Period Normalizer
Normalize all temporal expressions to comparable (start_date, end_date) tuples before conflict detection.

```python
TEMPORAL_PATTERNS = {
    # Fiscal quarters
    r"Q([1-4])\s*(\d{4})":          lambda m: quarter_to_range(int(m[1]), int(m[2])),
    r"([1-4])Q\s*(\d{4})":          lambda m: quarter_to_range(int(m[1]), int(m[2])),
    r"first quarter\s*(\d{4})":     lambda m: quarter_to_range(1, int(m[1])),
    r"second quarter\s*(\d{4})":    lambda m: quarter_to_range(2, int(m[1])),
    r"third quarter\s*(\d{4})":     lambda m: quarter_to_range(3, int(m[1])),
    r"fourth quarter\s*(\d{4})":    lambda m: quarter_to_range(4, int(m[1])),

    # Fiscal/calendar years
    r"FY\s*(\d{4})":               lambda m: (f"{m[1]}-01-01", f"{m[1]}-12-31"),
    r"(\d{4})\s*annual":           lambda m: (f"{m[1]}-01-01", f"{m[1]}-12-31"),
    r"CY\s*(\d{4})":              lambda m: (f"{m[1]}-01-01", f"{m[1]}-12-31"),

    # Half years
    r"H([12])\s*(\d{4})":         lambda m: half_to_range(int(m[1]), int(m[2])),
    r"([12])H\s*(\d{4})":         lambda m: half_to_range(int(m[1]), int(m[2])),

    # Month ranges
    r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[-–](Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(\d{4})":
        lambda m: month_range(m[1], m[2], int(m[3])),

    # Standalone year (assume calendar year)
    r"^(\d{4})$":                  lambda m: (f"{m[1]}-01-01", f"{m[1]}-12-31"),
}

def temporal_relationship(p1, p2):
    """Classify the relationship between two normalized periods."""
    if p1 == p2:
        return "IDENTICAL"
    elif p1.end <= p2.start or p2.end <= p1.start:
        gap = min(abs((p2.start - p1.end).days), abs((p1.start - p2.end).days))
        return "ADJACENT" if gap < 5 else "DISJOINT"
    elif p1.start >= p2.start and p1.end <= p2.end:
        return "CONTAINED_IN"    # p1 is inside p2 (e.g., Q1 inside FY)
    elif p2.start >= p1.start and p2.end <= p1.end:
        return "CONTAINS"        # p1 contains p2
    else:
        return "OVERLAPPING"
```

**Why this matters:** Without normalization, "Q1 2024" and "first quarter of 2024" are different strings. Conflict rule 1.2.2 ("two facts overlap in time but disagree") cannot fire. Temporal supersession (2.3) cannot determine adjacency. The aggregation planner (4.1) cannot determine if Q1+Q2+Q3+Q4 should sum to FY.

If temporal extraction fails (no recognizable pattern), set `time_period = UNKNOWN` and flag for LLM-assisted classification in the aggregation planner.

### 3.2 Table-Aware Parsing
Use layout-aware parsing or table reconstruction (Docling) to preserve table structure before extraction.

### 3.2a Metric Canonicalization Mapping
Map synonymous metric terms to canonical keys before resolution or compute.

```python
METRIC_CANONICAL_MAP = {
    # Revenue family
    "revenue": "REVENUE",
    "net revenue": "REVENUE",
    "net sales": "REVENUE",
    "sales": "REVENUE",
    "top-line": "REVENUE",
    "total revenue": "REVENUE",
    "annual revenue": "REVENUE",

    # Revenue — contract/relationship (see note below)
    "contract value": "CONTRACT_VALUE",
    "relationship value": "RELATIONSHIP_VALUE",
    "total contract value": "CONTRACT_VALUE",

    # Revenue subtypes (segment-level)
    "commercial revenue": "REVENUE.COMMERCIAL",
    "defense revenue": "REVENUE.DEFENSE",
    "services revenue": "REVENUE.SERVICES",

    # Capex family
    "capex": "CAPEX",
    "capital expenditure": "CAPEX",
    "capital spending": "CAPEX",

    # Other
    "backlog": "BACKLOG",
    "unfilled orders": "BACKLOG",
    "order backlog": "BACKLOG",
    "headcount": "HEADCOUNT",
    "employee count": "HEADCOUNT",
    "fte": "HEADCOUNT",
    "full-time equivalents": "HEADCOUNT",
}
```

**Note on "contract value" vs "revenue":** These are NOT always the same metric. A $10B contract over 5 years generates ~$2B/year in revenue. The flat map in the prior revision mapped both to REVENUE, which would create false conflicts. They are now separate canonical keys. The metric hierarchy (3.2c) defines how they relate.

Apply mapping both to extracted metrics and query intent terms.
If an extracted metric term is not in the map, use embedding similarity against canonical key descriptions as fallback, with a confidence threshold. Below threshold: leave as raw string and flag for manual review.

### 3.2b Metric Normalization Sequencing
For metric queries, normalize units and canonicalize metric names before conflict detection to avoid false conflicts (e.g., "10.2B" vs "10,200M"). Structured compute runs after conflict resolution.

Pipeline order:
1. Extract raw (value, unit, metric_name, time_expression, scope)
2. Normalize units (3.1)
3. Normalize time periods (3.1a)
4. Canonicalize metric names (3.2a)
5. Detect conflicts (Component 1) — now operating on canonical coordinates
6. Resolve conflicts (Component 2)
7. Classify conflict vs complement (4.1)
8. Execute structured compute (4.2)

### 3.2c Metric Hierarchy
Define parent-child relationships between canonical metrics. This is the structure that enables the aggregation planner (4.1) to distinguish hierarchical components from conflicts.

```python
METRIC_HIERARCHY = {
    "REVENUE": {
        "children": ["REVENUE.COMMERCIAL", "REVENUE.DEFENSE", "REVENUE.SERVICES"],
        "aggregation": "SUM",
        "description": "Total revenue is the sum of segment revenues"
    },
    "CAPEX": {
        "children": ["CAPEX.FACILITY", "CAPEX.EQUIPMENT", "CAPEX.IT"],
        "aggregation": "SUM",
        "description": "Total capex is the sum of category-level capex"
    },
    "HEADCOUNT": {
        "children": ["HEADCOUNT.ENGINEERING", "HEADCOUNT.SALES", "HEADCOUNT.OPERATIONS"],
        "aggregation": "SUM",
        "description": "Total headcount is the sum of departmental headcounts"
    },
}

# Cross-metric relationships (not parent-child, but related)
METRIC_RELATIONSHIPS = {
    ("CONTRACT_VALUE", "REVENUE"): {
        "type": "RELATED_NOT_EQUIVALENT",
        "note": "Contract value is total deal size; revenue is periodic recognition. Never treat as conflict."
    },
    ("RELATIONSHIP_VALUE", "REVENUE"): {
        "type": "RELATED_NOT_EQUIVALENT",
        "note": "Relationship value may aggregate across multiple contracts and time periods."
    },
    ("BACKLOG", "REVENUE"): {
        "type": "RELATED_NOT_EQUIVALENT",
        "note": "Backlog is unfilled portion of contracts; not equivalent to recognized revenue."
    },
}
```

**Why this matters:** Without hierarchy, two REVENUE values for Boeing — "$66.6B total" and "$25.3B commercial" — both canonicalize to the REVENUE family but are NOT conflicts. The hierarchy tells the aggregation planner that REVENUE.COMMERCIAL is a child of REVENUE, so the $25.3B is a component of $66.6B, not a rival estimate.

### 3.3 Metric Resolution
When multiple metric values exist for same scope:
- apply conflict resolver with temporal + source trust weighting
- do not default to most frequent value

---

## Component 4: Aggregation Planner + Structured Compute
Orchestrate multi-step aggregation queries: decompose, classify relationships between facts, resolve conflicts per group, then compute.

### 4.0 Query Decomposition for Aggregation
Aggregation queries require multi-step processing that the routing layer must recognize and decompose before entering the conflict/resolution pipeline.

```
If query_type == "aggregation":
    1. Identify the target metric (e.g., "total value", "combined revenue")
    2. Identify the entity set (e.g., "top 3 customers", "all projects", "each division")
    3. Identify the aggregation operation (SUM, AVG, MAX, COUNT, TOP-N)
    4. Decompose into sub-queries:
       a. Entity enumeration: "List all customer entities"
       b. Per-entity retrieval: For each entity, "What is {entity}'s {metric}?"
       c. Each sub-query enters the pipeline independently (grounding → conflict detection → resolution)
    5. Merge resolved per-entity results into the aggregation planner (4.1)
```

**Why decomposition matters:** "What is the total value of top 3 customer relationships?" sent as a single query returns a mixed bag of facts about multiple entities. The conflict detector can't distinguish "two values for Boeing" (conflict) from "one value for Boeing + one value for Airbus" (complement) without knowing the query structure. Decomposition makes entity boundaries explicit.

For simple queries where the entity set is already known from tree retrieval, decomposition is implicit — the tree already returns per-entity results. Explicit decomposition is needed when:
- The entity set must be enumerated ("all customers", "every project")
- The query requires ranking before aggregation ("top 3 by value")
- The query spans multiple metric types ("total revenue and capex")

### 4.1 Fact Coordinate Classification
After retrieval and resolution, classify the relationship between every pair of resolved facts that will enter the aggregation.

Each fact carries a **dimensional coordinate**: (entity, canonical_metric, normalized_period, scope, measurement_basis).

```python
def classify_fact_pair(fact_a, fact_b):
    """
    Classify the relationship between two resolved facts.
    Runs AFTER metric canonicalization (3.2a) and temporal normalization (3.1a).
    """

    # 1. Different entities → always complementary for cross-entity aggregation
    if fact_a.entity != fact_b.entity:
        return "COMPLEMENT_CROSS_ENTITY"

    # Same entity from here down
    metric_rel = metric_relationship(fact_a.canonical_metric, fact_b.canonical_metric)
    time_rel = temporal_relationship(fact_a.period, fact_b.period)

    # 2. Same canonical metric + same period + same scope → CONFLICT
    if metric_rel == "EQUIVALENT" and time_rel == "IDENTICAL" and fact_a.scope == fact_b.scope:
        return "CONFLICT"

    # 3. Same canonical metric + adjacent/disjoint periods → temporal series
    if metric_rel == "EQUIVALENT" and time_rel in ("ADJACENT", "DISJOINT"):
        return "COMPLEMENT_TEMPORAL"       # Q1 + Q2 can be summed for half-year

    # 4. Same canonical metric + one period contains the other → subsumption
    if metric_rel == "EQUIVALENT" and time_rel in ("CONTAINED_IN", "CONTAINS"):
        return "SUBSUMPTION"               # Q1 is inside FY — don't double-count

    # 5. One metric is child of the other in hierarchy → hierarchical component
    if metric_rel == "PARENT_CHILD":
        return "HIERARCHICAL"              # REVENUE.COMMERCIAL is part of REVENUE

    # 6. Same canonical metric + different scopes (e.g., region A vs region B)
    if metric_rel == "EQUIVALENT" and time_rel == "IDENTICAL" and fact_a.scope != fact_b.scope:
        return "COMPLEMENT_DIMENSIONAL"    # North America + Europe → sum for global

    # 7. Related but not equivalent metrics → do not compare or aggregate
    if metric_rel == "RELATED_NOT_EQUIVALENT":
        return "UNRELATED"                 # CONTRACT_VALUE vs REVENUE

    # 8. Unknown relationship → flag for LLM classification
    return "UNCERTAIN"


def metric_relationship(metric_a, metric_b):
    """Determine relationship using canonical map and hierarchy."""
    if metric_a == metric_b:
        return "EQUIVALENT"
    if is_parent_child(metric_a, metric_b):
        return "PARENT_CHILD"
    rel = METRIC_RELATIONSHIPS.get((metric_a, metric_b)) or METRIC_RELATIONSHIPS.get((metric_b, metric_a))
    if rel and rel["type"] == "RELATED_NOT_EQUIVALENT":
        return "RELATED_NOT_EQUIVALENT"
    return "UNKNOWN"
```

### 4.1a LLM Fallback for UNCERTAIN Classifications
When the dimensional classifier returns UNCERTAIN (metrics not in the canonical map, or ambiguous scope), use a few-shot LLM classifier:

```
Prompt: Given two data points about the same entity, classify their relationship.

Fact A: {entity} | {metric} | {value} | {period} | Source: {source}
Fact B: {entity} | {metric} | {value} | {period} | Source: {source}

Classify as ONE of:
- CONFLICT: Same data point, different values (rival estimates)
- COMPLEMENT_TEMPORAL: Same metric, different time periods (can sum)
- COMPLEMENT_DIMENSIONAL: Same metric, different segments/scopes (can sum)
- SUBSUMPTION: One value already includes the other (don't double-count)
- UNRELATED: Different metrics entirely (don't compare)

Output: {"classification": "...", "reasoning": "...", "confidence": 0.0-1.0}
```

If LLM confidence < 0.75, do not aggregate — return all values with provenance and let the user decide.

### 4.2 Structured Compute Path (Mandatory)
For aggregation queries, compute programmatically rather than via LLM.

```
Input: classified, resolved facts from 4.1

Step 1: For each entity, select the representative value
  - If only one resolved value: use it
  - If CONFLICT within entity: already resolved by Component 2
  - If COMPLEMENT_TEMPORAL: sum if query asks for total across periods
  - If SUBSUMPTION: use the broader value, discard the narrower
  - If HIERARCHICAL: use parent value if available, else sum children

Step 2: Apply aggregation operation
  - SUM: total = sum(per_entity_values)
  - TOP-N: sort descending, take first N, then sum if requested
  - AVG: mean(per_entity_values)
  - COUNT: len(per_entity_values)

Step 3: Compute coverage
  - For explicit "top N": coverage = retrieved_entities / N
  - For "all": coverage = retrieved_entities / known_entity_count
  - If coverage < 0.8: return partial result with caveat

Step 4: Cross-check against authoritative total
  If both component values and a reported_total exist:
    computed = aggregate(components)
    discrepancy = abs(computed - reported_total) / reported_total
    if discrepancy < 0.05: return computed (verified)
    elif discrepancy < 0.15: flag discrepancy, return reported_total, log for investigation
    else: possible missing component or wrong values — return reported_total with warning

Step 5: Return result + provenance chain + coverage + confidence
```

**Tolerance note:** The cross-check threshold is 5% (not 2% from prior revision). Extraction rounding ("$1.5B" for $1.52B) and currency conversion variance mean 2% is too tight and would false-flag clean aggregations. Use 5% for "verified match" and 15% for "investigate."

---

## Component 5: Hybrid Routing (Updated)
Routing must include entity grounding, conflict risk, and query decomposition.

### 5.1 Routing Signals
1. conflict_risk score from Conflict Detector
2. graph_density score for anchor
3. evidence_strength score for KG candidates
4. entity_grounding_valid (true/false)
5. doc_entropy score
6. entity_linking_certainty score
7. query_type (lookup / aggregation / ranking / comparison)
8. requires_decomposition (true/false)

### 5.2 Routing Logic
1. **Decomposition check first:** If query_type == "aggregation" or "ranking", decompose per 4.0 before routing sub-queries.
2. If entity_grounding_valid == false -> doc search required
3. If conflict_risk high or doc_entropy high -> KG + docs, then conflict resolve
4. If graph_density high and evidence strong -> tree traversal allowed
5. If graph weak -> docs first, KG as supporting evidence
6. If entity_linking_certainty low -> prefer doc fallback

### 5.3 Doc Fallback Query Construction
1. Extract named entities from query
2. Add relationship keywords (supplier, customer, agreement, offtake)
3. Require returned chunks contain all named entities
4. If none match, relax to primary entity only

---

## Ambiguity-Aware Prompting
Provide synthesis templates based on conflict state:
- Conflict detected: "Multiple sources disagree. Here is each value and provenance."
- Low confidence: "Insufficient high-confidence evidence. Best known answer is..."
- Doc fallback: "Based on retrieved documents, the answer is..."
- Grounding rejection: "Structured graph did not contain a direct relationship for [query entity]. Using document evidence..."
- Partial coverage: "Found values for {N} of {expected} entities. Partial result: ..."

---

## NULL > Wrong Principle
If KG and doc paths both fail grounding or confidence thresholds, return "insufficient data" rather than a confident guess.

---

## Observability
Every answer must carry a decision trace:
1. routing_path (including decomposition steps if applicable)
2. entity_grounding pass/fail + reasons
3. conflict_detected + conflict group details
4. **fact_coordinate_classification** per fact pair (CONFLICT / COMPLEMENT / SUBSUMPTION / etc.)
5. resolution_method: score-based / CATD / contested / NULL
6. **aggregation_plan**: which values were summed, which were excluded, why
7. confidence_level
8. source_documents
9. coverage_percent (for aggregation queries)

Traces should be stored in a structured table to support tuning and regression analysis.
Log score component breakdowns for each candidate to enable weight calibration.

---

## Expanded Test Plan
Category 0: Regression gate (mandatory)
- All currently passing questions must remain passing
- Any regression blocks deploy
- Use decision traces to identify cause

Category 1: Regression recovery
- Q3, Q14, Q25, Q51, Q100

Category 2: Metric normalization + aggregation
- Q40, Q66, Q79, Q100

Category 3: Doc fallback triggering
- Q7, Q18, Q26, Q27, Q38, Q67

Category 4: Entity-grounded retrieval validation
- Q17, Q48, Q83, Q71, Q37

Category 5: Negative test
- Inject a high-confidence wrong fact and verify system returns NULL or fallback

Category 6: Table parsing test
- Verify table metrics extracted correctly

Category 7: End-to-end interaction tests
- Grounding rejects correct candidate, passes wrong one -> does resolver still catch it?
- Conflict detection sees only 1 candidate after grounding filters -> does it miss the real conflict?
- Metric normalization succeeds but extracted value came from wrong entity context -> caught?

Category 8: Aggregation classification tests
- Two values for same entity, same metric, same period -> classified as CONFLICT
- Values for different entities, same metric -> classified as COMPLEMENT
- Q1 + Q2 + Q3 + Q4 values -> classified as COMPLEMENT_TEMPORAL, sum matches FY
- Segment revenue + total revenue for same entity -> classified as HIERARCHICAL, not summed
- Contract value vs annual revenue for same entity -> classified as UNRELATED, not compared
- Three sources provide similar values ($66.5B, $66.6B, $66.7B) -> rounding variance, not conflict

---

## Implementation Plan

### Workstream A: Conflict Path
- Cardinality registry + conflict detection + evidence-weighted scoring
- Temporal supersession + IAR semantics + CATD for numerical conflicts
- Test: regression recovery suite

### Workstream B: Grounding Path
- Entity grounding validation + routing fallback + NULL > wrong
- Doc fallback query construction rules
- Test: cross-wiring suite + doc fallback suite

### Workstream C: Metrics + Canonicalization
- Pydantic schema + verification pass
- **Temporal period normalizer (3.1a)**
- **Metric canonical map (3.2a) + metric hierarchy (3.2c)**
- Table-aware parsing
- Test: metric normalization + canonicalization suite

### Workstream D: Aggregation Pipeline
- **Query decomposition for aggregation queries (4.0)**
- **Fact coordinate classifier (4.1) + LLM fallback (4.1a)**
- Structured compute path with cross-check (4.2)
- Test: aggregation classification suite (Category 8)

### Recommended Build Order (One Week)
Day 1-2: Workstream C (canonicalization + temporal normalization — unblocks everything else)
Day 2-3: Workstream A (conflict detection + resolution — the scoring infrastructure)
Day 3-4: Workstream D (aggregation planner + classifier — the core novel component)
Day 4-5: Workstream B (grounding + routing — stabilization and fallback)
Day 5: Integration testing across all categories, regression gate validation

---

## Success Metrics
1. Recover 5 regressions via conflict resolution + validation.
2. Reduce cross-wiring errors by 3-5 questions.
3. Eliminate aggregation errors via structured compute with correct value selection.
4. Reduce FORMAT failures via schema validation.
5. Lower MISMATCH rate, even if NOT_FOUND rises temporarily.
6. Stable performance across re-extraction runs.
7. **Aggregation classification accuracy >90% on Category 8 test cases.**
8. **Zero double-counting errors (the subsumption and hierarchy cases).**

---

## Implementation Risks and Mitigations

### Risk 1: Entity grounding depends on entity resolution quality
Direct path validation requires accurate resolution of query entities (e.g., "GreenHydrogen facility"). If resolution confidence is low, grounding may fail silently or reject correct paths.

Mitigation:
- Use entity embeddings and alias tables for fuzzy matching.
- If entity_linking_certainty < threshold, skip grounding and route directly to doc fallback with entity keywords.

### Risk 2: IAR semantics may overcorrect on noisy re-extraction
IAR can suppress correct facts when a noisy duplicate exists, converting a correct answer into NULL.

Mitigation:
Apply IAR only at the end of the resolution cascade:
1) score candidates
2) apply ratio threshold
3) check temporal supersession
4) if still contested, then apply IAR and fall back to docs

### Risk 3: Automatic constraint mining (PaTeCon) may not be viable at current scale
Constraint mining requires sufficient data density to discover functional dependencies. The current corpus may be too small.

Mitigation:
- Keep manual registry as authoritative in current phase.
- Defer PaTeCon to future scalability work once multi-org corpora exist.

### Risk 4: Structured compute requires coverage definition
Aggregations fail if the system cannot determine component coverage.

Mitigation:
Define coverage rules:
- For explicit "top N": coverage = retrieved_components / N
- If coverage < 0.8, return partial result with caveat or fall back to docs
- Prefer authoritative total node over computed sum if available

### Risk 5: Missing regression gate can reintroduce failures
New logic may regress questions currently passing.

Mitigation:
Add Category 0 regression gate:
- All currently passing questions must remain passing
- Any regression blocks deploy
- Use decision trace logs to identify cause

### Risk 6: Ambiguity-aware prompting lacks grounding-rejection template
Without a grounding-specific template, users may not understand why KG results were rejected.

Mitigation:
Add a dedicated synthesis template:
"Structured graph did not contain a direct relationship for [query entity]. Using document evidence..."

### Risk 7: Doc fallback search quality is under-specified
If fallback query construction is weak, NOT_FOUND persists.

Mitigation:
- Require all named entities in fallback chunks where possible
- Relax only when no chunks match
- Log fallback query and match rate for tuning

### Risk 8: Metric canonical map may not cover domain-specific terms
The corpus may use metric terms not in the seed map, causing uncanonicalized metrics to bypass conflict detection.

Mitigation:
- Use embedding similarity fallback for unmapped terms (3.2a)
- Log every unmapped metric term; review weekly and add to map
- Set a confidence threshold for embedding matches — below threshold, flag rather than silently map

### Risk 9: Temporal normalization fails on ambiguous expressions
"2024" could mean FY2024 (Jan-Dec), fiscal year 2024 (Oct 2023 - Sep 2024), or calendar year. Fiscal year definitions vary by organization.

Mitigation:
- Default to calendar year unless corpus metadata specifies fiscal year end month
- Add an org-level config: `FISCAL_YEAR_END_MONTH = 12` (or 9 for Oct-Sep fiscal years)
- If temporal expression is truly ambiguous, set period to UNKNOWN and route to LLM classification

### Risk 10: Query decomposition adds latency for simple aggregations
Explicit decomposition into sub-queries adds retrieval round-trips.

Mitigation:
- Skip decomposition when tree retrieval already returns per-entity results (the common case)
- Only trigger explicit decomposition when entity set must be enumerated or query spans multiple metric types
- Set a latency budget: if decomposition would exceed 3 sub-queries, prefer single-pass retrieval with post-hoc classification
