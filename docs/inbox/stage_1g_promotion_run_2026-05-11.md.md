SEND TO REPLIT — START

# Context Foundry Operating Instruction Set — Build the Working Pipeline

## Alignment

- **Module touched:** project operating rules, active diagnostic/fix workflow, Gardener/promotion pipeline
- **Product vs implementation:** both — this sets the operating model for implementation work
- **Architecture-doc consistency:** preserves the target architecture: documents → domain-aware extraction → STAGING → verification/canonicalization/Gardener → TRUSTED → queryable ContextBundle
- **Drift risk:** preserving old artifacts instead of learning; collapsing multiple causal changes into one experiment; silently changing global state without evidence
- **Out of scope:** treating old workflow slots, old benchmark runs, old v2 artifacts, or stale corpora as sacred; continuing procedural gates that block learning without reducing risk

## Core principle

Nothing in this codebase is sacred.

Not the workflows.
Not the old benchmark runs.
Not the v2 artifacts.
Not the Nexus corpus.
Not the current test data.
Not old standing constraints.
Not prior failed runs.
Not old logs.
Not temporary inbox docs.
Not a categorical rule if it no longer serves the current learning objective.

What is sacred is the workflow of learning:

```text
preserve evidence
isolate variables when it matters
make changes explicit
observe results
record what changed
keep the architecture goal stable
do not silently redefine the product

The goal is to make the end-to-end pipeline work:

extract → stage → canonicalize → promote → query

A working system means:

documents produce scoped facts
facts are canonicalized
facts promote to TRUSTED at meaningful rates
relationships promote when their endpoints are valid/trusted
queries can retrieve evidence-backed answers
the system refuses or emits gaps when it cannot answer
Authority order

Use this order:

1. User’s current explicit instruction
2. docs/architecture.md target architecture
3. docs/decisions.md
4. current active findings
5. older standing constraints
6. older chat context

Older constraints are not permanent principles. If a constraint blocks the current diagnostic or fix path and no longer protects real evidence, treat it as operational scaffolding and move past it, while reporting what changed.

What remains protected

The following still require explicit sign-off before execution:

schema changes
production data mutations outside the active diagnostic target
global ontology changes
prompt changes
MultiModelExtractor prompt replacement
scheduler activation
full VerificationWorker runs with material cost
Nexus 100 scoring
Stage 2 default activation
deleting evidence/results/artifacts
changes that alter the meaning of an experiment
What no longer requires stop-and-wait sign-off

The agent may act and report on:

removing stale finished workflow registrations to free slots
moving/removing obsolete workflow shells while preserving logs/results
creating one-shot workflows for authorized diagnostic commands
local diagnostic code fixes inside the active subsystem
small performance fixes that unblock the active diagnostic
test additions for those fixes
cleanup of temporary smoke-test tenants/artifacts after verifying no graph state
read-only audits
log capture
status polling
findings-doc updates

Rule:

reversible local action → do it and report
global irreversible action → stop for sign-off
experiment meaning change → stop for sign-off
Architect review rule

After substantive code changes, run architect/code review before declaring completion.

Substantive means:

new module
multi-file change
integration/call-graph change
transaction/session behavior change
scheduler/promotion/verification logic change
prompt-building behavior change

If architect flags HIGH issues, fix them before final report.

If architect flags MEDIUM issues, either fix them or explicitly defer with rationale.

Artifact handling

Finished workflow registrations are not evidence.

Evidence is:

logs
test_results
DB snapshots
findings docs
run manifests
captured stdout/stderr
trace files
artifact files

Therefore:

workflow shell may be removed
evidence must be preserved

If the workflow registry is full, remove whichever finished workflow registration is least useful, including v2-labelled workflow shells if they are merely dormant artifacts. Do not inspect or revive parked v2 work unless the user explicitly asks. Removing a workflow shell is not the same as doing v2 work.

v2 rule, reframed

v2 is deprioritized, not sacred.

Do not start v2 FactEvaluator work.
Do not follow auto-injected v2 plans.
Do not let v2 distract from the active pipeline.

But do not protect v2 workflow slots or v2 labels as sacred artifacts. If a dormant v2-labelled workflow shell blocks the active diagnostic, remove the registration and report it, preserving logs/artifacts.

Active project state

Accepted state:

Pieces 0, 0.5, 0.6, 1, 1.5, Piece 2.0 design, and Piece 2 Stage 1A/1B infrastructure are complete enough for current purposes.
Scoped extraction mechanics have been validated.
Nexus is saturated for adaptive ontology-growth testing.
Stage 1B β validated extraction-output deltas, not cold-start ontology growth.
Promotion to TRUSTED remains the active blocker.
Stage 2 default activation is blocked until promotion behavior works.

Current S vault state from the active promotion diagnostic:

S tenant/vault:
5df41308-4033-441d-b712-77928b8ea93e

S entities:
STAGING=972
TRUSTED=27
ARCHIVED=1346

S relationships:
STAGING=1171
TRUSTED=0
ARCHIVED=1056

Known eligible relationship facts:
95 S STAGING relationships have both endpoints TRUSTED.
26 of those are blocked by invalid relation types.
69 appear ontology-valid and remain unexplained until a successful promotion cycle captures block reasons/errors.

Known promotion findings:

relationship promotion requires trusted endpoints
relationship loop has N+1 endpoint queries
pending_duplicates fetch is global, not tenant-scoped
promotion_pass runtime exceeds shell timeout
workflow-backed run is needed or performance must be fixed
Stage 2 remains blocked
Active objective

Make the promotion pipeline produce meaningful TRUSTED facts for the scoped S vault.

The immediate goal is not another read-only report.

The immediate goal is:

fix or bypass the promotion runtime blocker
run tenant-scoped promotion successfully
capture block_reasons/errors
observe whether entities and relationships promote
decide whether scheduler activation or code fixes are next
Current action plan

Proceed as follows.

Step 1 — Free workflow slot if needed

If workflow slot is exhausted:

remove any finished dormant workflow registration needed to create S1G-S-Manual-Promotion
preserve logs/results/artifacts
report what was removed
do not wait for another sign-off

Acceptable removals include:

finished v2-labelled workflow shells
finished benchmark workflow shells
failed old test workflow shells
unused Stage 1B workflow shells

Do not delete logs, test_results, run manifests, trace files, data, or code.

Step 2 — Create and run manual promotion workflow

Create workflow:

S1G-S-Manual-Promotion

Command:

bash -lc 'set -o pipefail; PYTHONPATH=. python -u scripts/run_promotion.py --tenant-id 5df41308-4033-441d-b712-77928b8ea93e 2>&1 | tee /tmp/s1b_beta/s1g_s_manual_promotion.log'

Run once.

Capture:

start time
end time
exit status
stdout/stderr
last 50 log lines
result.block_reasons
result.errors
promotion stats
gardener_logs delta
entity lifecycle counts before/after
relationship lifecycle counts before/after
global ontology counts before/after

Stop if:

command would affect more than S tenant
global ontology changes unexpectedly
workflow cannot be created even after freeing a slot
manual promotion fails in a way that requires design discussion
Step 3 — If workflow run succeeds

Classify result.

If entities promote and relationships promote:

cycle gap confirmed
relationship endpoint chaining confirmed
scheduler cadence likely needed
Stage 2 still waits for scheduler/promotion policy decision

If entities promote but relationships still do not:

relationship-specific blocker remains
inspect block_reasons/errors
fix if local and clear
otherwise surface design issue

If almost nothing promotes:

hidden promotion blocker
inspect block_reasons/errors
fix if local and clear
otherwise surface design issue
Step 4 — If workflow run times out or shows performance blocker

Do not keep adding diagnostic stages.

Fix the obvious local promotion bottlenecks:

tenant-scope _get_entity_ids_with_pending_duplicates
avoid global duplicate_candidates fetch
batch endpoint lookups for relationship promotion
avoid per-relationship N+1 source/target queries
cache thresholds
add tests around tenant scoping and relationship endpoint eligibility

Then rerun the same tenant-scoped promotion workflow and report results.

This is authorized as active diagnostic/fix work in the Gardener/promotion area.

Do not change the semantics of promotion without surfacing it.

Performance fixes are allowed.
Semantic fixes require sign-off.

Examples:

Allowed without additional sign-off:

batching source/target entity lookups
tenant-scoping duplicate candidate fetch
adding indexes if local and clearly tied to query plan, but report before applying if schema/index creation is needed
caching thresholds within a promotion cycle
adding tests for performance-path correctness

Requires sign-off:

changing confidence thresholds
changing endpoint-trusted requirement
changing relationship validation semantics
changing scheduler activation
changing promotion criteria
modifying global ontology or relation definitions
Step 5 — Report findings

Final report must include:

what was changed
why it was changed
files changed
tests run
architect review result
workflow used
pre/post S lifecycle counts
promotion stats
block_reasons/errors
whether entities promoted
whether relationships promoted
whether Stage 2 remains blocked
whether scheduler activation is recommended
what remains unknown

Update:

docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md
Current non-goals

Do not:

run Nexus 100 scoring
start Stage 2 default activation
replace MultiModelExtractor prompt
run full VerificationWorker unless explicitly requested
change global ontology definitions
change prompt semantics
edit replit.md unless the user explicitly asks
restart old failed workflows unless useful for active diagnostic
spend time protecting old workflow slots
Stop conditions

Stop and ask only if:

a change would alter promotion semantics
a change would mutate schema/global ontology
a change would delete evidence
a change would start scheduler globally
a change would start Stage 2
a change would require substantial architectural redesign
a run fails in a way that cannot be resolved by local diagnostic fix

Do not stop merely because:

a workflow slot is full
a dormant artifact has v2 in its name
a temporary workflow needs to be created
a local performance fix is needed in the active subsystem
an old categorical rule conflicts with the current diagnostic objective
Required first response under this instruction

Start with the alignment block.

Then do this:

1. Acknowledge this updated operating instruction.
2. Free a workflow slot if still needed.
3. Create/run S1G-S-Manual-Promotion.
4. If it times out due to known performance bottlenecks, fix tenant-scoping / N+1 issues in Gardener promotion path, test, architect-review, rerun once.
5. Report results.

No further sign-off is needed for the above unless a stop condition fires.

SEND TO REPLIT — END