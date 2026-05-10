# Stage 1B β — Start S Sign-off

## Alignment

- **Module touched:** Stage 1B β S-run execution only
- **Product vs implementation:** implementation-level continuation of L-vs-S pilot
- **Architecture-doc consistency:** matches signed-off β design: L and S run sequentially, same corpus, same current codebase, only env-var differs
- **Drift risk:** using wrong S vault ID; over-weighting lifecycle_state while Gardener is active; starting S without clean pre-S checks
- **Out of scope:** Stage 2, Nexus 100 scoring, prompt changes, MultiModelExtractor changes, `brain/app.py`, Gardener changes, Data Gates, v2, unrelated workflow restarts, `replit.md` edits

## Decision

Proceed.

## Confirmations

### 1. Vault ID

Canonical S vault ID is confirmed:

```text
5df41308-4033-441d-b712-77928b8ea93e
````

The `471d` value was a scratchpad typo and must not be used.

### 2. Command

Use exactly:

```bash
CF_PIECE2_SCOPED_EXTRACTION=true \
python -u scripts/run_vault_extraction.py --vault-id 5df41308-4033-441d-b712-77928b8ea93e
```

No other flags.

No `--use-ontology`.
No `--limit`.
No Nexus 100 scoring.

### 3. Start All / Gardener

Start All may continue running during S, same as during L.

Record this limitation:

```text
Gardener may lifecycle-shuffle S rows while the run is in progress. Lifecycle-state split is secondary. Primary L-vs-S comparison uses total entity/relationship counts and type/relation distributions.
```

Do not kill or restart Start All.

## Pre-S checks accepted

Accepted:

```text
S entities = 0
S relationships = 0
S documents = 100
S audit_records = 0
EXTRACTION_SYSTEM_PROMPT SHA = 5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963
ontology.types = 1037
ontology.relations = 254
L remains stable at 2258 entities / 2192 relationships
```

## Action

1. Register `S1B-Beta-S-Extract` one-shot workflow if not already configured.
2. Start it with the exact command above.
3. Capture S start epoch to:

```text
/tmp/s1b_beta/S_workflow_start_epoch.txt
```

4. Poll approximately every 10 minutes.

## During S polling, report

```text
workflow status
documents processed or extraction phase marker
entities total
relationships total
audit_records count
low_confidence count
skip_failed count/rate
ontology.types count
ontology.relations count
ontology rows created/updated since S start
```

## Stop triggers

Stop and report if:

```text
S workflow fails
skip_failed rate > 25%
scoped prompts include NULL-domain rows
scoped prompts fall back to full union
core is missing from scope
primary_domain is missing from scope
ontology.types changes
ontology.relations changes
MultiModelExtractor prompt SHA changes
brain/app.py changes
runtime or spend becomes concerning
```

## After S stabilizes

After S exits and counts stabilize:

1. Capture final S snapshot.
2. Compare L vs S:

   * total entities;
   * total relationships;
   * entity type distribution;
   * relationship type distribution;
   * audit_records;
   * low_confidence signals;
   * runtime.
3. Capture prompt-scope evidence for at least 3 scoped S documents.
4. Update:

```text
docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md
```

5. Run architect review.
6. Paste final Stage 1B β report.
7. Stop for sign-off.

## Findings doc must include

```text
Canonical S vault ID = 5df41308-4033-441d-b712-77928b8ea93e.
The 471d ID was a typo and did not exist.
The final L baseline is 2258 entities / 2192 relationships.
L and S comparison uses total counts and distributions as primary metrics.
Lifecycle_state split is secondary because Gardener was active.
Nexus is saturated for ontology-growth testing; β validates scoped prompt execution and extraction-output differences, not adaptive ontology growth.
```

## Continue constraints

Do not start Stage 2.

Do not run Nexus 100 scoring.

Do not touch prompts, MultiModelExtractor, `brain/app.py`, Gardener, Data Gates, v2, unrelated workflows, or `replit.md`.

## Stop condition

Stop after S completes, final β report is produced, and architect review is done.

Do not begin Stage 2.

````

Compact handoff:

```text
Decision:
Start S.

S vault:
5df41308-4033-441d-b712-77928b8ea93e

Command:
CF_PIECE2_SCOPED_EXTRACTION=true python -u scripts/run_vault_extraction.py --vault-id 5df41308-4033-441d-b712-77928b8ea93e

Accepted:
S prechecks green.
L stable.
Prompt SHA locked.
Global ontology unchanged.

Do not:
Do not use 471d.
Do not kill Start All.
Do not start Stage 2.
Do not run Nexus 100 scoring.
````
