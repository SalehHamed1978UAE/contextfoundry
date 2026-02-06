# Aggregation Conflict Resolution - ChatGPT Solutions Analysis

**Problem:** Q100 failure - "What is the total value of top 3 customer relationships?"

**Root cause:** Boeing has conflicting revenue values ($2.3B vs $1.8B), system arbitrarily picked $1.8B, leading to incorrect total ($4.2B instead of $4.7B).

**Key constraint:** Must distinguish **conflicting values** (same metric, same period) from **complementary values** (different periods like Q1 vs Q2).

---

## ChatGPT's 4 Novel Solutions

### Solution 1: Graph-Based Conflict Resolution with Temporal Reasoning

**Core innovation:** Model facts as a knowledge graph that **retains all candidates** with context (source, time, confidence) instead of overwriting.

**Why it works:**
- Stores multiple values per entity with temporal metadata
- Uses metric ontology to classify if values conflict or complement
- Applies "single-truth" assumption per property while preserving alternative facts
- Picks canonical value based on recency, confidence, or validity intervals

**Implementation:**

1. **Schema extensions:**
```python
# New table: customer_metric
CREATE TABLE customer_metric (
    entity_id UUID,
    metric_type VARCHAR,  # "annual_revenue", "contract_value"
    value DECIMAL,
    period VARCHAR,       # "annual", "Q1", "Q2"
    year INTEGER,
    source_id UUID,
    confidence FLOAT,
    evidence_count INTEGER
)
```

2. **Conflict vs. complementary logic:**
```python
def resolve_conflict(entity_values):
    # Group by canonical metric
    canonical_groups = group_by_canonical_metric(entity_values)

    for metric, values in canonical_groups.items():
        # Within each metric, check time period
        if has_temporal_info(values):
            # Pick most recent
            return max(values, key=lambda v: v.year)
        else:
            # Use source reliability + evidence
            return max(values, key=lambda v:
                v.evidence_count * 0.6 + v.confidence * 0.4
            )
```

3. **Metric canonicalization:**
```python
CANONICAL_METRICS = {
    "annual contract value": "Revenue",
    "relationship value": "Revenue",
    "contract value": "Revenue",
    "Q1 revenue": "Revenue_Q1",  # Different from annual
    "Q2 revenue": "Revenue_Q2",
}
```

4. **SQL integration:**
```sql
WITH per_customer AS (
    SELECT
        source_entity_id AS customer_id,
        resolve_conflict(array_agg(value ORDER BY confidence DESC)) AS chosen_value
    FROM customer_metric
    WHERE metric_type='Revenue'
    GROUP BY customer_id
)
SELECT SUM(chosen_value)
FROM (
    SELECT chosen_value FROM per_customer
    ORDER BY chosen_value DESC
    LIMIT 3
) top3;
```

**Trade-offs:**
- ✅ Better precision: Uses richer context (source, time, evidence)
- ✅ Temporal reasoning: Handles time-evolving data gracefully
- ✅ Complementary data: Preserves Q1+Q2 revenues as distinct
- ⚠ Complexity: Requires metric ontology and temporal logic
- ⚠ Edge cases: May pick wrong value if assumptions fail (e.g., revenue declined)
- ⚠ Performance: Slight overhead, mitigated by materialized views

**Alignment with our plan:** This is **very similar to our Week 1 CRH approach**, but adds explicit temporal reasoning and metric canonicalization.

---

### Solution 2: Ensemble Heuristic Pipeline for Value Reconciliation

**Core innovation:** Combine **multiple lightweight heuristics** (ensemble voting) to pick correct value.

**Why it works:**
- Each heuristic offers different perspective (temporal, source reliability, confidence, magnitude)
- Voting/weighting reduces chance of arbitrary picks
- No heavy training required, just rule-based logic

**Implementation:**

