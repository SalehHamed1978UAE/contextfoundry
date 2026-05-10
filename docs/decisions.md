# Context Foundry — Architectural Decision Records

> **Status:** Canonical decisions log. Created May 2026 alongside the architecture lock.
> **Companion:** `docs/architecture.md` (canonical architecture).
> **Authority order:** User instruction > `docs/architecture.md` > this document > task brief > recent chat > agent inference.

Decisions are listed in chronological order of acceptance. Each ADR is immutable once recorded; supersession is handled by adding a new ADR that references the prior one.

---

## ADR-001 (2026-05): Context Foundry target architecture and product surface

**Status:** Accepted.

**Decision.** Context Foundry builds a governed, domain-aware world model from enterprise documents and returns ContextBundles through a refuse-or-answer-with-evidence contract. The ContextBundle is the agent-facing product surface. The knowledge graph is an internal symbolic memory substrate, not the product.

**Rationale.** The value to downstream agents is the governed bundle of evidence, provenance, gates, and confidence — not raw graph access. Treating the graph as the product invites consumers to bypass the governance layer (verification, gating, provenance) and reintroduces hallucination risk at the boundary.

**Consequences.**
- Every query response surface — `/api/vault/chat`, MCP, internal callers — must return a ContextBundle, not raw entity/relationship rows.
- API design centers on the ContextBundle contract (Section 6 of the architecture document); graph-shaped responses are an internal detail.

---

## ADR-002 (2026-05): Eight canonical domains; document_type separate from domain

**Status:** Accepted.

**Decision.** The system uses eight canonical domain identifiers: `core`, `it_infrastructure`, `healthcare`, `finance`, `aviation`, `supply_chain`, `manufacturing`, `construction`. `core` denotes shared/foundation ontology, not unknown. `document_type` is a separate axis from `domain`: domain controls ontology scope; document_type controls extraction hints and source authority.

**Rationale.** The production system needs both signals to make scope and authority decisions correctly. Collapsing `document_type` into `domain` would prevent the system from distinguishing, e.g., a finance-domain board minutes document (authoritative for executive appointments) from a finance-domain policy document (authoritative for ownership/responsibility) — these have the same domain but different authority profiles for downstream queries.

**Consequences.**
- The classifier output shape includes both `primary_domain` (canonical id) and `document_type` (free-text label normalized against the document-type taxonomy).
- `secondary_domains` is a list, not a single fallback — board memos legitimately span finance + compliance + security and should not be forced into a single bucket.
- `core` is a first-class domain, not a fallback for "no match." Cross-domain types live in `core`.

---

## ADR-003 (2026-05): Ontology DB domain registry is canonical (post-Piece 0)

**Status:** Accepted.

**Decision.** The canonical domain registry lives in `ontology.types.domain_id` and `ontology.relations.domain_id`. The current DB is not populated; Piece 0 constructs and backfills it from seed-file provenance. Other registries (`brain/classifier.py`, `config/*.yaml`) align to or are deprecated against this canonical source.

**Rationale.** Prior state had three independent registries with conflicting labels (DB column was empty; classifier had 7 underscored snake_case labels; YAML files had Title Case strings like `"Core Foundation"`, `"Investment Portfolio"`), preventing the domain-aware extraction path from being wirable in production. A single canonical registry is the precondition for `SchemaPromptGenerator.get_snapshot(domain_id=…)` filtering, for Gardener domain-coherence checks, and for `MultiModelExtractor` domain-scoped prompts.

**Consequences.**
- Piece 0 backfills `ontology.types.domain_id` and `ontology.relations.domain_id` to one of the eight canonical IDs from ADR-002.
- `brain/classifier.py:DOMAIN_DESCRIPTIONS` is updated so its keys exactly match the eight canonical IDs (adding `core`).
- `config/domain_schema.yaml`, `config/fiction_schema.yaml`, `config/investment_schema.yaml`, `config/examples/investment_portfolio.yaml` are renamed to `_legacy.yaml` with a top-of-file note. Not deleted until salvage audit completes.
- After Piece 0, code may filter ontology types by `domain_id` and trust the result.

---

## ADR-004 (2026-05): v2 FactEvaluator is parked as primary recovery path

**Status:** Accepted.

**Decision.** The v2 inference engine (`src/context_foundry/inference/engine.py` + planner/gatherer/prover/adversary/meta/synthesizer chain) is not the primary recovery mechanism for the Nexus failure set or general query failures. Planner and presupposition outputs are reused as Gap Detector signals (D8.1, already shipped). Gatherer strategies are salvageable for retrieval improvements.

