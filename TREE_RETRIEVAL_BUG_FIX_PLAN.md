# Tree Retrieval Not Working - Root Cause & Fix Plan

**Date**: 2026-02-08
**Severity**: HIGH - Feature completely non-functional

---

## You Were Right!

The tree retrieval toggle in the UI doesn't actually enable tree retrieval. Here's what's happening:

### Current Broken Flow

1. **UI** → User selects "Tree Retrieval: ON" ✅
2. **Frontend** → Sends `tree_based_retrieval: true` to backend ✅
3. **Backend** → Saves to `test_runs.tree_based_retrieval` column ✅
4. **Test Executor** → Reads `CF_TREE_BASED_RETRIEVAL` env var → finds **"false"** ❌
5. **Brain API** → Also reads `CF_TREE_BASED_RETRIEVAL` env var → uses **flat retrieval** ❌
6. **Results JSON** → Shows `"tree_based_retrieval": false` ❌

**Root cause**: Tree retrieval is controlled by environment variable `CF_TREE_BASED_RETRIEVAL` that:
- Gets set at server startup
- NEVER gets updated during test runtime
- Is not passed as a parameter to Brain API

---

## Code Evidence

### Environment Variable Definition
**File**: `src/context_foundry/config/feature_flags.py:22`
```python
TREE_BASED_RETRIEVAL_ENABLED = os.getenv("CF_TREE_BASED_RETRIEVAL", "false").lower() == "true"
```

### Test Executor Reads Env Var (doesn't set it!)
**File**: `src/test_runner/test_executor.py:296`
```python
"config": {
    "tree_based_retrieval": os.environ.get("CF_TREE_BASED_RETRIEVAL", "false").lower() == "true"
}
```

### Brain API Call (no parameter passed!)
**File**: `src/test_runner/vault_manager.py:396`
```python
response = self.session.post(
    f"{self.api}/vault/chat",
    json={"query": question, "vault_id": vault_id},  # ❌ No tree flag!
    timeout=timeout
)
```

---

## Why "Restart Server" Was Required Before

You remembered correctly! Previously:
1. Set `CF_TREE_BASED_RETRIEVAL=true` in environment
2. **Restart the entire web server** to pick up new env var
3. Run test
4. **Restart server again** with `CF_TREE_BASED_RETRIEVAL=false` to turn it off

This is why you asked: **"How can I start a test, restart the server, and expect the test to continue?"**

Answer: **You can't!** The current architecture is broken for per-test tree retrieval control.

---

## Solution Options

### Option 1: Pass Tree Flag as Request Parameter (RECOMMENDED)

**Advantages:**
- No server restart needed
- Per-request control
- Clean architecture

**Changes required:**

1. **Modify vault_manager.py:396** - Add tree flag to request:
```python
response = self.session.post(
    f"{self.api}/vault/chat",
    json={
        "query": question,
        "vault_id": vault_id,
        "tree_based_retrieval": tree_flag  # ✅ Add this!
    },
    timeout=timeout
)
```

2. **Modify web_app.py:4289** - Read tree flag from request:
```python
data = request.get_json()
tree_flag = data.get('tree_based_retrieval', False)  # ✅ Add this!
```

3. **Pass tree flag through the entire agent chain:**
   - `ToolAgent.query(... tree_based_retrieval=tree_flag)`
   - `retrieval_router.retrieve(... tree_based_retrieval=tree_flag)`
   - Override environment variable when parameter is present

4. **Update test_executor.py:67** - Pass tree flag from database:
```python
def run_test(
    self,
    vault_id: str,
    tree_based_retrieval: bool = False,  # ✅ Add this!
    ...
):
    # Pass to vault_manager.query()
```

### Option 2: Set Environment Variable Per Test (HACKY)

**Disadvantages:**
- Environment variables are process-wide, not thread-safe
- Won't work if Brain API is separate process
- Race conditions if multiple tests run
- Generally bad practice

**Don't do this!**

---

## Implementation Plan

### Phase 1: Add Request Parameter Support

**Files to modify:**

1. `src/test_runner/vault_manager.py`
   - Add `tree_based_retrieval` parameter to `query()` method
   - Pass in request JSON to Brain API

2. `web_app.py` (`/api/vault/chat` endpoint)
   - Read `tree_based_retrieval` from request data
   - Pass to ToolAgent

3. `src/context_foundry/agents/tool_agent.py`
   - Add `tree_based_retrieval` parameter to `query()` method
   - Pass to retrieval router

4. `src/context_foundry/agents/retrieval_router.py`
   - Add `tree_based_retrieval` parameter
   - Use parameter instead of environment variable when provided

5. `src/test_runner/test_executor.py`
   - Read `tree_based_retrieval` from database for test run
   - Pass to vault_manager.query()

6. `src/test_runner/runner.py`
   - Pass `tree_based_retrieval` from CLI args to test executor

### Phase 2: Update Test Runner Integration

1. Ensure test run database column is populated correctly (already done via migration 025)
2. Read flag from database and pass through execution chain
3. Verify flag appears correctly in results JSON

### Phase 3: Testing

1. Run test with tree ON → verify `"tree_based_retrieval": true` in JSON
2. Run test with tree OFF → verify `"tree_based_retrieval": false` in JSON
3. Compare accuracy results

---

## Acceptance Criteria

- [ ] User can toggle tree retrieval ON in UI
- [ ] Test runs with tree retrieval actually ENABLED in Brain queries
- [ ] Results JSON shows `"tree_based_retrieval": true`
- [ ] No server restart required
- [ ] Multiple tests can run with different tree settings

---

## Current Workaround (Until Fixed)

**To actually test tree retrieval:**

1. Stop the web server
2. Set environment variable: `export CF_TREE_BASED_RETRIEVAL=true`
3. Start web server
4. Run test (tree will be ON regardless of UI setting)
5. Stop server
6. Unset variable: `export CF_TREE_BASED_RETRIEVAL=false`
7. Start server again

**This is exactly what you remembered - and it's broken architecture!**

---

## Estimated Effort

- **Quick fix (Option 1)**: 2-3 hours of focused work
- **Testing & validation**: 1 hour
- **Total**: Half day of work

Let me know if you want me to implement Option 1 now!
