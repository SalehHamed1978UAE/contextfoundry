#!/usr/bin/env python3
"""
Standard Vault Test Runner

Complete lifecycle test for any vault:
1. Delete existing vault (by exact name)
2. Create new vault via API
3. Upload all documents
4. Wait for extraction to complete
5. Run question bank test (if available)
6. Keep vault for manual inspection

Usage:
    python scripts/standard_vault_test.py "Manus Healthtec"
    python scripts/standard_vault_test.py "ClaudeCode Medsync"
    python scripts/standard_vault_test.py --list  # Show available vaults

The vault will remain after testing for manual queries via UI.
"""

import os
import sys
import json
import time
import re
import requests
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.vault_test_config import get_vault_config, list_vaults, VAULT_CONFIGS

BASE_URL = "http://localhost:5000"
BRAIN_URL = "http://localhost:3000"
RESULTS_DIR = "test_results"
REGISTRY_FILE = "outputs/vault_registry.json"
MAX_EXTRACTION_WAIT = 900
POLL_INTERVAL = 15


def load_registry() -> dict:
    """Load vault registry from file."""
    if os.path.exists(REGISTRY_FILE):
        with open(REGISTRY_FILE, 'r') as f:
            return json.load(f)
    return {"_description": "Vault Registry", "_updated": None, "vaults": {}}


def save_registry(registry: dict):
    """Save vault registry to file."""
    registry["_updated"] = datetime.now().isoformat()
    os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)
    with open(REGISTRY_FILE, 'w') as f:
        json.dump(registry, f, indent=2)


def update_registry(vault_name: str, tenant_id: str):
    """Update registry with new vault ID."""
    registry = load_registry()
    registry["vaults"][vault_name] = {
        "tenant_id": tenant_id,
        "created_at": datetime.now().isoformat()
    }
    save_registry(registry)
    print(f"[Registry] Updated: {vault_name} = {tenant_id}")


def get_vault_id(vault_name: str) -> Optional[str]:
    """Get vault ID from registry."""
    registry = load_registry()
    vault_data = registry.get("vaults", {}).get(vault_name)
    if vault_data:
        return vault_data.get("tenant_id")
    return None


def log(message: str):
    """Log with timestamp."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {message}")


def delete_existing_vault(vault_name: str):
    """Delete existing vault by exact name."""
    log(f"Step 1: Delete existing vault '{vault_name}'")
    
    from src.context_foundry.models.schema import get_session
    from sqlalchemy import text
    from src.context_foundry.utils.vault_operations import delete_vault_and_artifacts
    
    with get_session(use_rls_role=False) as session:
        result = session.execute(
            text("SELECT id FROM platform.tenants WHERE name = :name"),
            {"name": vault_name}
        ).fetchone()
        
        if not result:
            log("         No existing vault found")
            return
        
        tenant_id = str(result[0])
        log(f"         Found existing vault: {tenant_id}")
    
    try:
        deleted = delete_vault_and_artifacts(UUID(tenant_id))
        count = sum(v for v in deleted.values() if isinstance(v, int))
        log(f"         Deleted vault and {count} related rows")
    except Exception as e:
        log(f"         Warning: Cleanup had issues: {e}")
        from src.context_foundry.models.schema import get_session
        from sqlalchemy import text
        
        with get_session(use_rls_role=False) as session:
            session.execute(text("UPDATE public.entities SET superseded_by = NULL WHERE tenant_id = :tid"), {"tid": tenant_id})
            
            for table in ['relationships', 'entities', 'document_chunks']:
                try:
                    session.execute(text(f"DELETE FROM public.{table} WHERE tenant_id = :tid"), {"tid": tenant_id})
                except: pass
            
            for table in ['extraction_requests', 'documents', 'user_tenants']:
                try:
                    session.execute(text(f"DELETE FROM platform.{table} WHERE tenant_id = :tid"), {"tid": tenant_id})
                except: pass
            
            session.execute(text("DELETE FROM platform.tenants WHERE id = :tid"), {"tid": tenant_id})
            session.commit()
            log("         Deleted vault via fallback SQL")


def create_vault(vault_name: str) -> str:
    """Create vault via API and return tenant_id."""
    log(f"Step 2: Create vault '{vault_name}'")
    
    from src.context_foundry.models.schema import get_session
    from sqlalchemy import text
    
    with get_session(use_rls_role=False) as session:
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
                ON CONFLICT DO NOTHING
            """),
            {"user_id": user_id, "tenant_id": tenant_id}
        )
        
        session.commit()
    
    update_registry(vault_name, tenant_id)
    log(f"         Created vault: {tenant_id}")
    return tenant_id


