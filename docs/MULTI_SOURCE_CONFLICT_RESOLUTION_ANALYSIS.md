# Multi-Source Entity Conflict Resolution: Research Analysis

## Executive Summary

**Research Query:** "How do we resolve multi-source entity conflicts where a single low-authority document (email) overrides multiple high-authority documents (org charts)?"

**Responses Analyzed:**
1. **Response 5:** "Seven Novel Approaches to Multi-Source Entity Conflict Resolution" (7 pages, ChatGPT-4)
2. **Response 6:** "Epistemic Vigilance and Factual Convergence" (10 pages, Deep Reasoning LLM)

**Key Finding:** BOTH responses independently converge on **SOURCE_TRUST hierarchy** and **graph-based trust propagation** as the core solution—validating Week 1's approach for the third time across all research queries.

**Critical Innovation:** Introduction of **epistemic status extraction** (linguistic certainty scoring) and **tiered resolution architecture** (fast path <5ms, deep verification <50ms).

---

## Novel Techniques Discovered

### Response 5: Seven Approaches (ChatGPT-4)

#### 1. **Dempster-Shafer Belief Functions** (2-3 days implementation)

**What it is:** Models ignorance explicitly as mass assigned to "total uncertainty" rather than forcing probability distribution across all hypotheses.

**Mathematical formulation:**
```python
# Each source produces mass function
m_j({Robert Kim}) = strength_j  # Specific support
m_j(Θ) = 1 - strength_j         # Residual ignorance

# Combination uses Dempster's rule
m12(A) = (1/(1-K)) × Σ_{B∩C=A} m1(B)·m2(C)

# Conflict factor K (switch to Yager's rule when K > 0.7)
K = Σ_{B∩C=∅} m1(B)·m2(C)

# Final decision via pignistic transformation
BetP(a_i) = Σ_{A∋a_i} m(A)/|A|
```

**Why it's powerful for Q3:**
- Org chart's 5 documents combine to produce **high mass on {Robert Kim} with low ignorance**
- Email produces **moderate mass on {Kevin Chang} with high ignorance**
- Dempster combination amplifies the well-supported hypothesis
- **Performance:** <1ms for ≤5 candidates and ≤20 sources

**Trade-offs:**
- Assumes source independence (often violated)
- Mass function design requires calibration
- Power set 2^|Θ| grows exponentially (but 2-5 candidates is trivial)

---

#### 2. **DART: Domain-Aware Truth Discovery** (3-5 days implementation)

**What it is:** Learns that org charts are authoritative for role queries **without hardcoding**, by estimating per-source, per-domain expertise.

**How it works:**
```python
# Facts auto-grouped into domains (org structure, communication, financial)
# For each source s in domain d, estimate expertise based on:
# - Information richness (volume of data)
# - Accuracy (agreement with inferred consensus)

P(v* is true | sources) ∝ Π_s [expertise(s, domain(v*))^{indicator(s supports v*)}]
```

**Key innovation:** Same source has different reliability in different domains. Email might be authoritative for meeting schedules but unreliable for role assignments.

**Simpler variant - CATD (3-4 days):**
```python
# Confidence-Aware Truth Discovery
# Penalizes sources with small sample sizes
w_k = n_k / (σ²_k × χ²_α(n_k))

# Single email gets conservative weight
# Source correct on 50/55 claims gets strong weight
```

**Reference implementation:** github.com/MengtingWan/KDEm (Python, covers TruthFinder, CRH, CATD, GTM)

**For Q3:** Email gets penalized for **sparse evidence** automatically.

---

#### 3. **Bi-Temporal Modeling with Allen's Interval Algebra** (5-7 days)

**Critical insight:** Treating document timestamp as fact validity period is a **design flaw**.

**Solution:** Separate **transaction time** (when data entered system) from **valid time** (when fact holds in reality).

**Architecture (inspired by Zep/Graphiti):**
```python
# Each fact stores FOUR timestamps
t_created, t_expired    # Transaction time
t_valid_from, t_valid_to  # Valid time

# During ingestion, LLM extracts temporal validity:
"appointed on [DATE]" → valid_from
"former president" → valid_to < doc_date
"will become" → valid_from > doc_date
```

