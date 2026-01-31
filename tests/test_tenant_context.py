"""
Tests for tenant context management utilities.
"""
import pytest
from uuid import uuid4
from unittest.mock import Mock, MagicMock, patch
from sqlalchemy import text

from src.context_foundry.shared.tenant_context import (
    tenant_session,
    require_tenant,
    ensure_tenant_context,
    TenantContextError,
)


class TestTenantSession:
    """Tests for tenant_session context manager."""
    
    def test_tenant_session_sets_context(self):
        """Verify tenant context is set when entering context manager."""
        mock_session = Mock()
        tenant_id = str(uuid4())
        
        with tenant_session(mock_session, tenant_id):
            pass
        
        calls = mock_session.execute.call_args_list
        assert len(calls) >= 1
        first_call = calls[0]
        assert tenant_id in str(first_call)
    
    def test_tenant_session_rejects_none(self):
        """Verify None tenant_id raises error."""
        mock_session = Mock()
        
        with pytest.raises(TenantContextError) as exc_info:
            with tenant_session(mock_session, None):
                pass
        
        assert "tenant_id is required" in str(exc_info.value)
    
    def test_tenant_session_rejects_empty_string(self):
        """Verify empty string tenant_id raises error."""
        mock_session = Mock()
        
        with pytest.raises(TenantContextError) as exc_info:
            with tenant_session(mock_session, ""):
                pass
        
        assert "tenant_id is required" in str(exc_info.value)
    
    def test_tenant_session_rejects_invalid_uuid(self):
        """Verify invalid UUID format raises error."""
        mock_session = Mock()
        
        with pytest.raises(TenantContextError) as exc_info:
            with tenant_session(mock_session, "not-a-uuid"):
                pass
        
        assert "Invalid tenant_id format" in str(exc_info.value)
    
    def test_tenant_session_reasserts_after_exception(self):
        """Verify tenant context is re-asserted after exception and rollback."""
        mock_session = Mock()
        tenant_id = str(uuid4())
        
        try:
            with tenant_session(mock_session, tenant_id):
                raise ValueError("test error")
        except ValueError:
            pass
        
        mock_session.rollback.assert_called_once()
        calls = mock_session.execute.call_args_list
        assert len(calls) >= 2
    
    def test_tenant_session_reasserts_in_finally(self):
        """Verify tenant context is re-asserted in finally block."""
        mock_session = Mock()
        tenant_id = str(uuid4())
        
        with tenant_session(mock_session, tenant_id):
            pass
        
        calls = mock_session.execute.call_args_list
        assert len(calls) >= 2


class TestRequireTenantDecorator:
    """Tests for require_tenant decorator."""
    
    def test_require_tenant_sets_context(self):
        """Verify decorator sets tenant context before method execution."""
        mock_session = Mock()
        tenant_id = str(uuid4())
        
        class FakeAgent:
            def __init__(self, session, tid):
                self.session = session
                self.tenant_id = tid
            
            @require_tenant
            def do_thing(self):
                return "done"
        
        agent = FakeAgent(mock_session, tenant_id)
        result = agent.do_thing()
        
        assert result == "done"
        mock_session.execute.assert_called()
    
    def test_require_tenant_raises_without_tenant_id(self):
        """Verify decorator raises when tenant_id is None."""
        mock_session = Mock()
        
        class FakeAgent:
            def __init__(self, session):
                self.session = session
                self.tenant_id = None
            
            @require_tenant
            def do_thing(self):
                return "done"
        
        agent = FakeAgent(mock_session)
        
        with pytest.raises(TenantContextError) as exc_info:
            agent.do_thing()
        
        assert "requires tenant_id" in str(exc_info.value)
    
    def test_require_tenant_raises_without_tenant_attr(self):
        """Verify decorator raises when tenant_id attribute is missing."""
        mock_session = Mock()
        
        class FakeAgent:
            def __init__(self, session):
                self.session = session
            
            @require_tenant
            def do_thing(self):
                return "done"
        
        agent = FakeAgent(mock_session)
        
        with pytest.raises(TenantContextError):
            agent.do_thing()
    
    def test_require_tenant_rejects_invalid_uuid(self):
        """Verify decorator rejects invalid UUID format."""
        mock_session = Mock()
        
        class FakeAgent:
            def __init__(self, session, tid):
                self.session = session
                self.tenant_id = tid
            
            @require_tenant
            def do_thing(self):
                return "done"
        
        agent = FakeAgent(mock_session, "invalid-uuid")
        
        with pytest.raises(TenantContextError) as exc_info:
            agent.do_thing()
        
        assert "Invalid tenant_id format" in str(exc_info.value)
    
    def test_require_tenant_preserves_method_name(self):
        """Verify decorator preserves original method name."""
        class FakeAgent:
            def __init__(self):
                self.session = Mock()
                self.tenant_id = str(uuid4())
            
            @require_tenant
            def my_method(self):
                return "done"
        
        agent = FakeAgent()
        assert agent.my_method.__name__ == "my_method"


class TestEnsureTenantContext:
    """Tests for ensure_tenant_context function."""
    
    def test_ensure_tenant_context_sets_context(self):
        """Verify function sets tenant context."""
        mock_session = Mock()
        tenant_id = str(uuid4())
        
        ensure_tenant_context(mock_session, tenant_id)
        
        mock_session.execute.assert_called_once()
        call_args = mock_session.execute.call_args
        assert tenant_id in str(call_args)
    
    def test_ensure_tenant_context_rejects_none(self):
        """Verify function rejects None tenant_id."""
        mock_session = Mock()
        
        with pytest.raises(TenantContextError) as exc_info:
            ensure_tenant_context(mock_session, None)
        
        assert "tenant_id is required" in str(exc_info.value)
    
    def test_ensure_tenant_context_rejects_invalid_uuid(self):
        """Verify function rejects invalid UUID format."""
        mock_session = Mock()
        
        with pytest.raises(TenantContextError) as exc_info:
            ensure_tenant_context(mock_session, "bad-uuid")
        
        assert "Invalid tenant_id format" in str(exc_info.value)


class TestTenantContextErrorMessages:
    """Tests for error message clarity."""
    
    def test_error_includes_method_name(self):
        """Verify error message includes the method name that failed."""
        class FakeAgent:
            def __init__(self):
                self.session = Mock()
                self.tenant_id = None
            
            @require_tenant
            def important_operation(self):
                return "done"
        
        agent = FakeAgent()
        
        with pytest.raises(TenantContextError) as exc_info:
            agent.important_operation()
        
        assert "important_operation" in str(exc_info.value)
    
    def test_error_includes_invalid_value(self):
        """Verify error message includes the invalid tenant_id value."""
        mock_session = Mock()
        bad_id = "definitely-not-a-uuid-12345"
        
        with pytest.raises(TenantContextError) as exc_info:
            ensure_tenant_context(mock_session, bad_id)
        
        assert bad_id in str(exc_info.value)
