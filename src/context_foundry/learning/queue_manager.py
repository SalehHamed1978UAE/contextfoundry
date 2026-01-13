"""
Learning Queue Manager

Manages the queue of learning tasks, prioritizes them, and tracks progress.
"""

import logging
import re
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

from sqlalchemy import text

logger = logging.getLogger(__name__)


class LearningQueueManager:
    """Manages the learning task queue"""
    
    FREQUENCY_WEIGHT = 2.0
    RECENCY_WEIGHT = 1.5
    USER_FEEDBACK_WEIGHT = 3.0
    
    def __init__(self, db_session):
        self.db = db_session
    
    def queue_from_gap(self, gap_id: UUID) -> Optional[UUID]:
        """
        Create a learning task from a query gap.
        
        If a similar task already exists, increment its occurrence count
        and boost its priority instead of creating a duplicate.
        """
        
        gap = self.db.execute(text("""
            SELECT * FROM query_gaps WHERE id = :gap_id
        """), {"gap_id": gap_id}).fetchone()
        
        if not gap:
            logger.warning(f"Gap {gap_id} not found")
            return None
        
        gap = dict(gap._mapping)
        
        existing = self._find_similar_task(
            tenant_id=gap['tenant_id'],
            entity_name=gap.get('expected_entity_name'),
            entity_type=gap.get('expected_entity_type')
        )
        
        if existing:
            self._increment_task(existing['id'], gap_id)
            return existing['id']
        
        task_id = self._create_task(gap)
        
        self.db.execute(text("""
            UPDATE query_gaps SET status = 'QUEUED' WHERE id = :gap_id
        """), {"gap_id": gap_id})
        self.db.commit()
        
        return task_id
    
    def queue_from_feedback(self, feedback_id: UUID) -> UUID:
        """Create a high-priority learning task from user feedback"""
        
        feedback = self.db.execute(text("""
            SELECT * FROM user_feedback WHERE id = :feedback_id
        """), {"feedback_id": feedback_id}).fetchone()
        
        if not feedback:
            raise ValueError(f"Feedback {feedback_id} not found")
        
        feedback = dict(feedback._mapping)
        
        task_id = uuid4()
        base_priority = 80
        
        self.db.execute(text("""
            INSERT INTO learning_queue (
                id, tenant_id, task_type, target_entity_name,
                search_terms, priority, priority_reason, query_gap_ids
            ) VALUES (
                :id, :tenant_id, 'verify_entity', :entity_name,
                :search_terms, :priority, :reason, :gap_ids
            )
        """), {
            "id": task_id,
            "tenant_id": feedback['tenant_id'],
            "entity_name": feedback['corrected_value'],
            "search_terms": [feedback['corrected_value']] if feedback['corrected_value'] else [],
            "priority": base_priority,
            "reason": "User feedback correction",
            "gap_ids": [feedback['query_gap_id']] if feedback.get('query_gap_id') else []
        })
        self.db.commit()
        
        logger.info(f"Created high-priority learning task {task_id} from user feedback")
        
        return task_id
    
    def get_next_tasks(self, limit: int = 10, tenant_id: UUID = None) -> List[Dict[str, Any]]:
        """Get the next highest-priority tasks to process"""
        
        if tenant_id:
            result = self.db.execute(text("""
                SELECT * FROM learning_queue
                WHERE status = 'PENDING' AND tenant_id = :tenant_id
                ORDER BY priority DESC, created_at ASC
                LIMIT :limit
            """), {"limit": limit, "tenant_id": tenant_id})
        else:
            result = self.db.execute(text("""
                SELECT * FROM learning_queue
                WHERE status = 'PENDING'
                ORDER BY priority DESC, created_at ASC
                LIMIT :limit
            """), {"limit": limit})
        
        return [dict(r._mapping) for r in result.fetchall()]
    
    def start_task(self, task_id: UUID) -> None:
        """Mark a task as processing"""
        
        self.db.execute(text("""
            UPDATE learning_queue 
            SET status = 'PROCESSING', started_at = NOW()
            WHERE id = :task_id
        """), {"task_id": task_id})
        self.db.commit()
    
    def complete_task(
        self, 
        task_id: UUID, 
        entities_found: int = 0,
        relationships_found: int = 0
    ) -> None:
        """Mark a task as completed"""
        
        self.db.execute(text("""
            UPDATE learning_queue 
            SET status = 'COMPLETED', 
                completed_at = NOW(),
                entities_found = :entities,
                relationships_found = :relationships
            WHERE id = :task_id
        """), {
            "task_id": task_id,
            "entities": entities_found,
            "relationships": relationships_found
        })
        
        self.db.execute(text("""
            UPDATE query_gaps 
            SET status = 'RESOLVED', resolved_at = NOW()
            WHERE id = ANY(
                SELECT unnest(query_gap_ids) FROM learning_queue WHERE id = :task_id
            )
        """), {"task_id": task_id})
        
        self.db.commit()
        
        logger.info(f"Completed learning task {task_id}: {entities_found} entities, {relationships_found} relationships")
    
    def fail_task(self, task_id: UUID, error_message: str) -> None:
        """Mark a task as failed"""
        
        self.db.execute(text("""
            UPDATE learning_queue 
            SET status = 'FAILED', 
                completed_at = NOW(),
                error_message = :error
            WHERE id = :task_id
        """), {"task_id": task_id, "error": error_message[:1000]})
        self.db.commit()
        
        logger.error(f"Learning task {task_id} failed: {error_message}")
    
    def get_queue_stats(self, tenant_id: UUID = None) -> Dict[str, int]:
        """Get queue statistics"""
        
        if tenant_id:
            result = self.db.execute(text("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'PENDING') as pending,
                    COUNT(*) FILTER (WHERE status = 'PROCESSING') as processing,
                    COUNT(*) FILTER (WHERE status = 'COMPLETED') as completed,
                    COUNT(*) FILTER (WHERE status = 'FAILED') as failed
                FROM learning_queue
                WHERE tenant_id = :tenant_id
            """), {"tenant_id": tenant_id}).fetchone()
        else:
            result = self.db.execute(text("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'PENDING') as pending,
                    COUNT(*) FILTER (WHERE status = 'PROCESSING') as processing,
                    COUNT(*) FILTER (WHERE status = 'COMPLETED') as completed,
                    COUNT(*) FILTER (WHERE status = 'FAILED') as failed
                FROM learning_queue
            """)).fetchone()
        
        return dict(result._mapping) if result else {"pending": 0, "processing": 0, "completed": 0, "failed": 0}
    
    def _find_similar_task(
        self, 
        tenant_id: UUID, 
        entity_name: Optional[str],
        entity_type: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Find an existing similar task"""
        
        if not entity_name:
            return None
        
        result = self.db.execute(text("""
            SELECT * FROM learning_queue
            WHERE tenant_id = :tenant_id
              AND status IN ('PENDING', 'PROCESSING')
              AND (
                  target_entity_name ILIKE :name
                  OR :name = ANY(search_terms)
              )
            LIMIT 1
        """), {
            "tenant_id": tenant_id,
            "name": f"%{entity_name}%"
        }).fetchone()
        
        return dict(result._mapping) if result else None
    
    def _increment_task(self, task_id: UUID, gap_id: UUID) -> None:
        """Increment occurrence count and boost priority"""
        
        self.db.execute(text("""
            UPDATE learning_queue 
            SET occurrence_count = occurrence_count + 1,
                last_seen_at = NOW(),
                priority = LEAST(100, priority + :boost),
                query_gap_ids = array_append(query_gap_ids, :gap_id)
            WHERE id = :task_id
        """), {
            "task_id": task_id,
            "boost": int(self.FREQUENCY_WEIGHT * 5),
            "gap_id": gap_id
        })
        
        self.db.execute(text("""
            UPDATE query_gaps SET status = 'QUEUED' WHERE id = :gap_id
        """), {"gap_id": gap_id})
        
        self.db.commit()
        
        logger.info(f"Incremented task {task_id} occurrence, gap {gap_id} queued")
    
    def _create_task(self, gap: Dict[str, Any]) -> UUID:
        """Create a new learning task from a gap"""
        
        task_id = uuid4()
        
        task_type = "extract_entity"
        search_terms = []
        
        if gap.get('expected_entity_name'):
            search_terms.append(gap['expected_entity_name'])
        
        if gap.get('expected_entity_type'):
            search_terms.append(gap['expected_entity_type'])
        
        query_terms = self._extract_search_terms(gap['query_text'])
        search_terms.extend(query_terms)
        
        priority = self._calculate_priority(gap)
        
        self.db.execute(text("""
            INSERT INTO learning_queue (
                id, tenant_id, task_type, 
                target_entity_type, target_entity_name, search_terms,
                priority, priority_reason, query_gap_ids
            ) VALUES (
                :id, :tenant_id, :task_type,
                :entity_type, :entity_name, :search_terms,
                :priority, :reason, :gap_ids
            )
        """), {
            "id": task_id,
            "tenant_id": gap['tenant_id'],
            "task_type": task_type,
            "entity_type": gap.get('expected_entity_type'),
            "entity_name": gap.get('expected_entity_name'),
            "search_terms": list(set(search_terms)),
            "priority": priority,
            "reason": f"Gap type: {gap['gap_type']}",
            "gap_ids": [gap['id']]
        })
        self.db.commit()
        
        logger.info(f"Created learning task {task_id} with priority {priority}")
        
        return task_id
    
    def _extract_search_terms(self, query_text: str) -> List[str]:
        """Extract search terms from query text"""
        
        stop_words = {
            "who", "what", "where", "when", "how", "is", "are", "the", 
            "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
            "tell", "me", "about", "does", "do", "can", "could", "would"
        }
        
        words = re.findall(r'\b\w+\b', query_text.lower())
        
        return [w for w in words if w not in stop_words and len(w) > 2]
    
    def _calculate_priority(self, gap: Dict[str, Any]) -> int:
        """Calculate initial priority for a gap"""
        
        base_priority = 50
        
        if gap['gap_type'] == 'no_answer':
            base_priority += 10
        elif gap['gap_type'] == 'wrong_answer':
            base_priority += 20
        
        if gap.get('confidence_score') and gap['confidence_score'] < 0.5:
            base_priority += 10
        
        return min(100, base_priority)


def get_queue_manager(db_session) -> LearningQueueManager:
    """Get queue manager with provided session"""
    return LearningQueueManager(db_session)
