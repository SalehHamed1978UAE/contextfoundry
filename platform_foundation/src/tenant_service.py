"""
Tenant Service - Multi-tenancy Management

Platform Foundation owns tenant lifecycle.
"""

import logging
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID, uuid4

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


class TenantService:
    """Manages multi-tenant isolation and tenant lifecycle."""
    
    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or os.environ.get("DATABASE_URL")
        
    def _get_connection(self):
        return psycopg2.connect(self.database_url)
    
    def create_tenant(
        self,
        name: str,
        slug: str,
        tenant_type: str = "personal_sandbox",
        settings: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a new tenant.
        
        Args:
            name: Display name for the tenant
            slug: URL-safe unique identifier
            tenant_type: One of opco_production, opco_pilot, personal_sandbox, demo, qdata_internal
            settings: Optional JSON settings
            
        Returns:
            Created tenant record
        """
        settings = settings or {}
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO platform.tenants (name, slug, type, settings)
                    VALUES (%s, %s, %s, %s)
                    RETURNING *
                """, (name, slug, tenant_type, psycopg2.extras.Json(settings)))
                
                tenant = dict(cur.fetchone())
                conn.commit()
                
                cur.execute("""
                    INSERT INTO platform.tenant_quotas (tenant_id)
                    VALUES (%s)
                """, (tenant['id'],))
                conn.commit()
                
                logger.info(f"Created tenant: {name} ({slug})")
                return tenant
    
    def get_tenant(self, tenant_id: UUID) -> Optional[Dict[str, Any]]:
        """Get tenant by ID."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM platform.tenants WHERE id = %s
                """, (str(tenant_id),))
                result = cur.fetchone()
                return dict(result) if result else None
    
    def get_tenant_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Get tenant by slug."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM platform.tenants WHERE slug = %s
                """, (slug,))
                result = cur.fetchone()
                return dict(result) if result else None
    
    def list_tenants(self, status: str = "active") -> List[Dict[str, Any]]:
        """List tenants by status."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT * FROM platform.tenants WHERE status = %s ORDER BY name
                """, (status,))
                return [dict(row) for row in cur.fetchall()]
    
    def suspend_tenant(self, tenant_id: UUID) -> bool:
        """Suspend a tenant."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE platform.tenants 
                    SET status = 'suspended', updated_at = NOW()
                    WHERE id = %s
                """, (str(tenant_id),))
                conn.commit()
                updated = cur.rowcount > 0
                if updated:
                    logger.info(f"Suspended tenant: {tenant_id}")
                return updated
    
    def set_tenant_context(self, conn, tenant_id: UUID, role: str = "user"):
        """Set tenant context for RLS in a connection."""
        with conn.cursor() as cur:
            cur.execute("SELECT platform.set_current_tenant(%s)", (str(tenant_id),))
            cur.execute("SELECT platform.set_current_user_role(%s)", (role,))
