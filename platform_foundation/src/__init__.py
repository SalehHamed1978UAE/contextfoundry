"""
Platform Foundation Module

Multi-tenancy, authentication, document management, and metering.
Communicates with Brain ONLY through interface types.

CRITICAL: This module MUST NOT import from src/context_foundry/
"""

from .tenant_service import TenantService
from .document_service import DocumentService
from .metering_service import MeteringService

__all__ = [
    "TenantService",
    "DocumentService", 
    "MeteringService",
]