1. **Ensemble heuristics:**
```python
def choose_best(vals_in_period):
    scores = {}
    for val in vals_in_period:
        score = 0

        # Heuristic A: Source reliability (evidence_count)
        if val.evidence_count == max(v.evidence_count for v in vals_in_period):
            score += 2

        # Heuristic B: Confidence score
        if val.confidence >= 0.85:
            score += 1

        # Heuristic C: Recency hints (parse years from text)
        if extract_year(val.evidence_text) == max_year:
            score += 1

        # Heuristic D: Numeric magnitude (larger = newer for growth metrics)
        if val.value > median_value * 1.2:
            score += 1

        scores[val] = score

    return max(scores, key=scores.get)
```

2. **Metric type grouping (LLM-assisted):**
```python
def group_by_metric_type(values):
    """Use GPT-4o-mini to classify metric types."""
    prompt = f"""
    Classify each relationship into a canonical metric category:
    1. $2.3B described as "annual contract value"
    2. $1.8B described as "relationship value"

    Are these the same metric? If yes, what canonical name?
    """
    # LLM returns: "Both are 'Revenue' metrics"

    # Group values by LLM's canonical labels
    return grouped_values
```

3. **Time period grouping:**
```python
def group_by_time_period(vals):
    """Extract temporal info from properties or text."""
    periods = {}
    for val in vals:
        # Check JSONB properties
        period = val.properties.get("period", "unknown")
        year = val.properties.get("year") or extract_year_from_text(val.evidence_text)

        key = f"{year}_{period}"
        periods.setdefault(key, []).append(val)

    return periods
```

**Trade-offs:**
- ✅ Combines multiple signals: More robust than single criterion
- ✅ Quick implementation: Simple rules, no new infrastructure
- ✅ Flexible: Easy to add/adjust heuristics
- ⚠ Maintenance: Rules may need tuning as data patterns change
- ⚠ Imperfect inference: May guess wrong without explicit timestamps
- ⚠ Complementary handling: Must carefully avoid "resolving away" genuine multi-valued data

**Alignment with our plan:** This is **exactly our Week 1 CRH approach** with ensemble scoring! ChatGPT validated our strategy.

---

### Solution 3: LLM-Assisted Reasoning for Conflict Resolution

**Core innovation:** Use GPT-4 directly to **reason about conflicts** and choose correct value.

**Why it works:**
- LLMs understand context and can use evidence text clues (dates, phrases)
- Can handle novel/complex cases that rules miss
- Provides transparency via explanations

**Implementation:**

**Pattern A: Online LLM resolution**
```python
def resolve_with_llm(entity, conflicting_values):
    prompt = f"""
    {entity} has multiple reported customer value figures:
    (a) $2.3B described as an annual contract value in one document (3 sources)
    (b) $1.8B described as a relationship value in another document (1 source)

    For calculating the total value of the top 3 customer relationships as of now,
    which number should we use for {entity}? Why?

    Use only the provided facts. Answer in format: USE <value>
    """

    response = gpt4o_mini.complete(prompt)
    # Parse: "USE 2.3B" or structured JSON
    return parse_llm_decision(response)
```

**Pattern B: Offline LLM resolution (pre-computation)**
```python
# Preprocessing step (nightly batch)
def precompute_canonical_values():
    conflicts = detect_all_conflicts()

    for entity, values in conflicts:
        canonical = resolve_with_llm(entity, values)

        # Store in new table
        db.insert("entity_canonical_value", {
            "entity_id": entity.id,
            "metric": "revenue",
            "canonical_value": canonical,
            "reasoning_note": "contract value 2022 supersedes older figure"
        })

    # Query time: just use precomputed values
```

**LLM explaining aggregation logic:**
```python
# Final answer generation with self-check
synthesis_prompt = f"""
Generate the answer for: "What is the total value of top 3 customer relationships?"

Available values:
- Boeing: $2.3B (annual contract, 3 sources) OR $1.8B (relationship value, 1 source)
- Airbus: $1.5B
- DoD: $900M

Ensure to explain which values you used and why any duplicates were excluded.
Each entity should appear once.
"""

# LLM response:
# "The total is $4.7B (Boeing: $2.3B, Airbus: $1.5B, DoD: $0.9B).
#  We used Boeing's $2.3B contract value, not the $1.8B figure,
#  as it represents the current contract with higher evidence."
```

