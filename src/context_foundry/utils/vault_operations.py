"""Vault operations shared between web app and testing scripts.

This module contains vault management utilities that can be imported without
triggering Flask/web app startup code.
"""
import os
import shutil
import logging
import time
from uuid import UUID
from sqlalchemy import text

from src.context_foundry.models.schema import get_session

logger = logging.getLogger(__name__)

TENANT_STATUS_ACTIVE = 'active'
TENANT_STATUS_DELETING = 'deleting'
TENANT_STATUS_DELETED = 'deleted'


def is_tenant_available(tenant_id: str) -> bool:
    """Check if tenant is available for processing (not being deleted).
    
    Background workers should call this before processing any tenant-specific work.
    Returns False if tenant is marked as 'deleting' or doesn't exist.
    """
    db_session = get_session(use_rls_role=False)
    try:
        result = db_session.execute(
            text("SELECT status FROM platform.tenants WHERE id = :tid"),
            {'tid': str(tenant_id)}
        ).fetchone()
        
        if not result:
            return False
        
        return result.status == TENANT_STATUS_ACTIVE
    except Exception:
        return False
    finally:
        db_session.close()


def mark_tenant_deleting(tenant_id: str) -> bool:
    """Mark tenant as 'deleting' to prevent new work.
    
    This is the first step in graceful deletion - it blocks:
    - New extraction jobs from being queued
    - Gardener from processing this tenant
    - New queries from being executed
    
    Returns True if successfully marked, False if tenant doesn't exist.
    """
    db_session = get_session(use_rls_role=False)
    try:
        result = db_session.execute(
            text("UPDATE platform.tenants SET status = :status WHERE id = :tid"),
            {'status': TENANT_STATUS_DELETING, 'tid': str(tenant_id)}
        )
        db_session.commit()
        return result.rowcount > 0
    except Exception as e:
        db_session.rollback()
        logger.error(f"Failed to mark tenant as deleting: {e}")
        return False
    finally:
        db_session.close()


def cancel_pending_jobs(tenant_id: str) -> dict:
    """Cancel all pending extraction/learning jobs for a tenant.
    
    This should be called after marking tenant as 'deleting' to clean up
    any queued work that would conflict with deletion.
    """
    db_session = get_session(use_rls_role=False)
    cancelled = {}
    
    try:
        result = db_session.execute(
            text("""UPDATE platform.extraction_requests 
                    SET status = 'cancelled' 
                    WHERE tenant_id = :tid AND status IN ('pending', 'queued', 'processing')"""),
            {'tid': str(tenant_id)}
        )
        cancelled['extraction_requests'] = result.rowcount
        
        result = db_session.execute(
            text("""UPDATE public.extraction_jobs 
                    SET status = 'cancelled' 
                    WHERE tenant_id = :tid AND status IN ('pending', 'running')"""),
            {'tid': str(tenant_id)}
        )
        cancelled['extraction_jobs'] = result.rowcount
        
        result = db_session.execute(
            text("""UPDATE public.learning_queue 
                    SET status = 'cancelled' 
                    WHERE tenant_id = :tid AND status = 'pending'"""),
            {'tid': str(tenant_id)}
        )
        cancelled['learning_queue'] = result.rowcount
        
        db_session.commit()
        logger.info(f"[GracefulDelete] Cancelled jobs for tenant {tenant_id}: {cancelled}")
        return cancelled
    except Exception as e:
        db_session.rollback()
        logger.warning(f"Error cancelling jobs (non-fatal): {e}")
        return cancelled
    finally:
        db_session.close()


