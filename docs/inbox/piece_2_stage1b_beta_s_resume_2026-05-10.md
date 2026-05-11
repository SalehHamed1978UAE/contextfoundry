Stage 1B β — Resume S After Platform-Kill Recovery

Alignment

Module touched: Stage 1B β S-run recovery only

Product vs implementation: execution recovery for the scoped S run

Architecture-doc consistency: preserves signed-off β design: fresh L/S vaults, same corpus, same current codebase, only env-var differs

Drift risk: clearing valid partial extraction artifacts unnecessarily; restarting S while unrelated test workflows compete for API/CPU; treating a platform/runtime kill as product failure

Out of scope: Stage 2, Nexus 100 scoring, prompt changes, MultiModelExtractor changes, brain/app.py, Gardener changes, Data Gates, v2, unrelated workflow restarts, replit.md edits


Decision

Proceed with Case A: resume mode.

Do not clear partial outputs.

Do not cold-restart.

Restart S1B-Beta-S-Extract with the same approved command:

CF_PIECE2_SCOPED_EXTRACTION=true \
python -u scripts/run_vault_extraction.py --vault-id 5df41308-4033-441d-b712-77928b8ea93e

Accepted diagnosis

The read-only recovery investigation is accepted:

extraction_outputs/stage1b-s_2026-05-10/ exists
GPT-4o-mini outputs: 37
Claude Sonnet outputs: 36
paired complete docs: 36
GPT-only partial doc: 1
consensus outputs: none
run manifest: none
S entities: 0
S relationships: 0
S audit_records: 0
global ontology.types: 1037
global ontology.relations: 254

The partial outputs are valid resume input. Sampled JSON files parse cleanly and contain real entities/relationships.

Before restarting S

Reconfirm:

S vault ID = 5df41308-4033-441d-b712-77928b8ea93e
S entities = 0
S relationships = 0
S audit_records = 0
L remains stable at 2258 entities / 2192 relationships
ontology.types = 1037
ontology.relations = 254
EXTRACTION_SYSTEM_PROMPT SHA = 5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963
no unrelated Test workflows are running

If any check fails, stop and report.

Restart S

Restart S1B-Beta-S-Extract.

Capture:

restart time
workflow state
command
S restart epoch

Required early-resume check

In the first 5–10 minutes, confirm the resume scan detects the partial artifacts.

Expected shape:

already extracted / skipped: about 36 paired docs
partial/unpaired: 1 doc needing missing Claude pair
remaining: about 63 docs needing both models

Exact wording may differ.

If the scan reports something like:

Already extracted: 0
Remaining: 100

then stop and report before continuing. That would mean resume logic did not detect the surviving artifacts and S is about to re-extract from scratch.

During S

Poll approximately every 10 minutes.

Report:

workflow status
model-output progress if visible
entities total
relationships total
audit_records count
low_confidence count
skip_failed count/rate
ontology.types count
ontology.relations count
ontology rows created/updated since S restart

Stop triggers

Stop and report if:

resume scan does not detect partial artifacts
S workflow fails again
S dies again within roughly 30–60 minutes of restart before consensus/staging
another platform recycle kills S
partial outputs are misread or skipped incorrectly
S DB gets nonzero rows before consensus/staging should happen
skip_failed rate > 25%
scoped prompts include NULL-domain rows
scoped prompts fall back to full union
core is missing from scope
primary_domain is missing from scope
ontology.types changes
ontology.relations changes
MultiModelExtractor prompt SHA changes
brain/app.py changes
runtime from restart exceeds 3 hours without clear progress
runtime/spend becomes concerning

If S is killed again by a platform/runtime event, do not immediately restart. Investigate disk state again and report the recurrence.

Findings doc notes

When S completes, add to:

docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md

S first attempt died at ~23:40 UTC after ~41 minutes, before reaching consensus/staging and before writing KG rows. The later ~03:04 workspace recycle was not the moment S died; S was already dead. Cause of the 23:40 kill is unknown, possibly resource-related. Recovery used resume mode from 36 paired per-doc model outputs plus 1 GPT-only partial output.

Also record:

Surviving per-doc JSON outputs do not include extraction_scope/scope fields. Scoped-prompt activation cannot be proven from partial per-doc artifacts alone. It must be verified after S completes via manifest/telemetry/prompt-scope evidence.

And:

Test: ClaudeCode Medsync was stopped/removed during recovery to reduce unrelated LLM/API and CPU contention. It can be re-registered after Stage 1B closes if needed.

After S completes

After S exits and stabilizes:

1. Capture final S snapshot.


2. Compare L vs S:

total entities;

total relationships;

entity type distribution;

relationship type distribution;

audit_records;

low_confidence signals;

runtime.



3. Capture prompt-scope evidence for at least 3 scoped S documents.


4. Update:



docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md

5. Add the platform/runtime robustness note.


6. Run architect review.


7. Paste final Stage 1B β report.


8. Stop for sign-off.



Continue constraints

Do not start Stage 2.

Do not run Nexus 100 scoring.

Do not touch prompts, MultiModelExtractor, brain/app.py, Gardener, Data Gates, v2, unrelated workflows, or replit.md.

Do not restart Medsync now.

Do not restart failed test workflows.

Do not touch Start All.

Stop condition

Stop after S completes, final β report is produced, and architect review is done.

Do not begin Stage 2.