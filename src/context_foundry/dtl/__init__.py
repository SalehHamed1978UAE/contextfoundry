"""
Decision Trace Layer (DTL) - Library-First Architecture

This package implements precedent retrieval as a library-first core capability
with transport adapters. All retrieval logic lives in core.py.

Modules:
- core: Single source of truth for precedent search (AuthContext-based)
- dtl_http: HTTP adapter for external API access
- dtl_inline: In-process adapter for agents/orchestrator
"""

from .core import AuthContext, PrecedentResult, search_precedents
from .dtl_inline import inline_search_precedents, derive_auth_context_from_cf_request, InlineSearchResult

__all__ = [
    'AuthContext', 
    'PrecedentResult', 
    'search_precedents',
    'inline_search_precedents',
    'derive_auth_context_from_cf_request',
    'InlineSearchResult'
]
