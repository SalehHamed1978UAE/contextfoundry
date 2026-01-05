"""
Tests for RLM Sandbox execution environment.

Tests secure code execution, restriction enforcement,
timeout handling, and output capture.
"""

import pytest
import os
import sys
from unittest.mock import MagicMock
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_foundry.rlm.sandbox import (
    REPLSandbox,
    SandboxSecurityError,
    generate_retry_hint,
    SAFE_BUILTINS,
    RESTRICTED_PATTERNS,
)
from src.context_foundry.rlm.schemas import StaleEntityError


class MockMemoryAPI:
    """Mock Memory API for testing."""
    def __init__(self):
        self._accessed_entity_ids = []
        self._accessed_relationship_ids = []
        self._accessed_chunk_ids = []
    
    def get_accessed_entity_ids(self):
        return self._accessed_entity_ids
    
    def get_accessed_relationship_ids(self):
        return self._accessed_relationship_ids
    
    def get_accessed_chunk_ids(self):
        return self._accessed_chunk_ids
    
    def clear_access_tracking(self):
        self._accessed_entity_ids = []
        self._accessed_relationship_ids = []
        self._accessed_chunk_ids = []
    
    def find_entities(self, **kwargs):
        self._accessed_entity_ids.append("entity-1")
        return [{"id": "entity-1", "name": "Test Entity"}]


class TestSandboxSecurity:
    """Test security restrictions."""
    
    def test_import_rejected(self):
        """Import statements should be rejected."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("import os")
        assert result.success == False
        assert "Restricted pattern" in result.error
    
    def test_eval_rejected(self):
        """eval() should be rejected."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("x = eval('1+1')")
        assert result.success == False
        assert "Restricted pattern" in result.error
    
    def test_exec_rejected(self):
        """exec() should be rejected."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("exec('x=1')")
        assert result.success == False
        assert "Restricted pattern" in result.error
    
    def test_open_rejected(self):
        """File operations should be rejected."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("f = open('/etc/passwd')")
        assert result.success == False
        assert "Restricted pattern" in result.error
    
    def test_dunder_access_rejected(self):
        """Double underscore attribute access should be restricted."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("x = {}.__class__")
        assert result.success == False
        assert "Restricted pattern" in result.error
    
    def test_subprocess_rejected(self):
        """subprocess should be rejected."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("import subprocess")
        assert result.success == False
        assert "Restricted pattern" in result.error
    
    def test_session_access_rejected(self):
        """Access to ._session should be rejected (security: prevents raw SQL access)."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("session = semantic._session")
        assert result.success == False
        assert "Restricted pattern" in result.error
    
    def test_tenant_id_access_rejected(self):
        """Access to ._tenant_id should be rejected (security: prevents tenant spoofing)."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("tenant = semantic._tenant_id")
        assert result.success == False
        assert "Restricted pattern" in result.error
    
    def test_session_via_getattr_rejected(self):
        """Access to _session via getattr should be rejected."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("session = getattr(semantic, '_session')")
        assert result.success == False
        assert "Restricted pattern" in result.error


class TestSandboxExecution:
    """Test code execution."""
    
    def test_simple_code_executes(self):
        """Simple code should execute successfully."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("x = 1 + 1")
        assert result.success == True
        assert result.error is None
    
    def test_print_captured(self):
        """Print statements should be captured."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("print('Hello, World!')")
        assert result.success == True
        assert "Hello, World!" in result.output
    
    def test_multiple_prints_captured(self):
        """Multiple print statements should all be captured."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("""
print('Line 1')
print('Line 2')
print('Line 3')
""")
        assert result.success == True
        assert "Line 1" in result.output
        assert "Line 2" in result.output
        assert "Line 3" in result.output
    
    def test_safe_builtins_available(self):
        """Safe builtins should be accessible."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("""
numbers = [1, 2, 3, 4, 5]
print(f"Sum: {sum(numbers)}")
print(f"Max: {max(numbers)}")
print(f"Len: {len(numbers)}")
""")
        assert result.success == True
        assert "Sum: 15" in result.output
        assert "Max: 5" in result.output
        assert "Len: 5" in result.output
    
    def test_list_operations(self):
        """List operations should work."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("""
items = list(range(5))
filtered = [x for x in items if x > 2]
print(f"Filtered: {filtered}")
""")
        assert result.success == True
        assert "Filtered: [3, 4]" in result.output
    
    def test_dict_operations(self):
        """Dict operations should work."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("""
