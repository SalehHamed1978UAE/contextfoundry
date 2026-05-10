# Piece 0.6 Mutation — Narrow Preflight Relaxation and Execute If Clean

## Alignment

- **Module touched:** `ontology.relations`, repository-domain-filter tests, `docs/architecture.md`
- **Product vs implementation:** implementation-level prerequisite for Piece 2 domain-scoped prompts
- **Architecture-doc consistency:** matches signed-off Piece 2.0 design and approved Piece 0.6 relation disposition
- **Drift risk:** over-broad preflight blocking forever on read-only webapp connection-pool SELECTs; starting Piece 2 before relation governance is complete
- **Out of scope:** Piece 2 implementation, prompt changes, `SchemaPromptGenerator`, Gardener, v2, Nexus 100, workflow restarts, `replit.md` edits, restarting Start All

## Decision

Proceed with Option B, narrowly.

Relax Preflight #1 only for read-only `Start All` / webapp connection-pool transactions on `relationships`.

Do not relax checks on:

- `ontology.relations`;
- active extraction writers;
- target-row state;
- backup integrity;
- repository/domain-filter tests.

Reason:
Medsync is finished. The remaining idle-in-transaction rows are read-only webapp/Start All connection-pool reads on `relationships`, not Medsync extraction, not `ontology.relations`, and not row locks on the table being mutated.

Do not kill or restart Start All.

## Just-in-time preflight before mutation

Immediately before UPDATE, run:

1. Workflow status:
   - confirm `Test: ClaudeCode Medsync` is finished.

2. DB activity:
   - no idle-in-transaction on `ontology.relations`;
   - no locks on `ontology.relations`;
   - no active write queries on `entities`, `relationships`, or `document_chunks`;
   - read-only idle transactions on `relationships` from Start All are allowed.

3. Six target-row state:
   - all six rows still in expected pre-mutation state.

4. Backup:
   - `ontology.relations` count equals backup table count.

If any non-allowed condition appears, stop and report.

Allowed condition:
- read-only idle-in-transaction `SELECT` on `relationships` from Start All / webapp connection pool.

## Approved mutation

Run the approved Piece 0.6 transaction:

- `HOLDS_POSITION PERSON→JOB_TITLE` → `core`
- `HOLDS_POSITION PERSON→ORGANIZATION` → `core`
- `WORKS_AT PERSON→ORGANIZATION` → `core`
- `REPORTS_TO PERSON→PERSON` → `core`
- `HAS_COMPENSATION PERSON→COMPENSATION` → `finance`
- `HAS_COMPENSATION PERSON→CONCEPT` → deprecated, `domain_id` remains NULL

Do not touch sibling rows.

## Verify before COMMIT

Before COMMIT, verify:

```text
HOLDS_POSITION      core     ACTIVE      count 2
WORKS_AT            core     ACTIVE      count 1
REPORTS_TO          core     ACTIVE      count 1
HAS_COMPENSATION    finance  ACTIVE      count 1
HAS_COMPENSATION    NULL     DEPRECATED  count 1

If verification fails, ROLLBACK and report.

If verification matches, COMMIT.

Post-mutation

After COMMIT:

Run repository checks:
get_all_relations(domain_id='core')
get_all_relations(domain_id='finance')
get_all_relations()
get_all_relations(include_deprecated=True)
Run:
tests/ontology/test_repository_domain_filter.py
Update docs/architecture.md Gap 5 / Piece 0.6 section with final disposition.
Keep Gap 6 open.
Do not start Piece 2.
Final report

Report:

exact preflight results;
confirmation Medsync finished;
confirmation remaining idle transactions, if any, were read-only Start All / webapp relationships SELECTs;
SQL transaction run;
pre-COMMIT verification;
COMMIT confirmation;
post-mutation relation counts;
repository checks;
test results;
docs updated;
confirmation Piece 2 implementation did not start;
confirmation no prompts, SchemaPromptGenerator, Gardener, v2, Nexus, workflow restarts, or replit.md work occurred.
Stop condition

Stop after Piece 0.6 mutation final report.

Do not begin Piece 2 implementation.


# Why this is the right relaxation

The strict “zero idle-in-transaction on any related table” check is now too broad because Start All can maintain read-only pooled sessions indefinitely. If we keep waiting for those, the mutation may be blocked by normal app behavior rather than a real mutation risk.

The safety boundary we actually need is:

```text
Do not mutate while another process is reading or locking ontology.relations, or while an extraction writer is active.

The latest report says that condition is clean: no Medsync runner, no locks on ontology.relations, and target rows / backup are unchanged.

Compact handoff
Current state:
Piece 0.6 mutation approved.
Medsync finished.
Only blocker is read-only Start All/webapp idle SELECTs on relationships.

Decision:
Proceed with narrowly relaxed preflight.

Allowed:
Read-only idle SELECTs on relationships from Start All.

Still blocked by:
Any idle transaction or lock on ontology.relations.
Any active extraction writer.
Any target-row drift.
Any backup mismatch.

Do not do:
Do not restart Start All.
Do not start Piece 2.
Do not touch prompts, SchemaPromptGenerator, Gardener, v2, Nexus, workflows, or replit.md.