def upload_documents(tenant_id: str, doc_dir: str) -> List[str]:
    """Upload all documents from directory."""
    log(f"Step 3: Upload documents from '{doc_dir}'")
    
    if not os.path.exists(doc_dir):
        raise Exception(f"Document directory not found: {doc_dir}")
    
    all_files = []
    for root, dirs, files in os.walk(doc_dir):
        for f in files:
            if f.endswith(('.md', '.xlsx', '.xls', '.csv', '.txt', '.pdf')):
                if 'question_bank' not in f and 'qa_pairs' not in f:
                    all_files.append(os.path.join(root, f))
    
    if not all_files:
        raise Exception(f"No documents found in: {doc_dir}")
    
    log(f"         Found {len(all_files)} documents to upload")
    
    from platform_foundation.src.document_service import DocumentService
    
    doc_svc = DocumentService()
    doc_ids = []
    
    for filepath in sorted(all_files):
        filename = os.path.basename(filepath)
        
        with open(filepath, "rb") as f:
            file_content = f.read()
        
        if filepath.endswith(('.xlsx', '.xls')):
            mime_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        elif filepath.endswith('.csv'):
            mime_type = 'text/csv'
        elif filepath.endswith('.pdf'):
            mime_type = 'application/pdf'
        else:
            mime_type = 'text/plain'
        
        try:
            document = doc_svc.upload_document(
                tenant_id=UUID(tenant_id),
                filename=filename,
                mime_type=mime_type,
                file_content=file_content,
                auto_extract=True,
                priority='normal'
            )
            
            doc_ids.append(str(document['id']))
            log(f"         Uploaded: {filename}")
        except Exception as e:
            log(f"         ERROR uploading {filename}: {e}")
    
    log(f"         Total: {len(doc_ids)} documents uploaded")
    return doc_ids


def wait_for_extraction(tenant_id: str, doc_count: int) -> Dict[str, int]:
    """Wait for extraction to complete."""
    log(f"Step 4: Wait for extraction (up to {MAX_EXTRACTION_WAIT}s)")
    
    from src.context_foundry.models.schema import get_session
    from sqlalchemy import text
    
    start_time = time.time()
    last_complete = 0
    requests_created = False
    
    while time.time() - start_time < MAX_EXTRACTION_WAIT:
        with get_session(use_rls_role=False) as session:
            result = session.execute(
                text("""
                    SELECT 
                        COUNT(*) FILTER (WHERE status = 'COMPLETE') as complete,
                        COUNT(*) FILTER (WHERE status = 'FAILED') as failed,
                        COUNT(*) FILTER (WHERE status IN ('PENDING', 'PROCESSING')) as pending,
                        COUNT(*) as total
                    FROM platform.extraction_requests 
                    WHERE tenant_id = :tid
                """),
                {"tid": tenant_id}
            ).fetchone()
            
            complete, failed, pending, total = result
            
            if not requests_created and total > 0:
                requests_created = True
                log(f"         Extraction started: {total} requests created")
            
            if complete != last_complete:
                log(f"         Progress: {complete}/{doc_count} complete, {failed} failed, {pending} pending")
                last_complete = complete
            
            if requests_created and pending == 0:
                break
        
        time.sleep(POLL_INTERVAL)
    
    with get_session(use_rls_role=False) as session:
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
    
    log(f"         Extraction complete: {chunks} chunks, {entities} entities, {rels} relationships")
    
    if chunks == 0:
        raise Exception("Extraction produced no chunks - check for errors")
    
    return {"chunks": chunks, "entities": entities, "relationships": rels}


