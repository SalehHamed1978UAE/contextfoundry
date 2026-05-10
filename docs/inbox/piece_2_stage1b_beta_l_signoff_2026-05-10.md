# Stage 1B β — L Complete, Pre-S Decision

## Alignment

- **Module touched:** Stage 1B β measurement/control only
- **Product vs implementation:** execution control for the L-vs-S pilot
- **Architecture-doc consistency:** preserves signed-off β design: L and S run sequentially, fresh vaults, same corpus, env-var is the only intended extraction difference
- **Drift risk:** starting S while L workflow is still running; letting Gardener lifecycle promotion distort the L-vs-S interpretation; over-interpreting the global ontology null result without checking whether extraction can write ontology at all
- **Out of scope:** Stage 2, Nexus 100 scoring, prompt changes, MultiModelExtractor changes, brain/app.py, Gardener changes, Data Gates, v2, workflow restarts, replit.md edits

## Decision

Use **strict sequential execution**.

Do not start S while `S1B-Beta-L-Extract` is still running.

The L extraction phase is complete, but the workflow is still doing post-extraction embedding work. Wait for the L workflow to fully exit before creating or starting the S workflow.

## While waiting for L workflow exit

Do these read-only tasks only.

### 1. Capture a frozen L snapshot now

Capture and save:

```text
timestamp
L vault id
document count
extraction_requests status counts
entities total
entities by lifecycle_state
entities by entity_type / raw_entity_type if available
relationships total
relationships by lifecycle_state
relationships by relationship_type / raw_relationship_type if available
audit_records count by signal_type/severity
platform.extraction_events count/type if relevant
global ontology substrate:
  ontology.types total
  ontology.types count by domain_id
  ontology.relations total
  ontology.relations count by domain_id/status
````

This is a read-only snapshot. Do not lock tables. Do not mutate.

### 2. Run the 5-minute read-only grep for ontology writes

Authorize the read-only code grep.

Question:

```text
Does scripts/run_vault_extraction.py / MultiModelExtractor / OntologyCentricPipeline / KGIngestor ever INSERT or UPDATE ontology.types or ontology.relations during extraction?
```

Report:

```text
files searched
matches found
whether any match is on the L extraction path
interpretation:
  A. extraction has no ontology-write path, or
  B. ontology-write path exists but L did not trigger it, or
  C. ontology-write path exists and requires deeper investigation
```

Do not change code.

## After L workflow fully exits

Run final post-L checks:

```text
L workflow exit status
L runtime
final L entity/relationship counts
final L audit_records counts
final L extraction_events counts if relevant
final global ontology substrate snapshot
```

Compare the frozen L snapshot vs final post-L snapshot.

### If only lifecycle_state changed

Proceed. Record as:

```text
Start All / Gardener changed lifecycle_state during the L run. L-vs-S primary comparison uses total entity/relationship counts and type/relation distributions. Lifecycle split is reported as secondary and not used as the primary extraction-output metric.
```

### If total entity or relationship counts changed after the frozen snapshot

Stop and report before S.

This may indicate Gardener or another process changed more than lifecycle state, which can contaminate the comparison.

### If global ontology changed after L

Stop before S and report.

### If global ontology remains unchanged and L workflow exited cleanly

Proceed to S.

## S execution

Before S:

```text
capture pre-S global ontology substrate snapshot
confirm S graph outputs are still empty
confirm EXTRACTION_SYSTEM_PROMPT SHA unchanged
confirm CF_PIECE2_SCOPED_EXTRACTION=true
```

Then start `S1B-Beta-S-Extract`.

Use the same one-shot workflow approach as L.

Do not run L and S concurrently.

## Findings doc requirements

Update:

```text
docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md
```

Add:

```text
L frozen snapshot
L final snapshot
whether lifecycle_state changed due to Start All / Gardener
whether total graph counts changed
global ontology substrate checks
read-only grep result about ontology write paths
explicit statement that lifecycle split is secondary if Gardener was active
```

## Stop triggers

Stop and report if:

```text
L workflow fails
L workflow never exits
total L entity/relationship counts change due to Gardener after frozen snapshot
global ontology changes after L
ontology write path exists and appears active during extraction
S graph is no longer empty before S
S would start before L exits
```

## Continue constraints

Do not kill or restart Start All.

Do not change Gardener.

Do not start Stage 2.

Do not run Nexus 100 scoring.

Do not touch prompts, MultiModelExtractor, brain/app.py, Data Gates, v2, workflows other than the already-authorized one-shot β workflows, or replit.md.

## Stop condition

If L exits cleanly and all checks pass, start S.

If any stop trigger fires, stop and report.

After S completes, produce the full β final report and architect review as previously authorized.

````

Compact handoff:

```text
Current state:
L extraction phase complete.
L workflow still running embedding tail.
Global ontology unchanged through L.
Start All / Gardener is modifying lifecycle state.

Decision:
Wait for L workflow full exit before S.
Capture frozen L snapshot now.
Run read-only ontology-write-path grep while waiting.
Use total entity/relationship counts as primary comparison; lifecycle split secondary.
Start S only after L fully exits and final post-L checks are clean.

Do not:
Do not start S now.
Do not kill Start All.
Do not mutate code or DB outside already-authorized β execution.
Do not start Stage 2.
````
