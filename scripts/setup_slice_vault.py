#!/usr/bin/env python3
"""
Phase 2 Slice Vault Setup - Extraction Validation

Creates a new vault with only 5 documents to validate extraction improvements
against pre-committed pass/fail criteria before full re-extraction.
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.test_runner.vault_manager import VaultManager

CORPUS_PATH = "test documents/ClaudeCode_NExus_Industries_corpus/"
SLICE_VAULT_NAME = "ClaudeCode Nexus Slice (Extraction Validation)"
API_BASE = "http://localhost:5000/api"

# Phase 2 pre-committed test documents
SLICE_DOCUMENTS = [
    "stakeholders/01_boeing_customer_profile.md",          # Boeing as CUSTOMER_OF
    "stakeholders/09_nel_hydrogen_supplier.md",            # Nel Hydrogen SUPPLIES
    "meetings/03_greenhydrogen_steering_committee.md",     # Co-occurrence test
    "meetings/12_supplier_performance_review.md",          # Supply-chain relationships
    "stakeholders/05_siemens_healthineers_customer.md",    # Siemens as CUSTOMER_OF
]


def log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")
    sys.stdout.flush()


def main():
    log("="*70)
    log("PHASE 2: Slice Vault Setup (5 Documents)")
    log("="*70)
    log("")
    log("Testing extraction improvements on controlled slice:")
    log("  1. Boeing customer profile (CUSTOMER_OF + entity type)")
    log("  2. Nel Hydrogen supplier (SUPPLIES)")
    log("  3. GreenHydrogen steering committee (co-occurrence test)")
    log("  4. Supplier performance review (supply-chain edges)")
    log("  5. Siemens customer profile (CUSTOMER_OF)")
    log("")

    vm = VaultManager(API_BASE)

    log("[Step 1] Authenticating...")
    if not vm.authenticate_dev():
        log("  FAILED: Could not authenticate")
        return
    log("  ✓ Authenticated")

    log("[Step 2] Creating fresh slice vault...")
    existing = vm.find_vault_by_name(SLICE_VAULT_NAME)
    if existing:
        log(f"  Deleting existing slice vault: {existing}")
        vm.delete_vault(existing, SLICE_VAULT_NAME)
        time.sleep(3)

    vault_id = vm.create_vault(SLICE_VAULT_NAME)
    log(f"  ✓ Created vault: {vault_id}")

    vm.authenticate_dev(tenant_id=vault_id)

    log("[Step 3] Uploading 5 test documents...")
    corpus_path = Path(CORPUS_PATH)
    uploaded = 0
    failed = 0

    for doc_rel_path in SLICE_DOCUMENTS:
        doc_path = corpus_path / doc_rel_path

        if not doc_path.exists():
            log(f"  ✗ Not found: {doc_rel_path}")
            failed += 1
            continue

        log(f"  Uploading: {doc_rel_path}")
        try:
            if vm.upload_document(vault_id, doc_path):
                uploaded += 1
                log(f"    ✓ Success")
            else:
                failed += 1
                log(f"    ✗ Failed")
        except Exception as e:
            failed += 1
            log(f"    ✗ Error: {e}")

    log("")
    log(f"[Step 4] Upload complete: {uploaded} succeeded, {failed} failed")

    if uploaded == 5:
        log("")
        log("="*70)
        log("✓ SLICE VAULT READY")
        log("="*70)
        log(f"Vault ID: {vault_id}")
        log(f"Vault Name: {SLICE_VAULT_NAME}")
        log(f"Documents: {uploaded}/5")
        log("")
        log("Next step: Run extraction")
        log(f"  python scripts/run_vault_extraction.py --vault-id {vault_id} --use-ontology")
        log("")
    else:
        log("")
        log("✗ SETUP FAILED - not all documents uploaded")
        log(f"  Expected: 5 documents")
        log(f"  Uploaded: {uploaded} documents")
        log(f"  Failed: {failed} documents")


if __name__ == "__main__":
    main()
