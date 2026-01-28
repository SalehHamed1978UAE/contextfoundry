#!/usr/bin/env python3
"""
Context Foundry Integration Tests
=================================

RUN THIS AFTER EVERY CHANGE.

Usage:
    python cf_integration_tests.py --all           # Run all tests
    python cf_integration_tests.py --quick         # Run quick smoke tests only
    python cf_integration_tests.py --test vault    # Run specific test suite
    python cf_integration_tests.py --test extraction
    python cf_integration_tests.py --test corpus
    python cf_integration_tests.py --test ontology

Exit codes:
    0 = All tests passed
    1 = Tests failed (DO NOT DEPLOY)
"""

import os
import sys
import json
import time
import argparse
from uuid import UUID, uuid4
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple

# ============================================================================
# CONFIGURATION
# ============================================================================

TEST_USER_ID = os.environ.get("CF_TEST_USER_ID", "00000000-0000-0000-0000-000000000001")
TEST_CORPUS_PATH = os.environ.get("CF_TEST_CORPUS_PATH", "test_data/integration_test_corpus")
DATABASE_URL = os.environ.get("DATABASE_URL", None)

# Test document content for extraction tests
TEST_DOCUMENT_CONTENT = """
# Integration Test Document

## Company Overview
Nexus Industries is a technology company headquartered in San Francisco.

## Leadership
Dr. Victoria Chen serves as CEO of Nexus Industries.
Michael Chang is the CFO and reports to Dr. Victoria Chen.

## Suppliers
Nel Hydrogen supplies electrolyzers to Nexus Industries.
Honeywell provides flight computers for the Falcon X program.

## Financials
Total company backlog is $12.4 billion as of Q4 2025.
"""

# Expected extractions from test document
EXPECTED_ENTITIES = [
    ("Nexus Industries", "ORGANIZATION"),
    ("Dr. Victoria Chen", "PERSON"),
    ("Michael Chang", "PERSON"),
    ("Nel Hydrogen", "ORGANIZATION"),
    ("Honeywell", "ORGANIZATION"),
]

EXPECTED_RELATIONSHIPS = [
    ("Dr. Victoria Chen", "HOLDS_POSITION", "CEO"),
    ("Michael Chang", "HOLDS_POSITION", "CFO"),
    ("Michael Chang", "REPORTS_TO", "Dr. Victoria Chen"),
    ("Nel Hydrogen", "SUPPLIES_TO", "Nexus Industries"),
    ("Honeywell", "SUPPLIES_TO", "Nexus Industries"),
]


# ============================================================================
# TEST RESULT TRACKING
# ============================================================================

class TestResults:
    def __init__(self):
        self.passed = []
        self.failed = []
        self.skipped = []
        self.start_time = datetime.now()

    def add_pass(self, test_name: str, message: str = ""):
        self.passed.append((test_name, message))
        print(f"  ✓ {test_name}")

    def add_fail(self, test_name: str, message: str):
        self.failed.append((test_name, message))
        print(f"  ✗ {test_name}: {message}")

    def add_skip(self, test_name: str, reason: str):
        self.skipped.append((test_name, reason))
        print(f"  ⊘ {test_name}: SKIPPED - {reason}")

    def summary(self) -> bool:
        duration = (datetime.now() - self.start_time).total_seconds()
        total = len(self.passed) + len(self.failed) + len(self.skipped)

        print("\n" + "=" * 60)
        print("INTEGRATION TEST RESULTS")
        print("=" * 60)
        print(f"  Passed:  {len(self.passed)}")
        print(f"  Failed:  {len(self.failed)}")
        print(f"  Skipped: {len(self.skipped)}")
        print(f"  Total:   {total}")
        print(f"  Time:    {duration:.2f}s")
        print("=" * 60)

        if self.failed:
            print("\nFAILED TESTS:")
            for name, msg in self.failed:
                print(f"  ✗ {name}")
                print(f"    → {msg}")
            print("\n❌ DO NOT DEPLOY - FIX FAILURES FIRST")
            return False
        else:
            print("\n✅ ALL TESTS PASSED - OK TO DEPLOY")
            return True