def wait_for_active_transactions(tenant_id: str, timeout_seconds: int = 10) -> bool:
    """Wait for active transactions on this tenant to complete.
    
    Polls for active locks/transactions and waits for them to finish.
    Returns True if clear, False if timeout reached.
    """
    db_session = get_session(use_rls_role=False)
    start_time = time.time()
    
    try:
        while time.time() - start_time < timeout_seconds:
            result = db_session.execute(
                text("""
                    SELECT COUNT(*) as active_count
                    FROM pg_stat_activity 
                    WHERE state = 'active' 
                    AND query LIKE :pattern
                    AND pid != pg_backend_pid()
                """),
                {'pattern': f'%{tenant_id}%'}
            ).fetchone()
            
            if result.active_count == 0:
                logger.info(f"[GracefulDelete] No active transactions for tenant {tenant_id}")
                return True
            
            logger.info(f"[GracefulDelete] Waiting for {result.active_count} active transactions...")
            time.sleep(0.5)
        
        logger.warning(f"[GracefulDelete] Timeout waiting for transactions on tenant {tenant_id}")
        return False
    except Exception as e:
        logger.warning(f"Error checking active transactions: {e}")
        return True
    finally:
        db_session.close()


def terminate_tenant_sessions(tenant_id: str) -> int:
    """Terminate any database sessions still referencing this tenant.
    
    This is a last resort if wait_for_active_transactions times out.
    Use with caution - it will kill active queries.
    """
    db_session = get_session(use_rls_role=False)
    try:
        result = db_session.execute(
            text("""
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity 
                WHERE state = 'active' 
                AND query LIKE :pattern
                AND pid != pg_backend_pid()
            """),
            {'pattern': f'%{tenant_id}%'}
        )
        terminated = result.rowcount
        db_session.commit()
        if terminated > 0:
            logger.warning(f"[GracefulDelete] Terminated {terminated} sessions for tenant {tenant_id}")
        return terminated
    except Exception as e:
        db_session.rollback()
        logger.error(f"Failed to terminate sessions: {e}")
        return 0
    finally:
        db_session.close()


