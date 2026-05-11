SEND TO REPLIT — START

# Stage 1I Phase 1.6 — Runtime Cutover and Repair Readiness Check

## Alignment

- **Module touched:** runtime process state / Start All reload verification only
- **Product vs implementation:** implementation-level readiness gate before data repair
- **Architecture-doc consistency:** follows Stage 1I Phase 1 + 1.5: IdentityResolver writer fixed, call sites fixed, but running processes may still hold pre-fix code in memory
- **Drift risk:** repairing data while Start All is still running pre-fix IdentityResolver logic and can re-poison relationships
- **Out of scope:** data repair, DB trigger, schema constraint, DuplicateCandidate/MergeAudit schema changes, promotion cycles, scheduler activation, Stage 2, Nexus 100 scoring, VerificationWorker, v2 work, `replit.md` edits

## Sign-off

Stage 1I Phase 1.5 is accepted.

Accepted results:

```text
web_app.py call sites now pass tenant_id from g.tenant_id / TenantSession context.
scheduler.py bare IdentityResolver call removed and replaced with explicit NotImplementedError.
SchedulerConfig.run_identity_resolution default flipped to False.
init_scheduler() explicitly sets run_identity_resolution=False.
22/22 tests pass.
Architect HIGH issue fixed.
IdentityResolver Phase 1 guards remain intact.
New blocker before Phase 3

Start All is still running pre-fix code in memory.

Do not repair existing cross-tenant relationships until the active runtime is either:

reloaded onto the fixed code
or proven not to be running the pre-fix IdentityResolver / scheduler identity-resolution path
Goal

Make it safe to plan Phase 3 data repair by ensuring the active runtime cannot create new cross-tenant relationship contamination.

Required actions
1. Capture current runtime state

Before any restart/reload, capture:

Start All status
Start All PID(s)
command line
process start time
current git/checkpoint marker if available
recent Start All logs related to:
  IdentityResolver
  duplicate_candidates
  merge_audits
  cross-tenant merges
  scheduler
  gardener

Also capture current cross-tenant relationship counts:

DB-wide cross-tenant relationship count
S vault cross-tenant relationship count
L vault cross-tenant relationship count
latest cross-tenant relationship updated_at
latest merge_audits row where merged_by='identity_resolver'
2. Determine whether reload is required

If Start All started before the Stage 1I Phase 1 / 1.5 code changes, assume it is running stale code.

If Start All is already running the fixed code somehow, prove it with logs or runtime introspection and report.

3. Reload Start All if needed

Authorize restart/reload of Start All only if needed to load the fixed code.

This is explicitly authorized for this task because the active runtime may otherwise keep writing contaminated relationship endpoints.

Guardrails:

do not restart Manus
do not restart Ontology Vault
do not restart failed test workflows
do not touch v2 workflows
do not edit replit.md
do not start Stage 2

Preserve logs before restart if possible.

4. Verify post-reload behavior

After Start All reloads, verify:

Start All is running
SchedulerConfig.run_identity_resolution=False
init_scheduler() uses run_identity_resolution=False
no immediate IdentityResolver TypeError
no immediate duplicate_candidates FK crash caused by the Phase 1.5 call-site fix
no new cross-tenant relationship endpoints created in the first observation window

Observation window:

10–15 minutes

During the observation window, poll:

DB-wide cross-tenant relationship count
S vault cross-tenant relationship count
latest cross-tenant relationship updated_at
latest identity_resolver merge_audit
Start All logs for IdentityResolver / Gardener / scheduler errors
5. Pre-existing duplicate_candidates FK issue

Do not fix this in Phase 1.6.

Just classify it:

Does the ForeignKeyViolation recur after reload?
Does it involve duplicate_candidates_entity_a_id_fkey?
Does it block Start All from operating?
Does it appear related to Phase 5 candidate: DuplicateCandidate / MergeAudit tenant_id columns and FK cascade policy?

Record the answer as Phase 5 / triage input.

Stop triggers

Stop and report if:

Start All cannot be safely restarted/reloaded
Start All fails to come back
new cross-tenant relationships are created after reload
identity resolution still runs without tenant context
scheduler tries to run identity resolution despite default false
Phase 1.5 call-site changes produce a runtime TypeError on normal startup
duplicate_candidates FK issue blocks runtime operation
any action would require DB mutation or schema change
Do not do

Do not:

repair existing cross-tenant relationships
repair DB-wide contaminated rows
add DB trigger
add schema constraint
add DuplicateCandidate/MergeAudit tenant_id columns
run promotion cycles
start scheduler identity resolution
run Nexus 100 scoring
run VerificationWorker
start Stage 2
touch v2
edit replit.md
Findings doc update

Update:

docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md

Add:

Stage 1I Phase 1.6 runtime cutover
whether Start All was reloaded
pre/post cross-tenant counts
whether new contamination appeared
whether duplicate_candidates FK issue recurred
whether Phase 3 data repair is safe to plan
Final report

Report:

runtime state before reload
whether reload was required
reload action taken, if any
runtime state after reload
10–15 minute observation results
cross-tenant counts before/after
latest merge_audits before/after
duplicate_candidates FK observation
whether Phase 3 data repair is now safe to plan
whether Phase 4 DB trigger is now safe to plan
whether Stage 2 remains blocked
Stop condition

Stop after the Phase 1.6 runtime-readiness report.

Wait for sign-off before Phase 3 data repair, Phase 4 DB trigger, or any promotion rerun