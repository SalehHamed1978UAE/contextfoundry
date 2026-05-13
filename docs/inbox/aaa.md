# Stage 2F — Nexus 100 Evidence-Plane Classification Audit

## Alignment

- **Module touched:** read-only analysis only; no code or DB changes
- **Product vs implementation:** product/architecture validation before building new graph types
- **Architecture-doc consistency:** follows Stage 1J/2C/2D/2E findings: relational KG is tenant-safe and promotable, but answer coverage is limited because many questions require non-relational evidence
- **Drift risk:** building more relational ontology when the benchmark requires property, temporal, semantic, or procedural evidence
- **Out of scope:** code edits, DB mutations, ontology mutation, prompt changes, re-extraction, worker recovery, Stage 2 implementation, v2, `replit.md` edits

## Goal

Classify the Nexus 100 question set by the kind of evidence needed to answer each question.

Do not fix anything.

Do not run extraction.

Do not rerun scoring.

## Evidence-plane taxonomy

Use these labels:

```text
IDENTITY
RELATIONAL
PROPERTY
TEMPORAL
SEMANTIC
PROCEDURAL
AGGREGATE
MIXED

Definitions:

IDENTITY: entity disambiguation or name lookup.
RELATIONAL: typed relationships between entities, e.g. REPORTS_TO, OWNS, CUSTOMER_OF.
PROPERTY: structured attributes/specs/metrics/values on an entity, e.g. revenue, qubits, endurance, degree, certification.
TEMPORAL: dated events, timelines, appointments, milestones, before/after.
SEMANTIC: qualitative claims, summaries, narrative statements, strategic positioning.
PROCEDURAL: ordered steps, workflows, policies, conditions.
AGGREGATE: ranking, totals, comparisons, set aggregation.
MIXED: requires two or more evidence planes.

Inputs

Use:

test_questions/nexus_100q.json
Stage 1J results
Stage 2C/2D/2E results
failure analysis artifacts
legacy 176a4fb2 comparison if available

Required output table

For each question:

question_id
question text
gold answer
Stage 1J pass/fail
Stage 2D or latest pass/fail if available
legacy pass/fail if available
primary evidence plane
secondary evidence plane, if any
why this label
current system representation:
  TRUSTED relational graph
  STAGING relational graph
  document chunks only
  missing
suggested representation:
  identity layer
  relational graph
  property graph
  temporal graph
  semantic evidence
  procedural graph
  aggregate/composite handler

Summary

Report:

count by primary evidence plane
count by primary+secondary pair
pass rate by evidence plane
failure rate by evidence plane
which evidence plane explains most of the 50/100 gap
which evidence plane should be built first

Decision output

Recommend one of:

A. Build Property Graph MVP first.
B. Build Temporal Graph MVP first.
C. Improve Relational Graph extraction first.
D. Improve DOCUMENT_EVIDENCE / semantic plane first.
E. Build cross-graph ContextBundle synthesis first.
F. Mixed plan with sequence.

Specific questions to answer

Answer:

How many Nexus questions are fundamentally property/spec/metric/date/value questions?
How many are relational?
How many are temporal?
How many are semantic?
How many require aggregation?
How many would be solved by DOCUMENT_EVIDENCE alone?
How many require structured property or temporal extraction?
Does the five-evidence-plane architecture fit this benchmark?

Findings doc

Create:

docs/findings/stage2f_nexus100_evidence_plane_audit_2026-05-12.md

Do not do

Do not:

edit code
mutate DB
run extraction
rerun Nexus 100
change ontology
change prompts
wire new graph types
start Stage 2 implementation
touch v2
edit replit.md

Stop condition

Stop after the evidence-plane classification report.

Wait for sign-off before any implementation plan.