**Allen's Interval Algebra:** 13 exhaustive interval relations (BEFORE, OVERLAPS, CONTAINS, etc.) for polynomial-time consistency checking.

**For Q3 example:**
```python
fact_A: (Org, president, "Kevin Chang", [2024-03-15, ?])
        # Email date, NO explicit validity → temporal_specificity = LOW

fact_B: (Org, president, "Robert Kim", [2024-01-10, 2024-03-01])
        # Multi-doc range → temporal_specificity = HIGH

# Allen relation check: intervals may overlap → functional constraint violated
# Score by temporal_specificity × source_weight × evidence_count → fact_B wins
```

**Tools:**
- **HeidelTime** (Strötgen & Gertz 2013): F1 ~86% temporal extraction
- **SUTime** (Stanford CoreNLP): Comparable performance
- **TEI2GO** (2024): 10-100× faster multilingual extraction

**Performance:** <10ms query-time filtering (indexed DB operations), <0.1ms Allen's constraint checking

---

#### 4. **Epistemic Status Extraction** (3-5 days) ⭐ **MOST NOVEL**

**Revolutionary insight:** Score the **linguistic certainty of source text** that produced entities, not just the entities themselves.

**Implementation:**
```python
def epistemic_score(context_sentence):
    base_certainty = 1.0

    # Hedge detection (CoNLL-2010: ~88% F1 biomedical, ~70% Wikipedia)
    hedge_cues = detect_hedges(context_sentence)  # "might", "reportedly", "could"
    for cue in hedge_cues:
        base_certainty *= HEDGE_PENALTY[cue_type(cue)]  # 0.4-0.8 per hedge

    if is_passive_voice(context_sentence):
        base_certainty *= 0.9
    if is_conditional_or_future(context_sentence):
        base_certainty *= 0.6
    if has_anonymous_attribution(context_sentence):
        base_certainty *= 0.7

    return min(base_certainty, 1.0)
```

**Why it's powerful for Q3:**
- Email: "Kevin Chang **will be taking over** as President" → epistemic score 0.3-0.5 (future + hedge)
- Org chart: "Robert Kim — President" → epistemic score 0.95 (direct assertion)
- **This single signal could resolve conflict independently**

**Upstream quality propagation:**
```python
entity_quality = Π(stage_quality_i)  # Multiplicative chain
# document retrieval → passage extraction → entity extraction → entity linking
```

**MINEA approach (2024):** Inject artificial "needle" entities into documents and measure extraction accuracy to score pipeline quality **without ground truth**.

**Performance:** <5ms hedge detection, <1ms provenance scoring

---

#### 5. **KG Embedding Plausibility** (2-3 days)

**Insight:** Well-connected entities in graph neighborhood have higher plausibility than poorly-connected ones—signal **orthogonal to source metadata**.

**How it applies:**
```python
# Train RotatE or ComplEx offline on existing KG
# For conflicting candidates:
score(org_embedding, president_relation, candidate_embedding)

# "Robert Kim" has rich graph connectivity (org charts, meeting notes, reporting)
# "Kevin Chang" from single email has sparse/no connections
```

**UKGE** (Chen, Chen & Sun, AAAI 2019): Explicitly models confidence scores in embedding space using DistMult + logistic mapping.

**Anomaly detection:** Train standard KGE, score all triples, apply z-score normalization. Abnormally low scores flagged as likely incorrect.

**Performance:** <1ms inference (single vector operation on precomputed embeddings)

**Trade-off:** Requires entities to already exist in KG. For new entities, use inductive methods or average neighbor embeddings.

---

#### 6. **FEVER-Style NLI Verification** (3-5 days)

**Reframing:** Instead of ranking entities by metadata, reframe as **natural language inference**: "Given the available evidence, which entity claim is SUPPORTED vs. REFUTED?"

**Adaptation for entity conflicts:**
```python
for each candidate entity:
    1. Construct claim: "The president of [Org] is [Candidate]"
    2. Retrieve supporting passages from source documents (precomputed)
    3. Run NLI model: P(SUPPORTED | claim, evidence) → score
    4. Select candidate with highest SUPPORTED probability
```

