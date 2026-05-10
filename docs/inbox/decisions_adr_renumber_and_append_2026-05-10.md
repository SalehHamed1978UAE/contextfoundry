Thread 1: ADR numbering correction.
The append landed cleanly but only one ADR went in (the Piece 0.6 disposition, currently numbered ADR-007). Four operating-discipline ADRs still need to land — the ones I drafted in chat earlier: sign-off-gating, pushback, unclassified default, deferred dependency resolution. The numbering is off because the disposition ADR took the slot we'd reserved for sign-off-gating.
Renumber the existing appended ADR from ADR-007 to ADR-011. Then append the four operating-discipline ADRs as ADR-007 through ADR-010 in this order:

ADR-007: Schema and data changes are sign-off-gated
ADR-008: Pushback over picking from offered options
ADR-009: The 'unclassified' default for pre-existing rows
ADR-010: Defer dependency resolution until design proves it required
ADR-011: Piece 0.6 governed disposition of foundational relations (the existing append, renumbered)

Use the verbatim text from docs/inbox/adrs_007_010_full.md for ADR-011 (the existing content, just renumber). For the four operating-discipline ADRs, here is the verbatim text in plain chat — paste each in full:
ADR-007 (2026-05): Schema and data changes are sign-off-gated

Decision: All schema changes, data mutations on production tables, and code-file renames require explicit user sign-off before execution. The bar is intentionally low: even additive nullable columns, even rollbacks of the agent's own incorrect work, go through the gate.
Rationale: Established by Piece 0 closeout precedent. The Piece 0.5 strict-filter fix and the Piece 1 migration both demonstrated that schema and data changes have downstream effects (legacy callers, semantic contracts, default values) that aren't visible from the change itself. Gating every mutation, even ones that look safe, prevents silent assumptions from propagating into production data.
Implication: Migrations are pasted before they run. Rollbacks of incorrect work are surfaced and approved before execution. The agent stops at gates without being asked.

ADR-008 (2026-05): Pushback over picking from offered options

Decision: When a question is framed with offered options but the premise is wrong, the answer is to push back on the premise rather than choose from the options. Picking from a flawed premise silently authorizes work that may be out of scope.
Rationale: Established when the agent asked which LLM to use for the parked FactEvaluator (Anthropic, OpenAI, or both) — a question that assumed FactEvaluator work was active when ADR-004 had parked it. Choosing any of the three options would have implicitly unparked v2. The correct response was to push back on the premise and clarify scope before answering.
Implication: Multiple-choice questions from any source (the agent, the reviewer, the user, an auto-injected plan) are evaluated for premise validity first. If the premise is wrong, the response is "this question doesn't apply" with redirect, not a choice from the menu.

ADR-009 (2026-05): The 'unclassified' default for pre-existing rows

Decision: Schema changes adding classification, governance, or status fields default pre-existing rows to an explicit "never attempted" value (unclassified, null, pending, etc.), not to a value implying success (ok, core, approved, etc.).
Rationale: Established by Piece 1 migration on platform.documents. Defaulting unclassified rows to 'ok' would have silently asserted successful classification where none had occurred — the same drift pattern Gaps 2 and 5 demonstrated corrupts the system over time (803 ad-hoc types written outside governance, 4 untraceable relations assigned to core without provenance).
Implication: Every new status or governance column gets three states minimum: a success value, a failure value, and a "never attempted" default for pre-existing rows. CHECK constraints enforce the enum. The "never attempted" state is not the same as failure and not the same as success.

ADR-010 (2026-05): Defer dependency resolution until design proves it required

Decision: When an implementation Piece may have a prerequisite Piece (e.g., Piece 2 may need Piece 0.6 to govern certain relations), the prerequisite is not run until the dependent Piece's design phase confirms it is actually required. Premature governance based on guessed requirements expands scope without justification.
Rationale: Established when the sequencing question for Piece 0.6 was first raised. The reviewer initially recommended running Piece 0.6 before Piece 2.0 design; on reflection, the dependency was conditional — Piece 0.6 was needed only if Piece 2's scoped prompts required HOLDS_POSITION, WORKS_AT, REPORTS_TO, or HAS_COMPENSATION. Running Piece 0.6 first would have made governance decisions about four relations based on a guessed requirement rather than a designed one. The Piece 2.0 design phase confirmed the dependency, which then justified Piece 0.6 with concrete scope.
Implication: Conditional prerequisites stay deferred until the dependent Piece's design surfaces the requirement. Design phases for Pieces with possible prerequisites must explicitly answer "is the prerequisite actually required, and if so, what is its precise scope?"

After the renumber and the four appends, paste back ADR-007 through ADR-011 in full for verification. Quote the final sentence of every Rationale and every Implication paragraph.
Thread 2: Mutation pause holds.
Medsync still running per the diagnostic. Two idle-in-tx connections on relationships, one 2m44s old. Wait for Medsync to finish naturally. When the system log shows it cleared, run a fresh just-in-time preflight (idle-in-tx check on entities/relationships/document_chunks, locks check on ontology.relations, six-row recheck, backup count match) and proceed if clean.
If Medsync is still running 30 minutes from now, paste status and stop for direction.
Thread 3: docs/inbox/adrs_007_010_full.md cleanup.
Delete it. The ADRs it carried are now in docs/decisions.md (after Thread 1 lands). The inbox file was a one-off workaround for the chat truncation issue and shouldn't accumulate as repo noise.
All three threads run in parallel. Thread 1 (ADR renumber and append) is documentation only and doesn't conflict with the mutation pause.
Standing constraints unchanged. v2 stays parked. The 77+ system_reminder refusals continue.