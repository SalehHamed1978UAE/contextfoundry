"""
Conversation Store for Tool-Calling Agent.

Stores session history with tenant RLS for pronoun resolution.
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import Column, DateTime, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Session

from ..models.schema import Base, set_tenant_context

logger = logging.getLogger(__name__)


class ConversationMessage(Base):
    """Single message in a conversation."""
    __tablename__ = 'conversation_messages'
    __table_args__ = {'schema': 'platform'}
    
    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    tenant_id = Column(PGUUID(as_uuid=True), nullable=False, index=True)
    session_id = Column(String(100), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # 'user', 'assistant'
    content = Column(Text, nullable=False)
    msg_metadata = Column(JSONB, default={})
    mentioned_entities = Column(JSONB, default=[])  # For pronoun resolution
    created_at = Column(DateTime, default=datetime.utcnow)


class ConversationStore:
    """
    Manage conversation history for a session.
    
    Usage:
        store = ConversationStore(session, tenant_id, session_id)
        store.add_message("user", "How many jobs has Saleh done?")
        store.add_message("assistant", "Saleh has done 7 jobs.", entities=["Saleh Hamed"])
        history = store.get_history()
    """
    
    MAX_HISTORY = 10  # Keep last N messages
    
    def __init__(self, session: Session, tenant_id: str, session_id: str):
        self.db_session = session
        self.tenant_id = UUID(tenant_id)
        self.session_id = session_id
        set_tenant_context(session, tenant_id)
    
    def add_message(
        self,
        role: str,
        content: str,
        entities: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a message to conversation history."""
        try:
            msg = ConversationMessage(
                tenant_id=self.tenant_id,
                session_id=self.session_id,
                role=role,
                content=content,
                mentioned_entities=entities or [],
                msg_metadata=metadata or {}
            )
            self.db_session.add(msg)
            self.db_session.commit()
        except Exception as e:
            logger.error(f"Failed to add message: {e}")
            self.db_session.rollback()
    
    def get_history(self, limit: int = None) -> List[Dict[str, str]]:
        """Get conversation history in OpenAI message format."""
        limit = limit or self.MAX_HISTORY
        try:
            sql = text("""
                SELECT role, content, mentioned_entities
                FROM platform.conversation_messages
                WHERE tenant_id = :tid AND session_id = :sid
                ORDER BY created_at DESC
                LIMIT :lim
            """)
            rows = self.db_session.execute(sql, {
                "tid": str(self.tenant_id),
                "sid": self.session_id,
                "lim": limit
            }).fetchall()
            
            # Reverse to chronological order
            messages = []
            for row in reversed(rows):
                messages.append({
                    "role": row.role,
                    "content": row.content
                })
            return messages
        except Exception as e:
            logger.error(f"Failed to get history: {e}")
            return []
    
    def get_mentioned_entities(self) -> List[str]:
        """Get all entities mentioned in recent conversation for pronoun resolution."""
        try:
            sql = text("""
                SELECT mentioned_entities
                FROM platform.conversation_messages
                WHERE tenant_id = :tid AND session_id = :sid
                ORDER BY created_at DESC
                LIMIT 5
            """)
            rows = self.db_session.execute(sql, {
                "tid": str(self.tenant_id),
                "sid": self.session_id
            }).fetchall()
            
            entities = []
            for row in rows:
                if row.mentioned_entities:
                    entities.extend(row.mentioned_entities)
            return list(dict.fromkeys(entities))  # Dedupe preserving order
        except Exception as e:
            logger.error(f"Failed to get entities: {e}")
            return []
    
    def resolve_pronouns(self, text: str) -> str:
        """Replace pronouns with entity names from recent conversation."""
        entities = self.get_mentioned_entities()
        if not entities:
            return text
        
        # Simple pronoun replacement - use most recently mentioned person
        person_entity = entities[0] if entities else None
        if not person_entity:
            return text
        
        import re
        # Replace pronouns with the entity name
        pronouns = r'\b(he|she|him|her|his|hers|they|them|their)\b'
        
        def replace_pronoun(match):
            return person_entity
        
        return re.sub(pronouns, replace_pronoun, text, flags=re.IGNORECASE)