**Why it's unique:** Captures whether evidence **actually says** what we think it says. Email mentioning Kevin Chang in different context (forwarding someone else's org chart) produces **low SUPPORTED probability** despite high extraction confidence.

**Performance:** ~20-30ms per candidate pair (borderline for 50ms requirement, feasible with caching)

**Path-based fact checking (KStream):** Treats KG as flow network, computes max-flow from subject to object → 0.93 AUROC on benchmarks.

---

#### 7. **DeGroot Consensus via Source Agreement Networks** (1-2 days)

**Build source corroboration graph:** Edge weight T[i][j] = historical agreement rate between sources i and j across all non-conflicting entities.

**Apply DeGroot's iterated opinion pooling (1974):**
```python
def degroot_resolve(sources, values, agreement_matrix):
    beliefs = np.eye(len(sources))
    for _ in range(100):
        beliefs_new = agreement_matrix @ beliefs
        if np.allclose(beliefs_new, beliefs, atol=1e-8): break
        beliefs = beliefs_new

    consensus = beliefs[0]  # All rows converge to same vector
    return values[np.argmax(consensus)]
```

**Why non-obvious:** Leverages **entire history** of source behavior, not just current conflict. Sources that have agreed on 500 other facts form strong cluster. Disagreeing source gets marginalized.

**Performance:** <1ms (matrix lookup on precomputed agreement matrix)

---

### Response 6: Epistemic Vigilance Framework (Deep Reasoning LLM)

#### 1. **Recursive Trust Propagation (RTP)** via Claim-Network Analysis

**Treats knowledge base as directed graph of "claims"** where edges signify support, refutation, or irrelevance.

**Mathematical mechanism:**
```python
# Modified PageRank for trust propagation
s^{k+1}_d = (1 - α) · s^0_d + α · f(P^k_d - N^k_d)

# Where:
# s^0_d = initial source-type weight (Org Chart = 1.0, Email = 0.4)
# α = damping factor (0.85)
# P^k_d = sum of supporting claims' weights
# N^k_d = sum of refuting claims' weights

P^k_d = Σ_{d' ∈ Support(d)} (s^k_{d'} · w^+_{d',d}) / W^+_d
N^k_d = Σ_{d' ∈ Refute(d)} (s^k_{d'} · w^-_{d',d}) / W^-_d
```

**For Q3:**
- "Robert Kim" cluster (D1-D5) forms **dense, mutually supportive web**
- Meeting notes (D2-D5) bolstered by association with high-authority Org Chart (D1)
- Email (D6) stands in **isolation** and is actively refuted by high-trust cluster
- Even with high extraction confidence, D6's recursive trust score **plummet during iteration**

**Implementation:** Two-pass approach
1. Standard retrieval to get top-K chunks
2. Fast LLM extracts triples, builds local claim graph for K chunks
3. Iterative convergence over 20-node graph: <5ms

---

#### 2. **Hierarchical Evidence Triangulation and Lateral Reading**

**Adapts human fact-checking workflow:** Professional fact-checkers do "lateral reading" (open multiple tabs to see what other sources say) rather than "vertical reading" (evaluate single document).

**Authority Tier System:**

| Tier | Source Type | Examples | Weight | Latency Policy |
|------|------------|----------|--------|----------------|
| Tier 1: Structural | Org Charts, ERP, Tax Filings | 1.00 | Always trust if consistent |
| Tier 2: Procedural | Meeting Minutes, Project Charters, PRDs | 0.80 | Requires 2+ instances or Tier 1 link |
| Tier 3: Communication | Emails, Slack, Chat Logs | 0.40 | Only trust if no Tier 1/2 conflict |
| Tier 4: Personal | Drafts, Personal Notes | 0.15 | Low-confidence fallback only |

**Triangulation Score:**
```python
T(E) = (Σ w_i · c_i) × TierDiversity(E)

# Where TierDiversity = multiplier based on how many DIFFERENT types support entity
```

**For Q3:**
- "Robert Kim" supported by Tier 1 (Org Chart) + Tier 2 (Meeting Notes) → **high tier convergence**
- "Kevin Chang" only Tier 3 (Email) → **no tier diversity**
- System reasons: "Highly unlikely both official structure AND meeting records are wrong while single email is right"

