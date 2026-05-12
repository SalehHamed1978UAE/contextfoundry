SEND TO REPLIT — START

# Stage 1K — VerificationWorker Deadlock Fix on Clean Stage 1J Vault

## Alignment

- **Module touched:** VerificationWorker / verification-promotion path first; optional extraction_level bulk-update bug second if isolated
- **Product vs implementation:** implementation-level blocker fix before Stage 2 readiness discussion
- **Architecture-doc consistency:** follows Stage 1I/J findings: IdentityResolver tenant isolation is fixed and validated on fresh ingestion; remaining blocker is verification/promotion on clean data
- **Drift risk:** repairing historical contaminated vaults instead of validating the clean path; starting Stage 2 before fresh tenant-local facts can verify and promote; changing verification semantics while fixing a transaction/deadlock bug
- **Out of scope:** historical data repair mutation, DB trigger, schema constraint, scheduler activation, Stage 2, Nexus 100 scoring, v2, `replit.md` edits

## Sign-off

Stage 1J is accepted.

Accepted results:

```text
100/100 documents processed.
Fresh tenant ingestion completed.
0 new cross-tenant relationships.
0 new merge_audit rows.
Cross-tenant updated_at remained frozen at 2026-05-11 05:59:56.823.
merge_audits remained frozen at 2026-05-11 05:59:59.118 / 3901 rows.
ontology.types unchanged at 1037.
ontology.relations unchanged at 254.
IdentityResolver autonomous cross-tenant merge bug is fixed in runtime.

Stage 1J clean vault:

ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda

Do not delete this vault. It is the clean post-fix validation tenant.

Phase 3 adjustment

Phase 3 historical contamination repair is not a Stage 2 prerequisite.

Reason:

Stage 1J proved fresh ingestion under the fixed runtime stays tenant-clean.
Customer deployments will use fresh vaults.
The contaminated legacy vaults are forensic artifacts, not production launch data.

Do not repair historical contaminated vaults as general hygiene.

If Phase 3 ever becomes necessary, it should be for a specific use case, such as reactivating one historical vault or preserving a benchmark fixture.

For now:

keep contaminated legacy vaults as forensic/adversarial fixtures
do not mutate them
do not backfill them
do not delete them
Next task: VerificationWorker deadlock fix

The Stage 1J verification/promotion phase produced:

0 verified
0 promoted

because VerificationWorker deadlocked under load.

This is now the primary blocker before Stage 2 readiness discussion.

Required investigation

Read:

src/context_foundry/workers/verification_worker.py
any verification scheduler / worker launcher
the Stage 1J run logs
the deadlock error stack
tables touched by verification updates
entity / relationship verification status update code
promotion code path that requires verification

Find:

which table update deadlocked
which rows / indexes were involved
whether autoflush caused UPDATE order inversion
whether concurrent workers updated the same fact rows
whether the worker mixes entity and relationship verification in one session
whether verification writes and promotion writes share a transaction/session unsafely
whether the deadlock is reproducible on a small subset
Required fix

Apply the smallest targeted fix that prevents the deadlock without changing verification semantics.

Acceptable fix classes:

use session.no_autoflush around read-before-write sections
separate read phase from write phase
commit in deterministic batches
order updates by primary key before writing
avoid concurrent updates to the same fact row
use savepoints if one verification write fails
make worker retry on database deadlock with bounded retry count

Do not change:

verification criteria
promotion thresholds
required verification policy
fact confidence
ontology validation
tenant scoping

If the fix would require semantic changes, stop and report.

Tests

Add targeted tests for the deadlock fix.

Minimum coverage:

VerificationWorker can process a small batch without deadlock.
Entity verification updates are written.
Relationship verification updates are written.
A failed verification write does not rollback unrelated successful writes.
Worker remains tenant-scoped.
Deadlock retry, if implemented, is bounded and logged.

If a true deadlock is hard to unit-test, add:

a transaction-order regression test
a deterministic batch ordering test
a small integration smoke on 2–5 facts
Validation on clean Stage 1J vault

After the fix and tests pass, validate on the clean Stage 1J vault:

ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda

Run a bounded verification pass first.

If the bounded pass succeeds, run the minimum verification/promotion sequence needed to demonstrate:

facts verify successfully
verified facts can promote to TRUSTED
no new cross-tenant relationships appear
ontology.types remains 1037
ontology.relations remains 254

Do not run Nexus 100 scoring.

Do not repair historical contaminated vaults.

Do not start Stage 2.

Architect review

Run architect/code review focused on:

transaction/session safety
autoflush behavior
deadlock avoidance
tenant scoping
no semantic change to verification
no promotion-threshold change
no Stage 2 behavior

If architect flags HIGH issues, fix before final report.

Optional secondary fix: extraction_level bulk-update bug

After the VerificationWorker fix is done and tests pass, you may fix the non-blocking bulk-update bug if it is clearly isolated:

psycopg2.errors.UndefinedFunction: operator does not exist: uuid = text

Scope:

run_vault_extraction.py post-pipeline extraction_level='multi' bulk update only

Requirements:

fix UUID/text casting correctly
add a targeted test or smoke query
do not change per-document extraction behavior
do not change ingestion or classification semantics

If it is not obviously isolated, defer it and report.

Do not do

Do not:

repair historical contaminated relationships
repair the 2814 / ~4500 DB-wide cross-tenant relationships
delete contaminated legacy vaults
add DB trigger
add schema constraint
add DuplicateCandidate/MergeAudit tenant_id columns
run Nexus 100 scoring
start scheduler
start Stage 2
run v2
edit replit.md
Stage 2 readiness framing

After Stage 1K lands, the actual Stage 2 readiness conversation begins.

Remaining possible inputs to that conversation:

Phase 4 schema constraint, if needed
Phase 5 duplicate_candidates / merge_audits tenant_id columns
Scheduler per-tenant iteration design
Ontology hygiene
Extraction-vs-ontology relation alignment
MultiModelExtractor staged activation

None of those require Phase 3 historical repair as a prerequisite.

Findings doc update

Update the Stage 1J findings doc:

docs/findings/stage_1j_fresh_ingestion_validation_2026-05-12.md

or append to the existing Stage 1B/1J findings doc if that is where Stage 1J is tracked.

Add:

Stage 1J sign-off
VerificationWorker deadlock root cause
VerificationWorker fix
tests
architect review
clean-vault verification/promotion validation
whether Stage 2 readiness discussion can begin
Final report

Report:

root cause of VerificationWorker deadlock
files changed
exact fix
tests run and results
architect review result
bounded verification result on clean Stage 1J vault
promotion result on clean Stage 1J vault, if run
cross-tenant invariant check after verification/promotion
whether extraction_level bulk-update bug was fixed or deferred
whether Stage 2 readiness discussion can begin
whether Stage 2 remains blocked
Stop condition

Stop after Stage 1K final report.

Wait for sign-off before DB trigger, schema work, scheduler activation, or Stage 2.
