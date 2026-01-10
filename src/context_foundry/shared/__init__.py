"""
Shared Module - Cross-System Components

Components used by both Ontology Foundry and Context Foundry.
"""

from .message_bus import MessageBus, Message, EventType, ProcessingStatus
from .tenant_context import (
    tenant_session,
    require_tenant,
    ensure_tenant_context,
    TenantContextError,
)

__all__ = [
    'MessageBus',
    'Message',
    'EventType',
    'ProcessingStatus',
    'tenant_session',
    'require_tenant',
    'ensure_tenant_context',
    'TenantContextError',
]