def cleanup_orphaned_entities() -> dict:
    """Clean up entities whose tenant no longer exists.
    
    This handles the case where tenant deletion succeeded but entity deletion
    failed (e.g., due to FK constraints). Runs automatically on startup and
    can be called manually.
    
    Returns dict with counts of cleaned up items.
    """
    db_session = get_session(use_rls_role=False)
    cleaned = {}
    sp_counter = [0]
    
    def safe_delete(name: str, sql: str, params: dict) -> int:
        """Execute delete with savepoint to recover from errors."""
        sp_counter[0] += 1
        sp_name = f"sp_orphan_{sp_counter[0]}"
        try:
            db_session.execute(text(f"SAVEPOINT {sp_name}"))
            result = db_session.execute(text(sql), params)
            db_session.execute(text(f"RELEASE SAVEPOINT {sp_name}"))
            return result.rowcount
        except Exception as e:
            try:
                db_session.execute(text(f"ROLLBACK TO SAVEPOINT {sp_name}"))
                db_session.execute(text(f"RELEASE SAVEPOINT {sp_name}"))
            except:
                pass
            logger.debug(f"[OrphanCleanup] Skipped {name}: {type(e).__name__}")
            return 0
    
    try:
        orphaned_tenants = db_session.execute(text("""
            SELECT DISTINCT e.tenant_id, COUNT(*) as count
            FROM entities e
            LEFT JOIN platform.tenants t ON e.tenant_id = t.id
            WHERE t.id IS NULL
            GROUP BY e.tenant_id
        """)).fetchall()
        
        if not orphaned_tenants:
            logger.info("[OrphanCleanup] No orphaned entities found")
            return {'orphaned_tenants': 0, 'total_cleaned': 0}
        
        total_orphaned = sum(row.count for row in orphaned_tenants)
        logger.warning(f"[OrphanCleanup] Found {total_orphaned} orphaned entities across {len(orphaned_tenants)} deleted tenants")
        
        for row in orphaned_tenants:
            tenant_id = str(row.tenant_id)
            
            tables_to_clean = [
                # Nullify superseded_by references WITHIN the tenant
                ('superseded_by_nullify_self', "UPDATE entities SET superseded_by = NULL WHERE tenant_id = :tid"),
                # Nullify superseded_by references FROM OTHER tenants TO this tenant's entities
                ('superseded_by_nullify_refs', "UPDATE entities SET superseded_by = NULL WHERE superseded_by IN (SELECT id FROM entities WHERE tenant_id = :tid)"),
                ('relationships', "DELETE FROM relationships WHERE source_id IN (SELECT id FROM entities WHERE tenant_id = :tid) OR target_id IN (SELECT id FROM entities WHERE tenant_id = :tid)"),
                ('entity_mentions', "DELETE FROM entity_mentions WHERE entity_id IN (SELECT id FROM entities WHERE tenant_id = :tid)"),
                ('entity_aliases', "DELETE FROM entity_aliases WHERE entity_id IN (SELECT id FROM entities WHERE tenant_id = :tid)"),
                ('cf_entity_aliases', "DELETE FROM cf_entity_aliases WHERE entity_id::uuid IN (SELECT id FROM entities WHERE tenant_id = :tid)"),
                ('duplicate_candidates', "DELETE FROM duplicate_candidates WHERE entity_a_id IN (SELECT id FROM entities WHERE tenant_id = :tid) OR entity_b_id IN (SELECT id FROM entities WHERE tenant_id = :tid)"),
                ('conflict_logs', "DELETE FROM conflict_logs WHERE entity_id IN (SELECT id FROM entities WHERE tenant_id = :tid)"),
                ('user_feedback', "DELETE FROM user_feedback WHERE entity_id IN (SELECT id FROM entities WHERE tenant_id = :tid)"),
                ('merge_audits', "DELETE FROM merge_audits WHERE surviving_entity_id IN (SELECT id FROM entities WHERE tenant_id = :tid)"),
                ('inference_run_chunks', "DELETE FROM inference_run_chunks WHERE entity_id IN (SELECT id FROM entities WHERE tenant_id = :tid)"),
                ('learning_results', "DELETE FROM learning_results WHERE entity_id IN (SELECT id FROM entities WHERE tenant_id = :tid)"),
                ('proposed_relationships', "DELETE FROM proposed_relationships WHERE source_entity_id IN (SELECT id FROM entities WHERE tenant_id = :tid) OR target_entity_id IN (SELECT id FROM entities WHERE tenant_id = :tid)"),
                ('entities', "DELETE FROM entities WHERE tenant_id = :tid"),
            ]
            
            for table_name, sql in tables_to_clean:
                count = safe_delete(f"{table_name}:{tenant_id[:8]}", sql, {'tid': tenant_id})
                if count > 0:
                    cleaned[f"{table_name}:{tenant_id[:8]}"] = count
        
        db_session.commit()
        
        total_cleaned = sum(v for v in cleaned.values() if isinstance(v, int))
        if total_cleaned > 0:
            logger.info(f"[OrphanCleanup] Cleaned up {total_cleaned} orphaned records")
        
        return {
            'orphaned_tenants': len(orphaned_tenants),
            'total_cleaned': total_cleaned,
            'details': cleaned
        }
        
    except Exception as e:
        db_session.rollback()
        logger.error(f"[OrphanCleanup] Failed: {e}", exc_info=True)
        return {'error': str(e)}
    finally:
        db_session.close()


