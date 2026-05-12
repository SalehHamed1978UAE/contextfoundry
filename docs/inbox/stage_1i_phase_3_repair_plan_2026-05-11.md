# Stage 1I Phase 1.6 Sign-off — Runtime Cutover Accepted

## Alignment

- **Module touched:** runtime cutover verification only; next work is data repair planning
- **Product vs implementation:** implementation-level stabilization before relationship-endpoint repair
- **Architecture-doc consistency:** follows Stage 1H / Stage 1I finding: IdentityResolver was the writer of cross-tenant relationship endpoints; Phase 1 / 1.5 code fixes are now loaded in the runtime
- **Drift risk:** treating runtime cutover as Stage 2 readiness; repairing data without a plan; adding DB trigger before understanding repair sequencing; ignoring duplicate_candidates FK issue
- **Out of scope:** Stage 2, scheduler identity-resolution re-enable, promotion rerun, Nexus 100 scoring, v2, replit.md edits

## Decision

Accept Stage 1I Phase 1.6.

Runtime cutover succeeded.

Accepted facts:

```text
Start All was running stale pre-fix code.
Start All was restarted.
New PIDs started at 2026-05-11 20:53 UTC.
New log showed Brain + WebApp scheduler startup cleanly.
0 TypeError.
0 NotImplementedError.
0 ForeignKeyViolation during the observation window.
0 new cross-tenant relationships since restart.
0 updated cross-tenant relationships since restart.
0 identity_resolver merges since restart.
Latest cross-tenant relationship updated_at remained 2026-05-11 05:59:56.
Latest identity_resolver merge_audit remained 2026-05-11 05:59:59.

Interpretation

The active runtime is no longer producing new cross-tenant relationship contamination in the observed window.

This means it is safe to plan:

Phase 3 — data repair for existing cross-tenant relationships
Phase 4 — DB-level invariant / trigger after repair

This does not mean Stage 2 is ready.

Stage 2 remains blocked until:

existing cross-tenant relationship data is repaired or quarantined
DB/app invariant prevents recurrence
promotion path is re-tested on clean tenant-local relationships

Accepted open issue

The pre-existing duplicate_candidates_entity_a_id_fkey issue is not fixed.

Accepted classification:

Phase 5 issue.
DuplicateCandidate has no tenant_id.
FK cascade / stale candidate cleanup is missing.
Not blocking Phase 3 planning unless repair touches duplicate_candidates.

Do not fix Phase 5 in this task.

Next task: Phase 3 data repair plan only

Prepare a data repair plan for existing cross-tenant relationships.

Do not execute repair yet.

Required plan inputs:

DB-wide cross-tenant relationship count = 2814
S cross-tenant relationship count = 1718
Unique-equivalent endpoint candidates = 746 / 758
Multi-candidate endpoints = 12
Root cause fixed in IdentityResolver Phase 1 / 1.5
Runtime cutover clean in Phase 1.6

Phase 3 plan requirements

The plan must cover:

1. Repair scope

Separate:

S vault repair
L vault repair
original Nexus vault repair
DB-wide repair

Recommend whether to repair:

S first as pilot
then L
then original Nexus
then DB-wide

or another sequence.

2. Relationship bucket classification

For each affected tenant/vault, classify cross-tenant relationships into:

both endpoints have unique local equivalents
one endpoint has unique local equivalent, other already local
both endpoints have multi-candidate local equivalents
one or both endpoints have no local equivalent
relationship type invalid under ontology.relations
relationship already ARCHIVED
relationship STAGING and eligible for repair
relationship TRUSTED and requires extra caution

3. Repair action per bucket

Draft actions only:

remap endpoint to unique local equivalent
quarantine relationship
archive relationship
leave unchanged with justification
manual review required

Do not execute.

4. Safety checks

Plan must include pre/post checks:

count cross-tenant relationships before/after
count relationships by lifecycle_state before/after
sample repaired relationships and verify endpoint tenants
verify no ontology changes
verify no documents/chunks/entities deleted
verify no TRUSTED fact silently degraded
verify all changes are reversible via backup table

5. Backup strategy

Plan a backup before repair:

backup table for affected relationships
backup table for old source_id / target_id / tenant_id / lifecycle_state / updated_at
rollback SQL

Do not create backup yet.

6. Transaction strategy

Recommend:

one tenant per transaction
pilot on S first
verification block before COMMIT
rollback on mismatch

7. Quarantine strategy for 12 multi-candidate endpoints

Use:

quarantine first
manual review later
no LLM disambiguation yet

8. Tests to add before repair execution

Propose tests, but do not write them yet:

relationship endpoints remain tenant-local after repair
unique-equivalent mapping is deterministic
multi-candidate endpoints are quarantined, not guessed
repair is reversible
DB trigger would reject cross-tenant endpoint write after repair

9. Stage 2 readiness verdict

Report whether Stage 2 remains blocked after planning.

Expected:

Stage 2 remains blocked until Phase 3 repair executes and Phase 4 invariant is in place.

Phase 4 preview

Also draft, but do not implement, the DB invariant plan:

trigger or constraint ensuring relationship.tenant_id == source_entity.tenant_id
trigger or constraint ensuring relationship.tenant_id == target_entity.tenant_id
application-level assertion if DB trigger is too risky
RLS WITH CHECK review

Do not create trigger yet.

Standing constraints

Do not start Stage 2.

Do not run promotion cycles.

Do not start scheduler identity resolution.

Do not re-enable scheduler identity resolution.

Do not mutate DB.

Do not edit code.

Do not create schema constraints.

Do not repair relationships.

Do not run Nexus 100 scoring.

Do not run VerificationWorker.

Do not touch v2.

Do not edit replit.md.

Stop condition

Stop after Phase 3 / Phase 4 repair-plan report.

Wait for sign-off.