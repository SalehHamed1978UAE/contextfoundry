"""
Message Bus - Event-Driven Agent Communication

RFC v2 §12 - Loose coupling between governance agents via database-backed message queue.

Supports:
- Publish/subscribe pattern for broadcasting events
- Point-to-point messaging for directed communication
- Exactly-once processing semantics via processed_events tracking
- Delayed message scheduling
- Dead letter handling for failed messages
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, Any, List, Optional, Callable
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event types supported by the message bus."""
    TYPE_PROPOSED = "TYPE_PROPOSED"
    TYPE_VALIDATING = "TYPE_VALIDATING"
    TYPE_APPROVED = "TYPE_APPROVED"
    TYPE_ACTIVATED = "TYPE_ACTIVATED"
    TYPE_DEPRECATED = "TYPE_DEPRECATED"
    TYPE_REJECTED = "TYPE_REJECTED"
    EXTRACTION_REQUESTED = "EXTRACTION_REQUESTED"
    EXTRACTION_COMPLETE = "EXTRACTION_COMPLETE"
    ENTITY_STAGED = "ENTITY_STAGED"
    ENTITY_PROMOTED = "ENTITY_PROMOTED"
    ENTITY_ARCHIVED = "ENTITY_ARCHIVED"
    RELATIONSHIP_PROMOTED = "RELATIONSHIP_PROMOTED"
    ORPHAN_PATTERN_DETECTED = "ORPHAN_PATTERN_DETECTED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_COMPLETE = "APPROVAL_COMPLETE"
    CONFLICT_DETECTED = "CONFLICT_DETECTED"
    CONFLICT_RESOLVED = "CONFLICT_RESOLVED"


