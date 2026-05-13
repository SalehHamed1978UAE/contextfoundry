# Stage 2C — Score Recovery Isolation and Capability Restoration Plan

## Alignment

- **Module touched:** read-only score/capability diagnosis first; no production code changes yet
- **Product vs implementation:** product-quality recovery before Stage 2 implementation/default activation
- **Architecture-doc consistency:** preserves validated tenant-isolation, VerificationWorker, and Gardener fixes while investigating why Nexus score regressed from legacy ~76/100 to Stage 1J 50/100
- **Drift risk:** blindly restoring old behavior that improved score but reintroduces unsafe tenant/global behavior; mutating ontology or prompts before isolating retrieval-vs-extraction causes
- **Out of scope:** re-extraction, queue drain, Start All restart, ontology mutation, prompt changes, Stage 2 implementation, v2 work, `replit.md` edits

## Decision

Run a read-only score recovery isolation pass.

Do not mutate code yet.

Do not mutate ontology.

Do not re-extract any vault.

Do not drain `platform.extraction_requests`.

Do not restart Start All.

Do not undo IdentityResolver, VerificationWorker, or Gardener safety fixes.

## Accepted findings

Accept the latest "what did we lose" review:

```text
Almost nothing live was deleted.
The regression is caused by live behavior changes and unwired subsystems.

Accepted likely regression sources:

1. Ontology-constrained extraction narrowed attribute-bearing vocabulary.
2. Relation extractor emits names the validator drops, especially HOLDS_ROLE / FORMERLY_HELD vs HOLDS_POSITION.
3. CF_TREE_BASED_RETRIEVAL=true appears enabled despite prior evidence it costs ~10–11 points.
4. require_verification_for_promotion=False means verification verdicts are not gating promotion.
5. PrecedencePipeline / SymbolicOverrideEngine / FailureAnalyzer / TargetedExtractor / ImprovementLoop exist but are not wired into /api/vault/chat.
6. Chunk fallback does not reliably rescue attribute/spec/date/metric questions.

Also accepted:

Stage 1J clean vault scored 50/100.
Legacy 176a4fb2 scored ~76/100.
0/50 failures are solved by promoting the six orphan relation types.
32/50 failures are attribute/spec/date/metric facts.
14/50 failures are graph-edge precision/recall issues inside existing governed vocabulary.

Goal

Determine which recovery lever is highest value and safest.

Answer:

How much score can be recovered by retrieval-mode change alone?
How much requires extraction vocabulary restoration?
How much requires query/chunk fallback wiring?
Which old capabilities are present but unwired?
Which restorations are safe without undoing tenant isolation?

Step 1 — Current lever audit

Read only.

Report current state and code locations for:

CF_TREE_BASED_RETRIEVAL in start.sh and any request-level override
entity_extractor.py use_ontology_schema default
OntologyCentricPipeline prompt/ontology constraints
GardenerConfig.require_verification_for_promotion
relation extractor prompt/rules for HOLDS_ROLE / FORMERLY_HELD / HOLDS_POSITION
ontology.types coverage for DATE, BUDGET, MILESTONE, EVENT, SPECIFICATION, PARAMETER, METRIC, VALUE, CERTIFICATION
ontology.relations coverage for HAS_SPEC, MEETS_SPEC, HAS_VALUE, HAS_DATE, OCCURRED_ON, HAS_CERTIFICATION, HAS_METRIC
whether PrecedencePipeline is called by /api/vault/chat
whether SymbolicOverrideEngine is called by /api/vault/chat
whether CoherenceChecker is shadow-only or blocking
whether FailureAnalyzer / TargetedExtractor / ImprovementLoop / LearningOrchestrator are wired into production request flow

Do not change any of these yet.

Step 2 — Historical/correlation audit

Read only.

For each lever, report:

current value
when it changed if determinable from git/logs
what the old value likely was when 176a4fb2 scored ~76
whether it plausibly affects the 34 regressions
predicted score impact: low / medium / high
risk of restoring: low / medium / high

Special focus:

CF_TREE_BASED_RETRIEVAL=true
use_ontology_schema=True
HOLDS_ROLE / FORMERLY_HELD mismatch
missing attribute ontology vocabulary
unwired chunk fallback / precedence path

Step 3 — Safe question-only retrieval-mode test

If and only if it can be done without restart or mutation, run the Stage 1J question-only test with tree retrieval OFF.

Vault:

ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda

Requirements:

existing data only
no delete/upload/extract
no verification
no promotion
no extraction queue drain
no Start All restart
no DB mutation

If tree retrieval cannot be disabled per request/test-harness without changing start.sh or restarting services, stop and report. Do not edit start.sh.

Capture:

score
pass/fail IDs
no_match count
no_data count
questions recovered vs tree=true
questions lost vs tree=true
artifact paths
post-test mutation check

Step 4 — Legacy harness parity if safe

If safe and non-mutating, run the same thin question-only harness against:

176a4fb2-0bb4-4da3-9068-0e26268fca71

Run with the same retrieval setting(s) used for Stage 1J.

If legacy vault cannot be tested safely because its document parents are missing/orphaned, report that and do not force it.

Goal:

Confirm whether the old ~76/100 is reproduced under the same harness/settings.

Step 5 — Recovery plan

Produce a ranked restoration plan.

Each candidate fix should include:

what changes
why it helps
which failure bucket it targets
estimated score impact
risk
test needed
whether it preserves tenant isolation
whether it requires ontology mutation
whether it requires prompt change
whether it requires service restart

Candidate levers to evaluate:

A. Disable tree retrieval by default or gate it narrowly

Question:

Does tree=false recover points on Stage 1J?

B. Restore attribute-fact coverage

Options to evaluate:

add governed attribute types/relations:
  DATE
  BUDGET
  MILESTONE
  EVENT
  SPECIFICATION
  PARAMETER
  METRIC
  VALUE
  CERTIFICATION
  HAS_SPEC
  MEETS_SPEC
  HAS_VALUE
  HAS_DATE
  OCCURRED_ON
  HAS_CERTIFICATION
  HAS_METRIC

or add a DOCUMENT_EVIDENCE fallback for attribute questions
or hybrid: selective ontology expansion + DOCUMENT_EVIDENCE fallback

C. Fix relation prompt/validator mismatch

Evaluate:

HOLDS_ROLE / FORMERLY_HELD should map to HOLDS_POSITION
or prompt should emit HOLDS_POSITION only
or canonicalizer should map them before staging/promotion

D. Wire chunk fallback / ContextBundle evidence classes

Evaluate:

TRUSTED_GRAPH_FACT
STAGING_GRAPH_FACT
DOCUMENT_EVIDENCE
GAP

Question:

Can chunk evidence answer attribute facts when KG lacks them, without pretending they are TRUSTED graph facts?

E. Wire only the useful dormant systems

Evaluate whether any of these directly addresses the 34 regressions:

PrecedencePipeline
SymbolicOverrideEngine
CoherenceChecker blocking mode
FailureAnalyzer
TargetedExtractor
ImprovementLoop
LearningOrchestrator
multi-hop role traversal

Do not recommend wiring all of them blindly.

Step 6 — Stage 2 readiness update

Update the readiness verdict with separate categories:

pipeline safety readiness
answer-quality readiness
Stage 2 design readiness
Stage 2 implementation readiness
Stage 2 default activation readiness

Do not call Stage 2 implementation ready if answer-quality recovery remains below an acceptable threshold.

Findings doc

Create:

docs/findings/stage2c_score_recovery_isolation_2026-05-12.md

Include:

executive summary
current lever audit
historical/correlation audit
retrieval-mode test result if run
legacy harness parity result if run
ranked restoration plan
expected score impact
Stage 2 readiness update

Do not do

Do not:

restart Start All
drain extraction_requests
re-extract any vault
run mode=fresh
mutate DB facts
mutate ontology
change prompts
change production code
edit start.sh
start Stage 2 implementation
touch v2
edit replit.md

Stop triggers

Stop and report if:

tree retrieval cannot be disabled safely per run
legacy parity test would mutate or require re-extraction
a proposed fix would undo tenant isolation
a proposed fix would reintroduce global/cross-tenant behavior
a proposed fix requires ontology mutation or prompt change
a dormant subsystem wiring requires broad architecture choice

Final report

Report:

which capabilities were disabled/narrowed/unwired
retrieval-mode score delta if tested
legacy parity result if tested
ranked recovery plan
top 3 recommended fixes
what should not be restored
what must remain protected from prior fixes
whether Stage 2 remains blocked by answer quality
findings doc path

Stop condition

Stop after the Stage 2C score recovery isolation report.

Wait for sign-off before any restoration, config change, ontology mutation, prompt change, re-extraction, worker recovery, or Stage 2 implementation.