Stage 1B β — Final Sign-off and Closeout

Alignment

Module touched: Stage 1B β closeout only

Product vs implementation: sign-off on controlled scoped-extraction validation

Architecture-doc consistency: matches signed-off Piece 2 / Stage 1B design: scoped path tested through run_vault_extraction.py, no default flip, no Nexus 100 scoring, no Stage 2

Drift risk: overstating β as an adaptive-ontology test; starting Stage 2 or cold-corpus work before sign-off

Out of scope: Stage 2 implementation, Nexus 100 scoring, cold-corpus execution, full S VerificationWorker run, schema fixes, prompt changes, MultiModelExtractor changes, brain/app.py, Gardener changes, Data Gates, v2, workflow restarts, replit.md edits


Sign-off

Stage 1B β is accepted and closed.

Accept revised β Findings 1–6 as published.

Accepted summary:

S completed cleanly.
S resumed after platform/runtime interruption without data loss.
S produced 2345 entities / 2227 relationships.
L baseline remains 2258 entities / 2192 relationships.
Delta: +87 entities (+3.9%), +35 relationships (+1.6%).
Ontology unchanged in both L and S.
VerificationWorker errors = 0.
No stop conditions triggered.
MultiModelExtractor prompt SHA unchanged.
No Nexus 100 scoring run.
No Stage 2 work.

The initial “2× archive ratio” interpretation is rejected. The archived rows are identity-resolution merges, not quality rejections.

The TRUSTED gap is accepted as dwell-time lag unless the follow-up query proves otherwise.

Adaptive ontology claim

Record this conclusion:

The adaptive-ontology claim is defensible as a codebase/design claim: raw ontology write paths, discovery/candidate paths, and governed Ontology Foundry infrastructure exist. Historical 803 ad-hoc types show that adaptive ontology growth has occurred.

However, Stage 1B β on Nexus does not validate adaptive ontology behavior because Nexus is saturated after repeated extraction and development cycles. Stage 1B β validates scoped extraction mechanics and extraction-output differences, not novel ontology growth.

Record future validation need:

A cold-corpus validation is required to test adaptive ontology behavior on genuinely novel domains.

Do not run that test now.

Do not draft the cold-corpus brief now.

What Stage 1B β proves

Record as accepted:

- Scoped extraction code path runs to completion on 100 Nexus docs.
- Scoped extraction produces equivalent or slightly larger fact volume than legacy.
- Scoped extraction changes predicate distribution toward more typed/discriminating verbs.
- Scoped extraction triggers more identity-resolution merges, consistent with finer-grained mention extraction.
- Confidence distributions are equivalent; no quality degradation evident.
- Per-doc disk-artifact resume is robust to platform/runtime interruption.

What Stage 1B β does not prove

Record as accepted:

- It does not prove Nexus 100 question-answering accuracy.
- It does not prove adaptive ontology behavior on novel domains.
- It does not prove final TRUSTED parity until S has had enough dwell time.

Open item 1 — TRUSTED dwell re-query

Do the cheap follow-up only if the dwell window has elapsed.

Rule:

If current UTC time is >= 2026-05-11 07:35:13 UTC:
    run the TRUSTED/STAGING/ARCHIVED re-query for S and L.
Else:
    do not wait.
    record the due time and stop.

Query only. No code changes. No workflow work.

Report:

L entities by lifecycle_state
S entities by lifecycle_state
L relationships by lifecycle_state
S relationships by lifecycle_state
whether S TRUSTED count moved after min_dwell_time_hours=1.0
whether β-Finding 4 is closed or still pending

Do not run this as a long wait loop. If the time has not elapsed, defer.

Open item 2 — relationships.source_document_id observability gap

Accept as Stage 2 design input, not immediate action.

Record:

Observability Gap: relationships.source_document_id is varchar and does not join cleanly to documents.id uuid. This blocks per-doc precision/recall audits. Architect upgraded this to high-priority Stage 2 observability input.

Do not fix now.

Do not migrate schema now.

Do not start a schema-design task in this turn.

Open item 3 — cold-corpus adaptive-ontology test

Accept as pre-Stage 2 planning input, not immediate execution.

Record future task name:

Piece 2X — Adaptive Ontology Cold-Corpus Validation

Purpose:

Use a fresh domain/corpus the system has not repeatedly extracted to test:
- missing schema detection;
- schema proposal;
- Ontology Foundry governance path;
- approved schema activation;
- rejected schema exclusion.

Do not draft the Piece 2X brief in this task.

Do not run the cold-corpus test now.

Do not mutate data.

Do not start Stage 2.

Open item 4 — full S VerificationWorker run

Defer.

Do not run the optional full S VerificationWorker now.

Reason:

It is medium priority, estimated ~360k tokens, and not required for Stage 1B β closeout.

If Stage 2 design needs a complete S verification picture, request it as a separate sign-off-gated task.

Findings doc

Ensure:

docs/findings/piece_2_stage1b_nexus_l_vs_s_findings_2026-05-10.md

contains:

- final L/S counts;
- revised Finding 2 and Finding 4;
- identity-resolution archive explanation;
- dwell-time TRUSTED limitation;
- saturated-corpus limitation;
- adaptive-ontology code-exists / Nexus-saturated distinction;
- cold-corpus future validation note;
- observability gap note;
- explicit statement that Nexus 100 was not scored.

Standing constraints

Unchanged:

NO replit.md trim.
NO Manus/Ontology restart.
NO killing Start All.
NO v2 work.
Paste findings and wait for sign-off before new implementation tasks.
Alignment block remains required.

Final status

Stage 1B β is closed after the dwell re-query is either:

completed if time has elapsed
or deferred if time has not elapsed

After that, paste the closeout summary.

Do not start Stage 2.

Do not run Nexus 100 scoring.

Do not draft or run the cold-corpus task.

Do not run full S VerificationWorker.

Do not implement schema fixes.

Stop after the dwell-query status report / deferral note and the Stage 1B β closeout summary.