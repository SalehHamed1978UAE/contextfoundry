# Piece 0.6 Mutation — Execution Brief

## Alignment

- **Module touched:** `ontology.relations` (six row UPDATEs); `tests/ontology/test_repository_domain_filter.py`; `docs/architecture.md` (Gap 5 resolution + Piece 0.6 prerequisite section update).
- **Product vs implementation:** implementation execution of the signed-off Piece 0.6 disposition (ADR-011).
- **Architecture-doc consistency:** matches Piece 2.0 design §4 and ADR-011 verbatim. Resolves Gap 5.
- **Drift risk:** running mutation while Medsync is still extracting (mid-extraction snapshot inconsistency); skipping the just-in-time preflight; updating documentation to "RESOLVED" before the data actually changes.
- **Out of scope:** Piece 2 implementation, prompt changes, `SchemaPromptGenerator`, Gardener, v2 work, Nexus 100 run, workflow restarts, `replit.md` edits, sibling relations.

## Standing Constraints

- No `replit.md` edits.
- No workflow restarts. No killing workflows.
- No prompt changes.
- No `SchemaPromptGenerator` changes.
- No Gardener changes.
- No v2 work. v2 stays parked per ADR-004.
- No Nexus 100 run.
- One DB mutation transaction only.
- Sign-off-gated per ADR-007.
- Every response begins with the alignment block.

## Trigger condition

Execute this brief only when:

1. Test: ClaudeCode Medsync is no longer listed as running in the system log.
2. The just-in-time preflight passes (defined below).

If either condition fails, stop and report. Do not proceed.

## Just-in-time preflight (run immediately before mutation)

1. **Idle-in-transaction recheck.** Run:

```sqlSELECT pid, application_name, state,
now() - state_change AS idle_duration,
now() - xact_start AS xact_age,
left(query, 200) AS query_preview
FROM pg_stat_activity
WHERE datname = current_database()
AND state = 'idle in transaction'
AND (query ILIKE '%ontology.relations%'
OR query ILIKE '%relationships%'
OR query ILIKE '%entities%'
OR query ILIKE '%document_chunks%');

   Expected: zero rows. If any row returned, stop and report.

2. **Lock recheck.** Confirm zero locks held on `ontology.relations`. Same query as Preflight 6 from the original mutation brief.

3. **Six-row state recheck.** Confirm the six target rows are still `domain_id = NULL`, `status = 'ACTIVE'`, `valid_to = NULL`. Use the exact full UUIDs from the prior preflight (Preflight 2 paste-back):

   - HOLDS_POSITION PERSON → JOB_TITLE     = `479a23c5-22a1-45cf-83af-e200aa5ead87`
   - HOLDS_POSITION PERSON → ORGANIZATION  = `5c615de9-d365-4253-8474-95de22dfce99`
   - WORKS_AT       PERSON → ORGANIZATION  = `058414f9-7530-41e5-9c20-94789aa32452`
   - REPORTS_TO     PERSON → PERSON        = `91b9ae86-fa99-4dbb-aa0e-bf5b478ddefa`
   - HAS_COMPENSATION PERSON → COMPENSATION = `247c30fc-f06c-4891-8626-7dcf35046679`
   - HAS_COMPENSATION PERSON → CONCEPT     = `9dfd6070-cd8c-4f3c-9c44-9d898c293ff9`

4. **Backup integrity recheck.** Confirm `ontology.relations` and `ontology.relations_backup_pre_piece_0_6` both contain 254 rows.

If any preflight check fails, stop and report. Do not proceed to mutation.

## Mutation transaction

If preflight passes, run a single transaction. Use the deprecation semantics from the prior Preflight 4 finding (paste it back from the prior preflight report). Use the approval-metadata behavior from Preflight 5 (no fake values per ADR-009).

```sqlBEGIN;-- Updates 1-4: HOLDS_POSITION ×2, WORKS_AT, REPORTS_TO → core
UPDATE ontology.relations
SET domain_id = 'core',
updated_at = now()
-- approved_by/approved_at per Preflight 5 column types
WHERE id IN (
'479a23c5-22a1-45cf-83af-e200aa5ead87'::uuid,
'5c615de9-d365-4253-8474-95de22dfce99'::uuid,
'058414f9-7530-41e5-9c20-94789aa32452'::uuid,
'91b9ae86-fa99-4dbb-aa0e-bf5b478ddefa'::uuid
)
AND domain_id IS NULL
AND status = 'ACTIVE';-- Confirm exactly 4 rows updated. If not, ROLLBACK.-- Update 5: HAS_COMPENSATION PERSON → COMPENSATION → finance
UPDATE ontology.relations
SET domain_id = 'finance',
updated_at = now()
WHERE id = '247c30fc-f06c-4891-8626-7dcf35046679'::uuid
AND domain_id IS NULL
AND status = 'ACTIVE';-- Confirm exactly 1 row updated. If not, ROLLBACK.-- Update 6: HAS_COMPENSATION PERSON → CONCEPT → DEPRECATED
-- Use deprecation semantics from Preflight 4
UPDATE ontology.relations
SET <deprecation field per Preflight 4>,
updated_at = now()
WHERE id = '9dfd6070-cd8c-4f3c-9c44-9d898c293ff9'::uuid
AND domain_id IS NULL
AND status = 'ACTIVE';-- Confirm exactly 1 row updated. If not, ROLLBACK.-- Verification block — run before COMMIT
SELECT relation_type, domain_id, status, valid_to, COUNT(*)
FROM ontology.relations
WHERE relation_type IN ('HOLDS_POSITION','WORKS_AT','REPORTS_TO','HAS_COMPENSATION')
GROUP BY 1, 2, 3, 4
ORDER BY 1, 2 NULLS FIRST, 3;-- Expected (modulo deprecation field choice):
--   HOLDS_POSITION   | core    | ACTIVE      | 2
--   WORKS_AT         | core    | ACTIVE      | 1
--   REPORTS_TO       | core    | ACTIVE      | 1
--   HAS_COMPENSATION | finance | ACTIVE      | 1
--   HAS_COMPENSATION | <NULL>  | DEPRECATED  | 1-- COMMIT;
-- Leave commented. Verify the SELECT output matches expectations, then un-comment and run COMMIT.

