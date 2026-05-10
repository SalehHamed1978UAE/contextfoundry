# Verification Task: Paste-back of Critical Design Sections to Detect Truncation

## Alignment

- **Module touched:** none (read-only paste-back of existing files)
- **Product vs implementation:** verification of the design and architecture documents that govern remaining implementation work
- **Architecture-doc consistency:** confirms canonical documents are intact before Piece 2 implementation depends on them
- **Drift risk:** undetected truncation in design or architecture documents that would make implementation drift from intended spec; the Piece 0.6 mutation ADR and ADR-010 already showed this can happen
- **Out of scope:** any code edits, DB mutations, prompt changes, Piece 0.6 mutation, Piece 2 implementation, v2 work, Nexus, workflow restarts, replit.md edits

## Standing Constraints

- Read-only.
- Do not modify any file.
- This task is independent of the in-flight Piece 0.6 mutation pause and the ADR append work. All three threads can run in parallel.

## Background

Two ADR paragraphs (ADR-010 Rationale and the Piece 0.6 disposition ADR Rationale) reached you with literal `...[Truncated]` markers between paragraphs. The truncation happened on the input side of the chat interface when long structured documents were sent. We need to confirm that other long structured documents — the Piece 2.0 design and the architecture document — were not similarly affected.

## Required paste-back

Paste back the following sections exactly as they appear in the files on disk. Do not summarize. Do not paraphrase. Verbatim paste only.

### From `docs/piece2_domain_scoped_prompting_design_2026-05.md`

1. **§2 in full** — the five-option evaluation (Options A through E) plus the recommendation that follows.
2. **§3 in full** — the confidence and margin policy, including the three-stage threshold revision plan.
3. **§6 in full** — implementation boundaries, including:
   - the repository vs scoped prompt-builder distinction
   - the `audit_records` minimal schema (with the six columns: id, document_id, signal_type, severity, payload, created_at)
   - the MultiModelExtractor three-stage rollout
4. **§8 in full** — the eight sign-off gates.

### From `docs/architecture.md`

5. **The "Implementation gaps recorded at design lock" section in full** — Gap 1 through Gap 6, including the "Three observed Ontology Foundry bypass patterns" subsection if present.
6. **The implementation sequence section** — Pieces 0 through 8 with their summaries.

## What to look for during paste-back

As you paste each section, scan for any of these signals:
- Literal `...[Truncated]` markers in the file content (these would indicate truncation reached disk).
- Paragraphs that end mid-sentence.
- Bullet lists that end abruptly without a trailing period or fenced-block close.
- Section headings followed by suspiciously short content (less than 1-2 paragraphs) where you'd expect substantive text.
- Any place where a numbered list jumps from N to N+2 or skips an obvious step.

If you find any of the above, flag it explicitly in the paste-back. Do not silently fix it.

## Stop condition

Stop after the paste-back. The user reads it and either confirms the documents are intact or sends specific corrections.

This task does not interact with the Piece 0.6 mutation, the ADR append, or any other in-flight work. All three can land independently.
