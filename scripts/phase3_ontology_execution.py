#!/usr/bin/env python3
"""
Phase 3 Ontology Execution Script

This script orchestrates the complete Phase 3 workflow with validation checkpoints.
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.test_runner.vault_manager import VaultManager

CORPUS_PATH = "test documents/ClaudeCode_NExus_Industries_corpus/"
VAULT_NAME = "ClaudeCode Nexus Industries (Ontology)"
API_BASE = "http://localhost:5000/api"

INCLUDE_FOLDERS = [
    "All docs", "communications", "financials", "meetings",
    "organizational", "policies", "projects", "stakeholders",
    "strategy", "technical"
]
VALID_EXTENSIONS = [".md", ".txt", ".pdf", ".docx", ".xlsx", ".csv"]
EXCLUDE_FILES = [
    "README.md", "readme.md", "00_CORPUS_MANIFEST.json",
    "01_VALIDATION_QUESTIONS.json", "nexus_100q.json"
]


def log(msg: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}")
    sys.stdout.flush()


def collect_documents() -> list:
    """Collect all documents from corpus folders."""
    corpus_path = Path(CORPUS_PATH)
    if not corpus_path.exists():
        log(f"ERROR: Corpus path does not exist: {CORPUS_PATH}")
        sys.exit(1)

    documents = []

    for folder in INCLUDE_FOLDERS:
        folder_path = corpus_path / folder
        if folder_path.exists() and folder_path.is_dir():
            for file_path in folder_path.rglob("*"):
                if file_path.is_file():
                    if file_path.suffix.lower() in VALID_EXTENSIONS:
                        if file_path.name not in EXCLUDE_FILES:
                            documents.append(file_path)

    for file_path in corpus_path.iterdir():
        if file_path.is_file():
            if file_path.suffix.lower() in [".md", ".txt"]:
                if file_path.name not in EXCLUDE_FILES:
                    documents.append(file_path)

    return documents


def main():
    log("="*80)
    log("PHASE 3: ONTOLOGY INTEGRATION VALIDATION - OPTION A (FRESH VAULT)")
    log("="*80)

    # Step 1: Create fresh vault
    log("\n[STEP 1] Creating fresh vault...")
    vm = VaultManager(API_BASE)

    if not vm.authenticate_dev():
        log("  ❌ FAILED: Could not authenticate")
        sys.exit(1)
    log("  ✅ Authenticated")

    existing = vm.find_vault_by_name(VAULT_NAME)
    if existing:
        log(f"  ⚠️  Vault exists, deleting: {existing}")
        vm.delete_vault(existing, VAULT_NAME)
        time.sleep(5)

    vault_id = vm.create_vault(VAULT_NAME)
    log(f"  ✅ Created vault: {vault_id}")
    log(f"  ✅ Vault name: {VAULT_NAME}")

    vm.authenticate_dev(tenant_id=vault_id)

    # Step 2: Upload documents
    log("\n[STEP 2] Collecting and uploading documents...")
    documents = collect_documents()
    log(f"  Found {len(documents)} documents to upload")

    if len(documents) < 100:
        log(f"  ❌ FAILED: Only found {len(documents)} documents (need at least 100)")
        sys.exit(1)

    uploaded = 0
    failed = 0
    for i, doc_path in enumerate(documents, 1):
        if i % 10 == 0 or i == len(documents):
            log(f"  Uploading {i}/{len(documents)}...")
        try:
            if vm.upload_document(vault_id, doc_path):
                uploaded += 1
            else:
                failed += 1
        except Exception as e:
            log(f"  ⚠️  Failed to upload {doc_path.name}: {e}")
            failed += 1

    log(f"  ✅ Uploaded: {uploaded}, Failed: {failed}")

    if uploaded < 100:
        log(f"  ❌ FAILED: Only uploaded {uploaded} documents (need at least 100)")
        sys.exit(1)

    # Step 3: Run ONTOLOGY extraction
    log("\n[STEP 3] Running ONTOLOGY extraction (--use-ontology)...")
    log("  This will take 30-60 minutes...")

    cmd = [
        "python", "scripts/run_vault_extraction.py",
        "--vault-id", vault_id,
        "--use-ontology"
    ]

    log(f"  Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        log(f"  ❌ FAILED: Extraction command failed with code {result.returncode}")
        sys.exit(1)

    log("  ✅ Extraction completed")

    # Step 4: Run 100Q test
    log("\n[STEP 4] Running 100-question test...")
    log("  This will take 10-15 minutes...")

    cmd = [
        "python", "-m", "src.test_runner.runner",
        "--vault-id", vault_id,
        "--questions", "src/test_questions/nexus_100q.json",
        "--force"
    ]

    log(f"  Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        log(f"  ❌ FAILED: Test command failed with code {result.returncode}")
        sys.exit(1)

    log("  ✅ Test completed")

    # Step 5: Run validation
    log("\n[STEP 5] Running deterministic validation...")

    cmd = [
        "python", "scripts/phase3_ontology_validator.py",
        vault_id,
        VAULT_NAME
    ]

    log(f"  Command: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=False)

    if result.returncode != 0:
        log("  ❌ VALIDATION FAILED - See output above")
        sys.exit(1)

    log("  ✅ Validation passed")

    # Final summary
    log("\n" + "="*80)
    log("✅ PHASE 3 COMPLETE - ALL VALIDATION GATES PASSED")
    log("="*80)
    log(f"\nVault ID: {vault_id}")
    log(f"Vault Name: {VAULT_NAME}")
    log("\nValidation results: data/phase3_validation_results.json")
    log("Test results: data/test-runner/status.json")
    log("\nNext step: Review results and decide to flip ontology as default")
    log("="*80)


if __name__ == "__main__":
    main()
