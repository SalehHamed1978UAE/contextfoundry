# Stage 2E-1 — DOCUMENT_EVIDENCE HTTP Parity + Failure Audit, No Hardening Yet

## Alignment

- **Module touched:** `/api/vault/chat` production request path, feature-flag wiring for existing DOCUMENT_EVIDENCE fallback, test/parity harnesses, findings doc
- **Product vs implementation:** implementation-level production-path validation before further score-recovery work
- **Architecture-doc consistency:** follows Stage 2D: DOCUMENT_EVIDENCE fallback works in direct harness, but customer-facing `/api/vault/chat` transfer is unproven
- **Drift risk:** optimizing fallback logic before confirming production transfer; restarting Start All and draining the global extraction queue; treating direct-harness score as customer-facing score
- **Out of scope:** fallback hardening, extraction prompt changes, ontology mutation, re-extraction, queue drain, Start All restart, HOLDS_POSITION canonicalization, Stage 2 default activation, v2 work, `replit.md` edits

## Sign-off

Stage 2D is accepted.

Accepted result:

```text
Stage 1J tree=true: 50/100
Stage 2C tree=false: 55/100
Stage 2D tree=false + DOCUMENT_EVIDENCE fallback: 60/100

Net recovery from low point: +10
Net recovery from Stage 2C: +5
Fallback-driven recoveries: 8
Code-caused regressions: 0
Tests: 29/29 pass
Architect verdict: PASS on fallback implementation

Accepted caveat:

Stage 2D was validated through the direct in-process harness, not the production /api/vault/chat path.
The +5 may not transfer unchanged through ToolAgent, HTTP wrapper, ConversationStore writes, timeout/retry behavior, or response shaping.

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

Goal

Answer two questions before authorizing fallback hardening:

1. Does existing Stage 2D DOCUMENT_EVIDENCE fallback transfer to /api/vault/chat?
2. Why did fallback recover only 8 questions, and which remaining failures are realistically recoverable?

This stage is parity + audit.

Do not change fallback logic yet.

Do not tune prompts yet.

Do not broaden fallback triggers yet.

Part A — Production-path wiring, default off

Wire the existing Stage 2D DOCUMENT_EVIDENCE fallback into /api/vault/chat behind a feature flag.

Requirements:

feature flag default OFF
no fallback behavior when flag is absent/off
per-request override if feasible
environment override if feasible
no Start All restart
no extraction worker startup
no queue drain
no fallback logic change

Suggested names:

CF_DOCUMENT_EVIDENCE_FALLBACK=true
request payload: document_evidence_fallback=true

Use project naming conventions if different.

Required code-path audit before wiring

Read and report:

/api/vault/chat route
ToolAgent request entrypoint
QueryPipeline answer path
where Stage 2D direct harness invokes fallback
where no_data / insufficient-data responses are formed
where response metadata is shaped
where ConversationStore.add_message writes occur
whether Flask test_client can exercise the route without starting worker threads

Then wire the smallest possible hook.

Production behavior when flag is enabled

Use the existing Stage 2D fallback logic unchanged:

1. Run normal KG/query path first.
2. If normal path returns a TRUSTED graph answer, preserve it.
3. If normal path returns no_data / insufficient information for an attribute/spec/date/metric-style query, invoke existing DOCUMENT_EVIDENCE fallback.
4. If fallback finds evidence, return answer_source=DOCUMENT_EVIDENCE with chunk/document provenance.
5. If fallback finds no evidence, return GAP/no_data.

Do not override confident KG answers in this stage.

For cases like Q40 where KG gives a confident wrong scalar, record diagnostics only. Do not replace the answer.

Response metadata

Ensure the production response can expose:

answer_source:
  TRUSTED_GRAPH_FACT
  STAGING_GRAPH_FACT
  DOCUMENT_EVIDENCE
  GAP

document_evidence:
  document_id
  filename
  chunk_id
  quote or excerpt
  confidence / score if available

diagnostics:
  fallback_triggered
  fallback_reason
  kg_conflict_shadow if already implemented

Do not label DOCUMENT_EVIDENCE as TRUSTED graph evidence.

Tests

Add/update tests covering:

1. Feature flag absent/off → no fallback behavior.
2. Feature flag on + graph no_data + supporting chunk → DOCUMENT_EVIDENCE answer with provenance.
3. Feature flag on + TRUSTED graph fact exists → graph answer preserved, fallback not used.
4. Feature flag on + no supporting chunk → GAP/no_data.
5. answer_source survives response shaping.
6. fallback remains tenant-scoped.
7. no mutation of entities, relationships, ontology, documents, chunks, or extraction_requests.
8. ConversationStore writes, if unavoidable in route tests, are limited to conversation_messages and do not touch KG/ontology/extraction state.

If full HTTP tests require Start All restart, do not use them.

Use one of:

Flask test_client in-process
direct route handler invocation
local app construction without worker startup

Part B — HTTP parity validation

Attempt a safe HTTP-path replay against the clean Stage 1J vault:

vault_id = ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda
question set = test_questions/nexus_100q.json
tree_based_retrieval=false
DOCUMENT_EVIDENCE flag enabled
existing data only

Use the closest-to-production path available without restarting Start All.

Preferred:

Flask test_client or in-process route call

Not allowed:

live Start All restart
mode=fresh
delete/upload/extract
worker queue

Capture:

score
pass/fail IDs
no_match count
no_data count
which of the 8 Stage 2D recoveries transfer:
  Q14, Q32, Q34, Q41, Q51, Q58, Q84, Q96

which of the 5 Stage 2C tree-off recoveries remain recovered:
  Q15, Q36, Q40, Q68, Q100

questions behaving differently between direct and HTTP paths
answer_source distribution
DOCUMENT_EVIDENCE answer count
latency/runtime
artifact paths

If full 100Q HTTP replay is too slow or unsafe, run focused replay first:

8 Stage 2D recovered questions
5 Stage 2C recovered questions
Q40
10 representative remaining attribute failures

Then report whether a full 100Q replay is safe.

Part C — Failure audit, no hardening

Using Stage 2D artifacts and HTTP parity artifacts, classify remaining failures.

For each remaining failed question, classify into exactly one primary bucket:

A. fallback did not trigger but should have
B. fallback triggered but retrieved wrong chunks
C. fallback retrieved right chunks but extracted wrong answer
D. fallback extracted plausible answer but evaluator failed
E. confident KG answer blocked fallback
F. answer genuinely absent from chunks
G. graph-edge extraction issue, not fallback issue
H. aggregate/composite question not handled by fallback
I. HTTP/direct path mismatch
J. inconclusive

For the original 32 attribute/spec/date/metric failures, produce a compact table:

question_id
fact needed
chunk evidence exists? yes/no
fallback fired in direct harness? yes/no
fallback fired in HTTP path? yes/no
fallback answer if any
reason not recovered
predicted fix category
estimated impact if fixed

Do not implement fixes in this stage.

Recovery plan output

Based on the parity + audit, propose Stage 2E-2 hardening work.

For each proposed fix, include:

fix name
failure bucket targeted
question IDs targeted
expected score impact
risk
whether it needs code change
whether it needs fallback prompt change
whether it needs retrieval change
whether it needs ontology mutation
whether it needs re-extraction

Rank by expected score recovery.

Post-validation invariant check

Verify:

entities unchanged
relationships unchanged
documents unchanged
chunks unchanged
extraction_requests not drained
ontology.types unchanged
ontology.relations unchanged
latest cross-tenant timestamp unchanged

Conversation messages may be written if the HTTP route requires it. Report that separately.

Architect review

Run architect/code review.

Focus:

feature flag default-off behavior
tenant scoping
answer_source provenance
no graph-trust mislabeling
no confident KG override
no worker startup
no Start All restart
no extraction queue drain
no ontology or prompt mutation
no fallback hardening slipped in

If architect flags HIGH issues, fix before final report.

Findings doc

Create or update:

docs/findings/stage2e1_http_parity_and_fallback_audit_2026-05-12.md

Include:

Stage 2D accepted state
production-path wiring summary
feature flag behavior
tests
HTTP parity method
score / focused replay result
transferred recoveries
lost recoveries
answer_source distribution
direct-vs-HTTP differences
failure audit table
attribute-failure table
recommended Stage 2E-2 hardening plan
post-test invariant check

Do not do

Do not:

restart Start All
drain extraction_requests
re-extract any vault
run mode=fresh
mutate ontology
change extraction prompts
harden fallback logic yet
canonicalize HOLDS_ROLE / FORMERLY_HELD yet
repair worker queue
run Nexus fresh scoring
start Stage 2 default activation
touch v2
edit replit.md

Stop triggers

Stop and report if:

HTTP parity requires Start All restart
route construction starts worker threads
fallback cannot be feature-flagged default-off
fallback cannot be tenant-scoped
fallback cannot carry provenance
fallback would answer without evidence
fallback would override confident KG answers
tests fail
architect flags HIGH
validation mutates KG/ontology/extraction state

Final report

Report:

files changed
feature flag name and behavior
production-path hook location
tests run and results
architect review result
HTTP/focused parity result
full 100Q result if safely run
which Stage 2D recoveries transferred
which questions differ direct vs HTTP
DOCUMENT_EVIDENCE answer count
answer_source distribution
failure bucket table
Stage 2E-2 recommended fixes
post-test mutation check
remaining gap to 70/76
confirmation Start All was not restarted
confirmation extraction queue was not drained

Stop condition

Stop after Stage 2E-1 final report.

Wait for sign-off before fallback hardening, ontology mutation, prompt change, re-extraction, worker recovery, canonicalization fix, runtime restart, or Stage 2 default activation.

