#!/usr/bin/env python3
"""
Setup TEST Vault with Ontology-Centric Extraction

Creates a new vault, uploads Nexus Industries corpus, runs ontology extraction,
then compares accuracy against baseline (82%).
"""

import os
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.test_runner.vault_manager import VaultManager

CORPUS_PATH = "test documents/ClaudeCode_NExus_Industries_corpus/"
TEST_VAULT_NAME = "TEST - Nexus Ontology Extraction"
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
    log("="*70)
    log("TEST VAULT SETUP: Ontology-Centric Extraction")
    log("="*70)
    
    vm = VaultManager(API_BASE)
    
    log("[Step 1] Authenticating...")
    if not vm.authenticate_dev():
        log("  FAILED: Could not authenticate")
        return
    log("  Authenticated")
    
    log("[Step 2] Creating fresh vault...")
    existing = vm.find_vault_by_name(TEST_VAULT_NAME)
    if existing:
        log(f"  Deleting existing vault: {existing}")
        vm.delete_vault(existing, TEST_VAULT_NAME)
        time.sleep(3)
    
    vault_id = vm.create_vault(TEST_VAULT_NAME)
    log(f"  Created vault: {vault_id}")
    
    vm.authenticate_dev(tenant_id=vault_id)
    
    log("[Step 3] Collecting corpus documents...")
    documents = collect_documents()
    log(f"  Found {len(documents)} documents to upload")
    
    log("[Step 4] Uploading documents...")
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
            log(f"  Failed to upload {doc_path.name}: {e}")
            failed += 1
    
    log(f"  Uploaded: {uploaded}, Failed: {failed}")
    
    log("[Step 5] Triggering standard extraction...")
    extract_response = vm.trigger_extraction(vault_id)
    if extract_response:
        log("  Extraction triggered")
    else:
        log("  Extraction trigger failed, may already be running")
    
    log("[Step 6] Waiting for extraction to complete...")
    start_time = time.time()
    max_wait = 1800
    
    while time.time() - start_time < max_wait:
        stats = vm.get_vault_stats(vault_id)
        if stats:
            completed = stats.get('completed', 0)
            total = stats.get('total', 0)
            pending = stats.get('pending', 0)
            processing = stats.get('processing', 0)
            
            elapsed = int(time.time() - start_time)
            log(f"  [{elapsed}s] Extraction: {completed}/{total} complete, {pending} pending, {processing} processing")
            
            if total > 0 and pending == 0 and processing == 0:
                log("  Extraction complete!")
                break
        
        time.sleep(15)
    
    log("\n" + "="*70)
    log("VAULT SETUP COMPLETE")
    log(f"Vault ID: {vault_id}")
    log(f"Vault Name: {TEST_VAULT_NAME}")
    log("="*70)
    log("\nNext steps:")
    log("1. Run: python -m src.test_runner.runner --corpus 'ClaudeCode Nexus Industries' --vault-id <id>")
    log("2. Compare accuracy to baseline (82%)")


if __name__ == "__main__":
    main()