If verification matches, COMMIT. Otherwise ROLLBACK and stop.

## Post-mutation verification

After COMMIT, run repository checks:

```pythonget_all_relations(domain_id='core')      # expect 17 + 4 = 21
get_all_relations(domain_id='finance')   # expect 27 + 1 = 28
get_all_relations()                      # expect 254 (legacy no-filter)
get_all_relations(include_deprecated=True)  # if signature exists

Paste the row counts. If actual counts differ, explain why.

## Tests

Update `tests/ontology/test_repository_domain_filter.py`:

- `test_relations_strict_filter_core`: expected count 17 → 21.
- Update finance test (if present) for new count 27 → 28.
- Add tests asserting HOLDS_POSITION (both signatures), WORKS_AT, REPORTS_TO are in `get_all_relations(domain_id='core')`.
- Add test asserting HAS_COMPENSATION (PERSON → COMPENSATION) is in `get_all_relations(domain_id='finance')`.
- Add test asserting deprecated HAS_COMPENSATION (PERSON → CONCEPT) is excluded from default active calls per Preflight 4 semantics.
- Confirm NULL-domain rows still don't leak into scoped calls.

Run tests. Paste pass/fail. All tests must pass before next step.

## Documentation updates

Only after the mutation commits and tests pass:

**`docs/architecture.md` Gap 5 update.** Edit Gap 5 to mark it resolved by Piece 0.6:

> ### Gap 5 (RESOLVED by Piece 0.6, 2026-05-10): Foundational relations governed
>
> [Original finding text preserved.]
>
> **Resolution:** Piece 0.6 mutation (ADR-011) governed the four foundational relations and deprecated the mis-targeted HAS_COMPENSATION (PERSON → CONCEPT) row:
>
> - `HOLDS_POSITION` (PERSON → JOB_TITLE) → `core`
> - `HOLDS_POSITION` (PERSON → ORGANIZATION) → `core`
> - `WORKS_AT` (PERSON → ORGANIZATION) → `core`
> - `REPORTS_TO` (PERSON → PERSON) → `core`
> - `HAS_COMPENSATION` (PERSON → COMPENSATION) → `finance`
> - `HAS_COMPENSATION` (PERSON → CONCEPT) → `DEPRECATED`
>
> Sibling rows (HELD_POSITION, AFFILIATED_WITH, MANAGES, OWNS, etc.) were audited but not mutated. They remain Piece 7 governance scope.
>
> Gap 6 (HR-domain compensation extraction) remains open — Piece 0.6's disposition does not solve it.

**`docs/architecture.md` "Piece 0.6 (prerequisite to Piece 2)" section.** Append a "Resolution" line indicating the mutation completed on 2026-05-10 with reference to ADR-011.

## Final report

- Trigger condition status (Medsync cleared confirmation).
- Just-in-time preflight results (all four checks).
- Mutation SQL run (with full UUIDs filled in and deprecation semantics applied).
- Verification block output.
- COMMIT confirmation or ROLLBACK reason.
- Post-mutation repository check results.
- Test results (pass/fail per test).
- `docs/architecture.md` Gap 5 update confirmation.
- `docs/architecture.md` Piece 0.6 prerequisite section update confirmation.
- Confirmation that no Piece 2 implementation, prompt, Gardener, v2, Nexus, workflow, or `replit.md` work occurred.

## Stop condition

Stop after final report. Do not begin Piece 2 implementation. Wait for confirmation.