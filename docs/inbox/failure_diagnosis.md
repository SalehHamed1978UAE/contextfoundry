Stage 1B β — Investigate Dead S Run Before Restart

Alignment

Module touched: read-only investigation of S partial outputs, then controlled recovery decision

Product vs implementation: execution recovery for Stage 1B β scoped run

Architecture-doc consistency: preserves signed-off β design: fresh L/S vaults, same corpus, same current codebase, only env-var differs

Drift risk: restarting S blindly and losing reusable partial extraction output; running S concurrently with unrelated LLM-heavy test workflows; treating a platform recycle as a product failure

Out of scope: Stage 2, Nexus 100 scoring, prompt changes, MultiModelExtractor changes, brain/app.py, Gardener changes, Data Gates, v2, workflow restarts other than the already-authorized S workflow, replit.md edits


Updates from user

1. The 03:04 event was platform-triggered, not user-triggered. I was asleep. Treat this as a Replit/workspace recycle or platform runtime event. The underlying cause is unknown and may recur.


2. For this specific Stage 1B β recovery, the prior “do not kill Test workflows” rule is relaxed for test workflows only. You may stop currently running Test workflows if doing so helps S complete cleanly.


3. Do not kill or restart Start All.


4. v2 stays parked. brain/app.py untouched. MultiModelExtractor untouched. No replit.md edits.



Decision

Do not restart S yet.

First perform a read-only disk and DB investigation.

Step 1 — Read-only S artifact investigation

Inspect:

extraction_outputs/stage1b-s_2026-05-10/
run manifests
per-model output folders
gpt / claude JSON outputs
consensus outputs if any
logs for S1B-Beta-S-Extract
/tmp/s1b_beta/

Report:

does extraction_outputs/stage1b-s_2026-05-10/ exist?
number of per-doc GPT outputs
number of per-doc Claude outputs
number of complete paired doc outputs
any consensus outputs
any run_manifest
latest modified timestamp
last successful doc, if identifiable
any traceback or API error

Do not delete anything.

Do not mutate the DB.

Step 2 — Confirm S DB state

Reconfirm:

S vault id = 5df41308-4033-441d-b712-77928b8ea93e
S documents = 100
S entities = 0
S relationships = 0
S audit_records = 0
S extraction_requests status counts
global ontology.types = 1037
global ontology.relations = 254
ontology rows created/updated since S start = 0

Step 3 — Classify restart mode

After Step 1 and Step 2, classify S into one of these cases.

Case A — Reusable partial extraction exists

Criteria:

some meaningful per-doc model outputs exist
outputs are well-formed
run_vault_extraction.py resume logic can skip already-produced model outputs
no KG writes occurred

Recommendation:

resume S workflow with the same command
do not clear outputs

Case B — No useful partial output

Criteria:

no meaningful model outputs exist
or outputs are corrupt / too incomplete to resume

Recommendation:

cold restart S workflow with the same command
no cleanup needed unless corrupt files would confuse resume logic

Case C — Partial outputs are present but incompatible with resume

Criteria:

some files exist
but run_vault_extraction.py would misread them or skip incorrectly

Recommendation:

stop and report
do not delete
paste cleanup/resume plan for sign-off

Step 4 — Stop unrelated Test workflows if active

Check:

Test: ClaudeCode Medsync
Test: ClaudeCode Nexus
Test: Manus Orion
Test: Ontology Vault

For this Stage 1B β recovery only:

if Test: ClaudeCode Medsync or Test: ClaudeCode Nexus is actively running, stop it;

if Test: Manus Orion or Test: Ontology Vault is failed, leave it alone;

do not restart failed Test workflows;

do not touch Start All.


Reason:

S is a long LLM-heavy extraction run.
Concurrent test workflows are not relevant to Stage 1B β.
Stopping them frees API/CPU capacity and removes a concurrent-workload variable.

Report what was stopped.

Step 5 — Recovery recommendation

After artifact investigation and test-workflow cleanup, report:

artifact investigation result
S DB state
test workflow status / cleanup actions
case classification A/B/C
recommended restart mode
whether any cleanup is needed
whether S can safely be restarted

Robustness note for findings doc

Add this to:

docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md

Stage 1B β experienced a platform-triggered workspace restart at ~03:04 UTC during S's first attempt. The event was not user-triggered. It killed the S extraction process after several hours of runtime with zero KG writes. Recovery used [resume mode | cold restart] based on disk artifact state. Future long-running controlled experiments in this environment should anticipate workspace recycle events and rely on resumable extraction or workflow-level recovery.

Fill in [resume mode | cold restart] after the disk investigation.

Stop conditions

Stop and report if:

partial outputs exist but are not clearly resumable
test workflow stop fails
S DB has nonzero KG writes
global ontology changed
another platform recycle pattern is detected

Stop condition for this turn

Stop after:

read-only S artifact investigation
S DB state confirmation
Test workflow cleanup
restart-mode recommendation

Do not restart S until sign-off on the restart mode.