**Trade-offs:**
- ✅ Powerful reasoning: Utilizes context that algorithms miss
- ✅ Reduced manual rules: Prompt engineering instead of complex heuristics
- ✅ Transparency: LLM explains which values were used
- ⚠ Latency/Cost: API calls can be slow (mitigated by offline processing or caching)
- ⚠ Correctness: LLMs can hallucinate, need constrained prompts
- ⚠ Dependency: Relies on external API availability

**Alignment with our plan:** This is **NEW** - we hadn't considered using LLM for conflict resolution itself, only for extraction/synthesis. Interesting augmentation!

---

### Solution 4: Uncertainty-Aware Aggregation (Propagate Conflicts)

**Core innovation:** Instead of picking one value, **propagate uncertainty** to final answer via ranges.

**Why it works:**
- Avoids confidently reporting wrong numbers
- Informs user of data quality issues
- Preferable to single potentially-wrong figure in analytics contexts

**Implementation:**

1. **Mark conflicts as uncertain:**
```python
def resolve_value_conflict(entity_values):
    if len(entity_values) == 1:
        return entity_values[0].value  # No conflict

    # Try heuristics first
    best_guess = apply_heuristics(entity_values)

    if confidence_in_guess < 0.7:
        # Return range instead of single value
        return {
            "min": min(v.value for v in entity_values),
            "max": max(v.value for v in entity_values)
        }
    else:
        return best_guess
```

2. **Aggregate with ranges:**
```python
def aggregate_top_3_with_uncertainty(customer_values):
    # For each customer, get value or range
    boeing_value = {"min": 1.8, "max": 2.3}  # Uncertain
    airbus_value = 1.5  # Certain
    dod_value = 0.9  # Certain

    # Calculate best-case and worst-case totals
    best_case = 2.3 + 1.5 + 0.9  # $4.7B
    worst_case = 1.8 + 1.5 + 0.9  # $4.2B

    return f"${worst_case}-{best_case}B"
```

3. **Answer format:**
```python
answer = """
The total value of the top 3 relationships is about $4.7B,
but could be as low as $4.2B due to conflicting reports for Boeing.

Boeing's value is uncertain between $1.8B and $2.3B.
If Boeing's value is $2.3B, top 3 sum to $4.7B.
If it's $1.8B, sum is $4.2B.
"""
```

**Trade-offs:**
- ✅ No wrong answers: Avoids trap of confidently wrong number
- ✅ Easy to implement: Just track (min, max) tuples
- ✅ General applicability: Works for avg, count, etc.
- ⚠ User experience: Not a crisp number, may confuse some users
- ⚠ When to use: Only when conflict can't be resolved with confidence
- ⚠ Top-N logic: Composition of "top 3" might itself be uncertain
- ⚠ Perceived indecisiveness: System seems less "smart"

**Alignment with our plan:** This is **NEW** - we hadn't considered uncertainty propagation. Could be valuable fallback for unresolvable conflicts.

---

## Comparison with Our Week 1 Plan

| Aspect | Our Week 1 Plan | ChatGPT Solutions | Verdict |
|--------|----------------|-------------------|---------|
| **Core approach** | CRH scorer with SOURCE_TRUST + cardinality | Solutions 1 & 2: Same approach! | ✅ Validated |
| **Metric canonicalization** | Not explicitly mentioned | Solution 1: Canonical metric mapping | 🆕 Add to Week 1 |
| **Temporal reasoning** | Basic (via evidence metadata) | Solution 1: Explicit time period grouping | 🆕 Enhancement |
| **LLM for resolution** | Not considered | Solution 3: LLM resolves conflicts | 🆕 Optional augmentation |
| **Uncertainty propagation** | Not considered | Solution 4: Return ranges for uncertain values | 🆕 Fallback strategy |
| **Implementation time** | 12 hours (Week 1) | "Implementable in <1 week" | ✅ Aligned |

