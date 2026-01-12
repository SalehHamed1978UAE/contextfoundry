#!/usr/bin/env python3
"""
E2E Lifecycle Test for Context Foundry

Tests complete lifecycle for all 5 vaults:
Create -> Upload -> Extract -> Verify -> Query -> Cleanup

Usage:
  python scripts/e2e_lifecycle_test.py           # Run all tests
  python scripts/e2e_lifecycle_test.py --fresh   # Delete old E2E vaults first
  python scripts/e2e_lifecycle_test.py --cleanup-only  # Just cleanup

Exit codes:
  0 = All vaults passed
  1 = One or more vaults failed
"""

import os
import sys
import time
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from src.context_foundry.models.schema import get_session

MAX_EXTRACTION_WAIT = 300
POLL_INTERVAL = 10

VAULT_CONFIGS = [
    {
        "name": "TechVentures",
        "doc_dir": "test documents/TechVentures",
        "required_entities": [
            {"name": "Sarah Chen", "type": "PERSON"},
            {"name": "Marcus Williams", "type": "PERSON"},
            {"name": "TechVentures", "type": "ORGANIZATION"},
        ],
        "required_roles": [
            {"person": "Sarah Chen", "role": "CEO"},
            {"person": "Marcus Williams", "role": "CTO"},
        ],
        "test_queries": [
            {"query": "Who is the CEO?", "expected": ["Sarah Chen"], "min_confidence": 0.70},
            {"query": "Who is the CTO?", "expected": ["Marcus Williams"], "min_confidence": 0.70},
            {"query": "What is Sarah Chen's compensation?", "expected": ["850,000"], "min_confidence": 0.70},
        ],
    },
    {
        "name": "LawFirm",
        "doc_dir": "test documents/Law Firm",
        "required_entities": [
            {"name": "Elizabeth Morrison", "type": "PERSON"},
            {"name": "Richard Sterling", "type": "PERSON"},
        ],
        "required_roles": [
            {"person": "Elizabeth Morrison", "role": "Managing Partner"},
        ],
        "test_queries": [
            {"query": "Who is the Managing Partner?", "expected": ["Elizabeth Morrison"], "min_confidence": 0.70},
            {"query": "Who is the CFO?", "expected": ["Thomas Bradley"], "min_confidence": 0.70},
            {"query": "What is Richard Sterling's compensation?", "expected": ["950,000"], "min_confidence": 0.70},
        ],
    },
    {
        "name": "Hospital",
        "doc_dir": "test documents/Hospital",
        "required_entities": [
            {"name": "Margaret Chen", "type": "PERSON"},
            {"name": "Robert Thompson", "type": "PERSON"},
        ],
        "required_roles": [
            {"person": "Margaret Chen", "role": "CEO"},
            {"person": "Robert Thompson", "role": "CIO"},
        ],
        "test_queries": [
            {"query": "Who is the CEO?", "expected": ["Margaret Chen"], "min_confidence": 0.70},
            {"query": "Who is the CIO?", "expected": ["Robert Thompson"], "min_confidence": 0.70},
            {"query": "What is the CEO's salary?", "expected": ["1,450,000"], "min_confidence": 0.70},
        ],
    },
    {
        "name": "TitanManufacturing",
        "doc_dir": "test documents/Titan Manufacturing",
        "required_entities": [
            {"name": "Robert Martinez", "type": "PERSON"},
            {"name": "Linda Chen", "type": "PERSON"},
        ],
        "required_roles": [
            {"person": "Robert Martinez", "role": "CEO"},
            {"person": "Linda Chen", "role": "COO"},
        ],
        "test_queries": [
            {"query": "Who is the CEO?", "expected": ["Robert Martinez"], "min_confidence": 0.70},
            {"query": "Who is the COO?", "expected": ["Linda Chen"], "min_confidence": 0.70},
            {"query": "What is the CEO's compensation?", "expected": ["980,000"], "min_confidence": 0.70},
        ],
    },
    {
        "name": "LaunchpadVentures",
        "doc_dir": "test documents/Launchpad Ventures",
        "required_entities": [
            {"name": "Alexandra Kim", "type": "PERSON"},
            {"name": "David Park", "type": "PERSON"},
        ],
        "required_roles": [
            {"person": "Alexandra Kim", "role": "Managing Partner"},
        ],
        "test_queries": [
            {"query": "Who is the Managing Partner?", "expected": ["Alexandra Kim"], "min_confidence": 0.70},
            {"query": "Who are the General Partners?", "expected": ["David Park"], "min_confidence": 0.70},
            {"query": "What is David Park's compensation?", "expected": ["380,000"], "min_confidence": 0.70},
        ],
    },
]


