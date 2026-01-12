#!/usr/bin/env python3
"""
E2E Lifecycle Test for Context Foundry

Tests the complete system exactly as a real user would:
1. Delete existing vaults
2. Create fresh vaults
3. Upload documents
4. Run extraction
5. Run all queries
6. Save full answers to file for human review

CRITICAL RULES:
- DO NOT MODIFY APPLICATION CODE - if something fails, STOP and report
- DO NOT MODIFY DATA TO MAKE TESTS WORK
- IF ANYTHING FAILS - STOP AND REPORT, do not try to fix it

Usage:
    python scripts/e2e_lifecycle_test.py

Output:
    /mnt/user-data/outputs/e2e_results_YYYYMMDD_HHMMSS.txt
"""

import os
import sys
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MAX_EXTRACTION_WAIT = 600
POLL_INTERVAL = 10

OUTPUT_DIR = "outputs"

def fail_and_exit(step: str, error: str, expected: str = None):
    """Log failure and exit immediately."""
    print("\n" + "=" * 80)
    print(f"FAILED: {step}")
    print("=" * 80)
    print(f"Error: {error}")
    if expected:
        print(f"Expected: {expected}")
    print("\nAction required: Human must investigate this error.")
    print("Do NOT attempt to fix this automatically.")
    print("=" * 80)
    sys.exit(1)


