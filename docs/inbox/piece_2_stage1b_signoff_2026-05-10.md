# Piece 2 Stage 1B Sign-off

## Alignment

- **Module touched:** none (sign-off message only)
- **Product vs implementation:** sign-off on Stage 1B design decisions
- **Architecture-doc consistency:** matches Piece 2 Stage 1B brief and signed-off Piece 2.0 design
- **Drift risk:** none (sign-off only)
- **Out of scope:** Stage 2, Stage 3, accuracy benchmarking via test runner

## Sign-off on five decisions

**1a, 2a, 3a, 4a, 5a — all agent recommendations approved.** Brief is approved. Proceed with execution after the architect verification step (Section A of the brief).

Clarifying notes alongside the decisions:

**On 1a (env-var on run_vault_extraction.py only):** Confirmed. The audit finding that `brain/app.py` callers don't pass classification metadata is decisive — they couldn't take the scoped path even if the flag were on. Gating activation on the one runner that has the prerequisites (run_vault_extraction.py:781) is the lowest blast radius. brain/app.py stays untouched. Any future scoped activation on production paths is a separate Stage 2 decision after Stage 1B validates the runner.

**On 2a (Nexus Industries pilot):** Confirmed. One reconciliation note: the architecture document and prior session memory record the Nexus 100 baseline as 74/100 (uncontaminated). The brief mentions 77/100. Confirm in the findings doc which baseline applies and reconcile. Doesn't change the choice.

**On 3a (counts + audit signals only first):** Confirmed. Stage 1B's purpose is "prove the path works end-to-end through the actual runner with real metadata." Counts of types extracted, relations extracted, and audit_records emitted is sufficient. Test-runner accuracy comparison is Piece 8 territory or a separate Stage 1B-2.

**On 4a (`platform.extraction_events` for telemetry):** Confirmed. ADR-007 sign-off-gates schema changes; using an existing table avoids triggering that gate for a pilot. If the pilot data reveals telemetry shape limitations, note them in the findings doc.

**On 5a (skip_failed rate > 25% rollback trigger):** Confirmed. Concrete definition: of all documents the runner attempts to process with `CF_PIECE2_SCOPED_EXTRACTION=true`, more than 25% take the `classification_failed` branch (flag-on AND metadata-invalid → audit_record emitted, extraction skipped). Above the threshold: pilot rolls back, findings doc records the failure mode, next decision is whether classifier calibration (Piece 2.5) precedes Stage 2. At or below: Stage 2 promotion becomes a viable next brief.

## Architect review first

Per the brief's Section A: run architect review on the post-fix Stage 1A code before starting Stage 1B execution. If architect surfaces anything new, fix the blocker, rerun targeted tests, then proceed to Section B.

## Standing constraints

Unchanged. v2 stays parked. brain/app.py stays untouched. MultiModelExtractor stays unchanged. No workflow restarts. No replit.md edits.

## Stop condition

After Stage 1B final report, stop. Do not begin Stage 2. Wait for sign-off on findings.