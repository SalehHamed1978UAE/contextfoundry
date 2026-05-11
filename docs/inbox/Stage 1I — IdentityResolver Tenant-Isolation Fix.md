# Stage 1I — IdentityResolver Tenant-Isolation Fix

## Alignment

- **Module touched:** `src/context_foundry/agents/identity_resolver.py`, targeted tests, findings doc
- **Product vs implementation:** implementation-level must-fix before Stage 2
- **Architecture-doc consistency:** follows Stage 1H finding: scoped extraction and promotion can work, but tenant-boundary integrity is broken by identity-resolution relationship retargeting
- **Drift risk:** repairing data before fixing the writer; adding schema trigger before code is safe; allowing cross-tenant merges to continue; starting Stage 2 while relationship endpoints are tenant-unsafe
- **Out of scope:** DB data repair, schema triggers, ontology backfill, scheduler activation, Stage 2 implementation, Nexus 100 scoring, VerificationWorker full run, v2 work, `replit.md` edits

## Decision

Authorize **Phase 1: IdentityResolver tenant-isolation code fix + tests**.

Do not repair existing data yet.

Do not add schema trigger yet.

Do not backfill S relationships yet.

Do not run promotion cycles yet.

Do not start Stage 2.

## Accepted Stage 1H finding

Accepted root cause:

