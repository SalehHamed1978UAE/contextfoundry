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
    
    def list_user_vaults(self, user_id: UUID) -> List[Dict[str, Any]]:
        """List all vaults (tenants) the user has access to via user_tenants join table."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT t.*, 
                           ut.role as user_role
                    FROM platform.tenants t
                    JOIN platform.user_tenants ut ON ut.tenant_id = t.id
                    WHERE ut.user_id = %s AND t.status = 'active'
                    ORDER BY t.updated_at DESC
                """, (str(user_id),))
                vaults = [dict(row) for row in cur.fetchall()]
                
                for vault in vaults:
                    vault['document_count'] = 0
                    try:
                        cur.execute("""
                            SELECT COUNT(*) FROM platform.documents WHERE tenant_id = %s
                        """, (str(vault['id']),))
                        vault['document_count'] = cur.fetchone()[0]
                    except Exception:
                        pass
                
                return vaults
    
    def user_has_vault_access(self, user_id: UUID, tenant_id: UUID) -> bool:
        """Check if user has access to a specific vault."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT 1 FROM platform.user_tenants
                    WHERE user_id = %s AND tenant_id = %s
                """, (str(user_id), str(tenant_id)))
                return cur.fetchone() is not None
    
    def get_user_vault_role(self, user_id: UUID, tenant_id: UUID) -> Optional[str]:
        """Get user's role for a specific vault (e.g., 'owner', 'admin', 'member')."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT role FROM platform.user_tenants
                    WHERE user_id = %s AND tenant_id = %s
                """, (str(user_id), str(tenant_id)))
                result = cur.fetchone()
                return result[0] if result else None
    
    def user_is_vault_owner(self, user_id: UUID, tenant_id: UUID) -> bool:
        """Check if user is the owner of a specific vault."""
        role = self.get_user_vault_role(user_id, tenant_id)
        return role == 'owner'
    
    def create_vault_for_user(
        self,
        user_id: UUID,
        name: str
    ) -> Dict[str, Any]:
        """
        Create a new vault and grant user access via user_tenants join table.
        
        Args:
            user_id: The user creating the vault
            name: Display name for the vault
            
        Returns:
            Created vault record
        """
        import re
        base_slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        slug = f"{base_slug}-{uuid4().hex[:8]}"
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    INSERT INTO platform.tenants (name, slug, type, settings)
                    VALUES (%s, %s, 'personal_sandbox', '{}')
                    RETURNING *
                """, (name, slug))
                
                tenant = dict(cur.fetchone())
                conn.commit()
                
                cur.execute("""
                    INSERT INTO platform.tenant_quotas (tenant_id)
                    VALUES (%s)
                    ON CONFLICT (tenant_id) DO NOTHING
                """, (tenant['id'],))
                conn.commit()
                
                cur.execute("""
                    INSERT INTO platform.user_tenants (user_id, tenant_id, role)
                    VALUES (%s, %s, 'owner')
                """, (str(user_id), tenant['id']))
                conn.commit()
                
                logger.info(f"Created vault '{name}' for user {user_id}")
                return tenant
    
    def get_vault_stats(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get document stats for a vault."""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_documents,
                        COUNT(*) FILTER (WHERE status = 'completed') as completed_documents,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed_documents,
                        MAX(updated_at) as last_activity
                    FROM platform.documents
                    WHERE tenant_id = %s
                """, (str(tenant_id),))
                return dict(cur.fetchone())