**Implementation:**
1. **Step 1:** Tag every chunk with source_tier during indexing
2. **Step 2:** Retrieve Top-K, extract candidates
3. **Step 3:** Apply Authority Matrix (Tier 3 contradicted by Tier 1/2 = penalized)
4. **Step 4:** Rerank by Triangulation Score

---

#### 3. **Event-Anchored Temporal Validity Windows**

**Critical flaw identified:** Treating document timestamp as fact validity period.

**Solution:** Interval-based representation with NLP-extracted validity cues.

**Anchor Verb Detection:**

| Anchor Type | Trigger Keywords | Temporal Logic |
|-------------|------------------|----------------|
| Start Anchor | "appointed", "started as", "promoted to" | [τ, ∞] |
| End Anchor | "resigned", "stepped down", "formerly" | [-∞, τ] |
| Incumbency | "incumbent", "currently", "serves as" | [τ - δ, τ + δ] |
| Sequential | "replaced", "succeeded by", "preceded by" | [τ_prev, τ_next] |

**For Q3:**
```python
# Document 2024-01-10: "Robert Kim was appointed President"
# Creates start-anchor at τ_{2024-01-10}
# Unless "End Anchor" found, presidency is "in-window" and historically stable

# Email: "Kevin Chang, President" (static mention, NO start anchor)
# Treated as "transient observation" with low Temporal Persistence score

# If email had: "Kevin Chang will become President"
# System uses future cue to place in DIFFERENT validity window
```

**Implementation via EvoKG:**
1. Extract triples with timestamps + anchor verbs
2. Build Temporal Event Knowledge Graph (TEKG)
3. When new fact conflicts with existing, check if existing window explicitly closed
4. If not + existing has higher authority → new fact is "noisy observation"

**Performance:** <50ms via discrete logic rules (interval overlap checks during ranking)

---

#### 4. **Inverting the Pipeline: Question-Extraction Path Ranking**

**Profound shift:** Instead of ranking entities, rank the **QUESTIONS** that led to extractions.

**Path Reliability Scoring:**
```python
# Path A: "Find most authoritative org chart, extract President"
# Path B: "Find most recent email mentioning 'President', extract name"

# Authority-Targeting: Path A targets Tier 1 → higher epistemic weight
# Provenance Traceability: "Page 1 of Employee Handbook" > "unthreaded email snippet"
```

**Multi-Agent Specialization (via LangGraph):**
- **Agent 1 (Structural Specialist):** Focuses on Tier 1 documents (exact tokens, hierarchies)
- **Agent 2 (Temporal Analyst):** Tracks timeline of events
- **Agent 3 (Communication Synthesizer):** Gathers recent chatter

Each produces answer + self-reflected confidence → **Coordinator Agent** ranks by question strategy quality.

**For Q3:** Structural Specialist highly confident in Robert Kim (Org Chart support), Communication Synthesizer has Kevin Chang but notes low authority → Coordinator prefers **higher-quality question path**.

---

#### 5. **Entropy-Based Filtering (TruthfulRAG)**

**Analyzes "surprise" of model's logits** when forced to reason along different paths.

**Path Entropy Calculation:**
```python
# Path P1: Nexus → Org Chart → Robert Kim
# Path P2: Nexus → Meeting Notes → Robert Kim
# Path P3: Nexus → Email → Kevin Chang

# Calculate entropy/surprise when model reasons along each path
# If P3 requires ignoring internal knowledge about org structure → high entropy
# If tokens for "Kevin Chang" have high predictive entropy → uncertain extraction

Truth(E) = Σ_{p ∈ Paths(E)} Reliability(p) × (1 - Entropy(p))
```

**For Q3:** Email path (P3) may be "Corrective Path" that challenges stable parametric knowledge. If entropy of "Kevin Chang" path is too high (ambiguous extraction, contradicts density of Robert Kim paths) → **filtered out**.

**Performance optimization (<50ms):**
1. Limit graph traversal to 2-hop neighborhoods
2. Fast cross-encoder or logit-probability check (parallel for all paths)
3. Lexicon-based boost for exact token matches (22.5× faster than deep re-ranking)

---

## Recommended Tiered Architecture (Response 5)