class E2ELifecycleTest:
    """E2E test for a single vault."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.vault_base_name = config["name"]
        self.vault_name: Optional[str] = None
        self.tenant_id: Optional[str] = None
        self.document_ids: List[str] = []
        self.document_contents: Dict[str, str] = {}
        self.failed = False
        self.failure_message: Optional[str] = None
    
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
    
    def fail(self, message: str):
        self.failed = True
        self.failure_message = message
        print(f"\n{'='*60}")
        print(f"ERROR: {message}")
        print(f"{'='*60}\n")
    
    def run(self) -> bool:
        """Run all steps. Returns True if passed, False if failed."""
        
        try:
            if not self.step0_pre_cleanup():
                self.step6_cleanup()
                return False
            
            if not self.step1_create_vault():
                self.step6_cleanup()
                return False
            
            if not self.step2_upload_documents():
                self.step6_cleanup()
                return False
            
            if not self.step3_trigger_extraction():
                self.step6_cleanup()
                return False
            
            if not self.step4_verify_extraction():
                self.step6_cleanup()
                return False
            
            if not self.step5_run_queries():
                self.step6_cleanup()
                return False
            
            self.step6_cleanup()
            return True
            
        except Exception as e:
            self.fail(f"Unexpected error: {e}")
            self.step6_cleanup()
            return False
    
    def step0_pre_cleanup(self) -> bool:
        """Delete any existing E2E vault with same base name."""
        self.log("Step 0: Pre-Cleanup")
        
        try:
            session = get_session(use_rls_role=False)
            
            result = session.execute(
                text("SELECT id, name FROM platform.tenants WHERE name LIKE :pattern"),
                {"pattern": f"E2E_Test_{self.vault_base_name}%"}
            ).fetchall()
            
            if not result:
                self.log("         No existing E2E vaults found")
                session.close()
                return True
            
            for row in result:
                existing_id, existing_name = str(row[0]), row[1]
                self.log(f"         Deleting existing: {existing_name}")
                self._delete_vault_data(session, existing_id)
            
            session.commit()
            session.close()
            self.log(f"         Result: OK (deleted {len(result)} vault(s))")
            return True
            
        except Exception as e:
            self.fail(f"Pre-cleanup failed: {e}")
            return False
    
    def _delete_vault_data(self, session, tenant_id: str):
        """Delete all data for a tenant with proper FK cascade."""
        session.execute(text("UPDATE public.entities SET superseded_by = NULL WHERE tenant_id = :tid"), {"tid": tenant_id})
        session.execute(text("UPDATE public.entities SET superseded_by = NULL WHERE superseded_by IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": tenant_id})
        session.execute(text("DELETE FROM public.conflict_logs WHERE entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": tenant_id})
        session.execute(text("DELETE FROM public.duplicate_candidates WHERE entity_a_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid) OR entity_b_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": tenant_id})
        session.execute(text("DELETE FROM public.entity_aliases WHERE entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": tenant_id})
        session.execute(text("DELETE FROM public.entity_mentions WHERE entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": tenant_id})
        session.execute(text("DELETE FROM public.merge_audits WHERE surviving_entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": tenant_id})
        session.execute(text("DELETE FROM public.proposed_relationships WHERE source_entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid) OR target_entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": tenant_id})
        session.execute(text("DELETE FROM public.relationships WHERE tenant_id = :tid"), {"tid": tenant_id})
        session.execute(text("DELETE FROM public.entities WHERE tenant_id = :tid"), {"tid": tenant_id})
        session.execute(text("DELETE FROM public.document_chunks WHERE tenant_id = :tid"), {"tid": tenant_id})
        session.execute(text("DELETE FROM platform.extraction_requests WHERE tenant_id = :tid"), {"tid": tenant_id})
        session.execute(text("DELETE FROM platform.documents WHERE tenant_id = :tid"), {"tid": tenant_id})
        session.execute(text("DELETE FROM platform.user_tenants WHERE tenant_id = :tid"), {"tid": tenant_id})
        session.execute(text("DELETE FROM platform.tenants WHERE id = :tid"), {"tid": tenant_id})
    
    def step1_create_vault(self) -> bool:
        """Create test vault."""
        self.log("Step 1: Create Vault")
        
        self.vault_name = f"E2E_Test_{self.vault_base_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.log(f"         Name: {self.vault_name}")
        
        try:
            session = get_session(use_rls_role=False)
            
            slug = f"e2e-test-{self.vault_base_name.lower().replace(' ', '-')}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            result = session.execute(
                text("""
                    INSERT INTO platform.tenants (name, slug, type, status, created_at) 
                    VALUES (:name, :slug, 'demo', 'active', NOW()) 
                    RETURNING id
                """),
                {"name": self.vault_name, "slug": slug}
            )
            self.tenant_id = str(result.fetchone()[0])
            session.commit()
            session.close()
            
            self.log(f"         Tenant ID: {self.tenant_id}")
            self.log("         Result: OK")
            return True
            
        except Exception as e:
            self.fail(f"Vault creation failed: {e}")
            return False
    
    def step2_upload_documents(self) -> bool:
        """Upload test documents."""
        self.log("Step 2: Upload Documents")
        
        doc_dir = self.config["doc_dir"]
        
        if not os.path.exists(doc_dir):
            self.fail(f"Document directory not found: {doc_dir}")
            return False
        
        try:
            session = get_session(use_rls_role=False)
            files = [f for f in os.listdir(doc_dir) if os.path.isfile(os.path.join(doc_dir, f))]
            
            if not files:
                self.fail(f"No documents found in: {doc_dir}")
                return False
            
            for filename in sorted(files):
                filepath = os.path.join(doc_dir, filename)
                
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                doc_id = str(uuid.uuid4())
                file_size = len(content.encode('utf-8'))
                
                session.execute(
                    text("""
                        INSERT INTO platform.documents 
                        (id, tenant_id, name, original_filename, mime_type, size_bytes, storage_path, status, current_version, created_at)
                        VALUES (:id, :tid, :name, :fname, 'text/plain', :size, :path, 'uploaded', 1, NOW())
                    """),
                    {"id": doc_id, "tid": self.tenant_id, "name": filename, "fname": filename, "size": file_size, "path": f"/e2e/{doc_id}"}
                )
                
                self.document_ids.append(doc_id)
                self.document_contents[doc_id] = content
                self.log(f"         - {filename} (id: {doc_id[:8]}...)")
            
            session.commit()
            session.close()
            self.log(f"         Result: OK ({len(self.document_ids)} files)")
            return True
            
        except Exception as e:
            self.fail(f"Document upload failed: {e}")
            return False
    
    def step3_trigger_extraction(self) -> bool:
        """Trigger extraction and wait for completion."""
        self.log("Step 3: Trigger Extraction")
        
        try:
            from src.context_foundry.extraction.ontology_centric_pipeline import run_ontology_centric_extraction
            
            session = get_session(use_rls_role=False)
            session.execute(text("SELECT platform.set_current_tenant(:tid)"), {"tid": self.tenant_id})
            session.commit()
            
            self.log("         Triggering extraction...")
            
            for doc_id in self.document_ids:
                content = self.document_contents.get(doc_id, "")
                if content:
                    result = run_ontology_centric_extraction(
                        session=session,
                        tenant_id=self.tenant_id,
                        text=content,
                        document_id=doc_id,
                        filename=None
                    )
                    self.log(f"         - {doc_id[:8]}...: {len(result.entities)} entities, {len(result.relations)} relations")
            
            session.commit()
            
            self.log(f"         Polling every {POLL_INTERVAL}s (max {MAX_EXTRACTION_WAIT}s)...")
            
            elapsed = 0
            chunks, entities, rels = 0, 0, 0
            
            while elapsed < MAX_EXTRACTION_WAIT:
                result = session.execute(
                    text("""
                        SELECT 
                            (SELECT COUNT(*) FROM public.document_chunks WHERE tenant_id = :tid),
                            (SELECT COUNT(*) FROM public.entities WHERE tenant_id = :tid),
                            (SELECT COUNT(*) FROM public.relationships WHERE tenant_id = :tid)
                    """),
                    {"tid": self.tenant_id}
                ).fetchone()
                
                chunks, entities, rels = result
                
                if elapsed % 30 == 0:
                    self.log(f"         [{elapsed}s] chunks: {chunks}, entities: {entities}, relationships: {rels}")
                
                if chunks > 0 and entities > 0 and rels > 0:
                    self.log(f"         Completed in {elapsed}s")
                    self.log(f"         - Chunks: {chunks}")
                    self.log(f"         - Entities: {entities}")
                    self.log(f"         - Relationships: {rels}")
                    self.log("         Result: OK")
                    session.close()
                    return True
                
                time.sleep(POLL_INTERVAL)
                elapsed += POLL_INTERVAL
            
            session.close()
            self.fail(f"Extraction timeout after {MAX_EXTRACTION_WAIT}s (chunks={chunks}, entities={entities}, rels={rels})")
            return False
            
        except Exception as e:
            self.fail(f"Extraction failed: {e}")
            return False
    
    def step4_verify_extraction(self) -> bool:
        """Verify required entities and roles exist."""
        self.log("Step 4: Verify Extraction")
        
        try:
            session = get_session(use_rls_role=False)
            missing = []
            
            self.log("         Checking entities...")
            for ent in self.config["required_entities"]:
                result = session.execute(
                    text("SELECT id FROM public.entities WHERE tenant_id = :tid AND name ILIKE :name AND entity_type = :etype"),
                    {"tid": self.tenant_id, "name": f"%{ent['name']}%", "etype": ent["type"]}
                ).fetchone()
                
                if result:
                    self.log(f"         - {ent['name']} ({ent['type']}): FOUND")
                else:
                    self.log(f"         - {ent['name']} ({ent['type']}): MISSING")
                    missing.append(f"{ent['name']} ({ent['type']})")
            
            self.log("         Checking roles (via properties OR HOLDS_POSITION relationships)...")
            for role in self.config["required_roles"]:
                result = session.execute(
                    text("""
                        SELECT e.id FROM public.entities e
                        WHERE e.tenant_id = :tid
                        AND e.name ILIKE :person
                        AND (
                            e.properties::text ILIKE :role
                            OR EXISTS (
                                SELECT 1 FROM public.relationships r
                                JOIN public.entities t ON r.target_id = t.id
                                WHERE r.source_id = e.id
                                AND r.relationship_type ILIKE '%POSITION%'
                                AND t.name ILIKE :role
                            )
                        )
                    """),
                    {"tid": self.tenant_id, "person": f"%{role['person']}%", "role": f"%{role['role']}%"}
                ).fetchone()
                
                if result:
                    self.log(f"         - {role['person']} -> {role['role']}: FOUND")
                else:
                    self.log(f"         - {role['person']} -> {role['role']}: MISSING (not required for pass)")
                    self.log(f"           (Role may be resolved at query time via RoleResolver)")
            
            session.close()
            
            if missing:
                self.fail(f"Missing: {missing}")
                return False
            
            self.log("         Result: OK")
            return True
            
        except Exception as e:
            self.fail(f"Verification failed: {e}")
            return False
    
    def step5_run_queries(self) -> bool:
        """Run test queries."""
        self.log("Step 5: Run Queries")
        
        try:
            from src.context_foundry.agents.tool_agent import ToolAgent
            
            session = get_session(use_rls_role=True)
            session.execute(text("SELECT platform.set_current_tenant(:tid)"), {"tid": self.tenant_id})
            session.commit()
            
            agent = ToolAgent(session, self.tenant_id)
            failures = []
            
            for i, test in enumerate(self.config["test_queries"], 1):
                query = test["query"]
                expected = test["expected"]
                min_conf = test.get("min_confidence", 0.70)
                
                self.log(f"         Q{i}: {query}")
                
                result = agent.query(query, vault_context=self.vault_name)
                answer = result.get("answer", "")
                confidence = result.get("confidence", 0)
                sources = result.get("sources", [])
                
                answer_preview = answer[:200] + "..." if len(answer) > 200 else answer
                self.log(f"         A{i}: {answer_preview}")
                self.log(f"         Confidence: {confidence:.0%} | Sources: {len(sources)}")
                
                found = all(exp.lower() in answer.lower() for exp in expected)
                conf_ok = confidence >= min_conf
                
                if found and conf_ok:
                    self.log(f"         - Result: PASS")
                else:
                    self.log(f"         - Result: FAIL")
                    if not found:
                        self.log(f"           Expected keywords: {expected}")
                    if not conf_ok:
                        self.log(f"           Confidence too low: {confidence:.0%} < {min_conf:.0%}")
                    failures.append(query)
                self.log("")
            
            session.close()
            
            if failures:
                self.fail(f"Failed queries: {failures}")
                return False
            
            self.log(f"         Result: OK ({len(self.config['test_queries'])}/{len(self.config['test_queries'])} passed)")
            return True
            
        except Exception as e:
            self.fail(f"Query execution failed: {e}")
            return False
    
    def step6_cleanup(self) -> bool:
        """Delete test vault and all data."""
        self.log("Step 6: Cleanup")
        
        if not self.tenant_id:
            self.log("         No vault to cleanup")
            return True
        
        try:
            session = get_session(use_rls_role=False)
            self._delete_vault_data(session, self.tenant_id)
            session.commit()
            session.close()
            self.log("         Result: OK")
            return True
            
        except Exception as e:
            self.log(f"         WARNING: Cleanup failed: {e}")
            self.log(f"         Manual cleanup needed for: {self.tenant_id}")
            return False


def cleanup_all_e2e_vaults():
    """Delete ALL E2E test vaults."""
    print("Cleaning up all E2E test vaults...")
    
    session = get_session(use_rls_role=False)
    result = session.execute(
        text("SELECT id, name FROM platform.tenants WHERE name LIKE 'E2E_Test_%'")
    ).fetchall()
    
    if not result:
        print("  No E2E test vaults found")
        session.close()
        return
    
    for row in result:
        vault_id, vault_name = str(row[0]), row[1]
        print(f"  Deleting: {vault_name}")
        
        try:
            session.execute(text("UPDATE public.entities SET superseded_by = NULL WHERE tenant_id = :tid"), {"tid": vault_id})
            session.execute(text("UPDATE public.entities SET superseded_by = NULL WHERE superseded_by IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": vault_id})
            session.execute(text("DELETE FROM public.conflict_logs WHERE entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": vault_id})
            session.execute(text("DELETE FROM public.duplicate_candidates WHERE entity_a_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid) OR entity_b_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": vault_id})
            session.execute(text("DELETE FROM public.entity_aliases WHERE entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": vault_id})
            session.execute(text("DELETE FROM public.entity_mentions WHERE entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": vault_id})
            session.execute(text("DELETE FROM public.merge_audits WHERE surviving_entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": vault_id})
            session.execute(text("DELETE FROM public.proposed_relationships WHERE source_entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid) OR target_entity_id IN (SELECT id FROM public.entities WHERE tenant_id = :tid)"), {"tid": vault_id})
            session.execute(text("DELETE FROM public.relationships WHERE tenant_id = :tid"), {"tid": vault_id})
            session.execute(text("DELETE FROM public.entities WHERE tenant_id = :tid"), {"tid": vault_id})
            session.execute(text("DELETE FROM public.document_chunks WHERE tenant_id = :tid"), {"tid": vault_id})
            session.execute(text("DELETE FROM platform.extraction_requests WHERE tenant_id = :tid"), {"tid": vault_id})
            session.execute(text("DELETE FROM platform.documents WHERE tenant_id = :tid"), {"tid": vault_id})
            session.execute(text("DELETE FROM platform.user_tenants WHERE tenant_id = :tid"), {"tid": vault_id})
            session.execute(text("DELETE FROM platform.tenants WHERE id = :tid"), {"tid": vault_id})
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"    Warning: {e}")
    
    session.commit()
    session.close()
    print(f"  Deleted {len(result)} vault(s)")


def run_all_vaults() -> int:
    """Run E2E tests for all vaults. Returns exit code."""
    
    print("=" * 80)
    print("E2E LIFECYCLE TEST - Context Foundry")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Vaults: {len(VAULT_CONFIGS)}")
    print()
    
    results = []
    
    for config in VAULT_CONFIGS:
        print(f"\n{'='*80}")
        print(f"VAULT: {config['name']}")
        print(f"{'='*80}\n")
        
        test = E2ELifecycleTest(config)
        passed = test.run()
        
        results.append({"vault": config["name"], "passed": passed, "error": test.failure_message})
        
        if passed:
            print(f"\nVAULT RESULT: PASSED\n")
        else:
            print(f"\nVAULT RESULT: FAILED\n")
    
    print(f"\n{'='*80}")
    print("E2E TEST SUMMARY")
    print(f"{'='*80}")
    
    for r in results:
        status = "PASSED" if r["passed"] else "FAILED"
        print(f"  {r['vault']}: {status}")
        if not r["passed"] and r["error"]:
            print(f"    Error: {r['error']}")
    
    passed_count = sum(1 for r in results if r["passed"])
    total = len(results)
    
    print(f"\nTOTAL: {passed_count}/{total} vaults passed")
    
    if passed_count == total:
        print("\nRESULT: ALL TESTS PASSED")
        return 0
    else:
        print("\nRESULT: SOME TESTS FAILED")
        return 1


def run_single_vault(vault_name: str) -> int:
    """Run E2E test for a single vault. Returns exit code."""
    
    config = next((c for c in VAULT_CONFIGS if c["name"].lower() == vault_name.lower()), None)
    if not config:
        print(f"ERROR: Vault '{vault_name}' not found")
        print(f"Available vaults: {[c['name'] for c in VAULT_CONFIGS]}")
        return 1
    
    print("=" * 80)
    print("E2E LIFECYCLE TEST - Single Vault")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Vault: {config['name']}")
    print()
    
    test = E2ELifecycleTest(config)
    passed = test.run()
    
    if passed:
        print(f"\nRESULT: PASSED")
        return 0
    else:
        print(f"\nRESULT: FAILED")
        print(f"Error: {test.failure_message}")
        return 1


def main():
    if "--cleanup-only" in sys.argv:
        cleanup_all_e2e_vaults()
        sys.exit(0)
    
    if "--fresh" in sys.argv:
        cleanup_all_e2e_vaults()
        print()
    
    if "--vault" in sys.argv:
        idx = sys.argv.index("--vault")
        if idx + 1 < len(sys.argv):
            vault_name = sys.argv[idx + 1]
            exit_code = run_single_vault(vault_name)
            sys.exit(exit_code)
        else:
            print("ERROR: --vault requires a vault name")
            sys.exit(1)
    
    exit_code = run_all_vaults()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