class ProcessingStatus(Enum):
    """Message processing status."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


@dataclass
class Message:
    """A message in the queue."""
    id: UUID
    event_type: EventType
    source_agent: str
    target_agent: Optional[str]
    payload: Dict[str, Any]
    correlation_id: Optional[UUID]
    causation_id: Optional[UUID]
    status: ProcessingStatus
    created_at: datetime
    scheduled_for: Optional[datetime]


class MessageBus:
    """
    Database-backed message bus for agent coordination.
    
    Usage:
        bus = MessageBus()
        
        # Publish an event
        bus.publish(
            event_type=EventType.TYPE_PROPOSED,
            source_agent="TypeValidator",
            payload={"type_id": "...", "type_name": "..."}
        )
        
        # Get pending messages for an agent
        messages = bus.get_pending_messages("OrphanDetector")
        
        # Process and acknowledge
        for msg in messages:
            process_message(msg)
            bus.acknowledge(msg.id, "OrphanDetector")
    """
    
    def __init__(self):
        self.database_url = os.environ.get("DATABASE_URL")
        if not self.database_url:
            raise ValueError("DATABASE_URL environment variable not set")
    
    def _get_connection(self):
        return psycopg2.connect(self.database_url)
    
    def publish(
        self,
        event_type: EventType,
        source_agent: str,
        payload: Dict[str, Any],
        target_agent: Optional[str] = None,
        correlation_id: Optional[UUID] = None,
        causation_id: Optional[UUID] = None,
        scheduled_for: Optional[datetime] = None
    ) -> UUID:
        """
        Publish an event to the message bus.
        
        Args:
            event_type: Type of event
            source_agent: Name of the publishing agent
            payload: Event data (JSON-serializable)
            target_agent: Optional specific recipient (None = broadcast)
            correlation_id: For request/response patterns
            causation_id: ID of event that caused this one
            scheduled_for: Optional delayed processing time
            
        Returns:
            UUID of the published message
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO shared.message_queue (
                        event_type, source_agent, target_agent, payload,
                        correlation_id, causation_id, scheduled_for
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s
                    ) RETURNING id
                """, (
                    event_type.value,
                    source_agent,
                    target_agent,
                    json.dumps(payload),
                    str(correlation_id) if correlation_id else None,
                    str(causation_id) if causation_id else None,
                    scheduled_for
                ))
                
                row = cur.fetchone()
                conn.commit()
                
                message_id = UUID(row['id'])
                logger.info(
                    f"[MessageBus] Published {event_type.value} from {source_agent}"
                    f" (id={message_id})"
                )
                return message_id
    
    def get_pending_messages(
        self,
        agent_name: str,
        limit: int = 10
    ) -> List[Message]:
        """
        Get pending messages for an agent based on its subscriptions.
        
        Only returns messages that:
        - Match an active subscription for this agent
        - Have not been processed by this agent yet
        - Are past their scheduled_for time (if set)
        - Are either broadcast (target_agent=NULL) or targeted to this agent
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        mq.id,
                        mq.event_type,
                        mq.source_agent,
                        mq.target_agent,
                        mq.payload,
                        mq.correlation_id,
                        mq.causation_id,
                        mq.status,
                        mq.created_at,
                        mq.scheduled_for
                    FROM shared.message_queue mq
                    INNER JOIN shared.event_subscriptions es 
                        ON es.event_type = mq.event_type
                        AND es.subscriber_agent = %s
                        AND es.is_active = TRUE
                    LEFT JOIN shared.processed_events pe 
                        ON pe.message_id = mq.id 
                        AND pe.subscriber_agent = %s
                    WHERE mq.status = 'PENDING'
                      AND pe.id IS NULL
                      AND (mq.target_agent IS NULL OR mq.target_agent = %s)
                      AND (mq.scheduled_for IS NULL OR mq.scheduled_for <= NOW())
                    ORDER BY mq.created_at ASC
                    LIMIT %s
                """, (agent_name, agent_name, agent_name, limit))
                
                messages = []
                for row in cur.fetchall():
                    messages.append(Message(
                        id=UUID(row['id']),
                        event_type=EventType(row['event_type']),
                        source_agent=row['source_agent'],
                        target_agent=row['target_agent'],
                        payload=row['payload'] if isinstance(row['payload'], dict) else json.loads(row['payload']),
                        correlation_id=UUID(row['correlation_id']) if row['correlation_id'] else None,
                        causation_id=UUID(row['causation_id']) if row['causation_id'] else None,
                        status=ProcessingStatus(row['status']),
                        created_at=row['created_at'],
                        scheduled_for=row['scheduled_for']
                    ))
                
                return messages
    
    def acknowledge(
        self,
        message_id: UUID,
        agent_name: str,
        status: str = "SUCCESS",
        result: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Acknowledge processing of a message.
        
        Records that this agent has processed this message, enabling
        exactly-once semantics. If all subscribers have processed,
        marks the message as COMPLETED.
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO shared.processed_events 
                        (message_id, subscriber_agent, result_status, result_payload)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (message_id, subscriber_agent) DO UPDATE
                    SET processed_at = NOW(), 
                        result_status = EXCLUDED.result_status, 
                        result_payload = EXCLUDED.result_payload
                """, (
                    str(message_id),
                    agent_name,
                    status,
                    json.dumps(result) if result else None
                ))
                
                cur.execute("""
                    SELECT target_agent, event_type 
                    FROM shared.message_queue WHERE id = %s
                """, (str(message_id),))
                msg_info = cur.fetchone()
                
                if msg_info and msg_info['target_agent'] is not None:
                    cur.execute("""
                        UPDATE shared.message_queue 
                        SET status = 'COMPLETED', completed_at = NOW()
                        WHERE id = %s
                    """, (str(message_id),))
                else:
                    cur.execute("""
                        SELECT COUNT(*) as pending
                        FROM shared.event_subscriptions es
                        LEFT JOIN shared.processed_events pe 
                            ON pe.message_id = %s 
                            AND pe.subscriber_agent = es.subscriber_agent
                        WHERE es.event_type = %s
                        AND es.is_active = TRUE
                        AND pe.id IS NULL
                    """, (str(message_id), msg_info['event_type'] if msg_info else None))
                    
                    row = cur.fetchone()
                    pending_count = row['pending'] if row else 0
                    
                    if pending_count == 0:
                        cur.execute("""
                            UPDATE shared.message_queue 
                            SET status = 'COMPLETED', completed_at = NOW()
                            WHERE id = %s
                        """, (str(message_id),))
                
                conn.commit()
                
                logger.debug(f"[MessageBus] {agent_name} acknowledged {message_id}")
                return True
    
    def fail(
        self,
        message_id: UUID,
        agent_name: str,
        error: str
    ) -> bool:
        """
        Mark a message processing as failed.
        
        Increments retry count. If max retries exceeded, moves to dead letter.
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    UPDATE shared.message_queue
                    SET retry_count = retry_count + 1,
                        error_message = %s
                    WHERE id = %s
                    RETURNING retry_count, max_retries
                """, (error, str(message_id)))
                
                row = cur.fetchone()
                if row and row['retry_count'] >= row['max_retries']:
                    cur.execute("""
                        UPDATE shared.message_queue
                        SET status = 'DEAD_LETTER',
                            dead_lettered_at = NOW(),
                            dead_letter_reason = %s
                        WHERE id = %s
                    """, (f"Max retries exceeded: {error}", str(message_id)))
                    
                    logger.warning(
                        f"[MessageBus] Message {message_id} moved to dead letter"
                    )
                
                conn.commit()
                return True
    
    def subscribe(
        self,
        agent_name: str,
        event_type: EventType,
        filter_expression: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Subscribe an agent to an event type.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO shared.event_subscriptions 
                        (subscriber_agent, event_type, filter_expression)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (subscriber_agent, event_type) 
                    DO UPDATE SET is_active = TRUE,
                                  filter_expression = EXCLUDED.filter_expression
                """, (
                    agent_name,
                    event_type.value,
                    json.dumps(filter_expression) if filter_expression else None
                ))
                conn.commit()
                
                logger.info(
                    f"[MessageBus] {agent_name} subscribed to {event_type.value}"
                )
                return True
    
    def unsubscribe(
        self,
        agent_name: str,
        event_type: EventType
    ) -> bool:
        """
        Unsubscribe an agent from an event type.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE shared.event_subscriptions
                    SET is_active = FALSE
                    WHERE subscriber_agent = %s AND event_type = %s
                """, (agent_name, event_type.value))
                conn.commit()
                
                logger.info(
                    f"[MessageBus] {agent_name} unsubscribed from {event_type.value}"
                )
                return True
    
    def get_dead_letters(
        self,
        limit: int = 50
    ) -> List[Message]:
        """
        Get messages in dead letter queue for manual inspection.
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, event_type, source_agent, target_agent, payload,
                           correlation_id, causation_id, status, created_at, scheduled_for
                    FROM shared.message_queue
                    WHERE status = 'DEAD_LETTER'
                    ORDER BY dead_lettered_at DESC
                    LIMIT %s
                """, (limit,))
                
                messages = []
                for row in cur.fetchall():
                    messages.append(Message(
                        id=UUID(row['id']),
                        event_type=EventType(row['event_type']),
                        source_agent=row['source_agent'],
                        target_agent=row['target_agent'],
                        payload=row['payload'] if isinstance(row['payload'], dict) else json.loads(row['payload']),
                        correlation_id=UUID(row['correlation_id']) if row['correlation_id'] else None,
                        causation_id=UUID(row['causation_id']) if row['causation_id'] else None,
                        status=ProcessingStatus(row['status']),
                        created_at=row['created_at'],
                        scheduled_for=row['scheduled_for']
                    ))
                
                return messages
    
    def replay_dead_letter(
        self,
        message_id: UUID
    ) -> bool:
        """
        Replay a dead letter message by resetting its status.
        """
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE shared.message_queue
                    SET status = 'PENDING',
                        retry_count = 0,
                        error_message = NULL,
                        dead_lettered_at = NULL,
                        dead_letter_reason = NULL
                    WHERE id = %s AND status = 'DEAD_LETTER'
                """, (str(message_id),))
                
                cur.execute("""
                    DELETE FROM shared.processed_events
                    WHERE message_id = %s
                """, (str(message_id),))
                
                conn.commit()
                
                logger.info(f"[MessageBus] Replayed dead letter {message_id}")
                return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get message bus statistics.
        """
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        status,
                        COUNT(*) as count
                    FROM shared.message_queue
                    GROUP BY status
                """)
                
                status_counts = {row['status']: row['count'] for row in cur.fetchall()}
                
                cur.execute("""
                    SELECT 
                        event_type,
                        COUNT(*) as count
                    FROM shared.message_queue
                    WHERE created_at > NOW() - INTERVAL '24 hours'
                    GROUP BY event_type
                    ORDER BY count DESC
                """)
                
                recent_by_type = {row['event_type']: row['count'] for row in cur.fetchall()}
                
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM shared.event_subscriptions
                    WHERE is_active = TRUE
                """)
                
                active_subscriptions = cur.fetchone()['count']
                
                return {
                    'status_counts': status_counts,
                    'recent_24h_by_type': recent_by_type,
                    'active_subscriptions': active_subscriptions
                }
