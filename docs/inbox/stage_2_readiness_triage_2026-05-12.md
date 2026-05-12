# Stage 2 Readiness Triage — Read-Only Audit

## Alignment

- **Module touched:** read-only readiness audit only
- **Product vs implementation:** product/implementation triage before Stage 2 design or activation
- **Architecture-doc consistency:** follows Stage 1J and Stage 1K: fresh tenant ingestion is tenant-clean; VerificationWorker deadlock is fixed; clean-vault verification/promotion now works on bounded validation
- **Drift risk:** moving into Stage 2 implementation without knowing the actual clean-vault TRUSTED/STAGING state and remaining v1 blockers
- **Out of scope:** code edits, DB mutations, schema changes, scheduler activation, Stage 2 implementation, Nexus 100 scoring, v2 work, `replit.md` edits

## Sign-off

Stage 1K is accepted.

Accepted results:

```text
VerificationWorker deadlock root cause identified.
Smallest viable fix landed:
  - no_autoflush around read-before-write sections
  - per-batch commits
  - deterministic ordering
  - bounded deadlock retry with sqlstate/pgcode hardening

8/8 unit tests passed.
Architect review PASS.
2 of 3 architect medium follow-ups applied.
lock_timeout hardening deferred to Stage 1L.
5-fact bounded smoke passed.
~50-fact background validation completed and committed batch-by-batch.
Cross-tenant invariants remained frozen.
ontology.types stayed 1037.
ontology.relations stayed 254.
No Stage 2 work was done.
No Nexus 100 scoring was run.
````

Important interpretation:

```text
Stage 1K validates the VerificationWorker fix and demonstrates durable batched verification writes.
Before Stage 2 readiness is claimed, measure the actual final clean-vault state.
```

## Goal

Produce a structured Stage 2 Readiness Triage report.

This is read-only.

No code changes.

No DB mutations.

No new fixes.

## Clean validation vault

Use the Stage 1J clean vault:

```text
ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda
```

Do not delete it.

Do not mutate it except for read-only queries.

## Required report section 1 — Current clean-vault state

Report current state of the clean Stage 1J vault:

```text
document count
entity count by lifecycle_state
relationship count by lifecycle_state
verified entity count
verified relationship count
fact_verifications count
TRUSTED entity count
TRUSTED relationship count
STAGING entity count
STAGING relationship count
ARCHIVED entity count
ARCHIVED relationship count
latest cross-tenant relationship updated_at
merge_audits count and latest timestamp
ontology.types count
ontology.relations count
```

Also report:

```text
block_reasons distribution for remaining STAGING facts, if available
result.errors if any
verification error count
promotion error count
```

## Required report section 2 — Extraction / ontology alignment

For the clean Stage 1J vault, report:

```text
relationship_type distribution
entity_type distribution
orphan relationship types not present in ontology.relations
orphan entity types not present in ontology.types
any ad-hoc ontology types created during fresh extraction
```

Specifically check the orphan relation types surfaced earlier:

```text
FUNDED_BY
USES
HAS_SPEC
RELATED_TO
USES_MATERIAL
OWNED_BY
WORKS_FOR
FOCUSES_ON
```

Classify each:

```text
already governed
missing from ontology.relations
should be mapped to existing governed relation
should be added through governance later
should be blocked from extraction
```

Do not mutate ontology.

Do not backfill ontology.

## Required report section 3 — Remaining v1 launch backlog

Categorize each item as:

```text
Must fix before Stage 2 design
Must fix before Stage 2 default activation
Can defer with known limitation
Future architecture / Piece 3+
No longer needed
```

For each item, include:

```text
scope estimate: small / medium / large
why it matters
dependency order
recommended priority
```

Items to cover:

```text
Phase 4: relationship endpoint tenant-alignment DB guard / trigger
Phase 5: duplicate_candidates and merge_audits tenant_id columns + FK cascade policy
Scheduler per-tenant iteration design (scheduler.py:225 NotImplementedError)
Single-shot Gardener / scheduler not activated
8 orphan relation types
803 ad-hoc ontology types / ontology governance hygiene
relationships.source_document_id varchar→uuid schema gap
Stage 1L items:
  - lock_timeout hardening
  - deterministic ordering for other verification writers in web_app.py / brain/app.py
  - extraction_level uuid=text bulk-update bug
Legacy contaminated vault disposition:
  - preserve as forensic/adversarial fixtures
  - delete later
  - repair only for a specific use case
Cold-corpus adaptive ontology validation
MultiModelExtractor staged activation
audit_records consumer / review queue
```

Add any other backlog item you discover.

## Required report section 4 — Stage 2 readiness verdict

Recommend one:

```text
A. Stage 2 ready for design conversation now.
B. Stage 2 needs one more bounded fix first.
C. Stage 2 needs a substantial new piece first.
```

For the verdict, distinguish:

```text
Stage 2 design conversation
Stage 2 implementation
Stage 2 default activation
```

These are not the same.

## Required report section 5 — Recommended sequencing

Order the remaining v1 work by:

```text
what blocks what
what is cheap vs expensive
what reduces risk
what unlocks product decision-making
what is mechanical cleanup
```

Produce a proposed sequence like:

```text
1. ...
2. ...
3. ...
```

## Required report section 6 — What is no longer required

Explicitly state whether these are still needed:

```text
Phase 3 historical contamination repair
re-running the contaminated S1B vaults
Nexus 100 scoring before Stage 2 design
full S VerificationWorker run on contaminated vault
```

Use the current project stance:

```text
Historical contaminated vaults are forensic/adversarial fixtures unless a specific use case requires repair.
Fresh clean-vault path is the production-relevant validation path.
```

## Findings doc update

Update or create a readiness report document:

```text
docs/findings/stage_2_readiness_triage_2026-05-12.md
```

Also reference the Stage 1J / Stage 1K findings docs.

## Do not do

Do not:

```text
edit code
mutate DB
add schema trigger
repair historical contaminated relationships
run promotion cycles
start scheduler
run Nexus 100 scoring
run VerificationWorker full pass unless explicitly authorized
start Stage 2 implementation
touch v2
edit replit.md
```

## Final report

Report:

```text
clean vault current state
TRUSTED/STAGING/ARCHIVED counts
verification/promotion status
orphan type/relation findings
remaining backlog categorized
Stage 2 readiness verdict
recommended sequence
what remains blocked
what is safe to defer
findings doc path
```

## Stop condition

Stop after the Stage 2 Readiness Triage report.

Wait for sign-off before any new Phase, fix, schema work, scheduler activation, or Stage 2 implementation.