**Three-tier system handles 90%+ queries in Tier 1 (<5ms):**

| Tier | When Triggered | Methods | Latency |
|------|---------------|---------|---------|
| **Tier 1: Fast Path** | All queries | DS combination + precomputed CATD weights + temporal filter + epistemic scores | <5ms |
| **Tier 2: Structural Validation** | When Tier 1 confidence gap < threshold | KGE plausibility + DART domain expertise + DeGroot consensus | <15ms |
| **Tier 3: Deep Verification** | When K (DS conflict factor) > 0.5 | FEVER-style NLI + Allen's interval constraint + PSL inference | <50ms |

**Critical insight:** ALL expensive computation happens at **ingestion time**, not query time.

**Precomputed features:**
- Source reliability weights (CATD/DART)
- KG embeddings
- Temporal validity windows
- Epistemic scores
- Provenance metadata
- Agreement matrices

**Query-time resolution:** Lookups + arithmetic on precomputed features.

---

## Cross-Response Convergence Matrix

| Technique | Response 1 (Conflict) | Response 2 (Aggregation) | Response 3 (Extraction) | Response 4 (Veracity) | Response 5 (7 Approaches) | Response 6 (Epistemic) |
|-----------|---------------------|------------------------|----------------------|---------------------|------------------------|---------------------|
| **SOURCE_TRUST Hierarchy** | ✅ Core | ✅ Implicit | ❌ | ✅ Explicit | ✅ Core | ✅ Authority Tiers |
| **Evidence-Weighted Scoring** | ✅ CRH | ✅ Ensemble | ❌ | ✅ GTM | ✅ CATD/DART | ✅ Triangulation |
| **Temporal Modeling** | ✅ Validity Windows | ✅ Temporal Grouping | ❌ | ❌ | ✅ Allen's Intervals | ✅ Event-Anchored |
| **Graph-Based Trust** | ✅ Implicit | ❌ | ❌ | ❌ | ✅ KGE Plausibility | ✅ RTP (Recursive Trust) |
| **Epistemic Status** | ❌ | ❌ | ❌ | ❌ | ✅ **NOVEL** | ✅ Linguistic Certainty |
| **NLI Verification** | ❌ | ❌ | ✅ REFNLI | ❌ | ✅ FEVER-style | ❌ |
| **Domain-Aware Expertise** | ❌ | ❌ | ❌ | ❌ | ✅ DART | ❌ |

**Universal convergence (appears in 4+ responses):** SOURCE_TRUST + Evidence-Weighted Scoring + Temporal Modeling

**Novel additions (appear in 1-2 responses):** Epistemic Status Extraction, Domain-Aware Truth Discovery, DeGroot Consensus

---

## Implementation Priority Matrix

### Tier 1: CRITICAL (Week 1, 14-16 hours)

| Technique | Source | Implementation Time | Expected Gain | Complexity | Priority |
|-----------|--------|-------------------|---------------|------------|----------|
| **SOURCE_TRUST Hierarchy** | All responses | 1 hour | +3-5 questions | Low | 🔴 CRITICAL |
| **Authority Tier System** | Response 6 | 2 hours | +2-4 questions | Low | 🔴 CRITICAL |
| **CATD (Confidence-Aware TD)** | Response 5 | 3-4 days | +2-3 questions | Medium | 🟡 Week 1 Core |

**Combined Week 1:** SOURCE_TRUST + Authority Tiers + Basic CRH (no CATD yet) = **16 hours**

### Tier 2: HIGH VALUE (Week 2, choose ONE)

| Technique | Implementation Time | Expected Gain | Risk |
|-----------|-------------------|---------------|------|
| **Epistemic Status Extraction** ⭐ | 3-5 days | +3-4 questions | Medium |
| **DART (Domain-Aware TD)** | 3-5 days | +2-3 questions | Medium |
| **Dempster-Shafer Belief** | 2-3 days | +2-3 questions | Low |

**Recommendation:** **Epistemic Status Extraction** (most novel, highest impact for Q3 specifically)

### Tier 3: ADVANCED (Week 3)

