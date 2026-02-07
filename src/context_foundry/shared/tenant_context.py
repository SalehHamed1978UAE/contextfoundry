"""
Tenant Context Management for RLS (Row-Level Security).

Provides utilities to ensure tenant context is properly set for all database
operations, preventing data leakage across tenants.
"""
from contextlib import contextmanager
from sqlalchemy import text
from functools import wraps
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class TenantContextError(Exception):
    """Raised when tenant context is missing or invalid."""
    pass


@contextmanager
def tenant_session(session, tenant_id: str):
    """
    Context manager that ensures tenant context is set for all operations.
    Re-asserts tenant after commits/rollbacks to prevent leakage.
    
    Usage:
        with tenant_session(session, tenant_id) as s:
            # all operations here are tenant-scoped
            s.query(Entity).all()  # only returns this tenant's entities
    
    Args:
        session: SQLAlchemy session
        tenant_id: UUID string of the tenant
        
    Raises:
        TenantContextError: If tenant_id is missing or invalid
    """
    if not tenant_id:
        raise TenantContextError("tenant_id is required")
    
    try:
        UUID(tenant_id)
    except ValueError:
        raise TenantContextError(f"Invalid tenant_id format: {tenant_id}")
    
    def set_tenant():
        session.execute(text("SET app.current_tenant_id = :tid"), {"tid": tenant_id})
        session.execute(text("SET app.current_tenant = :tid"), {"tid": tenant_id})
    
    try:
        set_tenant()
        yield session
    except Exception:
        session.rollback()
        set_tenant()
        raise
    finally:
        try:
            set_tenant()
        except Exception:
            pass


def require_tenant(func):
    """
    Decorator that ensures tenant_id is set before method execution.
    Use on agent methods that access the database.
    
    Usage:
        class MyAgent:
            def __init__(self, session, tenant_id):
                self.session = session
                self.tenant_id = tenant_id
            
            @require_tenant
            def query(self, text):
                # tenant context guaranteed here
                ...
    
    Raises:
        TenantContextError: If self.tenant_id is missing
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, 'tenant_id') or not self.tenant_id:
            raise TenantContextError(f"{func.__name__} requires tenant_id")
        
        try:
            UUID(str(self.tenant_id))
        except ValueError:
            raise TenantContextError(f"Invalid tenant_id format: {self.tenant_id}")
        
        self.session.execute(
            text("SET app.current_tenant_id = :tid"), 
            {"tid": str(self.tenant_id)}
        )
        self.session.execute(
            text("SET app.current_tenant = :tid"),
            {"tid": str(self.tenant_id)}
        )
        return func(self, *args, **kwargs)
    return wrapper


def ensure_tenant_context(session, tenant_id: str) -> None:
    """
    Set tenant context on session. Call this before any tenant-scoped operation.
    
    This is a simpler alternative to tenant_session for cases where a context
    manager doesn't fit the code structure.
    
    Args:
        session: SQLAlchemy session
        tenant_id: UUID string of the tenant
        
    Raises:
        TenantContextError: If tenant_id is missing or invalid
    """
    if not tenant_id:
        raise TenantContextError("tenant_id is required")
    
    try:
        UUID(tenant_id)
    except ValueError:
        raise TenantContextError(f"Invalid tenant_id format: {tenant_id}")
    
    session.execute(text("SET app.current_tenant_id = :tid"), {"tid": tenant_id})
    session.execute(text("SET app.current_tenant = :tid"), {"tid": tenant_id})
    logger.debug(f"Set tenant context: {tenant_id}")