def graceful_delete_vault(vault_uuid: UUID, timeout_seconds: int = 10) -> dict:
    """Gracefully delete a vault with proper quiescing.
    
    This is the recommended way to delete a vault. It:
    1. Marks tenant as 'deleting' to block new work
    2. Cancels all pending extraction/learning jobs
    3. Waits for active transactions to complete
    4. Terminates stuck sessions if needed
    5. Performs the actual deletion
    6. Cleans up storage artifacts
    
    Returns dict with deletion status and counts.
    """
    tenant_id_str = str(vault_uuid)
    result = {
        'vault_id': tenant_id_str,
        'status': 'pending',
        'steps': {}
    }
    
    try:
        logger.info(f"[GracefulDelete] Starting deletion of vault {tenant_id_str}")
        
        if not mark_tenant_deleting(tenant_id_str):
            result['status'] = 'failed'
            result['error'] = 'Vault not found or already deleted'
            return result
        result['steps']['mark_deleting'] = 'success'
        logger.info(f"[GracefulDelete] Step 1: Marked tenant as 'deleting'")
        
        cancelled = cancel_pending_jobs(tenant_id_str)
        result['steps']['cancel_jobs'] = cancelled
        logger.info(f"[GracefulDelete] Step 2: Cancelled pending jobs: {cancelled}")
        
        time.sleep(0.5)
        
        if not wait_for_active_transactions(tenant_id_str, timeout_seconds):
            logger.warning(f"[GracefulDelete] Step 3: Timeout waiting, terminating sessions")
            terminated = terminate_tenant_sessions(tenant_id_str)
            result['steps']['terminate_sessions'] = terminated
            time.sleep(0.5)
        else:
            result['steps']['wait_transactions'] = 'clear'
        logger.info(f"[GracefulDelete] Step 3: Active transactions cleared")
        
        delete_result = delete_vault_and_artifacts(vault_uuid)
        result['steps']['delete_artifacts'] = delete_result
        result['status'] = 'success'
        logger.info(f"[GracefulDelete] Step 4: Deletion complete")
        
        return result
        
    except Exception as e:
        logger.error(f"[GracefulDelete] Failed: {e}", exc_info=True)
        result['status'] = 'failed'
        result['error'] = str(e)
        db_session = get_session(use_rls_role=False)
        try:
            db_session.execute(
                text("UPDATE platform.tenants SET status = :status WHERE id = :tid"),
                {'status': TENANT_STATUS_ACTIVE, 'tid': tenant_id_str}
            )
            db_session.commit()
        except:
            db_session.rollback()
        finally:
            db_session.close()
        return result