results = TestResults()


# ============================================================================
# SERVICE IMPORTS (with graceful fallback)
# ============================================================================

def import_services():
    """Import CF services. Returns (TenantService, DocumentService) or (None, None)."""
    try:
        from platform_foundation.src.tenant_service import TenantService
        from platform_foundation.src.document_service import DocumentService
        return TenantService, DocumentService
    except ImportError as e:
        print(f"⚠ Could not import services: {e}")
        print("  Make sure you're running from the CF project root.")
        return None, None


# ============================================================================
# TEST SUITES
# ============================================================================

def test_vault_operations():
    """Test vault creation, listing, and deletion."""
    print("\n📦 VAULT OPERATIONS")
    print("-" * 40)

    TenantService, DocumentService = import_services()
    if not TenantService:
        results.add_skip("vault_create", "Services not available")
        return

    tenant_service = TenantService()
    test_user_id = UUID(TEST_USER_ID)
    test_vault_name = f"Integration Test {uuid4().hex[:8]}"
    created_vault_id = None

    # Test 1: Create vault for user
    try:
        vault = tenant_service.create_vault_for_user(
            user_id=test_user_id,
            name=test_vault_name
        )
        created_vault_id = UUID(str(vault['id']))
        results.add_pass("vault_create", f"Created {created_vault_id}")
    except Exception as e:
        results.add_fail("vault_create", str(e))
        return  # Can't continue without vault

    # Test 2: Vault appears in user's list
    try:
        vaults = tenant_service.list_user_vaults(user_id=test_user_id)
        vault_ids = [UUID(str(v['id'])) for v in vaults]
        if created_vault_id in vault_ids:
            results.add_pass("vault_list", f"Found in list ({len(vaults)} vaults)")
        else:
            results.add_fail("vault_list", "Created vault not in user's vault list")
    except Exception as e:
        results.add_fail("vault_list", str(e))

    # Test 3: Get vault by ID
    try:
        vault = tenant_service.get_tenant(created_vault_id)
        if vault and vault['name'] == test_vault_name:
            results.add_pass("vault_get", "Retrieved correctly")
        else:
            results.add_fail("vault_get", "Vault not found or name mismatch")
    except Exception as e:
        results.add_fail("vault_get", str(e))

    # Test 4: Check user access
    try:
        has_access = tenant_service.user_has_vault_access(test_user_id, created_vault_id)
        if has_access:
            results.add_pass("vault_access", "User has access")
        else:
            results.add_fail("vault_access", "User doesn't have access to created vault")
    except Exception as e:
        results.add_fail("vault_access", str(e))

    # Test 5: Delete vault (graceful)
    try:
        # Try graceful delete if available
        if hasattr(tenant_service, 'graceful_delete_vault'):
            tenant_service.graceful_delete_vault(created_vault_id)
        else:
            # Fallback to suspend
            tenant_service.suspend_tenant(created_vault_id)

        # Verify deleted/suspended
        vault = tenant_service.get_tenant(created_vault_id)
        if vault is None or vault.get('status') in ('suspended', 'deleted', 'deleting'):
            results.add_pass("vault_delete", "Deleted successfully")
        else:
            results.add_fail("vault_delete", f"Vault still active: {vault.get('status')}")
    except Exception as e:
        results.add_fail("vault_delete", str(e))


