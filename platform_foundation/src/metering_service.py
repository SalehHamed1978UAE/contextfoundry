"""
Metering Service - Usage Tracking & Quota Enforcement

Platform Foundation tracks token consumption and enforces quotas.
Brain reports consumption; Platform enforces limits.
"""

import logging
import os
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID, uuid4

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class MeteringService:
    """Tracks usage and enforces quotas."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        
    def _get_connection(self):
        return psycopg2.connect(self.database_url)
    
    def record_usage_event(
        self,
        tenant_id: UUID,
        event_type: str,
        tokens_consumed: int,
        user_id: Optional[UUID] = None,
        api_key_id: Optional[UUID] = None,
        document_id: Optional[UUID] = None,
        request_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Record a usage event for billing.
        
        Args:
            tenant_id: Tenant being charged
            event_type: extraction, query, or upload
            tokens_consumed: Number of tokens used
            user_id: Optional user who triggered
            api_key_id: Optional API key used
            document_id: Optional related document
            request_id: Optional extraction request
            metadata: Additional context
            
        Returns:
            Created usage event record
        """
        metadata = metadata or {}
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO platform.usage_events
                    (tenant_id, user_id, api_key_id, event_type, tokens_consumed,
                     document_id, request_id, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING *
                """, (
                    str(tenant_id),
                    str(user_id) if user_id else None,
                    str(api_key_id) if api_key_id else None,
                    event_type,
                    tokens_consumed,
                    str(document_id) if document_id else None,
                    str(request_id) if request_id else None,
                    psycopg2.extras.Json(metadata)
                ))
                
                event = dict(cur.fetchone())
                conn.commit()
                
                logger.info(f"Recorded usage event: {event_type} - {tokens_consumed} tokens for tenant {tenant_id}")
                return event
    
    def get_daily_usage(self, tenant_id: UUID) -> Dict[str, int]:
        """Get today's usage for a tenant."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM platform.get_tenant_daily_usage(%s)
                """, (str(tenant_id),))
                result = cur.fetchone()
                return {
                    "extraction_tokens": result['extraction_tokens'],
                    "query_tokens": result['query_tokens']
                } if result else {"extraction_tokens": 0, "query_tokens": 0}
    
    def get_tenant_quotas(self, tenant_id: UUID) -> Optional[Dict[str, Any]]:
        """Get quota limits for a tenant."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM platform.tenant_quotas WHERE tenant_id = %s
                """, (str(tenant_id),))
                result = cur.fetchone()
                return dict(result) if result else None
    
    def check_quota(
        self,
        tenant_id: UUID,
        event_type: str,
        tokens_needed: int
    ) -> Tuple[bool, str]:
        """
        Check if tenant has quota for an operation.
        
        Returns:
            Tuple of (allowed: bool, reason: str)
        """
        quotas = self.get_tenant_quotas(tenant_id)
        if not quotas:
            return False, "Tenant quotas not configured"
        
        usage = self.get_daily_usage(tenant_id)
        
        if event_type == "extraction":
            current = usage.get("extraction_tokens", 0)
            limit = quotas.get("extraction_tokens_daily", 0)
            if current + tokens_needed > limit:
                return False, f"Daily extraction quota exceeded: {current}/{limit}"
                
        elif event_type == "query":
            current = usage.get("query_tokens", 0)
            limit = quotas.get("query_tokens_daily", 0)
            if current + tokens_needed > limit:
                return False, f"Daily query quota exceeded: {current}/{limit}"
        
        return True, "Within quota"
    
    def update_quotas(
        self,
        tenant_id: UUID,
        extraction_tokens_daily: Optional[int] = None,
        query_tokens_daily: Optional[int] = None,
        document_limit: Optional[int] = None,
        storage_gb_limit: Optional[int] = None,
        api_rate_limit_per_min: Optional[int] = None
    ) -> bool:
        """Update tenant quotas."""
        updates = []
        params = []
        
        if extraction_tokens_daily is not None:
            updates.append("extraction_tokens_daily = %s")
            params.append(extraction_tokens_daily)
        if query_tokens_daily is not None:
            updates.append("query_tokens_daily = %s")
            params.append(query_tokens_daily)
        if document_limit is not None:
            updates.append("document_limit = %s")
            params.append(document_limit)
        if storage_gb_limit is not None:
            updates.append("storage_gb_limit = %s")
            params.append(storage_gb_limit)
        if api_rate_limit_per_min is not None:
            updates.append("api_rate_limit_per_min = %s")
            params.append(api_rate_limit_per_min)
            
        if not updates:
            return False
            
        updates.append("updated_at = NOW()")
        params.append(str(tenant_id))
        
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"""
                    UPDATE platform.tenant_quotas 
                    SET {', '.join(updates)}
                    WHERE tenant_id = %s
                """, params)
                conn.commit()
                return cur.rowcount > 0
    
    def create_daily_snapshot(self, tenant_id: UUID) -> Dict[str, Any]:
        """Create daily usage snapshot for a tenant."""
        usage = self.get_daily_usage(tenant_id)
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT COUNT(*) as doc_count,
                           COALESCE(SUM(size_bytes), 0) as storage_used
                    FROM platform.documents
                    WHERE tenant_id = %s
                """, (str(tenant_id),))
                doc_stats = cur.fetchone()
                
                cur.execute("""
                    INSERT INTO platform.usage_snapshots
                    (tenant_id, snapshot_date, extraction_tokens_used, query_tokens_used,
                     documents_count, storage_bytes_used)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (tenant_id, snapshot_date) 
                    DO UPDATE SET 
                        extraction_tokens_used = EXCLUDED.extraction_tokens_used,
                        query_tokens_used = EXCLUDED.query_tokens_used,
                        documents_count = EXCLUDED.documents_count,
                        storage_bytes_used = EXCLUDED.storage_bytes_used
                    RETURNING *
                """, (
                    str(tenant_id),
                    date.today(),
                    usage.get("extraction_tokens", 0),
                    usage.get("query_tokens", 0),
                    doc_stats['doc_count'],
                    doc_stats['storage_used']
                ))
                
                snapshot = dict(cur.fetchone())
                conn.commit()
                return snapshot
    
    def get_usage_history(
        self,
        tenant_id: UUID,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get usage history snapshots."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM platform.usage_snapshots
                    WHERE tenant_id = %s
                      AND snapshot_date >= CURRENT_DATE - INTERVAL '%s days'
                    ORDER BY snapshot_date DESC
                """, (str(tenant_id), days))
                return [dict(row) for row in cur.fetchall()]
