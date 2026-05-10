# Piece 2 Stage 1 — Step B Sign-off

## Alignment

- **Module touched:** `platform.audit_records` migration, then Piece 2 Stage 1 scoped-prompt implementation after migration
- **Product vs implementation:** implementation-level work making domain-aware ontology extraction real
- **Architecture-doc consistency:** matches signed-off Piece 2 design: low-confidence signals persist to `audit_records`; prompt scope remains `core ∪ primary_domain`; MultiModelExtractor remains unchanged in Stage 1
- **Drift risk:** changing audit schema semantics, adding UI/review workflow, or touching MultiModelExtractor prompt during Stage 1
- **Out of scope:** Piece 2 Stage 2 adapter, MultiModelExtractor prompt replacement, Gardener, Data Gates, v2, Nexus 100, workflow restarts, `replit.md` edits

## Decision 1 — Migration SQL approved

Approve the migration SQL as-is.

Run:

```sql
BEGIN;

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

SELECT to_regclass('platform.audit_records') AS table_exists;

SELECT indexname
FROM pg_indexes
WHERE schemaname='platform'
  AND tablename='audit_records'
ORDER BY indexname;

COMMIT;

Approved choices:

No ON DELETE clause. Default NO ACTION is correct for governance records.
document_id remains nullable.
No RLS in Stage 1.
No UI, review queue, routing, notifications, or consumer logic.
No additional indexes beyond document_id and signal_type.

Rationale:

audit_records is a write-only governance-signal table in Stage 1. Consumer behavior is Piece 2.1 or later. Governance signals should not silently disappear through cascade behavior.

Decision 2 — gen_random_uuid()

Confirmed.

No pgcrypto extension step is needed because gen_random_uuid() is available from pg_catalog.

Decision 3 — Prompt SHA target

Confirmed.

Use this exact SHA for the Stage 1 lock-test:

5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963

This is the SHA Pieces 1 and 1.5 verified as byte-identical, and Replit re-confirmed it in Step A.

Decision 4 — Prompt symbol location

Confirmed.

The actual symbol is module-level:

src.context_foundry.extraction.multi_extractor.EXTRACTION_SYSTEM_PROMPT

not:

MultiModelExtractor.EXTRACTION_SYSTEM_PROMPT

Use this lock-test target:

from src.context_foundry.extraction import multi_extractor
import hashlib

sha = hashlib.sha256(
    multi_extractor.EXTRACTION_SYSTEM_PROMPT.encode()
).hexdigest()

assert sha == "5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963"

The brief’s class-attribute notation was imprecise. The substantive constraint is that the prompt remains unchanged in Stage 1.

Continue Piece 2 Stage 1

After running and verifying the migration, continue with Steps D through J from the signed-off brief:

Implement scoped prompt construction for the ontology path only.
Enforce:
scope = core ∪ primary_domain
Exclude:
NULL-domain rows;
other named domains;
full-union fallback.
Preserve repository no-filter behavior for legacy callers.
Emit audit_records for:
classification_confidence < 0.30;
top_two_margin < 0.05, if recoverable from classification_evidence.
If top-two margin cannot be parsed reliably, implement only the low-confidence audit record and report the limitation.
Do not change prompt scope based on confidence.
Do not change classification_status.
Do not modify MultiModelExtractor or its prompt.
Do not start Stage 2.
Required final checks

Before final report, include:

migration verification;
scoped prompt API behavior;
scoped prompt examples;
prompt diff for at least one known document/classification pair;
audit_records example row;
tests run;
smoke/dry-run result;
EXTRACTION_SYSTEM_PROMPT SHA unchanged;
confirmation no Stage 2, Gardener, Data Gates, v2, Nexus 100, workflow, or replit.md work occurred.
Stop condition

Stop after Piece 2 Stage 1 final report.

Do not start Piece 2 Stage 2.
Do not run Nexus 100.


Compact handoff:

```text
Current state:
Piece 2 Stage 1 Step A/B complete. Migration SQL approved.

Next allowed action:
Run audit_records migration, then implement ontology-path scoped prompts.

Do not do:
Do not touch MultiModelExtractor prompt.
Do not start Stage 2.
Do not change Gardener, Data Gates, v2, Nexus 100, workflows, or replit.md.

Prompt SHA target:
5d299a6786b975539006470e66424f27ac8bd4f4f4c9577f758c22748db08963

Prompt symbol:
module-level multi_extractor.EXTRACTION_SYSTEM_PROMPT.