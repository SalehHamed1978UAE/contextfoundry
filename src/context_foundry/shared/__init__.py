"""
Shared Module - Cross-System Components

Components used by both Ontology Foundry and Context Foundry.
"""

from .message_bus import MessageBus, Message, EventType, ProcessingStatus

__all__ = [
    'MessageBus',
    'Message',
    'EventType',
    'ProcessingStatus',
]