**Rationale.** Oracle experiments showed 0/26 PROVEN/SUPPORTED on the failure set; 19/26 failures cannot be represented as `Fact(s, r, t)`; post-vector diagnostic showed 5/5 cleaner cases short-circuit at the planner/presupposition gate before retrieval can matter. The engine cannot be the main path when its target failure class is structurally unrepresentable in its input contract. The investment is recovered by salvaging the planner/gap-detection layer (D8.1 shipped) and treating the rest as parked.

**Consequences.**
- The engine and its sub-stages remain in the repo as **ORPHAN** (no production caller).
- Tests under `tests/inference/` are retained for the salvaged planner/gap behaviors but are not gating production.
- New retrieval/recovery work is planned at the QueryPipeline / DataGates / GapQueue layer (Pieces 4–6), not by extending the v2 engine.
- Any future task instruction to "wire FactEvaluator into production" must explicitly cite this ADR and either supersede it (new ADR) or scope the work to a non-primary path.

---

## ADR-005 (2026-05): Nexus is a competency benchmark, not the product

**Status:** Accepted.

**Decision.** Nexus benchmark results are diagnostic signals for the world model and ContextBundle pipeline. Optimization targets the architecture (extraction, ontology, governance, gap routing), not benchmark-specific behavior.

**Rationale.** The benchmark exists to expose gaps; closing those gaps must happen at the product layer, otherwise improvements do not generalize and the system overfits to a single corpus. The architecture document (Section 7) sequences product-layer Pieces 0–7 ahead of Piece 8 (Nexus 100 re-run) explicitly to enforce this ordering.

**Consequences.**
- "It improves Nexus by N points" is not, by itself, a sufficient justification for a code change. The change must also be expressible as a product-layer improvement (a new gap type, a Gardener rule, an extraction-prompt scope change, etc.).
- Nexus-specific hardcoding (e.g., anchor-org rules tuned for "Nexus Industries", regex patterns mentioning specific Nexus people) is out-of-scope. If such code exists from prior iterations, it is parked for salvage review, not extended.
- Piece 8 (Nexus re-run) is a measurement, not an iteration target.

---

## ADR-006 (2026-05): Recent task context does not redefine architecture

**Status:** Accepted.

**Decision.** Recent debugging, benchmark, retrieval, cache, or v2 context is subordinate to the architecture document and decisions log unless the user explicitly updates the product direction.

**Rationale.** Prevents LLM recency bias from silently changing product framing across sessions. Without this rule, a long debugging thread on (say) tree retrieval could implicitly elevate tree retrieval to a product-defining concern and cause subsequent tasks to optimize around it instead of the ContextBundle contract.

**Consequences.**
- The Required Replit Alignment Block (in `docs/architecture.md`) requires every response to declare alignment against this document before doing work.
- The Implementation Gate (in `docs/architecture.md`) requires every implementation task to be mapped to a specific Piece (0–8) from the locked implementation sequence.
- Conflicts between a task instruction and this document or the architecture document must be flagged in the alignment block and stop work — not silently resolved by following the task.

---

## ADR-007: Piece 0.6 governed disposition of foundational relations

Date: 2026-05

Decision:
`HOLDS_POSITION`, `WORKS_AT`, and `REPORTS_TO` are governed as `core` relations. Both existing `HOLDS_POSITION` rows are preserved: `PERSON → JOB_TITLE` and `PERSON → ORGANIZATION`. `WORKS_AT PERSON → ORGANIZATION` and `REPORTS_TO PERSON → PERSON` are also adopted into `core`.

`HAS_COMPENSATION PERSON → COMPENSATION` is governed as a `finance` relation. The older `HAS_COMPENSATION PERSON → CONCEPT` row is deprecated, preserved by UUID, and not deleted.

No sibling relations are changed in Piece 0.6. `HELD_POSITION`, `AFFILIATED_WITH`, `MANAGES`, `OWNS`, and other near-duplicates remain future governance scope unless separately approved.

Rationale:
Piece 2 scoped prompts use `core ∪ primary_domain`. If required organizational relations stay `domain_id = NULL`, they are excluded from scoped prompts. The Piece 0.6 audit showed that both `HOLDS_POSITION` rows are valid and used, `WORKS_AT` is the canonical employment relation, and `REPORTS_TO` is cross-domain organizational structure. The audit also showed that `HAS_COMPENSATION PERSON → COMPENSATION` is the canonical compensation relation, while `HAS_COMPENSATION PERSON → CONCEPT` is unused and mis-targeted.

Implication:
Piece 2 can build scoped prompts without losing role, employment, and reporting relations. Compensation remains finance-scoped. HR-domain compensation extraction remains recorded under Gap 6 and is not solved by this decision.
