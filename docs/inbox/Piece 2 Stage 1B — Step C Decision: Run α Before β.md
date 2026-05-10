# Piece 2 Stage 1B — Step C Decision: Run α Before β

## Alignment

- **Module touched:** Stage 1B dry-run validation only
- **Product vs implementation:** implementation-level validation before scoped extraction pilot
- **Architecture-doc consistency:** matches Stage 1B brief Section C and Decision 5a: validate `skip_failed > 25%` rollback trigger before extraction spend
- **Drift risk:** jumping to full L+S extraction based on a 20-doc sample that may not represent the full Nexus corpus
- **Out of scope:** Step D extraction pilot, Stage 2, MultiModelExtractor prompt changes, Nexus 100 scoring, Gardener, Data Gates, v2, workflow restarts, `replit.md` edits

## Decision

Proceed with **Option α**:

```text
Run full 100-doc classifier-only dry-run on ClaudeCode Nexus Industries.
Use the live extraction-time path:
Plain text
brain.classification_wrapper.classify()
Do not rely on the persisted platform.documents.primary_domain column for this dry run. The 20-doc sample showed that the persisted column is stale/incomplete, while the live classifier path is the Stage 1B execution path.
Required outputs
For the 100-doc dry run, report:
Total docs evaluated.
Count and rate for:
scoped
skip_failed_no_metadata
skip_failed_unknown_domain
no_text
classifier_error
Rollback-trigger result:
Plain text
skip_failed rate > 25% ?
Domain distribution.
Document type distribution.
Confidence distribution:
min
max
mean
median
count below 0.30
Low-confidence audit-signal count that would be emitted.
Any unknown domains.
Any classifier errors.
Top 10 lowest-confidence docs with:
filename
primary_domain
confidence
document_type
short classification_evidence preview
Findings to record in the Stage 1B findings doc
Record these two findings from the 20-doc dry run:
Finding 1: Persisted classification columns are stale
Only 7/100 Nexus documents currently have non-NULL platform.documents.primary_domain, but live classification via brain.classification_wrapper.classify() classified all 20 sampled docs successfully.
Implication:
Plain text
For Stage 1B, live classification is the source of truth.
If Stage 2 plans to rely on persisted classification columns, it needs a backfill or freshness check.
Finding 2: 20-doc sample may be domain-skewed
The 20-doc sample appears it_infrastructure-heavy. The full 100-doc dry run must verify whether Nexus actually exercises the expected domain breadth.
Step D pilot remains deferred
Do not start Option β yet.
After α completes:
if skip_failed > 25%, stop and report;
if skip_failed <= 25%, recommend whether to proceed to Step D L-vs-S pilot;
if domain distribution is unexpectedly narrow, surface that before extraction spend;
wait for sign-off before Step D.
Architect call
After the 100-doc dry run completes and findings are recorded, run architect review on the Stage 1B A/B/C/dry-run state before any extraction pilot.
Review focus:
Env-var gate affects only run_vault_extraction.py.
Default remains legacy.
brain/app.py untouched.
MultiModelExtractor prompt unchanged.
Telemetry path is safe.
Dry-run classification logic matches real execution path.
No Stage 2 behavior slipped in.
If architect finds HIGH issues, fix only those blockers and rerun targeted tests.
Stop condition
Stop after the 100-doc dry-run findings and architect review result.
Do not begin Step D L+S pilot. Do not run Nexus 100 scoring. Do not start Stage 2. Wait for sign-off.

Compact handoff:

```text
Current state:
Stage 1B Steps A/B/C complete. 106/106 tests pass. 20-doc dry run: 20 scoped, 0 skip_failed.

Next allowed action:
Option α — full 100-doc classifier-only dry run using live classification_wrapper path.

Do not do:
Do not start L+S extraction pilot yet.
Do not run Nexus 100 scoring.
Do not change MultiModelExtractor prompt.
Do not start Stage 2.

Stop condition:
Return 100-doc dry-run results + architect review, then wait for sign-off before Step D.