---

## Key Insights from ChatGPT

### 1. Metric Canonicalization is Critical

ChatGPT emphasizes that "annual contract value" and "relationship value" must be mapped to a canonical "Revenue" metric to detect conflicts.

**Implementation:**
```python
# Add to ontology YAML
metric_canonical_mapping:
  "annual revenue": "Revenue"
  "contract value": "Revenue"
  "relationship value": "Revenue"
  "quarterly revenue": "Revenue_Quarterly"  # Different from annual
  "Q1 revenue": "Revenue_Q1"
  "Q2 revenue": "Revenue_Q2"
```

**Why critical:** Without this, system can't tell if two values represent the same metric or different ones (e.g., annual vs quarterly).

### 2. Temporal Grouping Prevents Over-Resolution

ChatGPT warns: "We must ensure not to 'resolve away' genuine multi-valued data."

**Example:**
- Boeing Q1 revenue: $600M
- Boeing Q2 revenue: $700M
- Query: "What's Boeing's total revenue for 2024?"
- **Correct:** Sum both → $1.3B
- **Wrong:** Conflict resolution picks one → $700M

**Solution:** Group by `(metric, period)` before conflict detection.

```python
def detect_conflicts(facts, relationship_type):
    groups = {}
    for fact in facts:
        # Key includes BOTH metric AND period
        key = f"{fact.canonical_metric}:{fact.period}:{fact.year}"
        groups.setdefault(key, []).append(fact)

    # Only groups with >1 fact are conflicts
    return [g for g in groups.values() if len(g) > 1]
```

### 3. Ensemble Voting Exactly Matches Our CRH Approach

ChatGPT's "Heuristic E: Majority vote / ensemble scoring" is identical to our CRH formula:

**ChatGPT's scoring:**
```python
score = (
    2 * (evidence_count == max_evidence) +  # +2 for most evidence
    1 * (confidence >= 0.85) +               # +1 for high confidence
    1 * (is_most_recent) +                   # +1 for recency
    1 * (is_larger_by_20pct)                 # +1 for magnitude
)
```

**Our CRH formula:**
```python
crh_score = (
    0.4 * source_trust +      # Document authority
    0.3 * confidence +        # LLM confidence
    0.3 * log(evidence_count + 1)  # Evidence support
)
```

**Verdict:** Different weightings, same philosophy. ChatGPT's is simpler (integer scores), ours is more nuanced (continuous weights). Both valid!

### 4. LLM-Assisted Resolution is Novel

ChatGPT proposes using GPT-4 to **directly resolve conflicts** by reasoning over evidence text.

**When useful:**
- Temporal info is in unstructured text ("in the latest report", "as of 2023")
- Metric equivalence is ambiguous ("contract value" vs "relationship value")
- Heuristics yield ties or low confidence

**Implementation strategy:**
1. Try heuristics first (fast)
2. If confidence < 0.7, invoke LLM (slow but accurate)
3. Cache LLM decisions for future queries

**Trade-off:** Adds latency, but can handle edge cases rules miss.

### 5. Uncertainty Propagation as Safety Net

ChatGPT's Solution 4 provides a **fallback** when conflicts are truly unresolvable.

**Use case:** When heuristics and LLM both uncertain, return range instead of guessing.

**Example answer:**
```
Q100: "What is the total value of top 3 customer relationships?"

Answer: "The total is approximately $4.7B, but could be as low as $4.2B
due to conflicting data for Boeing ($1.8B vs $2.3B). We recommend
verifying Boeing's current contract value."
```

**Benefit:** Avoids confidently wrong answers, maintains trust.

---

## Recommended Hybrid Strategy

