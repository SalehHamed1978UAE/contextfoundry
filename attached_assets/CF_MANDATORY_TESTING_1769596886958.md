# MANDATORY: Run Integration Tests After Every Change

## The Rule

**EVERY code change MUST pass integration tests before being considered complete.**

No exceptions. No "I'll test it later." No "It should work."

---

## How to Run

```bash
# After ANY code change:
python cf_integration_tests.py --all

# Quick smoke test (minimum):
python cf_integration_tests.py --quick

# Specific test suite:
python cf_integration_tests.py --test vault
python cf_integration_tests.py --test document
python cf_integration_tests.py --test extraction
python cf_integration_tests.py --test ontology
python cf_integration_tests.py --test corpus
python cf_integration_tests.py --test supplies_to
```

---

## Exit Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | All tests passed | OK to deploy |
| 1 | Tests failed | **DO NOT DEPLOY - FIX FIRST** |

---

## What Gets Tested

| Test Suite | What It Verifies |
|------------|------------------|
| `smoke` | Services import, DB connection |
| `vault` | Create, list, access, delete vault |
| `document` | Upload (with correct params), list, get |
| `extraction` | Queue, status check, completion |
| `ontology` | Candidate storage (UUID handling) |
| `corpus` | Config has root_path, paths exist |
| `supplies_to` | Pattern extraction works |

---

## When to Run

| Situation | Command |
|-----------|---------|
| Any code change | `python cf_integration_tests.py --all` |
| Before PR/merge | `python cf_integration_tests.py --all` |
| Quick sanity check | `python cf_integration_tests.py --quick` |
| Changed vault code | `python cf_integration_tests.py --test vault` |
| Changed upload code | `python cf_integration_tests.py --test document` |
| Changed extraction | `python cf_integration_tests.py --test extraction` |
| Changed ontology | `python cf_integration_tests.py --test ontology` |

---

## If Tests Fail

1. **READ THE ERROR MESSAGE** - It tells you exactly what's wrong
2. **FIX THE ROOT CAUSE** - Not a band-aid
3. **RUN TESTS AGAIN** - Until they pass
4. **THEN** deploy

---

## Adding New Tests

When you add a new feature, add a test for it:

```python
def test_my_new_feature():
    """Test description."""
    print("\n🆕 MY NEW FEATURE")
    print("-" * 40)

    try:
        # Test the feature
        result = my_new_function()
        if result == expected:
            results.add_pass("my_feature", "Works correctly")
        else:
            results.add_fail("my_feature", f"Expected {expected}, got {result}")
    except Exception as e:
        results.add_fail("my_feature", str(e))
```

---

## The Point

We've had these failures because nothing was tested:
- `content` vs `file_content` - would have been caught
- `create_tenant()` vs `create_vault_for_user()` - would have been caught
- `root_path` not saved - would have been caught
- Delete deadlock - would have been caught
- SUPPLIES_TO UUID error - would have been caught

**Run the tests. Every time. No exceptions.**

---

## Template for Task Completion

When Replit completes ANY task, the response should include:

```
## Task Complete

[Description of what was done]

## Integration Test Results

$ python cf_integration_tests.py --all

[Paste test output here]

✅ All tests passed
```

If tests fail, the task is NOT complete.
