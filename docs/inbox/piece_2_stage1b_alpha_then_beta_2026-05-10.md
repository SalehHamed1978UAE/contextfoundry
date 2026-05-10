# Piece 2 Stage 1B — Complete α, Then Run β Full L+S Pilot

## Alignment

- **Module touched:** Stage 1B dry-run validation, then controlled legacy-vs-scoped extraction pilot
- **Product vs implementation:** implementation-level validation of scoped ontology activation
- **Architecture-doc consistency:** matches signed-off Piece 2 Stage 1B design: scoped path is opt-in via `CF_PIECE2_SCOPED_EXTRACTION`; default remains legacy; MultiModelExtractor remains unchanged
- **Drift risk:** starting the extraction pilot before completing full 100-doc classifier validation; using stale legacy vault state as the official control; silently downgrading to a weaker pilot method
- **Out of scope:** Nexus 100 scoring, Stage 2, MultiModelExtractor prompt changes, `brain/app.py`, Gardener, Data Gates, v2, workflow restarts, `replit.md` edits

## Decision

Two-step sequence:

```text
1. Finish α: full 100-doc classifier-only dry run.
2. If α passes, run β: fresh legacy + fresh scoped extraction pilot.

Do not start β until α is complete and passes the rollback trigger.

Do not use δ as the official Stage 1B comparison.

Do not use ε unless explicitly re-authorized after α.

Why β, not δ

Stage 1B must isolate the effect of scoped ontology prompting.

The official comparison must be:

same current codebase
same corpus
two fresh tenant_ids
same extraction runner
only intended difference = CF_PIECE2_SCOPED_EXTRACTION false vs true

The existing Nexus vault is useful historical context, but it is not a clean control. It predates some current governance and scoped-prompt infrastructure, so differences between that vault and a new scoped run could be caused by old extraction state, governance changes, classification metadata changes, or scoped prompting.

A fresh L run buys evidential value. Use it.

Thread 1 — Complete α first

Run the full 100-document classifier-only dry run on ClaudeCode Nexus Industries.

Use the live extraction-time classifier path:

brain.classification_wrapper.classify()

Do not rely on persisted platform.documents.primary_domain, because the earlier dry run showed it is stale/incomplete for historical Nexus rows.

Execution options:

1. Prefer workflow/runtime execution if it avoids shell-tool memory instability.


2. If not practical, run 25-doc batches with explicit pagination and accumulate results into one output file.


3. Ensure deduplication by document ID. Report the actual unique document count.



No extraction. No STAGING mutation. No Nexus 100 scoring.

Required α report

Report:

1. Total docs evaluated.


2. Actual unique document count.


3. Count and rate for:

scoped

skip_failed_no_metadata

skip_failed_unknown_domain

no_text

classifier_error



4. Rollback trigger:



skip_failed rate > 25% ?

5. Domain distribution.


6. Document type distribution.


7. Confidence distribution:

min

max

mean

median

count below 0.30



8. Low-confidence audit-signal count that would be emitted.


9. Unknown domains, if any.


10. Classifier errors, if any.


11. Top 10 lowest-confidence docs:

filename

primary_domain

confidence

document_type

short classification_evidence preview




α stop rule

If skip_failed > 25%, stop and report. Do not run β.

If skip_failed <= 25%, proceed to Thread 2.

Thread 2 — Run β full L+S pilot

Run the official Stage 1B pilot:

Run L = fresh legacy extraction with CF_PIECE2_SCOPED_EXTRACTION=false
Run S = fresh scoped extraction with CF_PIECE2_SCOPED_EXTRACTION=true

Use:

same Nexus corpus
two fresh tenant_ids
same current codebase
same extraction runner

Do not use the existing Nexus vault as the official L baseline.

Corpus equality verification

Before extraction, verify both fresh tenant contexts have the same corpus:

same document count;

same filenames;

same file sizes or content hashes if available.


If corpus equality fails, stop and report.

Environment verification

Before each run, log and verify:

Run L: CF_PIECE2_SCOPED_EXTRACTION=false
Run S: CF_PIECE2_SCOPED_EXTRACTION=true

Also verify:

MultiModelExtractor prompt SHA unchanged:
5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963

Use the module-level constant:

src.context_foundry.extraction.multi_extractor.EXTRACTION_SYSTEM_PROMPT

β metrics to collect

For each run:

tenant_id
document count
documents extracted
documents skipped
documents failed
entities extracted
relationships extracted
STAGING count
TRUSTED count if promotion runs
audit_records count
low_confidence count
narrow_margin count if implemented
skip_failed count
skip_failed rate
runtime
estimated LLM/API spend if available

For the scoped run specifically:

number of docs using scoped prompts
domain distribution
documents with classification_status != ok
documents with unknown/unseeded primary_domain
prompt scope examples for at least 3 documents
audit_records examples

Prompt-scope evidence

For at least three scoped documents, report:

filename
primary_domain
scope domains = [core, primary_domain]
type count
relation count
example included core types
example included primary-domain types
example included core relations
example included primary-domain relations
confirmation NULL-domain rows excluded
confirmation other named domains excluded

Do not paste full prompts unless short.

Legacy-vs-scoped comparison table

Produce:

Metric	Legacy L	Scoped S	Delta

documents processed			
documents failed			
entities extracted			
relationships extracted			
audit_records			
low_confidence signals			
runtime			


Also include qualitative observations:

Did scoped extraction reduce noisy entity types?
Did scoped extraction lose expected organizational relations?
Did scoped extraction skip any docs?
Did audit_records capture low-confidence cases?
Did scoped prompts include HOLDS_POSITION / WORKS_AT / REPORTS_TO after Piece 0.6?
Did HAS_COMPENSATION appear only in finance-scoped prompts?

Findings document

Create or update:

docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md

Include:

executive summary
setup
tenant_ids
corpus equality verification
α full dry-run results
legacy-vs-scoped counts
audit_records summary
prompt-scope evidence
rollback-trigger result
recommendation for Stage 2
known limitations

Add this note:

Historical Nexus baselines have varied: 77/100, 74/100, and 71/100 in different runs. Stage 1B does not score Nexus 100. It compares extraction outputs only.

Add this limitation if the 100-doc dry run confirms narrow domain coverage:

Stage 1B validates scoped extraction on the domains actually present in the Nexus corpus. Broader validation across all eight canonical domains requires a broader corpus and is deferred.

Architect review

After α and β are complete, run architect review before final report.

Focus:

env-var gate remained isolated to run_vault_extraction.py
default behavior remains legacy
brain/app.py untouched
MultiModelExtractor prompt unchanged
telemetry safe
findings doc distinguishes fresh L/S results from historical Nexus baselines
no Stage 2 behavior slipped in

If architect finds HIGH issues, stop and report.

Rollback / stop triggers

Stop and report immediately if:

skip_failed rate > 25%
scoped prompts include NULL-domain rows
scoped prompts fall back to full union
core is missing
primary_domain is missing from scope
MultiModelExtractor prompt SHA changes
brain/app.py changes
tests fail

If β hits cost, runtime, upload, or platform limits, stop and report. Do not silently downgrade to δ or ε.

Final report

Report:

α full 100-doc dry-run results;

tenant_ids used for L and S;

corpus equality verification;

L run metrics;

S run metrics;

L-vs-S comparison;

audit_records summary;

prompt-scope evidence;

findings doc path;

architect review result;

EXTRACTION_SYSTEM_PROMPT SHA;

confirmation no Nexus 100 scoring;

confirmation no Stage 2;

confirmation no MultiModelExtractor prompt change;

confirmation no brain/app.py, Gardener, DataGate, v2, workflow, or replit.md work.


Stop condition

Stop after the Stage 1B α + β final report.

Do not start Stage 2. Do not run Nexus 100 scoring.

Compact handoff:

```text
Current state:
Stage 1B A/B/C partial complete.
106/106 tests pass.
Sample dry-run: scoped, 0 skip_failed, but full α is not complete.

Next allowed action:
Complete α across all 100 docs. If α passes, run β fresh L+S pilot.

Decision:
β is official Step D. δ is not official acceptance.

Do not do:
Do not use stale Nexus vault as official L baseline.
Do not run Nexus 100 scoring.
Do not start Stage 2.
Do not change MultiModelExtractor prompt.
Do not touch brain/app.py, Gardener, Data Gates, v2, workflows, or replit.md.

Stop condition:
Return α + β findings and wait for sign-off.