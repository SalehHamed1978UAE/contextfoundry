

# Piece 2 Stage 1B — Fix Corpus Maker Fresh-Tenant Upload Blocker, Then Retry β

## Alignment

- **Module touched:** Corpus Maker tenant creation path, TenantService tenant creation helper, tests for fresh tenant upload
- **Product vs implementation:** implementation-level blocker fix for Stage 1B β
- **Architecture-doc consistency:** preserves the signed-off β requirement: two fresh tenant/vault contexts, same corpus, upload with `--no-extract`, extraction controlled explicitly by `CF_PIECE2_SCOPED_EXTRACTION`
- **Drift risk:** silently downgrading to SQL clone or old-vault baseline; changing extraction behavior while fixing an upload bug; creating tenants with IDs that do not match the CLI-minted vault_id
- **Out of scope:** Stage 2, MultiModelExtractor prompt changes, `brain/app.py`, Gardener, Data Gates, v2, Nexus 100 scoring, workflow restarts, `replit.md` edits

## Decision

Authorize **Option A**.

Fix the Corpus Maker fresh-tenant creation bug.

Do not use Option B unless Option A fails and a new sign-off is requested.
Do not use Option C unless the fix is not feasible.
Do not silently downgrade to δ or ε.

## Problem to fix

The Corpus Maker CLI mints a fresh `vault_id`, but `get_or_create_tenant(vault_id, corpus_name)` creates a tenant without using that `vault_id` as the tenant `id`.

Result:

```text
CLI vault_id = 2ee0896c-...
platform.tenants row = different auto-generated UUID
document writes use CLI vault_id
tenant_quotas FK fails because platform.tenants(id = CLI vault_id) does not exist

This blocks any fresh-tenant upload through the CLI.

Required fix

1. Fix tenant ID consistency

Update the tenant creation path so that when Corpus Maker creates a new tenant for a CLI-minted vault_id, the platform.tenants.id equals that vault_id.

Expected shape:

TenantService.create_tenant(..., tenant_id: str | uuid.UUID | None = None)

Behavior:

if tenant_id is provided, insert it explicitly into platform.tenants.id;

if tenant_id is not provided, preserve current behavior and let Postgres generate the UUID;

do not break existing callers.


Then update:

src/corpus_maker/uploader.py:get_or_create_tenant(...)

so it passes the CLI-minted vault_id into TenantService.create_tenant.

2. Handle update_tenant_metadata

The upload path also warned:

'TenantService' object has no attribute 'update_tenant_metadata'

Inspect the intended metadata update.

If straightforward, add a minimal TenantService.update_tenant_metadata(...) method that updates the existing tenant metadata/settings field without changing tenant identity.

If not straightforward, do not invent a broad metadata system. Leave the warning in place and report why it is non-blocking.

But the tenant-id mismatch must be fixed.

Tests

Add tests covering:

1. TenantService.create_tenant(..., tenant_id=<uuid>) creates a row with exactly that ID.


2. TenantService.create_tenant(...) without tenant_id preserves existing generated-ID behavior.


3. get_or_create_tenant(vault_id, corpus_name) returns a tenant whose id == vault_id when the tenant does not already exist.


4. Existing tenant lookup still returns the existing tenant and does not create a duplicate.


5. If update_tenant_metadata is implemented, test it updates metadata/settings without changing tenant ID.



Run targeted tests.

Cleanup from failed attempt

Before retrying β, inspect for orphan artifacts from the failed upload attempt.

Check:

src/test_config.json
test_questions/
platform.tenants
platform.documents
platform.tenant_quotas
entities
relationships
platform.audit_records

For any Stage1B-L 2026-05-10 or failed-upload tenant candidate:

if it has zero documents, zero entities, zero relationships, zero audit_records, and no required references, remove it;

if it has references, stop and report;

do not delete anything by name pattern alone without verifying zero references.


Report exactly what was removed.

Smoke test the fixed CLI before β

Run a minimal CLI upload smoke before the full β run.

Requirements:

use --no-extract;

use a tiny temporary corpus or a 1–2 document subset;

verify:

platform.tenants.id == CLI vault_id;

documents land successfully;

tenant_quotas FK does not fail;

registry/manifest written correctly;

no extraction runs.



Clean up the smoke tenant only if it has no extracted graph state and cleanup is safe.

Architect review

After the fix and tests, run architect review focused on:

TenantService.create_tenant preserves existing behavior when tenant_id is None
Corpus Maker fresh upload now creates platform.tenants.id == vault_id
No extraction behavior changed
No prompt behavior changed
No Stage 2 behavior slipped in
No broad schema or workflow changes were introduced

If architect reports HIGH issues, stop and report.

If fix + tests + smoke + architect are clean

Resume β exactly as previously authorized:

1. Upload L with Corpus Maker CLI using --no-extract.


2. Upload S with Corpus Maker CLI using --no-extract.


3. Verify corpus equality.


4. Run L extraction explicitly with:



CF_PIECE2_SCOPED_EXTRACTION=false

5. Run S extraction explicitly with:



CF_PIECE2_SCOPED_EXTRACTION=true

6. Preserve all previously signed-off β controls:

no Nexus 100 scoring;

no Stage 2;

no MultiModelExtractor prompt change;

no brain/app.py;

no Gardener/DataGate/v2/workflow/replit.md work.




Stop triggers

Stop and report if:

fresh tenant upload still fails
tenant ID does not equal CLI vault_id
smoke upload creates unexpected graph state
tests fail
architect review flags HIGH
Corpus Maker CLI still cannot create fresh tenants

Do not silently switch to SQL clone, old-vault baseline, manual UI, δ, or ε.

Final report

Report:

root cause confirmed;

files changed;

exact tenant creation fix;

whether update_tenant_metadata was implemented or deferred;

tests run and results;

cleanup performed;

CLI smoke result;

architect review result;

whether β was resumed;

if β resumed, include the full β report required by the previous brief;

confirmation no Stage 2, Nexus 100 scoring, MultiModelExtractor prompt change, brain/app.py, Gardener, DataGate, v2, workflow restart, or replit.md work occurred.


Stop condition

If the blocker fix succeeds and β completes, stop after the Stage 1B β final report.

If the blocker fix fails, stop after the blocker report.

Do not start Stage 2.

Why this is the right call:

- **A** preserves the scientific control of β: fresh L and fresh S under the same current codebase.
- **B** would work around the symptom but leave a broken fresh-tenant path in the platform.
- **C** would leave Stage 1B incomplete even though the blocker is small and well understood.

The attempted upload also proves why we should not rely on Corpus Maker auto-extraction: the clean plan remains `--no-extract`, then explicit extraction with the env var false/true. The Stage 1B gate is still isolated to `run_vault_extraction.py`, with existing callers remaining legacy unless explicitly opted in. 0

Compact handoff:

```text
Current state:
Stage 1B β blocked by Corpus Maker fresh-tenant bug.

Decision:
Choose Option A — fix CLI fresh-tenant creation.

Do not do:
Do not SQL-clone.
Do not use old Nexus vault as official baseline.
Do not use manual UI.
Do not downgrade to δ or ε.
Do not start Stage 2.
Do not change prompts or MultiModelExtractor.

Next:
Fix tenant-id mismatch, test it, smoke CLI upload, architect review, then resume β if clean.