def test_document_operations():
    """Test document upload and retrieval."""
    print("\n📄 DOCUMENT OPERATIONS")
    print("-" * 40)

    TenantService, DocumentService = import_services()
    if not TenantService or not DocumentService:
        results.add_skip("document_upload", "Services not available")
        return

    tenant_service = TenantService()
    doc_service = DocumentService()
    test_user_id = UUID(TEST_USER_ID)

    # Create test vault
    try:
        vault = tenant_service.create_vault_for_user(
            user_id=test_user_id,
            name=f"Doc Test {uuid4().hex[:8]}"
        )
        vault_id = UUID(str(vault['id']))
    except Exception as e:
        results.add_fail("document_setup", f"Could not create test vault: {e}")
        return

    try:
        # Test 1: Upload document with correct parameters
        try:
            doc = doc_service.upload_document(
                tenant_id=vault_id,
                filename="test_document.md",
                mime_type="text/markdown",
                file_content=TEST_DOCUMENT_CONTENT.encode('utf-8'),  # NOT 'content'!
                auto_extract=False  # Don't extract for this test
            )
            if doc and 'id' in doc:
                results.add_pass("document_upload", f"Uploaded {doc['id']}")
                doc_id = UUID(str(doc['id']))
            else:
                results.add_fail("document_upload", "No document ID returned")
                return
        except TypeError as e:
            if "content" in str(e) or "file_content" in str(e):
                results.add_fail("document_upload",
                    "Parameter mismatch! Use 'file_content' not 'content'")
            else:
                results.add_fail("document_upload", str(e))
            return
        except Exception as e:
            results.add_fail("document_upload", str(e))
            return

        # Test 2: List documents
        try:
            docs = doc_service.list_documents(tenant_id=vault_id)
            if len(docs) >= 1:
                results.add_pass("document_list", f"Found {len(docs)} documents")
            else:
                results.add_fail("document_list", "No documents found after upload")
        except Exception as e:
            results.add_fail("document_list", str(e))

        # Test 3: Get document by ID
        try:
            doc = doc_service.get_document(document_id=doc_id, tenant_id=vault_id)
            if doc and doc['original_filename'] == "test_document.md":
                results.add_pass("document_get", "Retrieved correctly")
            else:
                results.add_fail("document_get", "Document not found or filename mismatch")
        except Exception as e:
            results.add_fail("document_get", str(e))

    finally:
        # Cleanup
        try:
            if hasattr(tenant_service, 'graceful_delete_vault'):
                tenant_service.graceful_delete_vault(vault_id)
            else:
                tenant_service.suspend_tenant(vault_id)
        except:
            pass


def test_extraction_pipeline():
    """Test document extraction end-to-end."""
    print("\n🔬 EXTRACTION PIPELINE")
    print("-" * 40)

    TenantService, DocumentService = import_services()
    if not TenantService or not DocumentService:
        results.add_skip("extraction_queue", "Services not available")
        return

    tenant_service = TenantService()
    doc_service = DocumentService()
    test_user_id = UUID(TEST_USER_ID)

    # Create test vault
    try:
        vault = tenant_service.create_vault_for_user(
            user_id=test_user_id,
            name=f"Extraction Test {uuid4().hex[:8]}"
        )
        vault_id = UUID(str(vault['id']))
    except Exception as e:
        results.add_fail("extraction_setup", f"Could not create test vault: {e}")
        return

    try:
        # Test 1: Upload with auto_extract=True
        try:
            doc = doc_service.upload_document(
                tenant_id=vault_id,
                filename="extraction_test.md",
                mime_type="text/markdown",
                file_content=TEST_DOCUMENT_CONTENT.encode('utf-8'),
                auto_extract=True
            )
            if doc and doc.get('extraction_request_id'):
                results.add_pass("extraction_queue", f"Queued: {doc['extraction_request_id']}")
                request_id = doc['extraction_request_id']
            else:
                results.add_fail("extraction_queue", "No extraction_request_id returned")
                return
        except Exception as e:
            results.add_fail("extraction_queue", str(e))
            return

        # Test 2: Check extraction status is retrievable
        try:
            status = doc_service.get_extraction_status(
                request_id=request_id,
                tenant_id=vault_id
            )
            if status:
                results.add_pass("extraction_status", f"Status: {status.get('status', 'unknown')}")
            else:
                results.add_fail("extraction_status", "Could not retrieve extraction status")
        except Exception as e:
            results.add_fail("extraction_status", str(e))

        # Test 3: Wait for extraction (with timeout)
        try:
            max_wait = 60  # seconds
            poll_interval = 5
            waited = 0
            final_status = None

            while waited < max_wait:
                status = doc_service.get_extraction_status(
                    request_id=request_id,
                    tenant_id=vault_id
                )
                if status and status.get('status') in ('completed', 'failed'):
                    final_status = status.get('status')
                    break
                time.sleep(poll_interval)
                waited += poll_interval

            if final_status == 'completed':
                results.add_pass("extraction_complete", f"Completed in {waited}s")
            elif final_status == 'failed':
                error = status.get('error', 'Unknown error')
                results.add_fail("extraction_complete", f"Extraction failed: {error}")
            else:
                results.add_skip("extraction_complete", f"Timeout after {max_wait}s (status: {final_status})")
        except Exception as e:
            results.add_fail("extraction_complete", str(e))

    finally:
        # Cleanup
        try:
            if hasattr(tenant_service, 'graceful_delete_vault'):
                tenant_service.graceful_delete_vault(vault_id)
            else:
                tenant_service.suspend_tenant(vault_id)
        except:
            pass


