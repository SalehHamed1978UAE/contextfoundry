# v2 (FactEvaluator) — Architecture Lessons Worth Preserving

**Date:** 2026-05-09
**Audience:** future Context Foundry contributors
**Purpose:** internal continuity. Whatever happens to v2 after Task 4's decision, these patterns cost real engineering time to discover and validate. They are reusable across whatever we build next.

---

## 1. Postgres-backed LLM cache (`llm_cache` table)

**Problem solved:** deterministic-but-expensive LLM calls during iteration loops, benchmark runs, and replays.

**Pattern:**
- Single table `llm_cache(cache_key TEXT PRIMARY KEY, model TEXT, response JSONB, created_at TIMESTAMP)`.
- Cache key = `sha256(model || system_prompt || user_prompt || schema_class_name)`.
- Auto-created on first use (idempotent CREATE TABLE IF NOT EXISTS).
- Reads use a single PK lookup; writes use `ON CONFLICT DO NOTHING` to make concurrent writers safe.
- Postgres-only — no Redis, no separate cache infra. Lives next to the data.

**Why it works:** `temperature=0` makes the LLM a pure function of (model, prompt, schema). Identical inputs produce identical outputs, so a content-addressed cache is sound. Postgres's MVCC means concurrent benchmark runs don't corrupt entries.

**Known gap (now documented):** the cache key includes the rendered prompt text but not an explicit `prompt_template_version`, `schema_field_version`, or `reasoning_engine_version` tag. When prompt text changes, the hash changes and entries are stranded — fine. But when prompt text is unchanged while downstream parsing/semantics change, cached responses get reused under new contracts. This bit us on iter-4: we cleared it manually before Task 2. **Reusable rule:** any LLM cache should include a coarse "logical version" tag in the key, not just content hash.

**Required code change (not yet applied — only contamination cleared on 2026-05-09):**

Edit `src/context_foundry/inference/llm/client.py` (around L46–57, the `_cache_key` builder) so the SHA-256 input includes three explicit version tags in addition to the existing `(model, system, user, schema_class_name)`:

```python
PROMPT_TEMPLATE_VERSION = "v2"      # bump when any prompt .md changes
SCHEMA_FIELD_VERSION    = "v2"      # bump when any pydantic schema changes
REASONING_ENGINE_VERSION = "v2"     # bump when verdict logic / planner contract changes

def _cache_key(model, system, user, schema_cls):
    h = hashlib.sha256()
    for part in (
        PROMPT_TEMPLATE_VERSION,
        SCHEMA_FIELD_VERSION,
        REASONING_ENGINE_VERSION,
        model,
        system,
        user,
        schema_cls.__name__ if schema_cls else "_",
    ):
        h.update(part.encode("utf-8") + b"\x00")
    return h.hexdigest()
```

The three `*_VERSION` constants are owned by the engine maintainer; bumping any one invalidates all entries written under the prior value (no migration, no purge — Postgres just stops finding them and the new keys repopulate). Equivalent: a `version_tag` column on `llm_cache` with the constants written at insert time and a `WHERE version_tag = current_tag` filter at lookup. Either is fine; keying is simpler.

Why this is "code change required" not "documentation only": until this lands, every prompt-text-stable / semantics-changed deploy silently reuses stale entries. Manually clearing the table is not a substitute — it requires remembering to do it on every deploy, which is exactly the failure mode that bit us on iter-4. The version tags make the invariant enforcable from inside the cache module.

**File:** `src/context_foundry/inference/llm/client.py`

---

## 2. Structlog-based hierarchical tracer with span counters

**Problem solved:** observability across a multi-stage async pipeline (planner → gatherer → adversary → prover → meta → synthesizer) where you need to know *what each stage produced and how expensive each stage was* without inserting logging at every site.

**Pattern:**
- `tracer.trace()` context manager opens a per-evaluation context with a generated `trace_id`.
- `tracer.span(name, **attrs)` opens a nested span; counters bumped within the span absorb to it.
- `tracer.bump(counter_name)` increments the active span's counter (used by `LLMClient` for `llm_call_count`/`llm_cache_hit_count` and by `GraphTools` for `db_query_count`).
- `tracer.event(name, **payload)` emits structured events that aggregate up.
- On span exit, the counters roll up to the parent span; on `trace()` exit, the root span emits a final `evaluate_summary` event with all rolled counters.
- Output: structlog JSON, one event per line. Trivial to grep/jq.

**Why it works:** the bump-and-roll pattern means primitives don't need to know which stage they're in — the tracer figures it out from the active span ContextVar. Stages don't have to thread call-counters through their signatures.

**Known gap (now diagnosed):** when pytest's log-cli capture rebuilds the handler chain between tests, the structlog `cache_logger_on_first_use` setting can snapshot a stale handler. Fix: an autouse fixture force-resets `_trace_module._configured = False` before each test so structlog rebuilds against the current handler chain. **Reusable rule:** anything that caches a logger reference must be re-initializable from test fixtures.