```text
IdentityResolver._transfer_relationships() retargets relationship endpoints across tenants.

Accepted evidence:

2431 merges in the S extraction lag window
100% by merged_by='identity_resolver'
2418 / 2431 merges cross-tenant
relationship update timestamps match merge timestamps
relationships_transferred approximately matches the S cross-tenant relationship count

Accepted missing tenant guards:

identity_resolver.py L617-L622:
  _merge_pair loads entity_a/entity_b by ID only, without tenant guard

identity_resolver.py L726:
  rel.source_id = to_entity.id without checking to_entity.tenant_id == rel.tenant_id

identity_resolver.py L746:
  rel.target_id = to_entity.id without checking to_entity.tenant_id == rel.tenant_id

Accepted status:

Stage 2 is blocked.
Promotion convergence is blocked.
Gardener is correctly fail-closing under tenant-scoped RLS.
Step 0 — Read remaining IdentityResolver code first

Before editing, read the remaining unaudited sections:

src/context_foundry/agents/identity_resolver.py lines ~300-617
src/context_foundry/agents/identity_resolver.py lines ~755-837

Specifically inspect:

__init__
_find_candidates
candidate generation
candidate loading
_choose_survivor
merge audit write path
any duplicate candidate review/update path

Goal:

Find every place where a cross-tenant candidate pair can be generated, accepted, merged, or used to transfer relationships.

If you find more tenant-unsafe sites, include them in this same Phase 1 fix if they are in IdentityResolver and directly part of candidate/merge/transfer behavior.

If the issue spans outside IdentityResolver, stop and report.

Required code fixes
1. Tenant-scope candidate generation/loading

Ensure IdentityResolver never creates or accepts candidate pairs where either entity is outside self.tenant_id.

Required invariant:

candidate.entity_a.tenant_id == self.tenant_id
candidate.entity_b.tenant_id == self.tenant_id

If DuplicateCandidate has no tenant_id column, enforce by joining or loading both Entity rows and filtering on both entities’ tenant_id.

Do not rely on ID-only lookup.

2. Tenant-guard _merge_pair

In _merge_pair, load entity_a and entity_b with tenant guard:

Entity.id == candidate.entity_a_id AND Entity.tenant_id == self.tenant_id
Entity.id == candidate.entity_b_id AND Entity.tenant_id == self.tenant_id

If either entity is missing under the tenant-scoped lookup:

do not merge
do not transfer relationships
log / record skip reason
fail closed

Do not silently fall back to global lookup.

3. Tenant-guard survivor selection

Ensure _choose_survivor cannot choose a survivor outside self.tenant_id.

Required invariant:

survivor.tenant_id == self.tenant_id
merged_entity.tenant_id == self.tenant_id

If not true, skip merge.

4. Tenant-guard _transfer_relationships

Before retargeting any relationship endpoint, enforce:

rel.tenant_id == from_entity.tenant_id
rel.tenant_id == to_entity.tenant_id
from_entity.tenant_id == to_entity.tenant_id

Only transfer relationships inside the same tenant.

If a relationship or target entity violates the invariant:

skip transfer
do not rewrite source_id
do not rewrite target_id
record/log skip reason
5. Tenant-scope duplicate checks inside _transfer_relationships

Any dedup check around relationship transfer must include tenant scope.

Required invariant:

dedup relationship search is constrained by rel.tenant_id
dedup endpoint entity IDs belong to the same tenant

Do not let an existing relationship in another tenant suppress or redirect a relationship in the current tenant.

6. Fail-fast invariant helper

Add a small helper if useful, for example:

def _same_tenant(self, *entities) -> bool:
    return all(e is not None and e.tenant_id == self.tenant_id for e in entities)

or equivalent.

Keep it local to IdentityResolver.

Tests

Add targeted tests that would have caught this bug.

Minimum tests:

1. Cross-tenant candidate is rejected

Create two tenants with same-name / same-type entities.

Create or simulate a duplicate candidate pairing entity A from tenant 1 with entity B from tenant 2.

Run the merge path.

Assert:

no merge occurs
no relationship endpoint changes
no cross-tenant relationship created
2. _merge_pair loads by tenant

Given a candidate with entity IDs from different tenants, _merge_pair must fail closed.

Assert:

entity_a/entity_b global IDs exist
tenant-scoped lookup rejects one side
merge is skipped
3. _transfer_relationships does not retarget across tenants

Create:

relationship.tenant_id = tenant S
from_entity.tenant_id = tenant S
to_entity.tenant_id = tenant L

Run _transfer_relationships.

Assert:

relationship.source_id unchanged
relationship.target_id unchanged
relationships_transferred count does not increment
skip/log reason recorded if observable
4. Within-tenant transfer still works

Create two duplicate entities in the same tenant, with relationships pointing to the merged-away entity.

Run merge.

Assert:

relationship endpoint retargets to survivor
tenant_id remains unchanged
no cross-tenant endpoint appears
5. Candidate generation is tenant-scoped

If _find_candidates is in scope, assert:

same-name entities in different tenants do not produce a duplicate candidate pair
same-name entities inside the same tenant can produce a candidate pair
6. No cross-tenant leakage regression

After identity resolver run on synthetic two-tenant setup, assert:

SELECT COUNT(*) FROM relationships r
JOIN entities s ON s.id = r.source_id
JOIN entities t ON t.id = r.target_id
WHERE r.tenant_id != s.tenant_id OR r.tenant_id != t.tenant_id

returns zero for the synthetic test rows.

Architect review

After code + tests pass, run architect/code review focused on:

tenant isolation
no cross-tenant candidate generation
no cross-tenant merge acceptance
no cross-tenant relationship endpoint transfer
within-tenant merge behavior preserved
no data repair hidden inside code fix
no schema/global ontology/prompt/scheduler changes

If architect flags HIGH issues, fix before final report.

Do not do yet

Do not:

repair existing S data
repair DB-wide 2814 cross-tenant relationships
add DB trigger
add schema constraint
run promotion cycles
run scheduler
run Nexus 100 scoring
run VerificationWorker
backfill ontology
start Stage 2
touch v2
edit replit.md
Findings doc update

Update:

docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md

Add:

Stage 1I IdentityResolver tenant-isolation fix
files changed
tests added
architect review result
whether cross-tenant merge generation is fixed
whether cross-tenant relationship transfer is fixed
remaining data repair plan
Stage 2 readiness verdict
Final report

Report:

remaining IdentityResolver code sections read
all tenant-unsafe sites found
files changed
exact code fixes
tests run and results
architect review result
whether Phase 1 is complete
whether Phase 3 data repair is now safe to plan
whether Phase 4 schema trigger is now safe to plan
whether Stage 2 remains blocked
Stop condition

Stop after Phase 1 code fix + tests + architect review final report.

Wait for sign-off before any data repair, schema trigger, or promotion rerun.