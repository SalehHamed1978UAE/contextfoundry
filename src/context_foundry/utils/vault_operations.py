"""Vault operations shared between web app and testing scripts.

This module contains vault management utilities that can be imported without
triggering Flask/web app startup code.
"""
import os
import shutil
import logging
from uuid import UUID
from sqlalchemy import text

from src.context_foundry.models.schema import get_session

logger = logging.getLogger(__name__)


def delete_vault_and_artifacts(vault_uuid: UUID) -> dict:
    """Delete all artifacts associated with a vault/tenant.
    
    This is the canonical implementation used by both:
    - web_app.py (UI/API vault deletion)
    - E2E test scripts (cleanup between test runs)
    
    Returns dict with counts of deleted items per table.
    """
    db_session = get_session(use_rls_role=False)
    deleted = {}
    
    try:
        tenant_id_str = str(vault_uuid)
        
        public_tables = [
            'relationships', 'relationship_contexts', 'proposed_relationships',
            'entity_mentions', 'entity_aliases', 'cf_entity_aliases',
            'entities', 'entities_v2', 'document_chunks', 'documents',
            'extraction_events', 'inference_runs', 'gardener_runs',
            'query_logs', 'pipeline_progress', 'cf_interaction_events',
            'cf_memory_versions', 'ontology_relations', 'ontology_relationship_types',
            'ontology_types', 'api_keys'
        ]
        
        platform_tables = [
            'extraction_results', 'extraction_requests', 'sync_jobs',
            'source_connectors', 'documents', 'folders',
            'usage_events', 'usage_snapshots', 'tenant_quotas', 'api_keys'
        ]
        
        ontology_tables = [
            'canonical_relations', 'canonical_entity_types', 'reference_ontologies'
        ]
        
        for table in ontology_tables:
            try:
                result = db_session.execute(
                    text(f"DELETE FROM ontology.{table} WHERE tenant_id = :tid"),
                    {'tid': tenant_id_str}
                )
                deleted[f'ontology.{table}'] = result.rowcount
            except Exception as e:
                db_session.rollback()
                logger.warning(f"Could not delete from ontology.{table}: {e}")
                deleted[f'ontology.{table}'] = 'skipped'
        
        for table in public_tables:
            try:
                result = db_session.execute(
                    text(f"DELETE FROM public.{table} WHERE tenant_id = :tid"),
                    {'tid': tenant_id_str}
                )
                deleted[f'public.{table}'] = result.rowcount
            except Exception as e:
                db_session.rollback()
                logger.warning(f"Could not delete from public.{table}: {e}")
                deleted[f'public.{table}'] = 'skipped'
        
        for table in platform_tables:
            try:
                result = db_session.execute(
                    text(f"DELETE FROM platform.{table} WHERE tenant_id = :tid"),
                    {'tid': tenant_id_str}
                )
                deleted[f'platform.{table}'] = result.rowcount
            except Exception as e:
                db_session.rollback()
                logger.warning(f"Could not delete from platform.{table}: {e}")
                deleted[f'platform.{table}'] = 'skipped'
        
        result = db_session.execute(
            text("DELETE FROM platform.user_tenants WHERE tenant_id = :tid"),
            {'tid': tenant_id_str}
        )
        deleted['platform.user_tenants'] = result.rowcount
        
        result = db_session.execute(
            text("DELETE FROM platform.tenants WHERE id = :tid"),
            {'tid': tenant_id_str}
        )
        deleted['platform.tenants'] = result.rowcount
        
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
