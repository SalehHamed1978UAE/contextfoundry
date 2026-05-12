SEND TO REPLIT — START

# Stage 2 Readiness Follow-up — Bounded Gardener Promotion on Clean Stage 1J Vault

## Alignment

- **Module touched:** one tenant-scoped Gardener promotion run on the clean Stage 1J vault; read-only pre/post diagnostics
- **Product vs implementation:** implementation-level validation before Stage 2 implementation or default activation
- **Architecture-doc consistency:** follows Stage 2 Readiness Triage: design conversation is ready, but implementation needs one bounded promotion validation first
- **Drift risk:** claiming Stage 2 implementation readiness while the clean vault still has 0 TRUSTED facts; running broader scheduler/global promotion instead of one tenant-scoped validation
- **Out of scope:** Stage 2 implementation, scheduler activation, Nexus 100 scoring, schema changes, ontology backfill, orphan relation repair, historical contaminated vault repair, v2 work, `replit.md` edits

## Sign-off

Stage 2 Readiness Triage is accepted.

Accepted verdict:

```text
B — Stage 2 design conversation is ready now.
Implementation needs one bounded validation first.
Default activation needs three structural items.

Accepted clean vault state:

vault_id = ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda
documents = 100
entities = 2146, all STAGING
relationships = 2099, all STAGING
verified entities = 36
verified relationships = 10
fact_verifications = 55
TRUSTED entities = 0
TRUSTED relationships = 0
cross-tenant invariant remains clean
ontology.types = 1037
ontology.relations = 254
Decision

Authorize one bounded tenant-scoped Gardener promotion cycle on the clean Stage 1J vault.

Do not start scheduler.

Do not run global promotion.

Do not run promotion on contaminated legacy vaults.

Do not run Nexus 100 scoring.

Goal

Answer:

Can the clean, tenant-safe Stage 1J vault convert STAGING facts to TRUSTED under the fixed Gardener / VerificationWorker path?

This is the minimum required validation before Stage 2 implementation planning.

Pre-run snapshot

Before running promotion, capture:

timestamp
vault_id
entity count by lifecycle_state
relationship count by lifecycle_state
verified entity count
verified relationship count
fact_verifications count by status
promotion_thresholds active/default values
Gardener config:
  require_verification_for_promotion
  validate_against_ontology
  min_dwell_time_hours or equivalent
global ontology.types count
global ontology.relations count
cross-tenant relationship count for this vault

Also capture eligibility estimates:

STAGING entities total
STAGING entities confidence >= default threshold
STAGING entities validation_status valid
STAGING entities with verification status VERIFIED
STAGING relationships total
STAGING relationships confidence >= default threshold
STAGING relationships validation_status valid
STAGING relationships with both endpoints in same tenant
STAGING relationships with both endpoints TRUSTED
orphan relationship type counts
orphan entity type counts
Run

Run exactly one tenant-scoped promotion cycle:

PYTHONPATH=. python -u scripts/run_promotion.py --tenant-id ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda

If the foreground command cannot complete because of timeout, use a one-shot workflow only for this exact tenant-scoped command.

If a workflow slot issue appears, remove a finished dormant workflow registration, preserving logs/artifacts, and report what was removed.

Post-run snapshot

After the command exits, capture:

exit status
runtime
whether COMMIT occurred
new gardener_logs cycle id
entity count by lifecycle_state
relationship count by lifecycle_state
newly promoted entity count
newly promoted relationship count
newly archived entity count
newly archived relationship count
block_reasons
errors
global ontology.types count
global ontology.relations count
cross-tenant relationship count for this vault
Interpret outcome
Case 1 — Meaningful TRUSTED promotion

If entities and/or relationships promote meaningfully:

Clean-vault STAGING → TRUSTED path validated.
Stage 2 implementation planning may proceed, with default activation still gated by structural items.
Case 2 — No promotion

If no facts promote:

Promotion remains blocked on clean data.
Stage 2 implementation is not ready.

Report exact block reasons.

Case 3 — Entities promote but relationships do not

Report:

entity promotion works
relationship promotion remains blocked
endpoint trust / orphan relation / verification gate analysis required
Case 4 — Run errors or times out

Stop and report:

runtime
last log lines
whether any commit occurred
pre/post counts
likely blocker

Do not retry automatically.

Required relationship/orphan analysis

After the promotion cycle, report impact of the 6 orphan relation types:

FUNDED_BY
USES
RELATED_TO
OWNED_BY
FOCUSES_ON
WORKS_FOR

For each:

count in STAGING
count promoted, if any
whether missing from ontology.relations blocked promotion
recommended disposition:
  map to existing governed relation
  add through governance later
  block from extraction
  accept as known limitation

Also report PROJECT entity type behavior:

count of PROJECT entities
whether they were blocked by ontology mismatch
whether normalizer casing fix should be Stage 1L or Stage 2 pre-implementation
Findings doc update

Update:

docs/findings/stage_2_readiness_triage_2026-05-12.md

Add:

bounded Gardener promotion result
pre/post lifecycle counts
block_reasons
orphan relation impact
PROJECT casing impact
whether Stage 2 design / implementation / default activation are ready
Do not do

Do not:

start scheduler
start Stage 2 implementation
run Nexus 100 scoring
run full VerificationWorker beyond this promotion validation
mutate ontology
backfill orphan relation types
fix PROJECT normalizer
add DB trigger
add schema constraint
repair historical contaminated vaults
touch v2
edit replit.md
Final report

Report:

pre-run snapshot
command run
runtime and exit status
post-run snapshot
promotion deltas
block_reasons/errors
orphan relation impact
PROJECT casing impact
global ontology invariant check
cross-tenant invariant check
Stage 2 readiness verdict after promotion
recommended next action
findings doc path
Stop condition

Stop after the bounded promotion report.

Wait for sign-off before any Stage 2 implementation, scheduler activation, schema work, ontology work, or additional promotion cycles.