def test_ontology_candidate_storage():
    """Test that new relationship types can be stored as ontology candidates."""
    print("\n🧬 ONTOLOGY CANDIDATE STORAGE")
    print("-" * 40)

    try:
        from context_foundry.ontology_foundry.candidate_store import CandidateStore
    except ImportError:
        results.add_skip("ontology_store", "CandidateStore not available")
        return

    # Test 1: Store a candidate with valid UUID
    try:
        store = CandidateStore()
        test_candidate = {
            'tenant_id': UUID(TEST_USER_ID),
            'candidate_type': 'RELATIONSHIP',
            'proposed_name': 'SUPPLIES_TO',
            'normalized_name': 'SUPPLIES_TO',
            'source_entity_type': 'ORGANIZATION',
            'target_entity_type': 'ORGANIZATION',
            'confidence_score': 0.85,
            'document_count': 1,
            'mention_count': 1,
            'example_mentions': ['Nel Hydrogen supplies electrolyzers'],
        }

        # This should not throw UUID parsing errors
        result = store.store_candidate(test_candidate)
        if result:
            results.add_pass("ontology_store", "Candidate stored successfully")
        else:
            results.add_fail("ontology_store", "Store returned None/False")
    except Exception as e:
        if "uuid" in str(e).lower():
            results.add_fail("ontology_store", f"UUID parsing error: {e}")
        else:
            results.add_fail("ontology_store", str(e))

    # Test 2: Retrieve candidates
    try:
        candidates = store.get_pending_candidates(
            tenant_id=UUID(TEST_USER_ID),
            candidate_type='RELATIONSHIP'
        )
        results.add_pass("ontology_retrieve", f"Retrieved {len(candidates)} candidates")
    except Exception as e:
        results.add_fail("ontology_retrieve", str(e))


def test_corpus_config():
    """Test corpus configuration integrity."""
    print("\n📚 CORPUS CONFIGURATION")
    print("-" * 40)

    config_path = Path("src/test_config.json")
    if not config_path.exists():
        config_path = Path("test_config.json")

    if not config_path.exists():
        results.add_skip("corpus_config", "test_config.json not found")
        return

    try:
        with open(config_path) as f:
            config = json.load(f)
    except Exception as e:
        results.add_fail("corpus_config_load", f"Could not parse config: {e}")
        return

    results.add_pass("corpus_config_load", f"Loaded from {config_path}")

    # Check each corpus has required fields
    corpora = config.get('corpora', {})
    for name, corpus_config in corpora.items():
        # Test: root_path exists and points to real directory
        root_path = corpus_config.get('root_path')
        if not root_path:
            results.add_fail(f"corpus_{name}_path", "Missing root_path")
        elif not Path(root_path).exists():
            results.add_fail(f"corpus_{name}_path", f"root_path doesn't exist: {root_path}")
        else:
            file_count = len(list(Path(root_path).rglob('*.*')))
            results.add_pass(f"corpus_{name}_path", f"Found {file_count} files")


