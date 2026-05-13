# Stage 2D — Score Recovery: Tree-Off Default + DOCUMENT_EVIDENCE Fallback, No Runtime Restart

## Alignment

- **Module touched:** query/retrieval path and retrieval default configuration only
- **Product vs implementation:** implementation-level score recovery before Stage 2 default activation
- **Architecture-doc consistency:** preserves validated tenant-safe clean-vault pipeline; restores answer coverage without re-extraction, ontology mutation, or queue drain
- **Drift risk:** restarting Start All and accidentally draining the global extraction queue; implementing fallback without provenance labeling; treating DOCUMENT_EVIDENCE as TRUSTED graph evidence
- **Out of scope:** Start All restart, extraction worker repair, queue drain, re-extraction, ontology mutation, extraction prompt changes, Stage 2 default activation, v2 work, `replit.md` edits

## Sign-off

Stage 2C is accepted.

Accepted measured result:

```text
Stage 1J tree=true:  50/100
Stage 1J tree=false: 55/100
Delta: +5
Regressions: 0
Recovered: Q15, Q36, Q40, Q68, Q100

Accepted failure attribution:

0/50 failures are solved by orphan-relation promotion.
32/50 failures are attribute/spec/date/metric facts.
14/50 failures are graph-edge precision/recall issues inside existing governed vocabulary.

Accepted diagnosis:

The score gap is not caused by deleted code.
The score gap is caused by narrowed extraction vocabulary, tree retrieval drag, missing chunk fallback, and some unwired/underused capabilities.

Critical runtime safety rule

Do not restart Start All.

Reason:

The extraction worker queue is global FIFO, not tenant-scoped.
There are stale pending extraction_requests across multiple tenants.
Restarting Start All may revive the worker and drain unrelated tenants, including the clean Stage 1J vault.

Therefore:

No Start All restart.
No queue drain.
No re-extraction.
No mode=fresh.
No service reload unless explicitly authorized later.

Decision

Proceed with Stage 2D as a code + direct-harness validation task.

Implement:

A. tree_based_retrieval=false as the default for future normal requests
B. DOCUMENT_EVIDENCE fallback for attribute/spec/date/metric questions when KG cannot answer

Do not rely on the currently running Start All process to pick up these changes.

Validation must use either:

a direct local harness importing the updated code
or a test/integration path that does not require restarting Start All

If no safe direct validation path exists, stop and report.

Part A — Tree retrieval default off

Set the default so future normal requests use:

tree_based_retrieval=false

Requirements:

preserve per-request override
do not remove tree retrieval code
do not delete graph-hopping functionality
do not edit replit.md
do not restart Start All

Likely target:

start.sh
or the config/default resolution path that currently enables CF_TREE_BASED_RETRIEVAL=true

If start.sh is changed, record that the running process will not see it until a later safe runtime cutover.

Add or update a config test if a test surface exists:

default resolves false
explicit true override still works
explicit false override still works

Part B — DOCUMENT_EVIDENCE fallback

Implement a conservative fallback for cases where:

KG / graph answer path returns no_data or insufficient information
OR KG answer lacks the exact scalar/date/spec/metric value
AND relevant document chunks exist

Initial target question patterns:

revenue / amount / budget / backlog / capex
date / when / year
specification / endurance / temperature / qubits / capacity
certification / compliance status
credential / degree / education
milestone / target / goal

Do not make this a broad catch-all.

Evidence-source labeling

Responses must distinguish answer source.

Use or add a field equivalent to:

answer_source =
  TRUSTED_GRAPH_FACT
  STAGING_GRAPH_FACT
  DOCUMENT_EVIDENCE
  GAP

Rules:

If answer is from promoted KG facts → TRUSTED_GRAPH_FACT.
If answer is from chunks because KG lacks the fact → DOCUMENT_EVIDENCE.
If neither graph nor chunks support answer → GAP / no_data.

Do not label DOCUMENT_EVIDENCE as TRUSTED graph.

Do not answer without cited chunk/document provenance.

Required code-path audit before implementation

Read and report:

/api/vault/chat request path
ToolAgent / QueryPipeline answer path
where tree_based_retrieval flag is read
where graph no_data / insufficient-data response is generated
existing chunk retrieval function(s)
existing fallback_semantic_search behavior
where response metadata can include answer_source
whether ConversationStore writes are expected

Then implement the smallest hook.

Tests

Add targeted tests for DOCUMENT_EVIDENCE fallback.

Minimum tests:

1. If TRUSTED graph fact exists, answer_source remains TRUSTED_GRAPH_FACT and fallback is not used.
2. If KG lacks scalar/date/spec fact but a chunk contains it, answer_source=DOCUMENT_EVIDENCE and answer cites the chunk/document.
3. If neither KG nor chunks contain the answer, result remains GAP/no_data.
4. Fallback is tenant-scoped.
5. Fallback does not mutate entities, relationships, ontology, documents, or extraction_requests.
6. Tree retrieval default is false, but per-request override still works.

If full /api/vault/chat tests require the running service to reload, do not use that path. Use a direct local query harness or focused integration test instead.

Validation run

After code changes and tests pass, run a question-only validation against the existing clean Stage 1J vault using the updated code through a safe direct harness:

vault_id = ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda
question set = test_questions/nexus_100q.json
tree_based_retrieval=false
existing data only

Do not use a path that requires Start All restart.

Do not re-extract.

Do not drain extraction_requests.

Do not run mode=fresh.

Capture:

score
pass/fail IDs
no_match count
no_data count
questions recovered vs Stage 2C tree=false baseline
questions lost vs Stage 2C tree=false baseline
number of DOCUMENT_EVIDENCE answers
which recovered questions used DOCUMENT_EVIDENCE
which of Q15, Q36, Q40, Q68, Q100 remain recovered
which of the 32 attribute-fact failures are answered via DOCUMENT_EVIDENCE
artifact paths

Success target

Primary target:

Stage 1J score improves from 55/100 toward ≥70/100.

Minimum useful outcome:

+5 or more additional points with zero serious hallucination regressions.

If score does not improve, report why before attempting any other fix.

Architect review

Run architect/code review after implementation.

Architect focus:

fallback is tenant-scoped
fallback carries provenance
fallback does not claim graph trust
tree default change is low-risk and override preserved
no extraction prompt changes
no ontology mutation
no Stage 2 default activation
no Start All restart

If architect flags HIGH issues, fix before final report.

Findings doc

Create or update:

docs/findings/stage2d_score_recovery_document_evidence_2026-05-12.md

Include:

tree-default change
DOCUMENT_EVIDENCE fallback design
tests
architect review
question-only score result
recovered/lost question IDs
answer_source distribution
remaining failure buckets
recommended next recovery lever
runtime reload deferred note

Do not do

Do not:

restart Start All
drain extraction_requests
re-extract any vault
run mode=fresh
mutate ontology
change extraction prompts
canonicalize HOLDS_ROLE / FORMERLY_HELD yet
repair worker queue
run Nexus fresh scoring
start Stage 2 default activation
touch v2
edit replit.md

Stop triggers

Stop and report if:

fallback would require broad query rewrite
fallback cannot be tenant-scoped
fallback cannot carry provenance
fallback would answer without evidence
tree default cannot be changed without global side effects
validation requires Start All restart
tests fail
architect flags HIGH
validation run mutates facts or drains extraction queue

Final report

Report:

files changed
tree default change
DOCUMENT_EVIDENCE fallback hook
tests run and results
architect review result
question-only score
recovered/lost IDs
DOCUMENT_EVIDENCE answer count
whether Q15/Q36/Q40/Q68/Q100 remain recovered
which attribute-fact failures recovered
post-test mutation check
remaining gap to 70/76
recommended next action
confirmation Start All was not restarted
confirmation extraction queue was not drained

Stop condition

Stop after Stage 2D final report.

Wait for sign-off before ontology mutation, prompt change, re-extraction, worker recovery, canonicalization fix, runtime restart, or Stage 2 default activation.