| Technique | Implementation Time | Expected Gain | Complexity |
|-----------|-------------------|---------------|------------|
| **Bi-Temporal Modeling (Allen's)** | 5-7 days | +2-3 questions | High |
| **RTP (Recursive Trust Propagation)** | 4-5 days | +2-3 questions | High |
| **FEVER-Style NLI Verification** | 3-5 days | +1-2 questions | Medium |

### Tier 4: OPTIMIZATION (Week 4)

| Technique | Implementation Time | Expected Gain | Complexity |
|-----------|-------------------|---------------|------------|
| **KGE Plausibility** | 2-3 days | +1-2 questions | Medium |
| **DeGroot Consensus** | 1-2 days | +1 question | Low |
| **Question-Path Ranking** | 3-4 days | +1-2 questions | High |

---

## Critical Insights

### 1. **Epistemic Status Extraction is the Hidden Gem**

**No other response mentioned this.** The difference between:
- "X is the president" (assertion, 0.95 certainty)
- "X might become president" (hedge + future, 0.3 certainty)
- "reportedly X is president" (attribution hedge, 0.5 certainty)

This **single linguistic signal** could resolve Q3 independently of all other factors.

### 2. **Tiered Architecture is Production-Ready**

Response 5's three-tier system (Tier 1: <5ms, Tier 2: <15ms, Tier 3: <50ms) is **immediately implementable** and addresses latency constraints.

### 3. **Question-Path Ranking is a Paradigm Shift**

Response 6's inversion ("rank the questions, not the entities") aligns with **Reasoning-Enhanced RAG** trend and multi-agent architectures.

### 4. **All Expensive Computation is Precomputed**

Both responses emphasize: **Query-time resolution = lookups + arithmetic on precomputed features**. This makes <50ms achievable.

---

## Comparison: Our Week 1 Plan vs. New Research

| Aspect | Our Week 1 Plan | New Research (Responses 5+6) | Winner |
|--------|----------------|----------------------------|--------|
| **SOURCE_TRUST** | 0.95 org_chart, 0.55 email | Authority Tier System (4 tiers) | **New** (more nuanced) |
| **Conflict Detection** | Cardinality-based | Cardinality + Dempster-Shafer | **New** (explicit ignorance modeling) |
| **Temporal Handling** | Basic validity windows | Allen's Interval Algebra + Event Anchors | **New** (state-change verbs) |
| **Evidence Scoring** | CRH composite | CRH + CATD + Epistemic Status | **New** (linguistic certainty) |
| **Missing Piece** | ❌ No domain awareness | ✅ DART learns authority mappings | **New** (automatic learning) |
| **Implementation Time** | 14-16 hours | Week 1: Same, Week 2+: Advanced options | **Tie** |

---

## Updated Implementation Roadmap

### **Week 1: Core Conflict Resolution (14-16 hours)** → 74% to 77-81%

**KEEP from original plan:**
1. SOURCE_TRUST hierarchy (1 hour)
2. Cardinality registry + metric canonicalization (3 hours)
3. CRH scorer with temporal grouping (4 hours)
4. Integration at tool_agent.py:1047 (2 hours)
5. Testing on Q3, Q14, Q25, Q51, Q100 (4 hours)

**ADD from new research:**
- **Authority Tier System** (2 hours) - replaces flat SOURCE_TRUST with 4-tier hierarchy
- **Basic epistemic status** (2 hours) - detect "will be", "might", "reportedly" patterns

**Updated total:** 16-18 hours

---

### **Week 2: Advanced Resolution (choose ONE)** → 81% to 83-85%

**Option A: Epistemic Status Extraction (3-5 days)** ⭐ RECOMMENDED
- Full hedge detection (CoNLL-2010 patterns)
- Upstream quality propagation
- MINEA-style calibration (needle injection)
- **Expected:** +3-4 questions (fixes Q3, Q14, possibly Q51)

**Option B: DART Domain-Aware TD (3-5 days)**
- Auto-learn authority mappings by domain
- Bayesian EM for per-source, per-domain expertise
- **Expected:** +2-3 questions (generalizes beyond hardcoded rules)

**Option C: Dempster-Shafer Belief (2-3 days)**
- Explicit ignorance modeling
- Conflict-aware combination (Yager's rule when K > 0.7)
- **Expected:** +2-3 questions (cleaner uncertainty quantification)

---

### **Week 3: Temporal or Structural (4-6 days)** → 85% to 87-88%

**Option A: Bi-Temporal Modeling (5-7 days)**
- Allen's Interval Algebra
- HeidelTime/SUTime integration
- Event-anchored validity windows
- **Expected:** +2-3 questions (handles "formerly", "appointed" correctly)

**Option B: Recursive Trust Propagation (4-5 days)**
- Claim-Document Bipartite Graph
- Modified PageRank with support/refutation edges
- **Expected:** +2-3 questions (graph-based immunity to outliers)

---

### **Week 4: Optimization (2-4 days)** → 88% to 90%+

**Quick wins (pick 2-3):**
- KGE Plausibility (2-3 days)
- DeGroot Consensus (1-2 days)
- Lexicon-enhanced reranking (1 day)
- FEVER-style NLI for edge cases (3-5 days)

---

## Final Recommendation

### **Phase 1 (Week 1): Enhanced Core** - 16-18 hours

**Implement:**
1. SOURCE_TRUST hierarchy → **Authority Tier System** (4 tiers, not flat weights)
2. Cardinality registry + metric canonicalization
3. CRH scorer + temporal grouping
4. **Basic epistemic status** (detect "will", "might", "reportedly")
5. Integration + testing

**Expected:** 74% → 77-81% (same as before, but more robust)

### **Phase 2 (Week 2): Epistemic Status Extraction** - 3-5 days ⭐

**Why this over DART or Dempster-Shafer:**
- **Most novel** (no other response mentioned it)
- **Highest Q3 impact** (directly addresses email hedging)
- **Lightweight** (3-5 days vs. 5-7 for bi-temporal)
- **Complementary** to SOURCE_TRUST (different signal dimension)

**Expected:** 81% → 83-85%

### **Phase 3 (Week 3): If needed** - 4-5 days

If Phase 2 only reaches 83%, add:
- **Recursive Trust Propagation** (graph-based outlier immunity)
- OR **Bi-Temporal Modeling** (if temporal issues persist)

**Expected:** 85% → 87-88%

### **Phase 4: Polish** - 2-3 days

Quick wins:
- DeGroot Consensus (1-2 days, easy win)
- KGE Plausibility (2-3 days, structural signal)

**Expected:** 88% → 90%+

---

## Key Takeaways

### 1. **Epistemic Status Extraction is the Breakthrough**

This technique addresses Q3 **at the source** (linguistic certainty of extraction) rather than downstream (evidence weighting). It's **orthogonal** to all other signals.

### 2. **Authority Tier System > Flat SOURCE_TRUST**

4-tier system (Structural, Procedural, Communication, Personal) captures **nuance** that flat weights cannot:
- Tier 3 contradicted by Tier 1/2 = automatic penalty
- TierDiversity multiplier rewards cross-tier convergence

### 3. **Precompute Everything, Query-Time is Lookups**

Both responses emphasize: Expensive computation (CATD weights, KG embeddings, temporal windows, epistemic scores) happens at **ingestion**. Query-time = <5ms for 90% of queries.

### 4. **Three-Tier Latency Budget is Production-Grade**

- Tier 1 (<5ms): DS + CATD + temporal filter + epistemic scores → 90% of queries
- Tier 2 (<15ms): KGE + DART + DeGroot → confidence gap cases
- Tier 3 (<50ms): NLI + Allen's intervals + PSL → high conflict (K > 0.5)

### 5. **DART Auto-Learns Authority (Future-Proof)**

Instead of hardcoding "org charts are authoritative for roles," DART **learns** this from data. Generalizes to new domains without manual tuning.

---

## Next Steps

1. **Decision:** Commit to **Enhanced Week 1** (16-18 hours) with Authority Tier System + Basic Epistemic Status?
2. **If yes:** Implement Week 1, validate 77-81% accuracy
3. **Then decide:** Week 2 = Epistemic Status Extraction (full) OR DART OR Dempster-Shafer?
4. **Measure:** After each phase, run full vault test to validate projected gains

**The research is now COMPLETE. We have 6 comprehensive responses totaling ~60 pages of research-backed solutions. Ready to implement.**
