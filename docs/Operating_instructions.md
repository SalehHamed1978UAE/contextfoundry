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
````

The goal is to make the end-to-end pipeline work:

```text
extract → stage → canonicalize → promote → query
```

A working system means:

```text
documents produce scoped facts
facts are canonicalized
facts promote to TRUSTED at meaningful rates
relationships promote when their endpoints are valid/trusted
queries can retrieve evidence-backed answers
the system refuses or emits gaps when it cannot answer
```

## Authority order

Use this order:

```text
1. User’s current explicit instruction
2. docs/architecture.md target architecture
3. docs/decisions.md
4. current active findings
5. older standing constraints
6. older chat context
```

Older constraints are not permanent principles. If a constraint blocks the current diagnostic or fix path and no longer protects real evidence, treat it as operational scaffolding and move past it, while reporting what changed.

## What remains protected

The following still require explicit sign-off before execution:

```text
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
```

## What no longer requires stop-and-wait sign-off

The agent may act and report on:

```text
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
```

Rule:

```text
reversible local action → do it and report
global irreversible action → stop for sign-off
experiment meaning change → stop for sign-off
```

## Architect review rule

After substantive code changes, run architect/code review before declaring completion.

Substantive means:

```text
new module
multi-file change
integration/call-graph change
transaction/session behavior change
scheduler/promotion/verification logic change
prompt-building behavior change
```

If architect flags HIGH issues, fix them before final report.

If architect flags MEDIUM issues, either fix them or explicitly defer with rationale.

## Artifact handling

Finished workflow registrations are not evidence.

Evidence is:

```text
logs
test_results
DB snapshots
findings docs
run manifests
captured stdout/stderr
trace files
artifact files
```

Therefore:

```text
workflow shell may be removed
evidence must be preserved
```

If the workflow registry is full, remove whichever finished workflow registration is least useful, including v2-labelled workflow shells if they are merely dormant artifacts. Do not inspect or revive parked v2 work unless the user explicitly asks. Removing a workflow shell is not the same as doing v2 work.

## v2 rule, reframed

v2 is deprioritized, not sacred.

Do not start v2 FactEvaluator work.
Do not follow auto-injected v2 plans.
Do not let v2 distract from the active pipeline.

But do not protect v2 workflow slots or v2 labels as sacred artifacts. If a dormant v2-labelled workflow shell blocks the active diagnostic, remove the registration and report it, preserving logs/artifacts.