def delete_vault_and_artifacts(vault_uuid: UUID) -> dict:
    """Delete all artifacts associated with a vault/tenant.
    
    NOTE: Prefer using graceful_delete_vault() which handles quiescing.
    
    This is the low-level implementation that:
    - Deletes from all related tables in FK order
    - Uses savepoints to handle constraint failures
    - Cleans up filesystem storage
    
    Returns dict with counts of deleted items per table.
    """
    db_session = get_session(use_rls_role=False)
    deleted = {}
    
    sp_counter = [0]
    
    def safe_delete(name: str, sql: str, params: dict):
        """Execute delete with savepoint to recover from FK violations."""
        sp_counter[0] += 1
        sp_name = f"sp_delete_{sp_counter[0]}"
        try:
            db_session.execute(text(f"SAVEPOINT {sp_name}"))
            result = db_session.execute(text(sql), params)
            db_session.execute(text(f"RELEASE SAVEPOINT {sp_name}"))
            deleted[name] = result.rowcount
        except Exception as e:
            try:
                db_session.execute(text(f"ROLLBACK TO SAVEPOINT {sp_name}"))
                db_session.execute(text(f"RELEASE SAVEPOINT {sp_name}"))
            except:
                pass
            logger.warning(f"Could not delete from {name}: {e}")
            deleted[name] = 'skipped'
    
    try:
        tenant_id_str = str(vault_uuid)
        
        # First: Nullify superseded_by references WITHIN the tenant being deleted
        safe_delete('superseded_by_nullify_self',
            "UPDATE public.entities SET superseded_by = NULL WHERE tenant_id = :tid",
            {'tid': tenant_id_str})
        
        # Second: Nullify superseded_by references FROM OTHER tenants TO this tenant's entities
        # This fixes the FK constraint violation when deleting entities
        safe_delete('superseded_by_nullify_cross_tenant',
            """UPDATE public.entities SET superseded_by = NULL 
               WHERE superseded_by IN (SELECT id FROM public.entities WHERE tenant_id = :tid)""",
            {'tid': tenant_id_str})
        
        fk_subquery_deletes = [
            ('public.duplicate_candidates', 
             """DELETE FROM public.duplicate_candidates 
                WHERE entity_a_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)
                   OR entity_b_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"""),
            ('public.merge_audits',
             """DELETE FROM public.merge_audits 
                WHERE surviving_entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"""),
            ('public.conflict_logs',
             """DELETE FROM public.conflict_logs 
                WHERE entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"""),
            ('public.inference_run_chunks',
             """DELETE FROM public.inference_run_chunks 
                WHERE entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"""),
            ('public.user_feedback',
             """DELETE FROM public.user_feedback 
                WHERE entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)
                   OR tenant_id = :tid"""),
            ('public.learning_results (entity_refs)',
             """DELETE FROM public.learning_results 
                WHERE entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"""),
            ('public.conflict_logs',
             """DELETE FROM public.conflict_logs 
                WHERE entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)
                   OR relationship_id IN (SELECT id FROM public.relationships WHERE tenant_id = :tid)"""),
            ('platform.document_versions',
             """DELETE FROM platform.document_versions 
                WHERE document_id IN (SELECT id FROM platform.documents WHERE tenant_id = :tid)"""),
            ('platform.extraction_results',
             """DELETE FROM platform.extraction_results WHERE tenant_id = :tid"""),
            ('platform.extraction_requests',
             """DELETE FROM platform.extraction_requests 
                WHERE document_id IN (SELECT id FROM platform.documents WHERE tenant_id = :tid)
                   OR tenant_id = :tid"""),
        ]
        
        for table_name, sql in fk_subquery_deletes:
            safe_delete(table_name, sql, {'tid': tenant_id_str})
        
        public_tables = [
            'relationship_contexts',
            'user_feedback', 'learning_results', 'learning_tickets',
            'proposed_relationships', 'entity_mentions', 'entity_aliases', 
            'cf_entity_aliases',
            'relationships',
            'entities', 'entities_v2',
            'document_chunks', 'documents',
            'extraction_events', 'inference_runs', 'gardener_runs',
            'query_logs', 'pipeline_progress', 'cf_interaction_events',
            'cf_memory_versions', 'ontology_relations', 'ontology_relationship_types',
            'ontology_types', 'api_keys',
            'extraction_jobs', 'learning_queue',
            'query_gaps', 'learning_patterns',
            'ontology_candidates', 'pending_extractions'
        ]
        
        platform_tables = [
            'sync_jobs', 'source_connectors', 'documents', 'folders',
            'usage_events', 'usage_snapshots', 'tenant_quotas', 'api_keys'
        ]
        
        ontology_tables = [
            'canonical_relations', 'canonical_entity_types', 'reference_ontologies'
        ]
        
        for table in ontology_tables:
            safe_delete(f'ontology.{table}',
                f"DELETE FROM ontology.{table} WHERE tenant_id = :tid",
                {'tid': tenant_id_str})
        
        safe_delete('public.relationships (cross-tenant refs)',
            """DELETE FROM public.relationships 
               WHERE source_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)
                  OR target_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)""",
            {'tid': tenant_id_str})
        
        for table in public_tables:
            safe_delete(f'public.{table}',
                f"DELETE FROM public.{table} WHERE tenant_id = :tid",
                {'tid': tenant_id_str})
        
        for table in platform_tables:
            safe_delete(f'platform.{table}',
                f"DELETE FROM platform.{table} WHERE tenant_id = :tid",
                {'tid': tenant_id_str})
        
        safe_delete('platform.user_tenants',
            "DELETE FROM platform.user_tenants WHERE tenant_id = :tid",
            {'tid': tenant_id_str})
        
        safe_delete('platform.tenants',
            "DELETE FROM platform.tenants WHERE id = :tid",
            {'tid': tenant_id_str})
        
        db_session.commit()
        
        storage_path = os.path.join('storage', 'tenants', tenant_id_str)
        if os.path.exists(storage_path):
            try:
                shutil.rmtree(storage_path)
                deleted['filesystem'] = f'deleted: {storage_path}'
                logger.info(f"Deleted storage directory: {storage_path}")
            except Exception as e:
                logger.warning(f"Could not delete storage directory {storage_path}: {e}")
                deleted['filesystem'] = f'error: {e}'
        else:
            deleted['filesystem'] = 'no directory'
        
        return deleted
        
    except Exception as e:
        db_session.rollback()
        logger.error(f"Failed to delete vault artifacts: {e}", exc_info=True)
        raise
    finally:
        db_session.close()
