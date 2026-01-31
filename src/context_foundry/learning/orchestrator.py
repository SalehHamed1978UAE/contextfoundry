"""
Learning Flow Orchestrator

Coordinates the entire learning flow process:
1. Detect gaps from queries
2. Queue learning tasks
3. Process tasks with targeted extraction
4. Update knowledge graph
"""

import logging
from typing import Optional, Dict, Any, List
from uuid import UUID

from sqlalchemy import text

from .gap_detector import get_gap_detector, GapDetector
from .queue_manager import get_queue_manager, LearningQueueManager
from .targeted_extractor import get_targeted_extractor, TargetedExtractor

logger = logging.getLogger(__name__)


class LearningFlowOrchestrator:
    """Orchestrates the learning flow process"""
    
    def __init__(self, db_session, llm_client=None):
        self.db = db_session
        self.gap_detector = get_gap_detector(db_session)
        self.queue_manager = get_queue_manager(db_session)
        self.extractor = get_targeted_extractor(db_session, llm_client)
    
    def on_query_response(
        self,
        tenant_id: UUID,
        query_text: str,
        response_text: str,
        confidence: float,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Hook to call after every query response.
        
        Detects gaps and queues learning tasks automatically.
        """
        
        valid_kwargs = {
            k: v for k, v in kwargs.items()
            if k in ('entities_used', 'relationships_used', 'user_id', 'session_id')
        }
        
        gap = self.gap_detector.analyze_response(
            tenant_id=tenant_id,
            query_text=query_text,
            response_text=response_text,
            confidence=confidence,
            **valid_kwargs
        )
        
        if gap:
            task_id = self.queue_manager.queue_from_gap(UUID(gap['gap_id']))
            gap['task_id'] = str(task_id) if task_id else None
            
            logger.info(f"Gap detected and queued: {gap['gap_type']}")
        
        return gap
    
    def on_user_feedback(
        self,
        tenant_id: UUID,
        original_value: str,
        corrected_value: str,
        correction_field: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Hook to call when user provides explicit feedback.
        
        Creates high-priority learning task.
        """
        
        feedback_id = self.gap_detector.record_user_correction(
            tenant_id=tenant_id,
            original_value=original_value,
            corrected_value=corrected_value,
            correction_field=correction_field,
            **kwargs
        )
        
        task_id = self.queue_manager.queue_from_feedback(feedback_id)
        
        return {
            "feedback_id": str(feedback_id),
            "task_id": str(task_id),
            "status": "queued"
        }
    
    def process_learning_queue(self, limit: int = 5, tenant_id: Optional[UUID] = None) -> Dict[str, Any]:
        """
        Process pending learning tasks.
        
        Call this periodically (e.g., every minute) or on-demand.
        """
        
        tasks = self.queue_manager.get_next_tasks(limit=limit, tenant_id=tenant_id)
        
        if not tasks:
            return {"processed": 0, "message": "No pending tasks"}
        
        results = []
        
        for task in tasks:
            task_id = task['id']
            
            try:
                self.queue_manager.start_task(task_id)
                
                result = self.extractor.process_task(task)
                
                self.queue_manager.complete_task(
                    task_id,
                    entities_found=result.get('entities_found', 0),
                    relationships_found=result.get('relationships_found', 0)
                )
                
                results.append({
                    "task_id": str(task_id),
                    "status": "completed",
                    **result
                })
                
            except Exception as e:
                logger.error(f"Failed to process task {task_id}: {e}")
                self.queue_manager.fail_task(task_id, str(e))
                results.append({
                    "task_id": str(task_id),
                    "status": "failed",
                    "error": str(e)
                })
        
        return {
            "processed": len(results),
            "results": results
        }
    
    def get_learning_status(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get learning flow status for a tenant"""
        
        result = self.db.execute(text("""
            SELECT * FROM learning_dashboard WHERE tenant_id = :tenant_id
        """), {"tenant_id": tenant_id}).fetchone()
        
        if result:
            data = dict(result._mapping)
            data['tenant_id'] = str(data['tenant_id'])
            return data
        
        return {
            "tenant_id": str(tenant_id),
            "vault_name": None,
            "open_gaps": 0,
            "resolved_gaps": 0,
            "pending_feedback": 0,
            "applied_feedback": 0,
            "queued_tasks": 0,
            "completed_tasks": 0,
            "total_entities_learned": 0,
            "total_relationships_learned": 0
        }
    
    def trigger_learning(self, tenant_id: UUID, limit: int = 10) -> Dict[str, Any]:
        """
        Manually trigger learning for a tenant.
        
        Useful for batch processing or admin actions.
        """
        
        gaps = self.gap_detector.get_open_gaps(tenant_id)
        
        queued = 0
        for gap in gaps:
            if gap['status'] == 'OPEN':
                self.queue_manager.queue_from_gap(gap['id'])
                queued += 1
        
        process_result = self.process_learning_queue(limit=limit, tenant_id=tenant_id)
        
        return {
            "gaps_queued": queued,
            "tasks_processed": process_result['processed'],
            "results": process_result.get('results', [])
        }
    
    def get_gap_summary(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get summary of gaps for a tenant"""
        
        result = self.db.execute(text("""
            SELECT 
                gap_type,
                status,
                COUNT(*) as count
            FROM query_gaps
            WHERE tenant_id = :tenant_id
            GROUP BY gap_type, status
        """), {"tenant_id": tenant_id})
        
        summary = {"by_type": {}, "by_status": {}}
        
        for row in result.fetchall():
            gap_type = row.gap_type
            status = row.status
            count = row.count
            
            if gap_type not in summary["by_type"]:
                summary["by_type"][gap_type] = 0
            summary["by_type"][gap_type] += count
            
            if status not in summary["by_status"]:
                summary["by_status"][status] = 0
            summary["by_status"][status] += count
        
        return summary


def get_orchestrator(db_session, llm_client=None) -> LearningFlowOrchestrator:
    """Get orchestrator with provided session"""
    return LearningFlowOrchestrator(db_session, llm_client)
