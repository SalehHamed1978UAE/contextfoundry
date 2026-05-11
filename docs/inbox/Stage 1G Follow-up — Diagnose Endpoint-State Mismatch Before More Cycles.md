SEND TO REPLIT — START

# Stage 1G Follow-up — Diagnose Endpoint-State Mismatch Before More Cycles

## Alignment

- **Module touched:** Gardener relationship endpoint-trust diagnostic and, if confirmed, scoped endpoint-lookup fix
- **Product vs implementation:** implementation-level diagnostic/fix before scheduler activation or Stage 2 default activation
- **Architecture-doc consistency:** follows Stage 1G result: promotion can work, but Cycle 2 convergence failed because relationship endpoint trust is not being recognized
- **Drift risk:** running more cycles while the endpoint gate is misreading trusted endpoints; changing promotion semantics instead of fixing lookup equivalence
- **Out of scope:** scheduler activation, Stage 2 implementation, Nexus 100 scoring, VerificationWorker full run, ontology backfill, prompt changes, v2 work, `replit.md` edits

## Accepted state

Accept the Cycle 2 result as a real convergence failure:

```text
Cycle 2 promoted 0 entities and 0 relationships.
Block reasons were effectively identical to Cycle 1.
SQL pre-snapshot measured 179 S relationships with both endpoints TRUSTED.
Gardener still reported endpoints_not_trusted=1115.

Therefore:

Do not run Cycle 3.
Do not start scheduler.
Do not start Stage 2.
Working hypothesis

H11:

The batched endpoint-state lookup is not seeing trusted endpoint entities that SQL says are trusted.

Likely causes:

UUID object vs string key mismatch
different row/attribute type returned by SQLAlchemy query
tenant/RLS visibility difference between diagnostic SQL and promotion_pass session
fresh-session vs inline-session mismatch not covered by current unit tests

Do not speculate-fix yet. Diagnose first.

Step 1 — RLS/session-context verification

Re-run the endpoint-eligible count under the same session context used by scripts/run_promotion.py.

Compare:

admin/direct SQL endpoint-eligible count
tenant_session(role='user') endpoint-eligible count
count inside the same code/session style used by promotion_pass

Report for S vault:

total STAGING relationships
relationships with trusted source endpoint
relationships with trusted target endpoint
relationships with both endpoints trusted
relationship_type distribution for both-endpoint-trusted relationships

If tenant-session count is not 179:

Stop and report. The pre-cycle SQL measurement was not comparable to promotion runtime context.

If tenant-session count is 179:

Proceed to Step 2.
Step 2 — Endpoint dict diagnostic

Without running another full promotion cycle, build the same endpoint-state dictionary used in promotion_pass.

For at least 10 relationships that SQL says have both endpoints TRUSTED, report:

rel.id
rel.relationship_type

repr(rel.source_id)
type(rel.source_id)
str(rel.source_id)

repr(rel.target_id)
type(rel.target_id)
str(rel.target_id)

repr(endpoint row id)
type(endpoint row id)
str(endpoint row id)

endpoint_state_by_id key count
source key present?
target key present?
source lifecycle_state from dict
target lifecycle_state from dict

old per-rel query source lifecycle_state
old per-rel query target lifecycle_state
batched dict source lifecycle_state
batched dict target lifecycle_state

The goal is to compare:

old per-rel query behavior
new batched dict behavior

If old per-rel query sees TRUSTED but batched dict does not, H11 is confirmed.

Step 3 — Apply targeted fix only if diagnosis confirms it

If H11 is confirmed, apply the smallest behavior-preserving fix.

Preferred shape:

Normalize endpoint dictionary keys consistently for both entity row IDs and relationship endpoint IDs.

Example pattern:

def _entity_id_key(value) -> str:
    return str(uuid.UUID(str(value)))

Use equivalent robust normalization if direct UUID keys are safer in the actual code.

Required invariant:

endpoint_state_by_id key construction and rel.source_id / rel.target_id lookup use the same canonical representation.

Do not change:

endpoint-trusted requirement
relationship promotion semantics
confidence thresholds
ontology validation
scheduler behavior
Step 4 — Regression tests

Add targeted tests that would have caught this issue.

Required tests:

1. Batched endpoint lookup matches old per-rel query across a committed/persisted entity+relationship setup.
2. Test runs in a fresh session, not only inline in the same transaction.
3. Test covers UUID object vs string key normalization if both can occur.
4. Relationship remains blocked when either endpoint is STAGING.
5. Relationship becomes endpoint-eligible when both endpoints are TRUSTED.
6. No cross-tenant endpoint leakage.

Run targeted Gardener tests.

If tests fail, stop and report.

Step 5 — Architect review

Run architect/code review focused on:

endpoint lookup equivalence
UUID/key normalization correctness
tenant/RLS session behavior
no promotion semantic change
relationship still requires trusted endpoints
no cross-tenant leakage

If architect flags HIGH issues, stop and report.

Step 6 — Retry one tenant-scoped cycle on S

If Steps 1–5 pass, run one tenant-scoped promotion cycle on S:

PYTHONPATH=. python -u scripts/run_promotion.py --tenant-id 5df41308-4033-441d-b712-77928b8ea93e

Capture:

pre/post S entities by lifecycle_state
pre/post S relationships by lifecycle_state
entity promotion delta
relationship promotion delta
result.block_reasons
result.errors
endpoint-eligible relationship count before and after
runtime
global ontology.types count
global ontology.relations count

Do not run Cycle 3 automatically.

Outcome classification
If relationships promote meaningfully

Report:

H11 confirmed and fixed.
Multi-cycle convergence resumed.
Scheduler cadence likely needed later.
Stage 2 still waits for convergence/scheduler decision.
If relationships still do not promote

Report:

H11 rejected or insufficient.
Remaining blocker from block_reasons/errors.
Stage 2 remains blocked.
If counts do not change and block_reasons remain identical

Stop. Do not run more cycles. Hidden blocker remains.

Findings doc update

Update:

docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md

Add:

Stage 1G Cycle 2 no-op result
H11 endpoint-state mismatch diagnostic
RLS/session-context endpoint eligibility result
endpoint dict diagnostic sample
key-normalization or visibility finding
tests added
architect review result
retry result if run
whether Stage 2 remains blocked
Stop triggers

Stop and report if:

RLS/session endpoint count differs from admin endpoint count
diagnostic requires schema mutation
diagnostic requires global ontology change
fix would change promotion semantics
tests fail
architect flags HIGH
retry cycle affects another tenant
global ontology changes
Standing constraints

Do not:

run Cycle 3
start scheduler
start Stage 2
run Nexus 100 scoring
run full VerificationWorker
change relationship promotion semantics
change endpoint-trusted requirement
backfill ontology for USES / FUNDED_BY / RELATED_TO
review/resolve pending duplicates
touch v2
edit replit.md
Final report

Report:

RLS/admin endpoint eligibility comparison
endpoint dict diagnostic sample
root cause verdict for H11
files changed
tests run and results
architect review result
promotion retry result if run
promotion deltas
block_reasons/errors
global ontology substrate check
updated hypothesis verdicts
recommendation for next action
whether Stage 2 remains blocked
Stop condition

Stop after the H11 diagnostic/fix report.

Wait for sign-off.