ChatGPT concludes with a **hybrid approach** combining all 4 solutions:

```python
def resolve_aggregation_conflict(entity, values):
    # Step 1: Metric canonicalization (Solution 1)
    canonical_groups = group_by_canonical_metric(values)

    # Step 2: Temporal grouping (Solution 1)
    temporal_groups = group_by_period(canonical_groups)

    # Step 3: Ensemble heuristics (Solution 2)
    for group in temporal_groups:
        if len(group) == 1:
            continue  # No conflict

        best_guess = ensemble_score(group)

        if best_guess.confidence >= 0.7:
            yield best_guess  # Confident resolution
        else:
            # Step 4: LLM fallback (Solution 3)
            llm_decision = resolve_with_llm(entity, group)

            if llm_decision.confidence >= 0.6:
                yield llm_decision
            else:
                # Step 5: Uncertainty propagation (Solution 4)
                yield {
                    "min": min(v.value for v in group),
                    "max": max(v.value for v in group),
                    "uncertain": True
                }
```

**Flow:**
1. Canonicalize metrics → detect true conflicts
2. Apply heuristics → fast resolution for 80% of cases
3. LLM for uncertain cases → handle edge cases
4. Propagate uncertainty → safety net for unresolvable conflicts

**Projected accuracy:** High (correctly picks $2.3B for Boeing in most scenarios)

---

## Integration with Our Week 1 Plan

### Additions to Week 1 Implementation

**1. Add metric canonicalization (2 hours):**

```python
# In ontology YAML
relationships:
  HAS_REVENUE:
    canonical_metric: "Revenue"
    aliases: ["contract_value", "relationship_value", "annual_revenue"]

  HAS_QUARTERLY_REVENUE:
    canonical_metric: "Revenue_Quarterly"
    aliases: ["Q1_revenue", "Q2_revenue", "quarterly_sales"]
```

**2. Add temporal grouping logic (1 hour):**

```python
def group_by_period(facts):
    """Group facts by canonical_metric + period + year."""
    groups = {}
    for fact in facts:
        metric = fact.canonical_metric
        period = fact.properties.get("period", "annual")
        year = fact.properties.get("year", extract_year(fact.evidence_text))

        key = f"{metric}:{period}:{year}"
        groups.setdefault(key, []).append(fact)

    return groups
```

**3. Optional: LLM fallback (3 hours):**

```python
def resolve_with_llm_fallback(entity, conflicting_facts):
    """Use LLM only when heuristics uncertain."""
    heuristic_winner = compute_crh_score(conflicting_facts)

    if heuristic_winner.crh_score > 0.7:
        return heuristic_winner  # Confident

    # Low confidence, invoke LLM
    return llm_resolve_conflict(entity, conflicting_facts)
```

**Updated Week 1 timeline:**
- Original: 12 hours
- **With additions: 15-18 hours** (still ~2 days)

---

## Success Criteria (Updated)

**Must achieve:**
- ✅ Q100 passes (correct Boeing revenue: $2.3B selected over $1.8B)
- ✅ Correct total: $4.7B (not $4.2B)
- ✅ Baseline maintained (no regressions)

**Validation tests:**
1. Boeing conflict: 3 evidence @ 0.9 conf → wins over 1 evidence @ 0.8 conf
2. Temporal grouping: Q1 + Q2 revenues both kept (not resolved as conflict)
3. Metric canonicalization: "contract value" and "relationship value" grouped as same metric
4. Uncertainty fallback: If truly ambiguous, return range instead of guessing

---

## Next Steps

1. **Incorporate metric canonicalization into Week 1 ConflictResolver**
2. **Add temporal grouping to detect_conflicts() logic**
3. **Implement ensemble scoring with ChatGPT's heuristics**
4. **Test on Q100 specifically with Boeing conflict**
5. **Optional: Add LLM fallback for uncertain cases**

**Expected outcome:** Q100 passes, 74% → 77-81% accuracy achieved.
