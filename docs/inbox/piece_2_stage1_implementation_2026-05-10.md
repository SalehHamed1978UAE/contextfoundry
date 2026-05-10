# Task: Piece 2 Stage 1 — Domain-Scoped Prompting for OntologyCentricPipeline Only

## Alignment

- **Module touched:** `SchemaPromptGenerator`, `OntologyCentricPipeline`, ontology prompt tests, minimal `audit_records` table/write path
- **Product vs implementation:** implementation-level work making domain-aware extraction real on the ontology path
- **Architecture-doc consistency:** matches signed-off Piece 2.0 design: `scope = core ∪ primary_domain`, no full-union fallback, low confidence emits audit signal only, MultiModelExtractor remains unchanged in Stage 1
- **Drift risk:** accidentally changing MultiModelExtractor prompt behavior; widening prompt scope on low confidence; globally breaking repository no-filter callers; letting audit signals disappear without persistence
- **Out of scope:** MultiModelExtractor adapter/replacement, Gardener, Data Gates, v2 FactEvaluator, Nexus 100 run, workflow restarts, `replit.md` edits, relation governance beyond completed Piece 0.6

## Standing Constraints

- No `replit.md` edits.
- No workflow restarts.
- No v2 work.
- No Nexus 100 run.
- No Gardener changes.
- No Data Gate changes.
- No MultiModelExtractor prompt replacement.
- No changes to `MultiModelExtractor.EXTRACTION_SYSTEM_PROMPT`.
- One schema-changing action at a time.
- Schema changes are sign-off-gated.
- Every response starts with the alignment block.

## Read First

1. `docs/architecture.md`
2. `docs/decisions.md`
3. `docs/piece2_domain_scoped_prompting_design_2026-05.md`
4. Piece 0.6 final report
5. `src/context_foundry/ontology/repository.py`
6. `src/context_foundry/ontology/prompt_generator.py`
7. `src/context_foundry/extraction/ontology_centric_pipeline.py`
8. `src/context_foundry/extraction/multi_extractor.py`
9. `tests/ontology/test_repository_domain_filter.py`

## Goal

Implement Piece 2 Stage 1:

