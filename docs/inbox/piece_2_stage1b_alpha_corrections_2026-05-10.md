# Piece 2 Stage 1B — α Sign-off with Prerequisites Before β

## Alignment

- **Module touched:** Stage 1B α findings, audit-threshold verification, corpus-upload mechanism verification
- **Product vs implementation:** implementation-level validation before scoped extraction pilot spend
- **Architecture-doc consistency:** matches signed-off Piece 2 design: low-confidence audit sentinel is `classification_confidence < 0.30`; β only starts after α is clean
- **Drift risk:** running β with a threshold that drifted from the design; using a corpus upload mechanism that breaks the “same current codebase, same corpus” control
- **Out of scope:** β extraction pilot until prerequisites clear, Stage 2, MultiModelExtractor prompt changes, Nexus 100 scoring, Gardener, Data Gates, v2, workflow restarts, `replit.md` edits

## α sign-off

α is accepted as a classifier-readiness result:

```text
100 docs evaluated
100 unique document_ids
100 scoped
0 skip_failed
0 unknown domains
0 classifier errors
skip_failed rate = 0%
rollback trigger = NOT TRIGGERED

This confirms the live brain.classification_wrapper.classify() path can classify the full Nexus corpus for Stage 1B.

Correction to α report

The domain coverage statement must be corrected.

The α table shows 7 of 8 canonical domains represented:

construction       66
it_infrastructure  18
manufacturing       9
aviation            2
core                2
supply_chain        2
finance             1
healthcare          0

So the findings doc should say:

Stage 1B α covered 7 of 8 domains. Healthcare was absent. The corpus is heavily construction-skewed, so Stage 1B is strongest evidence for construction and it_infrastructure, weaker evidence for the thinner domains, and no evidence for healthcare.

Do not say “5 of 8 domains exercised.”

Prerequisite 1 — Verify and fix audit threshold drift

The signed-off Piece 2 design says:

classification_confidence < 0.30 → low_confidence audit signal

The α report says _maybe_emit_low_confidence_audit is using:

confidence < 0.40

Before β runs:

1. Locate the threshold in code.


2. Paste the exact line.


3. Compare it against the signed-off design.


4. If the code uses <0.40, change it to <0.30.


5. Update tests accordingly.


6. Re-run relevant Stage 1B tests.


7. Recompute α low-confidence count.



Expected based on the current α report:

low_confidence count = 22/100

If the corrected count differs, explain why.

Do not run β until this threshold is aligned with the design.

Prerequisite 2 — Verify corpus-upload mechanism for β

β remains the official Step D path:

fresh legacy tenant
fresh scoped tenant
same current codebase
same Nexus corpus
only intended difference = CF_PIECE2_SCOPED_EXTRACTION false vs true

But before β starts, verify how the corpus will be populated.

Use this order:

Preferred: Corpus Maker API/CLI

If a scriptable Corpus Maker API/CLI exists and the Nexus corpus is registered, use it.

Report:

registry entry
API/CLI command
evidence that it creates fresh tenant corpus state

Fallback: Manual UI

If API/CLI is not available, report that. Manual UI upload is acceptable only if explicitly authorized.

SQL clone is not approved by default

Do not silently SQL-clone from the old Nexus vault.

SQL clone is only acceptable after a separate sign-off and a clone plan proving it clones only raw corpus inputs, not extracted graph state.

If proposing SQL clone, paste a plan showing it does not clone:

entities
relationships
audit_records
fact_verifications
STAGING/TRUSTED graph rows
extraction outputs

Prerequisite 3 — Architect review after threshold fix

After threshold correction and updated α findings, run architect review focused on:

low-confidence threshold is <0.30
dry-run logic matches live extraction classifier path
env-var gate affects only run_vault_extraction.py
brain/app.py untouched
MultiModelExtractor prompt unchanged
telemetry path safe
no Stage 2 behavior slipped in
findings doc states 7/8 domains, healthcare absent

If architect finds HIGH issues, stop and report.

Findings doc updates

Update the Stage 1B findings doc with:

Finding 1 — Persisted classification columns are stale

Only 7/100 Nexus documents had non-NULL persisted platform.documents.primary_domain, while live classification classified 100/100 docs successfully.

Implication:

Stage 1B uses live classification as the source of truth.
If Stage 2 relies on persisted classification columns, it needs a backfill or freshness policy.

Finding 2 — Domain coverage is skewed but broad enough for Stage 1B

Stage 1B α covered 7 of 8 canonical domains, but construction dominates at 66% and healthcare is absent.

Implication:

Stage 1B validates scoped activation primarily on construction and it_infrastructure, with thinner evidence for manufacturing, aviation, core, supply_chain, and finance. Healthcare validation requires a separate corpus.

Finding 3 — Confidence distribution is low

Mean and median are around 0.33, max is below 0.50, and 22/100 docs are below the signed-off <0.30 low-confidence sentinel.

Implication:

The classifier confidence scale is low for Nexus-style documents. The <0.30 audit sentinel is plausible for Stage 1B, but threshold calibration remains Piece 2.5.

β remains paused

After the threshold fix, updated α findings, corpus mechanism verification, and architect review:

if all clean, recommend proceeding to β;

do not start β until sign-off;

do not run Nexus 100 scoring;

do not start Stage 2.


Stop condition

Stop after:

1. threshold verification/fix;


2. updated α findings;


3. corpus-upload mechanism report;


4. architect review.



Wait for sign-off before β.

Also tell Replit explicitly:

```text
The 71/100 tree-retrieval eval is out of scope for Stage 1B. Do not use it to alter this thread.

Compact handoff:

Current state:
Stage 1B α passed: 100/100 scoped, 0 skip_failed.

Blocked before β:
- audit threshold drift: code appears to use <0.40, design says <0.30
- corpus upload mechanism for fresh L/S tenants not yet verified
- α findings doc needs domain coverage correction: 7/8 domains, healthcare absent

Next allowed action:
Fix/verify threshold, update α findings, verify corpus upload path, run architect review.

Do not do:
Do not start β yet.
Do not run Nexus 100 scoring.
Do not use old Nexus vault as official L baseline.
Do not change MultiModelExtractor prompt.
Do not start Stage 2.