**File:** `src/context_foundry/inference/observability/trace.py`

---

## 3. `Condition.kind` discriminator (typed presupposition handling)

**Problem solved:** a planner emits a heterogeneous list of conditions a fact must satisfy — some are graph facts (recursively evaluable), some are type checks (cheap DB lookup), some are identity checks (name match), some are domain custom rules (human review only). A naive design tries to evaluate all of them through one path and either (a) recursively explodes when a type-check spawns a sub-evaluation or (b) silently drops the kinds it doesn't know how to handle.

**Pattern:**
- `Condition.kind: Literal["graph_fact", "type_check", "identity_check", "custom"]`.
- `Condition` carries the union of fields all kinds need (`fact`, `entity_id`, `expected_entity_type`, `expected_name`, `description`).
- The orchestrator partitions presuppositions by `kind` and dispatches each to a kind-specific handler:
  - `graph_fact` → recursive `evaluate(c.fact, guard.child(...))`.
  - `type_check` → direct DB lookup, returns synthetic Verdict.
  - `identity_check` → direct DB lookup, returns synthetic Verdict.
  - `custom` → surfaced in the plan; never blocks the verdict.
- Every kind produces a Verdict the synthesizer can inspect uniformly.

**Why it works:** the discriminator is the contract. Adding a new kind requires (a) adding the literal, (b) adding the dispatch branch, (c) adding the handler. Forgetting any of these fails type-checking, not silently. The "custom never blocks" carve-out lets the planner emit aspirational/exploratory conditions without breaking determinism.

**Reusable rule:** when a producer emits a list of heterogeneous items for a single consumer, prefer a single tagged-union type with a discriminator over multiple parallel lists or overloaded fields. Pydantic + `Literal` makes this enforceable at the schema layer.

**File:** `src/context_foundry/inference/contracts.py`, dispatched in `engine.py`.

---

## 4. Fail-closed validator pattern (PlanValidationError + retry)

**Problem solved:** an LLM is asked to produce structured output that must reference real schema types (entity types, relationship types). It will, with non-trivial frequency, hallucinate types that don't exist. Naive code accepts the output and corrupts downstream stages (the engine evaluates a `LIVES_AT` relationship that doesn't exist in the schema; the gatherer searches for it; the synthesizer reasons over absence as evidence of contradiction).

**Pattern:**
- After receiving structured LLM output, run a deterministic validator against the actual schema (in our case: `entity_types` set ∪ `relationship_types` set, normalized to UPPER_SNAKE_CASE).
- If validation fails, raise `PlanValidationError(message)` with a precise reason.
- The caller catches `PlanValidationError`, decides whether to retry (with the validator's reason fed back into the next prompt as a corrective hint) or terminate.
- Cap retries (we use 3). On exhaustion, return a terminal Verdict with `status=UNDERSPECIFIED` and the validation failure recorded — **never** a guessed verdict.
- The verdict tracer logs `plan_validation_failed` so failures are visible, not silent.

**Why it works:** the failure mode is loud and locatable. The validator is the single source of truth for "what shapes are legal" — when the schema changes, the validator changes, and stale prompts surface as validation failures rather than as confident-wrong answers. The retry-with-feedback loop turns most validation errors into recoverable hiccups while still bounding the work.

**Reusable rule:** every LLM that produces structured output that's then *acted on* needs a deterministic validator between it and the rest of the system. The validator is more important than the prompt — the prompt can drift, the validator is the contract.

**File:** `src/context_foundry/inference/planner.py` (`PlanValidationError`, `EvaluationPlanner.plan`).

---

## Honourable mention: per-fact recursion guard with cycle detection

`RecursionGuard` carries the `fact_key` chain of ancestors and a depth counter. On entry: if `fact in chain`, return synthetic UNDERSPECIFIED with reason `"recursion cycle detected"`. If `depth >= max_depth`, return synthetic UNDERSPECIFIED with `terminated_by_ceiling=True`. Every recursive call uses `guard.child(fact)`. The pattern is small but load-bearing — without it, a graph cycle in presuppositions becomes an unbounded async storm. Worth lifting into any future engine that recurses over a graph.

**File:** `src/context_foundry/inference/recursion.py`

---

## What we're explicitly NOT preserving

- The MetaEvaluator's hypothesis-invention loop (it hallucinates falsifiers untethered from the original plan; redesign needed).
- The AdversarialChallenger's runaway-rounds termination (the `max_rounds` ceiling fires before the loop converges; the rebuttal-iteration termination criterion needs rethinking).
- The fact-construction pipeline. v2 evaluates `Fact(s, r, t)`; we never built a clean way to *get* such a fact from a NL query. Whatever evaluates facts in the future should either pair with a fact-extraction layer or accept facts as input only.

---

*This document is internal continuity, not external comms. The point is to make the next iteration cheaper than the last.*