data = {"a": 1, "b": 2}
data["c"] = 3
print(f"Keys: {sorted(data.keys())}")
""")
        assert result.success == True
        assert "Keys: ['a', 'b', 'c']" in result.output


class TestMemoryAPIAccess:
    """Test Memory API access from sandbox."""
    
    def test_semantic_api_accessible(self):
        """Semantic API should be accessible as 'semantic'."""
        mock_semantic = MockMemoryAPI()
        sandbox = REPLSandbox(
            memory_apis={"semantic": mock_semantic}
        )
        result = sandbox.execute("""
entities = semantic.find_entities()
print(f"Found {len(entities)} entities")
""")
        assert result.success == True
        assert "Found 1 entities" in result.output
    
    def test_entity_discovery_tracked(self):
        """Entity discovery should be tracked."""
        mock_semantic = MockMemoryAPI()
        sandbox = REPLSandbox(
            memory_apis={"semantic": mock_semantic}
        )
        result = sandbox.execute("entities = semantic.find_entities()")
        assert "entity-1" in result.new_entities_discovered
    
    def test_answer_variable_available(self):
        """answer variable should be available for storing results."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("answer = 'The result is 42'")
        assert result.success == True
        assert sandbox.get_variable("answer") == "The result is 42"
    
    def test_evidence_list_available(self):
        """evidence list should be available."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("""
evidence.append("Source: document.pdf")
evidence.append("Page: 5")
""")
        assert result.success == True
        evidence = sandbox.get_variable("evidence")
        assert len(evidence) == 2


class TestSandboxReset:
    """Test sandbox reset functionality."""
    
    def test_reset_clears_variables(self):
        """Reset should clear local variables."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        sandbox.execute("my_var = 'test'")
        assert sandbox.get_variable("my_var") is not None
        
        sandbox.reset()
        assert sandbox.locals_namespace == {}
    
    def test_reset_clears_output_buffer(self):
        """Reset should clear output buffer."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        sandbox.execute("print('test')")
        assert len(sandbox.output_buffer) > 0
        
        sandbox.reset()
        assert sandbox.output_buffer == []
    
    def test_reset_clears_discovery_tracking(self):
        """Reset should clear discovery tracking."""
        mock_semantic = MockMemoryAPI()
        sandbox = REPLSandbox(
            memory_apis={"semantic": mock_semantic}
        )
        sandbox.execute("entities = semantic.find_entities()")
        
        sandbox.reset()
        assert sandbox._discovered_entities == []


class TestErrorHandling:
    """Test error handling and retry hints."""
    
    def test_syntax_error_reported(self):
        """Syntax errors should be reported."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("if True print('x')")
        assert result.success == False
        assert "Syntax error" in result.error
    
    def test_runtime_error_reported(self):
        """Runtime errors should be reported."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("x = 1 / 0")
        assert result.success == False
        assert "ZeroDivisionError" in result.error
    
    def test_attribute_error_gets_hint(self):
        """AttributeError should get a helpful hint."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("""
data = {"name": "test"}
print(data.full_name)
""")
        assert result.success == False
        assert "AttributeError" in result.error


class TestRetryHintGenerator:
    """Test retry hint generation."""
    
    def test_attribute_error_hint(self):
        """AttributeError should generate helpful hint."""
        error = AttributeError("'EntitySummary' has no attribute 'full_name'")
        hint = generate_retry_hint(error, "entity.full_name")
        assert hint is not None
        assert "EntitySummary" in hint
    
    def test_key_error_hint(self):
        """KeyError should suggest .get()."""
        error = KeyError("missing_key")
        hint = generate_retry_hint(error, "data['missing_key']")
        assert hint is not None
        assert ".get()" in hint
    
    def test_index_error_hint(self):
        """IndexError should suggest length check."""
        error = IndexError("list index out of range")
        hint = generate_retry_hint(error, "items[10]")
        assert hint is not None
        assert "length" in hint.lower()
    
    def test_none_type_error_hint(self):
        """NoneType errors should explain None access."""
        error = TypeError("'NoneType' object is not subscriptable")
        hint = generate_retry_hint(error, "result['key']")
        assert hint is not None
        assert "None" in hint
    
    def test_stale_entity_error_hint(self):
        """StaleEntityError should suggest re-search."""
        error = StaleEntityError("entity-123")
        hint = generate_retry_hint(error, "entity.name")
        assert hint is not None
        assert "archived" in hint.lower() or "search" in hint.lower()


class TestExecutionTime:
    """Test execution time tracking."""
    
    def test_execution_time_recorded(self):
        """Execution time should be recorded."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("x = sum(range(1000))")
        assert result.execution_time_ms >= 0
    
    def test_fast_code_has_low_time(self):
        """Fast code should have low execution time."""
        sandbox = REPLSandbox(
            memory_apis={"semantic": MockMemoryAPI()}
        )
        result = sandbox.execute("x = 1")
        assert result.execution_time_ms < 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