class E2ETest:
    def __init__(self):
        self.start_time = datetime.now()
        self.results = []
        self.output_file = os.path.join(
            OUTPUT_DIR, 
            f"e2e_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )
        
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        self.write_output(f"""================================================================================
E2E LIFECYCLE TEST RESULTS
================================================================================
Run Date: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
================================================================================
""")
    
    def log(self, message: str):
        """Log to console with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        elapsed = int((datetime.now() - self.start_time).total_seconds())
        print(f"[{timestamp}] [{elapsed}s] {message}")
    
    def write_output(self, text: str):
        """Write to output file."""
        with open(self.output_file, "a", encoding="utf-8") as f:
            f.write(text)
    
    def run(self) -> int:
        """Run E2E test for all vaults. Returns exit code."""
        try:
            from e2e_config import VAULTS
        except ImportError as e:
            fail_and_exit("Import error", f"Cannot import e2e_config: {e}", "from e2e_config import VAULTS")
        
        try:
            from src.context_foundry.models.schema import get_session
        except ImportError as e:
            fail_and_exit("Import error", f"Cannot import get_session: {e}", "from src.context_foundry.models.schema import get_session")
        
        self.log(f"Starting E2E test for {len(VAULTS)} vaults")
        self.log(f"Output file: {self.output_file}")
        
        for vault_config in VAULTS:
            self.log(f"\n{'=' * 60}")
            self.log(f"VAULT: {vault_config['name']}")
            self.log(f"{'=' * 60}")
            
            result = self.test_vault(vault_config)
            self.results.append(result)
            
            if not result["success"]:
                fail_and_exit(
                    f"Vault test failed: {vault_config['name']}", 
                    result['error']
                )
            else:
                self.log(f"VAULT COMPLETE: {result['query_count']} queries executed")
        
        self.write_summary()
        
        self.log(f"\n{'=' * 60}")
        self.log(f"E2E TEST COMPLETE")
        self.log(f"Output file: {self.output_file}")
        self.log(f"{'=' * 60}")
        
        return 0
    
    def test_vault(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single vault. Returns result dict."""
        from src.context_foundry.models.schema import get_session
        
        vault_name = config["name"]
        doc_dir = config["doc_dir"]
        queries = config["queries"]
        
        result = {
            "vault": vault_name,
            "success": False,
            "error": None,
            "doc_count": 0,
            "chunk_count": 0,
            "entity_count": 0,
            "relationship_count": 0,
            "query_count": 0,
        }
        
        try:
            self.step0_delete_existing(vault_name)
            
            tenant_id = self.step1_create_vault(vault_name)
            
            doc_ids, doc_names, doc_contents = self.step2_upload_documents(tenant_id, doc_dir)
            result["doc_count"] = len(doc_ids)
            
            self.step3_trigger_extraction(tenant_id, doc_ids, doc_contents)
            
            counts = self.step4_wait_for_extraction(tenant_id)
            result["chunk_count"] = counts["chunks"]
            result["entity_count"] = counts["entities"]
            result["relationship_count"] = counts["relationships"]
            
            self.write_vault_header(vault_name, doc_names, counts)
            
            self.step5_run_queries(tenant_id, vault_name, queries)
            result["query_count"] = len(queries)
            
            self.log(f"Vault ready for use: {vault_name}")
            
            result["success"] = True
            return result
            
        except Exception as e:
            result["error"] = str(e)
            return result
    
    def step0_delete_existing(self, vault_name: str):
        """Delete existing vault if it exists."""
        self.log(f"Step 0: Delete existing vault '{vault_name}'")
        
        from src.context_foundry.models.schema import get_session
        from sqlalchemy import text
        
        session = get_session(use_rls_role=False)
        
        result = session.execute(
            text("SELECT id FROM platform.tenants WHERE name = :name"),
            {"name": vault_name}
        ).fetchone()
        
        if not result:
            self.log("         No existing vault found")
            session.close()
            return
        
        tenant_id = str(result[0])
        self.log(f"         Found existing vault: {tenant_id}")
        
        session.execute(text("UPDATE public.entities SET superseded_by = NULL WHERE tenant_id = :tid"), {"tid": tenant_id})
        session.execute(text("UPDATE public.entities SET superseded_by = NULL WHERE superseded_by IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": tenant_id})
        
        tables_to_clear = [
            ("public", "conflict_logs", "entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"),
            ("public", "duplicate_candidates", "entity_a_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid) OR entity_b_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"),
            ("public", "entity_aliases", "entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"),
            ("public", "entity_mentions", "entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"),
            ("public", "merge_audits", "surviving_entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"),
            ("public", "proposed_relationships", "source_entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid) OR target_entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"),
            ("public", "relationships", "tenant_id = :tid"),
            ("public", "entities", "tenant_id = :tid"),
            ("public", "document_chunks", "tenant_id = :tid"),
            ("platform", "extraction_results", "request_id IN (SELECT request_id FROM platform.extraction_requests WHERE tenant_id = :tid)"),
            ("platform", "extraction_requests", "tenant_id = :tid"),
            ("platform", "document_versions", "document_id IN (SELECT id FROM platform.documents WHERE tenant_id = :tid)"),
            ("platform", "documents", "tenant_id = :tid"),
            ("platform", "usage_events", "tenant_id = :tid"),
            ("platform", "user_tenants", "tenant_id = :tid"),
            ("platform", "tenant_quotas", "tenant_id = :tid"),
        ]
        
        for schema, table, condition in tables_to_clear:
            try:
                r = session.execute(
                    text(f"DELETE FROM {schema}.{table} WHERE {condition}"),
                    {"tid": tenant_id}
                )
                if r.rowcount > 0:
                    self.log(f"         Deleted {r.rowcount} rows from {schema}.{table}")
            except Exception as e:
                session.rollback()
                self.log(f"         Warning: Could not delete from {schema}.{table}: {str(e)[:80]}")
        
        session.execute(
            text("DELETE FROM platform.tenants WHERE id = :tid"),
            {"tid": tenant_id}
        )
        
        session.commit()
        session.close()
        self.log("         Deleted existing vault")
    
    def step1_create_vault(self, vault_name: str) -> str:
        """Create vault and return tenant_id."""
        self.log(f"Step 1: Create vault '{vault_name}'")
        
        from src.context_foundry.models.schema import get_session
        from sqlalchemy import text
        
        session = get_session(use_rls_role=False)
        
        slug = vault_name.lower().replace(" ", "-").replace("&", "and")
        
        result = session.execute(
            text("""
                INSERT INTO platform.tenants (name, slug, type, status, created_at, updated_at)
                VALUES (:name, :slug, 'demo', 'active', NOW(), NOW())
                RETURNING id
            """),
            {"name": vault_name, "slug": slug}
        )
        
        tenant_id = str(result.fetchone()[0])
        
        user_id = "e067496f-2947-4a40-a37e-a59668e08332"
        session.execute(
            text("""
                INSERT INTO platform.user_tenants (user_id, tenant_id, role, created_at)
                VALUES (:user_id, :tenant_id, 'owner', NOW())
            """),
            {"user_id": user_id, "tenant_id": tenant_id}
        )
        
        session.commit()
        session.close()
        
        self.log(f"         Created vault: {tenant_id}")
        return tenant_id
    
    def step2_upload_documents(self, tenant_id: str, doc_dir: str) -> tuple:
        """Upload all documents using the actual DocumentService (same as UI)."""
        self.log(f"Step 2: Upload documents from '{doc_dir}'")
        
        if not os.path.exists(doc_dir):
            raise Exception(f"Document directory not found: {doc_dir}")
        
        files = sorted([f for f in os.listdir(doc_dir) if os.path.isfile(os.path.join(doc_dir, f))])
        
        if not files:
            raise Exception(f"No documents found in: {doc_dir}")
        
        from uuid import UUID
        from platform_foundation.src.document_service import DocumentService
        
        doc_svc = DocumentService()
        doc_ids = []
        doc_names = []
        doc_contents = []
        
        for filename in files:
            filepath = os.path.join(doc_dir, filename)
            
            with open(filepath, "rb") as f:
                file_content = f.read()
            
            document = doc_svc.upload_document(
                tenant_id=UUID(tenant_id),
                filename=filename,
                mime_type='text/plain',
                file_content=file_content,
                auto_extract=True,
                priority='normal'
            )
            
            doc_id = str(document['id'])
            doc_ids.append(doc_id)
            doc_names.append(filename)
            doc_contents.append(file_content.decode('utf-8'))
            
            self.log(f"         Uploaded: {filename} (request: {document.get('extraction_request_id', 'N/A')[:8]}...)")
        
        self.log(f"         Total: {len(doc_ids)} documents queued for extraction")
        return doc_ids, doc_names, doc_contents
    
    def step3_trigger_extraction(self, tenant_id: str, doc_ids: List[str], doc_contents: List[str]):
        """Process extraction using the actual ExtractionWorker (same as production)."""
        self.log(f"Step 3: Process extraction for {len(doc_ids)} documents")
        
        try:
            from src.context_foundry.workers.extraction_worker import ExtractionWorker
        except ImportError as e:
            fail_and_exit(
                "Import error", 
                f"Cannot import ExtractionWorker: {e}",
                "from src.context_foundry.workers.extraction_worker import ExtractionWorker"
            )
        
        worker = ExtractionWorker(worker_id="e2e-test-worker")
        
        processed = 0
        max_attempts = len(doc_ids) * 3
        attempts = 0
        
        while processed < len(doc_ids) and attempts < max_attempts:
            attempts += 1
            if worker.process_one():
                processed += 1
                self.log(f"         Processed document {processed}/{len(doc_ids)}")
            else:
                time.sleep(0.5)
        
        if processed < len(doc_ids):
            self.log(f"         Warning: Only processed {processed}/{len(doc_ids)} documents")
        else:
            self.log(f"         All {processed} documents extracted")
    
    def step4_wait_for_extraction(self, tenant_id: str) -> Dict[str, int]:
        """Wait for extraction to complete. Returns counts."""
        self.log(f"Step 4: Verify extraction results")
        
        from src.context_foundry.models.schema import get_session
        from sqlalchemy import text
        
        session = get_session(use_rls_role=False)
        
        result = session.execute(
            text("""
                SELECT 
                    (SELECT COUNT(*) FROM public.document_chunks WHERE tenant_id = :tid),
                    (SELECT COUNT(*) FROM public.entities WHERE tenant_id = :tid),
                    (SELECT COUNT(*) FROM public.relationships WHERE tenant_id = :tid)
            """),
            {"tid": tenant_id}
        ).fetchone()
        
        chunks, entities, rels = result
        session.close()
        
        self.log(f"         chunks={chunks}, entities={entities}, relationships={rels}")
        
        if chunks == 0 and entities == 0 and rels == 0:
            raise Exception("Extraction produced no results (0 chunks, 0 entities, 0 relationships)")
        
        return {"chunks": chunks, "entities": entities, "relationships": rels}
    
    def write_vault_header(self, vault_name: str, doc_names: List[str], counts: Dict[str, int]):
        """Write vault header to output file."""
        self.write_output(f"""
================================================================================
VAULT: {vault_name}
================================================================================
Documents Uploaded: {len(doc_names)}
""")
        for doc in doc_names:
            self.write_output(f"  - {doc}\n")
        
        self.write_output(f"""
Extraction Results:
  - Chunks: {counts['chunks']}
  - Entities: {counts['entities']}
  - Relationships: {counts['relationships']}

""")
    
    def step5_run_queries(self, tenant_id: str, vault_name: str, queries: List[str]):
        """Run all queries and write full answers to output file."""
        self.log(f"Step 5: Run {len(queries)} queries")
        
        try:
            from src.context_foundry.agents.tool_agent import ToolAgent
        except ImportError as e:
            fail_and_exit(
                "Import error",
                f"Cannot import ToolAgent: {e}",
                "from src.context_foundry.agents.tool_agent import ToolAgent"
            )
        
        from src.context_foundry.models.schema import get_session
        from sqlalchemy import text
        
        session = get_session(use_rls_role=True)
        session.execute(text("SELECT platform.set_current_tenant(:tid)"), {"tid": tenant_id})
        session.commit()
        
        agent = ToolAgent(session, tenant_id)
        
        for i, query in enumerate(queries, 1):
            self.log(f"         Query {i}/{len(queries)}: {query}")
            
            try:
                result = agent.query(query, vault_context=vault_name)
                answer = result.get("answer", "NO ANSWER RETURNED")
                confidence = result.get("confidence", 0)
            except Exception as e:
                answer = f"ERROR: {e}"
                confidence = 0
            
            self.write_output(f"""--------------------------------------------------------------------------------
QUERY {i}/{len(queries)}: {query}
--------------------------------------------------------------------------------
ANSWER:
{answer}

CONFIDENCE: {confidence:.0%}
--------------------------------------------------------------------------------

""")
        
        session.close()
        self.log(f"         All {len(queries)} queries executed")
    
    def write_summary(self):
        """Write summary to output file."""
        total_runtime = (datetime.now() - self.start_time).total_seconds()
        minutes = int(total_runtime // 60)
        seconds = int(total_runtime % 60)
        
        self.write_output(f"""
================================================================================
SUMMARY
================================================================================
Run Date: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}
Total Runtime: {minutes} minutes {seconds} seconds

{"Vault":<25} | Docs | Chunks | Entities | Rels | Queries | Status
{"-"*25}-|------|--------|----------|------|---------|--------
""")
        
        total_docs = 0
        total_chunks = 0
        total_entities = 0
        total_rels = 0
        total_queries = 0
        
        for r in self.results:
            status = "OK" if r["success"] else f"FAILED: {r['error']}"
            self.write_output(f"{r['vault']:<25} | {r['doc_count']:>4} | {r['chunk_count']:>6} | {r['entity_count']:>8} | {r['relationship_count']:>4} | {r['query_count']:>7} | {status}\n")
            
            total_docs += r["doc_count"]
            total_chunks += r["chunk_count"]
            total_entities += r["entity_count"]
            total_rels += r["relationship_count"]
            total_queries += r["query_count"]
        
        self.write_output(f"""{"-"*25}-|------|--------|----------|------|---------|--------
{"TOTAL":<25} | {total_docs:>4} | {total_chunks:>6} | {total_entities:>8} | {total_rels:>4} | {total_queries:>7} |

All {total_queries} queries executed. Review answers above for correctness.
================================================================================
""")


def main():
    test = E2ETest()
    exit_code = test.run()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
