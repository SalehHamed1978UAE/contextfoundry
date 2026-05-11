# Stage 1I Phase 1.5 — IdentityResolver Call-Site Tenant Context Fix

## Alignment

- **Module touched:** `IdentityResolver` call sites only: scheduler/web paths that now fail closed without `tenant_id`
- **Product vs implementation:** implementation-level follow-up to Stage 1I Phase 1 tenant-isolation fix
- **Architecture-doc consistency:** follows Stage 1H/1I findings: cross-tenant relationship contamination was caused by tenant-unsafe identity resolution; Phase 1 fixed the writer, now legitimate callers must pass tenant context
- **Drift risk:** repairing data before all `IdentityResolver` callers are tenant-aware; adding DB constraints before runtime call sites are fixed; reintroducing global fallback behavior
- **Out of scope:** data repair, DB-wide backfill, schema trigger, DuplicateCandidate/MergeAudit tenant_id columns, promotion cycles, scheduler activation, Stage 2, Nexus 100 scoring, VerificationWorker, v2, `replit.md` edits

## Sign-off

Stage 1I Phase 1 is accepted.

Accepted results:

```text
IdentityResolver tenant-isolation fix landed.
Six tenant-invariant guards added.
Architect HIGH issue on opposite-endpoint guard was fixed.
12/12 tenant-isolation tests passed.
No data repair executed.
No schema trigger added.
No promotion cycles run.
````

The fail-closed TypeErrors are intentional and useful. They reveal call sites that were still relying on global behavior.

## Goal

Fix the three legitimate call sites so every real `IdentityResolver` invocation passes the correct tenant context.

Known fail-closed call sites:

```text
scheduler.py:225
web_app.py:6281
web_app.py:6786
```

## Required actions

### 1. Audit all call sites

Search for:

```text
IdentityResolver(
```

Report every call site and classify it as:

```text
production
scheduler
API/web
test
manual/dev utility
dead/orphan
```

### 2. Fix scheduler call site

For:

```text
scheduler.py:225
```

Pass the current tenant ID from the scheduler’s tenant/vault iteration context.

Required invariant:

```text
IdentityResolver(..., tenant_id=<current tenant id>)
```

Do not infer tenant from entity rows after the fact.

Do not add any global fallback.

If the scheduler does not have tenant context available at this point, stop and report.

### 3. Fix web/API call sites

For:

```text
web_app.py:6281
web_app.py:6786
```

Pass tenant ID from request/session context.

Expected source:

```text
TenantSession
session.tenant_id
request tenant/vault context
```

Use the actual tenant context already available in the route/session.

Do not use a hardcoded tenant.

Do not infer tenant from selected entities.

Do not bypass the required `tenant_id`.

If tenant context is not available, stop and report.

### 4. Tests

Add or update targeted tests covering:

```text
scheduler passes tenant_id into IdentityResolver
web/API path passes tenant_id into IdentityResolver
calling IdentityResolver without tenant_id still fails closed
no call site falls back to global behavior
no cross-tenant merge behavior is reintroduced
```

If direct web_app tests are heavy, add a focused regression/static test that verifies the call path supplies tenant_id.

### 5. Existing tests

Re-run:

```text
tests/test_identity_resolver_tenant_isolation.py
new call-site tests
any relevant scheduler/web tests if available
```

### 6. Architect review

Run architect/code review focused on:

```text
all IdentityResolver production call sites are tenant-aware
scheduler path is tenant-scoped
web/API paths are tenant-scoped
no global fallback introduced
Phase 1 tenant guards remain intact
no data repair or schema mutation slipped in
```

If architect flags HIGH issues, fix before final report.

## Do not do

Do not:

```text
repair existing S relationships
repair DB-wide cross-tenant relationships
add DB trigger
add schema constraint
add DuplicateCandidate/MergeAudit tenant_id columns
run promotion cycles
start scheduler
run VerificationWorker
run Nexus 100 scoring
start Stage 2
touch v2
edit replit.md
```

## Findings doc update

Update:

```text
docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md
```

Add:

```text
Stage 1I Phase 1.5 call-site fix
all IdentityResolver call sites audited
which call sites were updated
tests added/updated
architect review result
remaining Phase 3/4/5 plan
Stage 2 readiness verdict
```

## Final report

Report:

```text
all IdentityResolver call sites found
files changed
exact call-site fixes
tests run and results
architect review result
whether Phase 1.5 is complete
whether Phase 3 data repair is now safe to plan
whether Phase 4 DB trigger is now safe to plan
whether Stage 2 remains blocked
```

## Stop condition

Stop after Phase 1.5 call-site fix, tests, and architect review.

Wait for sign-off before data repair, schema trigger, promotion rerun, or Stage 2.