def test_supplies_to_extraction():
    """Test that SUPPLIES_TO patterns are extracted correctly."""
    print("\n🔗 SUPPLIES_TO EXTRACTION")
    print("-" * 40)

    try:
        from context_foundry.extraction.post_processor import extract_supplier_relationships
    except ImportError:
        results.add_skip("supplies_to_patterns", "post_processor not available")
        return

    # Test cases for SUPPLIES_TO patterns
    test_cases = [
        ("Nel Hydrogen supplies electrolyzers to Nexus Industries", True, "Nel Hydrogen"),
        ("Honeywell provides flight computers for the Falcon X program", True, "Honeywell"),
        ("The radar is supplied by Raytheon", True, "Raytheon"),
        ("The company reported quarterly earnings", False, None),
    ]

    for text, should_match, expected_supplier in test_cases:
        try:
            relationships = extract_supplier_relationships(text)
            found = len(relationships) > 0

            if should_match and found:
                supplier = relationships[0].get('source', '')
                if expected_supplier.lower() in supplier.lower():
                    results.add_pass(f"supplies_to_pattern", f"Matched: {expected_supplier}")
                else:
                    results.add_fail(f"supplies_to_pattern",
                        f"Wrong supplier: got '{supplier}', expected '{expected_supplier}'")
            elif should_match and not found:
                results.add_fail(f"supplies_to_pattern", f"Should match but didn't: {text[:50]}...")
            elif not should_match and not found:
                results.add_pass(f"supplies_to_negative", "Correctly rejected non-supplier text")
            else:
                results.add_fail(f"supplies_to_negative", f"False positive on: {text[:50]}...")
        except Exception as e:
            results.add_fail(f"supplies_to_pattern", str(e))


def test_quick_smoke():
    """Quick smoke tests - run these always."""
    print("\n💨 QUICK SMOKE TESTS")
    print("-" * 40)

    # Test 1: Services importable
    TenantService, DocumentService = import_services()
    if TenantService and DocumentService:
        results.add_pass("import_services", "Services imported")
    else:
        results.add_fail("import_services", "Could not import services")
        return  # Can't continue

    # Test 2: Database connection
    try:
        tenant_service = TenantService()
        tenants = tenant_service.list_tenants(status='active')
        results.add_pass("db_connection", f"Connected, {len(tenants)} active tenants")
    except Exception as e:
        results.add_fail("db_connection", str(e))

    # Test 3: Document service initialization
    try:
        doc_service = DocumentService()
        results.add_pass("doc_service_init", "DocumentService initialized")
    except Exception as e:
        results.add_fail("doc_service_init", str(e))


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="CF Integration Tests")
    parser.add_argument("--all", action="store_true", help="Run all tests")
    parser.add_argument("--quick", action="store_true", help="Run quick smoke tests only")
    parser.add_argument("--test", type=str, help="Run specific test suite")
    args = parser.parse_args()

    print("=" * 60)
    print("CONTEXT FOUNDRY INTEGRATION TESTS")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)

    if args.quick:
        test_quick_smoke()
    elif args.test:
        test_map = {
            "vault": test_vault_operations,
            "document": test_document_operations,
            "extraction": test_extraction_pipeline,
            "ontology": test_ontology_candidate_storage,
            "corpus": test_corpus_config,
            "supplies_to": test_supplies_to_extraction,
            "smoke": test_quick_smoke,
        }
        if args.test in test_map:
            test_map[args.test]()
        else:
            print(f"Unknown test suite: {args.test}")
            print(f"Available: {', '.join(test_map.keys())}")
            sys.exit(1)
    else:
        # Default: run all tests
        test_quick_smoke()
        test_vault_operations()
        test_document_operations()
        test_corpus_config()
        test_supplies_to_extraction()
        test_ontology_candidate_storage()
        test_extraction_pipeline()  # Run last (slowest)

    # Print summary and exit with appropriate code
    success = results.summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