def parse_questions(filepath: str) -> List[tuple]:
    """Parse question bank file."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    pattern = r'\*\*Q(\d+):\*\*\s*(.+?)\n\*\*A\1:\*\*\s*(.+?)(?=\n\*\*|$)'
    return [(int(n), q.strip(), a.strip().split('\n')[0].strip()) 
            for n, q, a in re.findall(pattern, content, re.DOTALL)]


def check_answer(response: str, expected: str) -> bool:
    """Check if response matches expected answer."""
    if not response:
        return False
    resp = response.lower().replace(',', '').replace('$', '').strip()
    exp = expected.lower().replace(',', '').replace('$', '').strip()
    if exp in resp:
        return True
    words = [w for w in exp.split() if len(w) > 2][:6]
    return words and sum(1 for w in words if w in resp) >= len(words) * 0.5


def run_question_test(tenant_id: str, question_bank: str, results_prefix: str) -> Dict[str, Any]:
    """Run question bank test."""
    log(f"Step 5: Run question bank test")
    
    if not question_bank or not os.path.exists(question_bank):
        log("         No question bank found, skipping test")
        return None
    
    questions = parse_questions(question_bank)
    log(f"         Testing {len(questions)} questions")
    
    session = requests.Session()
    session.post(f'{BASE_URL}/api/dev/auth', 
                json={'email': 'test@test.com', 'tenant_id': tenant_id})
    
    results = []
    
    for i, (qnum, query, expected) in enumerate(questions):
        try:
            r = session.post(f"{BASE_URL}/api/vault/chat",
                           json={"vault_id": tenant_id, "query": query}, timeout=90)
            answer = r.json().get('answer', '')[:300]
            passed = check_answer(answer, expected)
            results.append({
                'q': qnum, 'passed': passed, 
                'query': query[:50], 'expected': expected[:40],
                'answer': '' if passed else answer[:60]
            })
            if not passed:
                print(f"  X Q{qnum}: exp='{expected[:30]}' got='{answer[:50]}'")
        except Exception as e:
            results.append({'q': qnum, 'passed': False, 'query': query[:50], 'expected': expected[:40], 'answer': str(e)[:60]})
            print(f"  X Q{qnum}: ERROR - {e}")
        
        if (i + 1) % 25 == 0:
            p = sum(1 for r in results if r['passed'])
            print(f"  [{i+1}/{len(questions)}] {p}/{i+1} passed ({100*p/(i+1):.0f}%)")
    
    passed = sum(1 for r in results if r['passed'])
    failures = [r for r in results if not r['passed']]
    
    print("\n" + "=" * 60)
    print(f"FINAL: {passed}/{len(results)} ({100*passed/len(results):.1f}%)")
    print("=" * 60)
    
    os.makedirs(RESULTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    output = {
        'timestamp': timestamp,
        'vault_name': results_prefix,
        'tenant_id': tenant_id,
        'summary': {
            'total': len(results),
            'passed': passed,
            'failed': len(failures),
            'accuracy_pct': round(100*passed/len(results), 1)
        },
        'breakdown': {
            'Q1-100': {'passed': sum(1 for r in results if r['q'] <= 100 and r['passed']), 'total': sum(1 for r in results if r['q'] <= 100)},
            'Q101-200': {'passed': sum(1 for r in results if 100 < r['q'] <= 200 and r['passed']), 'total': sum(1 for r in results if 100 < r['q'] <= 200)},
            'Q201-235': {'passed': sum(1 for r in results if r['q'] > 200 and r['passed']), 'total': sum(1 for r in results if r['q'] > 200)}
        },
        'failures': failures
    }
    
    latest_file = f"{RESULTS_DIR}/{results_prefix}_results.json"
    timestamped_file = f"{RESULTS_DIR}/{results_prefix}_{timestamp}.json"
    
    with open(latest_file, 'w') as f:
        json.dump(output, f, indent=2)
    with open(timestamped_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    log(f"         Results saved to: {latest_file}")
    
    return output


def run_vault_test(vault_key: str):
    """Run complete test lifecycle for a vault."""
    config = get_vault_config(vault_key)
    
    print("\n" + "=" * 70)
    print(f"STANDARD VAULT TEST: {config['name']}")
    print(f"Description: {config['description']}")
    print("=" * 70 + "\n")
    
    start_time = time.time()
    
    delete_existing_vault(config['name'])
    
    tenant_id = create_vault(config['name'])
    
    doc_ids = upload_documents(tenant_id, config['doc_dir'])
    
    counts = wait_for_extraction(tenant_id, len(doc_ids))
    
    test_results = run_question_test(
        tenant_id, 
        config.get('question_bank'), 
        config['results_prefix']
    )
    
    elapsed = time.time() - start_time
    
    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)
    print(f"Vault Name: {config['name']}")
    print(f"Vault ID:   {tenant_id}")
    print(f"Documents:  {len(doc_ids)}")
    print(f"Chunks:     {counts['chunks']}")
    print(f"Entities:   {counts['entities']}")
    print(f"Relations:  {counts['relationships']}")
    if test_results:
        print(f"Test Score: {test_results['summary']['passed']}/{test_results['summary']['total']} ({test_results['summary']['accuracy_pct']}%)")
    print(f"Duration:   {elapsed:.0f}s")
    print("\nVault is ready for manual queries in UI!")
    print("=" * 70)
    
    return tenant_id, test_results


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/standard_vault_test.py <vault_key>")
        print("       python scripts/standard_vault_test.py --list")
        list_vaults()
        sys.exit(1)
    
    if sys.argv[1] == "--list":
        list_vaults()
        sys.exit(0)
    
    vault_key = sys.argv[1]
    
    try:
        run_vault_test(vault_key)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