```text
OntologyCentricPipeline uses domain-scoped ontology prompts.
Prompt scope = core ∪ primary_domain.
Low-confidence or narrow-margin classification emits audit_records only.
Prompt scope never widens.
MultiModelExtractor remains unchanged.
Locked Decisions
Prompt scope formula:
types = core_types ∪ primary_domain_types
relations = core_relations ∪ primary_domain_relations
core is always explicitly included.
NULL domain rows are excluded from scoped prompt construction.
Low confidence and narrow top-two margin do not alter prompt scope.
Provisional audit sentinels:
classification_confidence < 0.30
top_two_margin < 0.05
classification_status remains:
ok | failed | unclassified

No needs_review status.

audit_records minimal table/write path lands in Piece 2 Stage 1.
MultiModelExtractor remains on its existing prompt in Stage 1.
A. Preflight: capture prompt and code baselines

Before changes, capture SHA-256 for:

src/context_foundry/ontology/prompt_generator.py
src/context_foundry/extraction/ontology_centric_pipeline.py
src/context_foundry/extraction/entity_extractor.py
src/context_foundry/extraction/relation_extractor.py
src/context_foundry/extraction/multi_extractor.py
src/context_foundry/learning/targeted_extractor.py

Also capture in-memory SHA for:

MultiModelExtractor.EXTRACTION_SYSTEM_PROMPT

Report baselines before editing.

B. Compose audit_records migration — sign-off gated

Compose migration SQL for:

CREATE TABLE IF NOT EXISTS platform.audit_records (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid REFERENCES platform.documents(id),
  signal_type varchar(64) NOT NULL,
  severity varchar(16) NOT NULL,
  payload jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_records_document_id_idx
  ON platform.audit_records(document_id);

CREATE INDEX IF NOT EXISTS audit_records_signal_type_idx
  ON platform.audit_records(signal_type);

If gen_random_uuid() extension is unavailable, propose the minimal safe fix.

Paste migration SQL.

Stop and wait for sign-off before running migration.

C. After sign-off: run audit_records migration

After sign-off:

Run migration.
Verify table exists.
Verify indexes exist.
Verify no consumer/UI/review queue code was added.
D. Implement scoped prompt construction

Modify SchemaPromptGenerator or add a scoped prompt builder so that ontology extraction prompt construction requires an explicit domain_id.

Required behavior:

build_entity_extraction_prompt(domain_id=None) -> raises
build_relationship_extraction_prompt(domain_id=None) -> raises

For a valid domain:

scope = ['core', primary_domain]

Load:

types where domain_id in ('core', primary_domain)
relations where domain_id in ('core', primary_domain)

Do not include:

NULL-domain rows
other named domains
full union fallback

Important:

OntologyRepository.get_all_types() with no domain filter must remain unchanged.
OntologyRepository.get_all_relations() with no domain filter must remain unchanged.

The no-full-union rule is enforced at the scoped prompt-builder layer, not by globally breaking repository no-filter calls.

E. Wire OntologyCentricPipeline to scoped prompt builder

Modify OntologyCentricPipeline so that it reads:

classification_metadata['primary_domain']
classification_metadata['classification_status']
classification_metadata['classification_confidence']
classification_metadata['classification_evidence']

Behavior:

If classification_status == 'ok' and primary_domain is present

Build scoped prompts with:

core ∪ primary_domain
If classification is missing, failed, unclassified, or primary_domain is NULL

Do not fall back to full union.

Use one of these behaviors, in order of preference:

1. skip ontology extraction for that document and emit audit_record;
2. if skipping would break caller expectations, return a failed extraction result with clear reason and audit_record.

Do not silently use union prompts.

F. Low-confidence and narrow-margin audit signal

When classification metadata indicates:

classification_confidence < 0.30

write an audit_records row:

signal_type = 'low_confidence'
severity = 'warn'
payload includes:
  confidence
  primary_domain
  classifier_version
  classification_evidence

When top-two margin is recoverable from classification_evidence and:

top_two_margin < 0.05

write an audit_records row:

signal_type = 'narrow_margin'
severity = 'warn'
payload includes:
  top_two_margin
  top_domain
  runner_up_domain
  classifier_version
  classification_evidence

If top-two margin cannot be parsed reliably from current evidence string, do not invent it. Record this as a limitation and only implement low-confidence audit in Stage 1.

Low confidence must not change prompt scope.

G. MultiModelExtractor must remain unchanged

Do not modify:

src/context_foundry/extraction/multi_extractor.py
MultiModelExtractor.EXTRACTION_SYSTEM_PROMPT

Add a test or SHA check proving the prompt is unchanged.

Any MultiModelExtractor adapter is Stage 2 and requires separate sign-off.

H. Tests

Add or update tests.

Required tests:

For each of the eight domains, scoped prompt contains only:
core
selected domain
Scoped prompt excludes:
NULL-domain types
NULL-domain relations
other named domains
core is included explicitly.
build_entity_extraction_prompt(domain_id=None) raises.
build_relationship_extraction_prompt(domain_id=None) raises.
Repository no-filter calls still return full active set:
get_all_types()
get_all_relations()
Low-confidence metadata creates audit_records row and does not change prompt scope.
Narrow-margin metadata creates audit_records row if margin parsing is implemented.
Missing/failed classification does not fall back to full union.
MultiModelExtractor.EXTRACTION_SYSTEM_PROMPT SHA unchanged.
Stage 1 ontology path uses scoped prompts.
Multi-model path remains on existing prompt.
I. Smoke test

Run a small ontology-path smoke test.

Preferred:

2–3 Nexus documents through ontology path

If full ontology extraction is too slow or costly, use a dry-run/unit-level smoke proving:

classification metadata loaded
domain_id passed into scoped prompt builder
prompt scope contains core ∪ primary_domain only
audit_records written for low-confidence cases
MultiModelExtractor prompt unchanged

Do not run Nexus 100.

J. Prompt diff review

Paste before/after diff for ontology prompt output for at least one known document/classification pair.

The diff should show:

prompt now contains only scoped ontology types/relations
NULL-domain rows absent
other domains absent
core present
primary_domain present

Also paste SHA check proving:

MultiModelExtractor.EXTRACTION_SYSTEM_PROMPT unchanged
Acceptance Checks

All must pass:

audit_records table exists with minimal schema.
SchemaPromptGenerator scoped prompt APIs require explicit domain.
No full-union fallback in scoped prompt construction.
Repository no-filter behavior preserved.
Ontology path uses core ∪ primary_domain.
NULL-domain rows excluded.
Low-confidence audit signal written.
Prompt scope unchanged by confidence.
Missing classification does not fall back to union.
MultiModelExtractor prompt unchanged.
Tests pass.
Smoke/dry-run passes.
No Gardener changes.
No v2 changes.
No Nexus 100 run.
No workflow restarts.
No replit.md edits.
Final Report

Report:

files changed;
migration SQL and verification;
scoped prompt API behavior;
prompt scope examples;
audit_records examples;
tests run;
smoke/dry-run results;
prompt diffs;
MultiModelExtractor SHA verification;
confirmation no Piece 2 Stage 2 was started;
confirmation no Gardener/v2/Nexus/workflow/replit.md work occurred.
Stop Condition

Stop after Piece 2 Stage 1 final report.

Do not start Piece 2 Stage 2.
Do not run Nexus 100.
Wait for sign-off.


# Compact handoff

```text
Current state:
Piece 0.6 complete and accepted.
Gap 5 resolved.
Gap 6 remains open.

Next allowed action:
Piece 2 Stage 1 — ontology path scoped prompts + audit_records minimal write path.

Do not do:
Do not change MultiModelExtractor prompt.
Do not start Stage 2 adapter.
Do not change Gardener.
Do not run Nexus 100.
Do not touch v2 or replit.md.

Stop condition:
Replit completes Piece 2 Stage 1 and waits for sign-off.