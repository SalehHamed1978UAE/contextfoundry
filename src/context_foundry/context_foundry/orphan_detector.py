"""
OrphanDetector Agent - Feedback Channel to Ontology Foundry

RFC v2 §13 - Detects extraction patterns that don't match ACTIVE ontology types
and provides feedback to inform ontology evolution.

Responsibilities:
1. Monitor extraction events for unmatched entity types
2. Aggregate orphan patterns by frequency and source
3. Publish ORPHAN_PATTERN_DETECTED events to message bus
4. Track which patterns have been reported to avoid duplicates

This creates a feedback loop:
- Extractor tries to extract entities
- OrphanDetector notices patterns without matching types
- Publishes feedback to Ontology Foundry
- Domain experts can then propose new types based on real usage

"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from uuid import UUID

import psycopg2
from psycopg2.extras import RealDictCursor
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..shared.message_bus import MessageBus, EventType, Message

logger = logging.getLogger(__name__)


@dataclass
class OrphanPattern:
    """An extraction pattern without a matching ontology type."""
    id: UUID
    pattern_text: str
    suggested_type: Optional[str]
    frequency: int
    first_seen: datetime
    last_seen: datetime
    source_documents: List[str]
    sample_contexts: List[str]
    status: str


@dataclass
class OrphanScanResult:
    """Result of an orphan detection scan."""
    scan_id: str
    patterns_found: int
    patterns_new: int
    patterns_updated: int
    events_published: int
    duration_seconds: float
    errors: List[str]


class OrphanDetector:
    """
    Detects and tracks orphan extraction patterns.
    
    An "orphan pattern" is an entity type or pattern that the extractor
    encounters but cannot map to any ACTIVE type in the ontology.
    
    Usage:
        detector = OrphanDetector(session)
        
        # Record an orphan pattern during extraction
        detector.record_orphan(
            pattern_text="CloudFunction",
            suggested_type="ComputeResource.ServerlessFunction",
            source_document="doc-123",
            context="...deployed a CloudFunction to handle..."
        )
        
        # Run periodic scan to aggregate and publish feedback
        result = detector.run_scan()
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.message_bus = MessageBus()
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """Ensure the orphan_patterns table exists in context schema."""
        try:
            self.session.execute(text("""
                CREATE TABLE IF NOT EXISTS context.orphan_patterns (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    pattern_text VARCHAR(255) NOT NULL,
                    suggested_type VARCHAR(255),
                    frequency INT NOT NULL DEFAULT 1,
                    first_seen TIMESTAMP NOT NULL DEFAULT NOW(),
                    last_seen TIMESTAMP NOT NULL DEFAULT NOW(),
                    source_documents JSONB NOT NULL DEFAULT '[]',
                    sample_contexts JSONB NOT NULL DEFAULT '[]',
                    status VARCHAR(50) NOT NULL DEFAULT 'ACTIVE',
                    reported_at TIMESTAMP,
                    resolved_type_id UUID,
                    CONSTRAINT unique_pattern UNIQUE (pattern_text)
                );
                
                CREATE INDEX IF NOT EXISTS idx_orphan_patterns_status 
                    ON context.orphan_patterns(status);
                CREATE INDEX IF NOT EXISTS idx_orphan_patterns_frequency 
                    ON context.orphan_patterns(frequency DESC);
            """))
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.warning(f"[OrphanDetector] Table check: {e}")
    
    def record_orphan(
        self,
        pattern_text: str,
        suggested_type: Optional[str] = None,
        source_document: Optional[str] = None,
        context: Optional[str] = None
    ) -> Optional[UUID]:
        """
        Record an orphan pattern encountered during extraction.
        
        If the pattern already exists, updates frequency and adds source/context.
        """
        try:
            existing = self.session.execute(text("""
                SELECT id, source_documents, sample_contexts, frequency
                FROM context.orphan_patterns
                WHERE pattern_text = :pattern
            """), {'pattern': pattern_text}).fetchone()
            
            if existing:
                source_docs = existing.source_documents or []
                if isinstance(source_docs, str):
                    source_docs = json.loads(source_docs)
                if source_document and source_document not in source_docs:
                    source_docs = source_docs + [source_document]
                    if len(source_docs) > 10:
                        source_docs = source_docs[-10:]
                
                contexts = existing.sample_contexts or []
                if isinstance(contexts, str):
                    contexts = json.loads(contexts)
                if context and context not in contexts:
                    contexts = contexts + [context[:500]]
                    if len(contexts) > 5:
                        contexts = contexts[-5:]
                
                existing_id = existing.id if isinstance(existing.id, UUID) else UUID(str(existing.id))
                
                self.session.execute(text("""
                    UPDATE context.orphan_patterns
                    SET frequency = frequency + 1,
                        last_seen = NOW(),
                        source_documents = :docs,
                        sample_contexts = :contexts,
                        suggested_type = COALESCE(:suggested, suggested_type)
                    WHERE id = :id
                """), {
                    'id': str(existing_id),
                    'docs': json.dumps(source_docs),
                    'contexts': json.dumps(contexts),
                    'suggested': suggested_type
                })
                self.session.commit()
                return existing_id
            else:
                source_docs = [source_document] if source_document else []
                contexts = [context[:500]] if context else []
                
                result = self.session.execute(text("""
                    INSERT INTO context.orphan_patterns 
                        (pattern_text, suggested_type, source_documents, sample_contexts)
                    VALUES (:pattern, :suggested, :docs, :contexts)
                    RETURNING id
                """), {
                    'pattern': pattern_text,
                    'suggested': suggested_type,
                    'docs': json.dumps(source_docs),
                    'contexts': json.dumps(contexts)
                })
                row = result.fetchone()
                self.session.commit()
                
                logger.info(f"[OrphanDetector] New orphan pattern: {pattern_text}")
                if row:
                    return row.id if isinstance(row.id, UUID) else UUID(str(row.id))
                return None
                
        except Exception as e:
            self.session.rollback()
            logger.error(f"[OrphanDetector] Failed to record orphan: {e}")
            return None
    
    def run_scan(
        self,
        min_frequency: int = 3,
        publish_threshold: int = 5
    ) -> OrphanScanResult:
        """
        Run orphan detection scan and publish feedback to Ontology Foundry.
        
        Args:
            min_frequency: Minimum occurrences before considering a pattern
            publish_threshold: Minimum occurrences before publishing feedback
        
        Returns:
            OrphanScanResult with statistics
        """
        scan_id = f"scan-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        start_time = datetime.utcnow()
        result = OrphanScanResult(
            scan_id=scan_id,
            patterns_found=0,
            patterns_new=0,
            patterns_updated=0,
            events_published=0,
            duration_seconds=0,
            errors=[]
        )
        
        try:
            patterns = self.session.execute(text("""
                SELECT id, pattern_text, suggested_type, frequency,
                       first_seen, last_seen, source_documents, sample_contexts,
                       status, reported_at
                FROM context.orphan_patterns
                WHERE status = 'ACTIVE'
                  AND frequency >= :min_freq
                ORDER BY frequency DESC
                LIMIT 100
            """), {'min_freq': min_frequency}).fetchall()
            
            result.patterns_found = len(patterns)
            
            for row in patterns:
                if row.frequency >= publish_threshold and not row.reported_at:
                    self._publish_orphan_feedback(row)
                    result.events_published += 1
                    
                    self.session.execute(text("""
                        UPDATE context.orphan_patterns
                        SET reported_at = NOW()
                        WHERE id = :id
                    """), {'id': row.id})
            
            self.session.commit()
            
            logger.info(
                f"[OrphanDetector] Scan complete: {result.patterns_found} patterns, "
                f"{result.events_published} events published"
            )
            
        except Exception as e:
            self.session.rollback()
            result.errors.append(str(e))
            logger.error(f"[OrphanDetector] Scan error: {e}")
        
        result.duration_seconds = (datetime.utcnow() - start_time).total_seconds()
        return result
    
    def _publish_orphan_feedback(self, pattern) -> None:
        """Publish orphan pattern as feedback event to Ontology Foundry."""
        try:
            source_docs = pattern.source_documents
            if isinstance(source_docs, str):
                source_docs = json.loads(source_docs)
            
            contexts = pattern.sample_contexts
            if isinstance(contexts, str):
                contexts = json.loads(contexts)
            
            payload = {
                'pattern_id': str(pattern.id),
                'pattern_text': pattern.pattern_text,
                'suggested_type': pattern.suggested_type,
                'frequency': pattern.frequency,
                'first_seen': pattern.first_seen.isoformat() if pattern.first_seen else None,
                'last_seen': pattern.last_seen.isoformat() if pattern.last_seen else None,
                'source_documents': source_docs[:5],
                'sample_contexts': contexts[:3],
                'recommendation': self._generate_recommendation(pattern)
            }
            
            self.message_bus.publish(
                event_type=EventType.ORPHAN_PATTERN_DETECTED,
                source_agent='OrphanDetector',
                payload=payload
            )
            
        except Exception as e:
            logger.error(f"[OrphanDetector] Failed to publish feedback: {e}")
    
    def _generate_recommendation(self, pattern) -> str:
        """Generate a recommendation for handling the orphan pattern."""
        if pattern.frequency >= 20:
            return f"HIGH_PRIORITY: Pattern '{pattern.pattern_text}' seen {pattern.frequency} times. Consider adding as new type."
        elif pattern.frequency >= 10:
            return f"MEDIUM_PRIORITY: Pattern '{pattern.pattern_text}' seen {pattern.frequency} times. Review for potential type."
        else:
            return f"LOW_PRIORITY: Pattern '{pattern.pattern_text}' seen {pattern.frequency} times. Monitor for growth."
    
    def get_pending_patterns(
        self,
        limit: int = 50
    ) -> List[OrphanPattern]:
        """Get unreported orphan patterns above threshold."""
        rows = self.session.execute(text("""
            SELECT id, pattern_text, suggested_type, frequency,
                   first_seen, last_seen, source_documents, sample_contexts, status
            FROM context.orphan_patterns
            WHERE status = 'ACTIVE' AND reported_at IS NULL
            ORDER BY frequency DESC
            LIMIT :limit
        """), {'limit': limit}).fetchall()
        
        patterns = []
        for row in rows:
            source_docs = row.source_documents
            if isinstance(source_docs, str):
                source_docs = json.loads(source_docs)
            
            contexts = row.sample_contexts
            if isinstance(contexts, str):
                contexts = json.loads(contexts)
            
            pattern_id = row.id if isinstance(row.id, UUID) else UUID(str(row.id))
            patterns.append(OrphanPattern(
                id=pattern_id,
                pattern_text=row.pattern_text,
                suggested_type=row.suggested_type,
                frequency=row.frequency,
                first_seen=row.first_seen,
                last_seen=row.last_seen,
                source_documents=source_docs,
                sample_contexts=contexts,
                status=row.status
            ))
        
        return patterns
    
    def resolve_pattern(
        self,
        pattern_id: UUID,
        resolved_type_id: UUID
    ) -> bool:
        """
        Mark an orphan pattern as resolved by linking to a new type.
        
        Called when a new type is added to the ontology that matches
        this orphan pattern.
        """
        try:
            self.session.execute(text("""
                UPDATE context.orphan_patterns
                SET status = 'RESOLVED',
                    resolved_type_id = :type_id
                WHERE id = :id
            """), {'id': str(pattern_id), 'type_id': str(resolved_type_id)})
            self.session.commit()
            
            logger.info(f"[OrphanDetector] Pattern {pattern_id} resolved to type {resolved_type_id}")
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"[OrphanDetector] Failed to resolve pattern: {e}")
            return False
    
    def dismiss_pattern(
        self,
        pattern_id: UUID,
        reason: str
    ) -> bool:
        """
        Dismiss an orphan pattern that shouldn't become a type.
        """
        try:
            self.session.execute(text("""
                UPDATE context.orphan_patterns
                SET status = 'DISMISSED'
                WHERE id = :id
            """), {'id': str(pattern_id)})
            self.session.commit()
            
            logger.info(f"[OrphanDetector] Pattern {pattern_id} dismissed: {reason}")
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"[OrphanDetector] Failed to dismiss pattern: {e}")
            return False
    
    def process_extraction_event(self, message: Message) -> bool:
        """
        Process an EXTRACTION_COMPLETE event from the message bus.
        
        Checks for unmatched entities in the extraction result and
        records them as orphan patterns.
        """
        try:
            payload = message.payload
            
            unmatched = payload.get('unmatched_entities', [])
            document_id = payload.get('document_id')
            
            for entity in unmatched:
                self.record_orphan(
                    pattern_text=entity.get('type_guess', entity.get('name', 'Unknown')),
                    suggested_type=entity.get('suggested_type'),
                    source_document=document_id,
                    context=entity.get('context')
                )
            
            self.message_bus.acknowledge(message.id, 'OrphanDetector')
            return True
            
        except Exception as e:
            logger.error(f"[OrphanDetector] Failed to process event: {e}")
            self.message_bus.fail(message.id, 'OrphanDetector', str(e))
            return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get orphan detection statistics."""
        result = self.session.execute(text("""
            SELECT 
                status,
                COUNT(*) as count,
                SUM(frequency) as total_occurrences
            FROM context.orphan_patterns
            GROUP BY status
        """)).fetchall()
        
        by_status = {row.status: {'count': row.count, 'occurrences': row.total_occurrences} for row in result}
        
        top_patterns = self.session.execute(text("""
            SELECT pattern_text, frequency, suggested_type
            FROM context.orphan_patterns
            WHERE status = 'ACTIVE'
            ORDER BY frequency DESC
            LIMIT 10
        """)).fetchall()
        
        return {
            'by_status': by_status,
            'top_patterns': [
                {'pattern': row.pattern_text, 'frequency': row.frequency, 'suggested': row.suggested_type}
                for row in top_patterns
            ]
        }
