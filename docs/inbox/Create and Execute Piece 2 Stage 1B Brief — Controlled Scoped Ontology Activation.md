# Task: Create and Execute Piece 2 Stage 1B Brief — Controlled Scoped Ontology Activation

## Alignment

- **Module touched:** `docs/inbox/`, then controlled ontology-path scoped-prompt activation
- **Product vs implementation:** implementation-level validation of Piece 2 Stage 1
- **Architecture-doc consistency:** matches signed-off Piece 2.0 design and Stage 1A implementation: scoped prompting exists behind `enforce_scoped_prompts=True`; Stage 1B proves the scoped path through the actual runner without flipping defaults
- **Drift risk:** treating feature-flagged infrastructure as production-active scoped extraction; accidentally starting Stage 2 or changing `MultiModelExtractor`
- **Out of scope:** Stage 2 adapter, Stage 3 prompt replacement, Nexus 100, Gardener, Data Gates, v2, workflow restarts, `replit.md` edits

## Step 1 — Save the brief

Create:

```text
docs/inbox/piece_2_stage1b_controlled_activation_2026-05-10.md

with the following content.

Piece 2 Stage 1B — Controlled Activation of Scoped Ontology Path
Alignment
Module touched: OntologyCentricPipeline scoped-path activation, run_vault_extraction.py ontology-path flag/wiring if needed, scoped prompt smoke tests, audit_records verification
Product vs implementation: implementation-level validation of Piece 2 Stage 1
Architecture-doc consistency: matches signed-off Piece 2 design: ontology path uses core ∪ primary_domain scoped prompts; MultiModelExtractor remains unchanged
Drift risk: mistaking feature-flagged scoped infrastructure for production-active scoped extraction; accidentally starting MultiModelExtractor Stage 2
Out of scope: MultiModelExtractor adapter/replacement, EXTRACTION_SYSTEM_PROMPT changes, Gardener, Data Gates, v2 FactEvaluator, Nexus 100, workflow restarts, replit.md edits
Standing Constraints
No replit.md edits.
No workflow restarts.
No v2 work.
No Nexus 100 run.
No Gardener changes.
No Data Gate changes.
No MultiModelExtractor prompt changes.
No Stage 2 adapter work.
Do not flip scoped prompts on globally by default.
Every response begins with the alignment block.
Read First
docs/architecture.md
docs/decisions.md
docs/piece2_domain_scoped_prompting_design_2026-05.md
Piece 2 Stage 1A final report
src/context_foundry/extraction/ontology_centric_pipeline.py
src/context_foundry/ontology/prompt_generator.py
src/context_foundry/extraction/audit_recorder.py
scripts/run_vault_extraction.py
tests/ontology/test_piece_2_stage1_scoped_prompts.py
tests/extraction/test_pipeline_classification.py
Goal

Close the Stage 1 gap.

Current state:

scoped prompt infrastructure exists;
enforce_scoped_prompts=True activates the scoped path;
default callers still run legacy behavior;
this avoided silent production behavior change.

Required Stage 1B outcome:

provide an explicit, controlled way to run the ontology extraction path with scoped prompts enabled;
prove it works on a small smoke;
keep the default behavior unchanged;
keep MultiModelExtractor unchanged.
A. Architect verification

Run architect review on the final post-fix Stage 1A code, focused only on:

enforce_scoped_prompts=True activates the scoped path.
enforce_scoped_prompts=False preserves legacy behavior.
AuditRecorder.emit() SAVEPOINT isolation is correct.
Unknown-domain handling is correct.
No MultiModelExtractor prompt change occurred.
No Stage 2 behavior slipped in.

If architect finds a blocker, patch only the blocker and rerun targeted tests.

B. Controlled activation path

Check whether scripts/run_vault_extraction.py or the ontology extraction entry point already exposes a way to instantiate:

OntologyCentricPipeline(enforce_scoped_prompts=True)

If it already exists:

use it;
do not add a new flag.

If it does not exist:

add a minimal explicit opt-in flag or env var, for example:
--enforce-scoped-prompts

or:

CF_ENFORCE_SCOPED_PROMPTS=true

Requirements:

Default remains False.
The flag affects only the ontology-centric path.
The flag does not affect MultiModelExtractor.
The flag does not change prompts unless explicitly enabled.
The flag value is logged at ontology extraction start.

Do not silently flip the default to scoped.

C. Controlled smoke

Run a small controlled ontology-path smoke with scoped prompts enabled.

Preferred:

1–2 Nexus documents through ontology path with enforce_scoped_prompts=True.

If full extraction is too slow or costly:

run a dry-run/unit-level smoke proving:
the runner instantiates the pipeline with enforce_scoped_prompts=True;
classification metadata reaches the pipeline;
scoped prompt builder receives primary_domain;
prompt scope is core ∪ primary_domain.

The smoke must verify:

core included.
primary_domain included.
other named domains excluded.
NULL-domain rows excluded.
no full-union fallback.
low-confidence audit record written when confidence < 0.30.
prompt scope unchanged by confidence.
missing/failed classification does not fall back to union.
MultiModelExtractor prompt SHA unchanged.
D. Audit record verification

Verify platform.audit_records behavior:

Insert happens for low-confidence scoped ontology smoke.
signal_type='low_confidence'.
severity='warn'.
payload includes:
document_id
primary_domain
classification_confidence
classifier_version
classification_evidence
Audit insert failure does not roll back extraction/session state.
E. Prompt output verification

Paste one scoped prompt example:

document
primary_domain
scope domains = [core, primary_domain]
type count
relation count
example included types
example included relations
example excluded NULL-domain row
example excluded other-domain row

Do not paste the full prompt unless short enough. Summarize plus include enough evidence to verify scope.

F. Default behavior verification

Run or unit-test default behavior:

OntologyCentricPipeline(enforce_scoped_prompts=False)

Expected:

legacy branch used;
no scoped prompt enforcement;
no unexpected audit_records from scoped logic;
existing callers remain unchanged.
G. Tests

Run the relevant tests:

tests/ontology/test_piece_2_stage1_scoped_prompts.py
tests/extraction/test_pipeline_classification.py
tests/extraction/test_audit_recorder.py
tests/extraction/test_multi_extractor_prompt_sha.py

If there are new tests for the flag/activation path, include them.

H. Final report

Report:

architect review result;
whether a flag/env var was added or existing path used;
files changed;
scoped smoke result;
audit_records example;
scoped prompt summary;
default-behavior verification;
tests run and pass/fail;
EXTRACTION_SYSTEM_PROMPT SHA check;
confirmation Stage 2 was not started;
confirmation no Gardener/DataGate/v2/Nexus100/workflow/replit.md work occurred.
Stop Condition

Stop after Piece 2 Stage 1B final report.

Do not start Piece 2 Stage 2.
Do not run Nexus 100.
Wait for sign-off.

Step 2 — Execute

After saving the inbox brief, execute it.

Stop after the Stage 1B final report.


Then send:

```text
Read docs/inbox/piece_2_stage1b_controlled_activation_2026-05-10.md and execute. Standing constraints unchanged.
Compact handoff
Current state:
Piece 2 Stage 1A landed and tests pass, but it is feature-flagged infrastructure only.

Next allowed action:
Stage 1B controlled activation smoke through actual ontology path with enforce_scoped_prompts=True.

Do not do:
Do not start Stage 2.
Do not change MultiModelExtractor prompt.
Do not run Nexus 100.
Do not touch Gardener, Data Gates, v2, workflows, or replit.md.

Stop condition:
Replit returns Stage 1B final report and waits for sign-off.