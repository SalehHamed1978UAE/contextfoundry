# Piece 2 Stage 1B — β Sign-off and Execution

## Alignment

- **Module touched:** Stage 1B β pilot execution only
- **Product vs implementation:** implementation-level validation of scoped ontology activation
- **Architecture-doc consistency:** matches signed-off Stage 1B design: fresh L/S extraction comparison, same current codebase, same corpus, only env-var differs
- **Drift risk:** using auto-extraction or stale vault state and losing control over the legacy-vs-scoped comparison
- **Out of scope:** Nexus 100 scoring, Stage 2, MultiModelExtractor prompt changes, `brain/app.py`, Gardener, Data Gates, v2, workflow restarts, `replit.md` edits

## Sign-off

Proceed with **β**.

Prerequisites are accepted:

```text
α passed: 100/100 scoped, 0 skip_failed
threshold confirmed: production code uses <0.30
correct low-confidence count: 22/100
domain coverage corrected: 7/8 domains, healthcare absent
Corpus Maker CLI exists
Nexus corpus is registered
architect review: GO

Question file

Use:

./test documents/ClaudeCode_NExus_Industries_corpus/nexus_100q.json

Stage 1B does not score Nexus 100. This file is only to satisfy the Corpus Maker CLI contract.

Corpus setup

Use Corpus Maker CLI.

Create two fresh tenant/vault contexts:

L = legacy
S = scoped

Upload the same Nexus corpus to both using --no-extract.

Use the same source directory for both:

./test documents/ClaudeCode_Nexus_Industries 2/

or the verified equivalent source directory with exact 100/100 filename match.

Before extraction, verify corpus equality:

same document count
same filenames
same file sizes or content hashes if available
both graph outputs empty before extraction

Do not use the old Nexus vault as official L baseline.

Do not SQL-clone.

Do not use manual UI upload unless the CLI fails and you stop for sign-off.

Extraction execution

After both fresh tenants are populated:

Run L

CF_PIECE2_SCOPED_EXTRACTION=false
scripts/run_vault_extraction.py --vault-id <L_tenant_id>

Run S

CF_PIECE2_SCOPED_EXTRACTION=true
scripts/run_vault_extraction.py --vault-id <S_tenant_id>

If the exact runner flag is not --vault-id, use the existing supported tenant/vault argument, but report the command used.

Run L and S sequentially, not concurrently.

Environment verification

Before each extraction run, log:

tenant_id
corpus path
document count
CF_PIECE2_SCOPED_EXTRACTION value

Also verify:

EXTRACTION_SYSTEM_PROMPT SHA =
5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963

Use the module-level constant:

src.context_foundry.extraction.multi_extractor.EXTRACTION_SYSTEM_PROMPT

Stop triggers

Stop and report if any of these occur:

corpus equality fails
Corpus Maker CLI cannot create fresh tenants
upload requires a manual UI path
skip_failed rate > 25%
scoped prompts include NULL-domain rows
scoped prompts fall back to full union
core is missing from scope
primary_domain is missing from scope
MultiModelExtractor prompt SHA changes
brain/app.py changes
tests fail

Do not silently downgrade to δ or ε.

Metrics to collect

For each run, report:

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

For S specifically, report:

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

Comparison table

Produce:

Metric	Legacy L	Scoped S	Delta

documents processed			
documents failed			
entities extracted			
relationships extracted			
audit_records			
low_confidence signals			
runtime			


Also answer:

Did scoped extraction reduce noisy entity types?
Did scoped extraction lose expected organizational relations?
Did scoped extraction skip any docs?
Did audit_records capture low-confidence cases?
Did scoped prompts include HOLDS_POSITION / WORKS_AT / REPORTS_TO after Piece 0.6?
Did HAS_COMPENSATION appear only in finance-scoped prompts?

Findings document

Update:

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

Include these notes:

Historical Nexus baselines have varied: 77/100, 74/100, and 71/100 in different runs. Stage 1B does not score Nexus 100. It compares extraction outputs only.

Stage 1B α covered 7 of 8 canonical domains. Healthcare was absent. The corpus is construction-heavy, so Stage 1B is strongest evidence for construction and it_infrastructure, with thinner evidence for manufacturing, aviation, core, supply_chain, and finance.

Persisted classification columns were stale for historical Nexus rows. Stage 1B uses live classification as the source of truth. Any future plan to rely on persisted classification columns requires a backfill or freshness policy.

Architect review

After β finishes and before final report, run architect review focused on:

env-var gate remained isolated to run_vault_extraction.py
default behavior remains legacy
brain/app.py untouched
MultiModelExtractor prompt unchanged
telemetry safe
findings doc distinguishes fresh L/S results from historical Nexus baselines
no Stage 2 behavior slipped in

If architect finds HIGH issues, stop and report.

Final report

Report:

tenant_ids used
corpus equality verification
L run metrics
S run metrics
L-vs-S comparison
audit_records summary
prompt-scope evidence
findings doc path
architect review result
EXTRACTION_SYSTEM_PROMPT SHA
confirmation no Nexus 100 scoring
confirmation no Stage 2
confirmation no MultiModelExtractor prompt change
confirmation no brain/app.py, Gardener, DataGate, v2, workflow, or replit.md work

Stop condition

Stop after Stage 1B β final report.

Do not start Stage 2. Do not run Nexus 100 scoring.

Compact handoff:

```text
Current state:
Stage 1B α complete and corrected.
100/100 scoped, 0 skip_failed.
Threshold confirmed <0.30.
Corpus Maker CLI verified.
Architect GO.

Next allowed action:
Run β fresh L/S extraction pilot.

Choices:
question file = nexus_100q.json
upload = Corpus Maker CLI with --no-extract
extraction = explicit run_vault_extraction.py for L and S

Do not do:
Do not use stale Nexus vault as official L baseline.
Do not run Nexus 100 scoring.
Do not start Stage 2.
Do not change MultiModelExtractor prompt.
Do not touch brain/app.py, Gardener, Data Gates, v2, workflows, or replit.md.