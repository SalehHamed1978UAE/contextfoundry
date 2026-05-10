# Piece 0.6 — Resolve ADR Blocker, Then Wait for Medsync Before Mutation

## Alignment

- **Module touched:** `docs/decisions.md` first; DB mutation only after Medsync clears and JIT preflight passes
- **Product vs implementation:** implementation governance record + mutation safety gate
- **Architecture-doc consistency:** matches signed-off Piece 0.6 audit and Piece 2.0 dependency
- **Drift risk:** appending truncated ADR text; mutating while Medsync extraction is active
- **Out of scope:** Piece 2 implementation, prompt changes, SchemaPromptGenerator, Gardener, v2, Nexus 100, workflow restarts, `replit.md` edits

## Decision

You were correct not to append truncated ADR text.

Use the short ADR text below. It is intentionally concise to avoid truncation.

Append only this ADR. Do not append the previously truncated ADR text.

Use the next available ADR number after ADR-006.

## Append this ADR

```markdown
## ADR-XXX: Piece 0.6 governed disposition of foundational relations

Date: 2026-05

Decision:
`HOLDS_POSITION`, `WORKS_AT`, and `REPORTS_TO` are governed as `core` relations. Both existing `HOLDS_POSITION` rows are preserved: `PERSON → JOB_TITLE` and `PERSON → ORGANIZATION`. `WORKS_AT PERSON → ORGANIZATION` and `REPORTS_TO PERSON → PERSON` are also adopted into `core`.

`HAS_COMPENSATION PERSON → COMPENSATION` is governed as a `finance` relation. The older `HAS_COMPENSATION PERSON → CONCEPT` row is deprecated, preserved by UUID, and not deleted.

No sibling relations are changed in Piece 0.6. `HELD_POSITION`, `AFFILIATED_WITH`, `MANAGES`, `OWNS`, and other near-duplicates remain future governance scope unless separately approved.

Rationale:
Piece 2 scoped prompts use `core ∪ primary_domain`. If required organizational relations stay `domain_id = NULL`, they are excluded from scoped prompts. The Piece 0.6 audit showed that both `HOLDS_POSITION` rows are valid and used, `WORKS_AT` is the canonical employment relation, and `REPORTS_TO` is cross-domain organizational structure. The audit also showed that `HAS_COMPENSATION PERSON → COMPENSATION` is the canonical compensation relation, while `HAS_COMPENSATION PERSON → CONCEPT` is unused and mis-targeted.

Implication:
Piece 2 can build scoped prompts without losing role, employment, and reporting relations. Compensation remains finance-scoped. HR-domain compensation extraction remains recorded under Gap 6 and is not solved by this decision.

After appending, paste:

the ADR number used;
the final sentence of the Rationale paragraph;
the final sentence of the Implication paragraph.

That confirms the ADR was not truncated.

Medsync blocker

Do not mutate while Test: ClaudeCode Medsync is actively extracting.

Wait/recheck.

Run:

SELECT
  pid,
  usename,
  application_name,
  state,
  now() - xact_start AS xact_age,
  left(query, 300) AS query_preview
FROM pg_stat_activity
WHERE state = 'idle in transaction'
  AND (
    query ILIKE '%entities%'
    OR query ILIKE '%relationships%'
    OR query ILIKE '%document_chunks%'
    OR query ILIKE '%ontology.relations%'
  );

Also check workflow status.

Proceed only if:

- Medsync is no longer running, OR confirmed unrelated to extraction/ontology reads;
- no idle-in-transaction extraction signatures remain;
- no locks on ontology.relations;
- six target rows remain NULL / ACTIVE;
- backup count still matches source count.

If Medsync is still running, stop and report. Do not kill it.

If Medsync is clear

Run the already-approved Piece 0.6 mutation:

HOLDS_POSITION PERSON→JOB_TITLE        → core
HOLDS_POSITION PERSON→ORGANIZATION    → core
WORKS_AT PERSON→ORGANIZATION          → core
REPORTS_TO PERSON→PERSON              → core
HAS_COMPENSATION PERSON→COMPENSATION  → finance
HAS_COMPENSATION PERSON→CONCEPT       → deprecated, domain_id remains NULL

Do not touch sibling rows.

Run verification before COMMIT. If verification does not match, ROLLBACK.

Final report

Report:

ADR number appended;
ADR truncation verification;
Medsync status;
just-in-time DB preflight;
mutation SQL run if allowed;
pre-COMMIT verification;
post-mutation relation counts;
repository checks;
unit tests;
docs updated;
confirmation Piece 2 implementation did not start.

Bottom line:

```text
ADRs stopped at ADR-006 because Replit correctly refused truncated governance text.
Mutation stays paused because Medsync is actively extracting.
Next step: append the short ADR above, then wait/recheck Medsync before mutating.