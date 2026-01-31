"""
Shadow mode comparison metrics for extraction pipeline.

Logs comparison between legacy and constrained extraction paths
to validate before cutover. Persists to structured log file.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

SHADOW_LOG_PATH = Path("logs/shadow_extraction_metrics.jsonl")

shadow_logger = logging.getLogger("shadow_extraction")
shadow_logger.setLevel(logging.INFO)

if not SHADOW_LOG_PATH.parent.exists():
    SHADOW_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

file_handler = logging.FileHandler(SHADOW_LOG_PATH)
file_handler.setFormatter(logging.Formatter('%(message)s'))
shadow_logger.addHandler(file_handler)


class ShadowMetrics:
    """Tracks and logs shadow mode extraction comparisons"""
    
    @staticmethod
    def calculate_overlap(old_entities: List[Dict], new_entities: List[Dict]) -> float:
        """Calculate entity overlap ratio between old and new extraction"""
        if not old_entities and not new_entities:
            return 1.0
        if not old_entities or not new_entities:
            return 0.0
        
        old_names = {e.get('name', '').lower() for e in old_entities}
        new_names = {e.get('name', '').lower() for e in new_entities}
        
        intersection = old_names & new_names
        union = old_names | new_names
        
        return len(intersection) / len(union) if union else 0.0
    
    @staticmethod
    def calculate_type_distribution(entities: List[Dict]) -> Dict[str, int]:
        """Get count of entities by type"""
        distribution = {}
        for e in entities:
            entity_type = e.get('entity_type', 'UNKNOWN')
            distribution[entity_type] = distribution.get(entity_type, 0) + 1
        return distribution
    
    @classmethod
    def log_comparison(
        cls,
        document_id: str,
        old_result: Dict[str, Any],
        new_result: Dict[str, Any],
        source_text_length: int = 0
    ) -> Dict[str, Any]:
        """
        Log comparison metrics between old and new extraction results.
        
        Args:
            document_id: UUID of the source document
            old_result: Legacy extraction result with 'entities' and 'relationships'
            new_result: Constrained extraction result with 'entities', 'relationships', 'rejected_entities'
        
        Returns:
            The metrics dict that was logged
        """
        old_entities = old_result.get('entities', [])
        new_entities = new_result.get('entities', [])
        new_rejected = new_result.get('rejected_entities', [])
        new_skipped = new_result.get('skipped_entities', [])
        
        metrics = {
            "timestamp": datetime.utcnow().isoformat(),
            "document_id": str(document_id),
            "source_text_length": source_text_length,
            
            "old_entity_count": len(old_entities),
            "new_entity_count": len(new_entities),
            "new_rejected_count": len(new_rejected),
            "new_skipped_count": len(new_skipped),
            
            "old_relationship_count": len(old_result.get('relationships', [])),
            "new_relationship_count": len(new_result.get('relationships', [])),
            
            "old_type_distribution": cls.calculate_type_distribution(old_entities),
            "new_type_distribution": cls.calculate_type_distribution(new_entities),
            
            "overlap_ratio": cls.calculate_overlap(old_entities, new_entities),
            
            "precision_estimate": (
                len(new_entities) / (len(new_entities) + len(new_rejected))
                if (len(new_entities) + len(new_rejected)) > 0 else 1.0
            ),
            
            "rejection_types": [r.get('entity_type', 'UNKNOWN') for r in new_rejected],
            "skip_reasons": [s.get('reason', '') for s in new_skipped][:10],
        }
        
        shadow_logger.info(json.dumps(metrics))
        
        return metrics
    
    @classmethod
    def get_aggregate_metrics(cls, limit: int = 100) -> Dict[str, Any]:
        """
        Read recent shadow metrics and compute aggregates.
        
        Returns summary statistics for cutover decision.
        """
        if not SHADOW_LOG_PATH.exists():
            return {"error": "No shadow metrics logged yet", "count": 0}
        
        metrics_list = []
        with open(SHADOW_LOG_PATH, 'r') as f:
            for line in f:
                try:
                    metrics_list.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        
        if not metrics_list:
            return {"error": "No valid metrics found", "count": 0}
        
        recent = metrics_list[-limit:]
        
        avg_overlap = sum(m.get('overlap_ratio', 0) for m in recent) / len(recent)
        avg_precision = sum(m.get('precision_estimate', 0) for m in recent) / len(recent)
        avg_old_count = sum(m.get('old_entity_count', 0) for m in recent) / len(recent)
        avg_new_count = sum(m.get('new_entity_count', 0) for m in recent) / len(recent)
        
        return {
            "total_comparisons": len(metrics_list),
            "recent_sample_size": len(recent),
            "avg_overlap_ratio": round(avg_overlap, 3),
            "avg_precision_estimate": round(avg_precision, 3),
            "avg_old_entity_count": round(avg_old_count, 1),
            "avg_new_entity_count": round(avg_new_count, 1),
            "entity_count_delta_pct": round(
                (avg_new_count - avg_old_count) / avg_old_count * 100
                if avg_old_count > 0 else 0, 1
            ),
            "ready_for_cutover": avg_precision >= 0.93 and avg_overlap >= 0.85,
            "cutover_criteria": {
                "precision_target": 0.93,
                "precision_actual": round(avg_precision, 3),
                "overlap_target": 0.85,
                "overlap_actual": round(avg_overlap, 3),
            }
        }
