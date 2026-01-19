# Context Foundry: Standardized Test Infrastructure Spec
**Version:** January 19, 2026
**Purpose:** Reusable, one-command test runner for all corpora

---

## Overview

Create a test runner that:
- Works across all corpora with one command
- Handles vault lifecycle (delete old, create new)
- Properly waits for extraction to complete
- Uses fuzzy evaluation (not strict string matching)
- Preserves vault after test for manual queries
- Tracks state in config file

---

## File Structure

```
src/
├── test_runner/
│   ├── __init__.py
│   ├── runner.py           # Main entry point
│   ├── config.py           # Load/save test_config.json
│   ├── vault_manager.py    # Create/delete vaults, upload docs, wait for extraction
│   ├── document_uploader.py # Recursive upload with filtering
│   ├── test_executor.py    # Run questions against vault
│   └── evaluator.py        # Fuzzy matching evaluator
├── test_config.json        # Corpus definitions + state
└── test_results/           # Timestamped output files
```

---

## test_config.json

```json
{
  "api_base_url": "http://localhost:5000/api",
  "auth_token": "YOUR_TOKEN_HERE",
  "corpora": {
    "ClaudeCode Medsync": {
      "root_path": "test_documents/ClaudeCode Medsync/",
      "questions_file": "medsync_235q.json",
      "current_vault_id": null,
      "last_run": null,
      "last_accuracy": null
    },
    "Manus Healthtec": {
      "root_path": "test_documents/Manus Healthtec/",
      "questions_file": "medsync_235q.json",
      "current_vault_id": null,
      "last_run": null,
      "last_accuracy": null
    },
    "Manus Medsync": {
      "root_path": "test_documents/Manus Medsync/",
      "questions_file": "medsync_235q.json",
      "current_vault_id": null,
      "last_run": null,
      "last_accuracy": null
    }
  },
  "questions_dir": "test_questions/",
  "results_dir": "test_results/",
  "upload_rules": {
    "include_folders": ["documents", "excel_data"],
    "valid_extensions": [".pdf", ".docx", ".xlsx", ".xls", ".csv", ".txt", ".md"],
    "exclude_files": ["README.md"]
  },
  "extraction": {
    "timeout_minutes": 15,
    "min_expected_chunks": 50,
    "poll_interval_seconds": 5
  }
}
```

---

## Document Upload Rules

```python
# document_uploader.py

from pathlib import Path
from typing import List

def should_upload(file_path: Path, corpus_root: Path) -> bool:
    """
    Determine if a file should be uploaded.
    
    INCLUDE:
    - Files inside 'documents/' folder (recursive)
    - Files inside 'excel_data/' folder (recursive)
    
    EXCLUDE:
    - Everything at corpus root level
    - README.md anywhere
    - .py files anywhere
    """
    
    relative = file_path.relative_to(corpus_root)
    parts = relative.parts
    
    # Must be inside a subfolder
    if len(parts) < 2:
        return False  # File at root level - exclude
    
    # Check if top-level folder is in allowed list
    top_folder = parts[0].lower()
    allowed_folders = ['documents', 'excel_data']
    
    if top_folder not in allowed_folders:
        return False
    
    # Check file extension
    valid_extensions = ['.pdf', '.docx', '.xlsx', '.xls', '.csv', '.txt', '.md']
    if file_path.suffix.lower() not in valid_extensions:
        return False
    
    # Exclude README.md anywhere
    if file_path.name.lower() == 'readme.md':
        return False
    
    return True


def get_files_to_upload(corpus_root: Path) -> List[Path]:
    """Recursively find all files to upload from corpus."""
    
    files = []
    for file_path in corpus_root.rglob('*'):
        if file_path.is_file() and should_upload(file_path, corpus_root):
            files.append(file_path)
    
    return sorted(files)
```

---

## Vault Manager (CRITICAL: Proper Extraction Waiting)

```python
# vault_manager.py

import time
import requests
from pathlib import Path
from typing import Optional

class VaultManager:
    """Manage vault lifecycle via CF API."""
    
    def __init__(self, api_base_url: str, auth_token: str):
        self.api = api_base_url
        self.token = auth_token
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def find_vault_by_name(self, name: str) -> Optional[str]:
        """Find existing vault ID by name. Returns None if not found."""
        response = requests.get(f"{self.api}/vaults", headers=self.headers)
        vaults = response.json()
        
        for vault in vaults:
            if vault['name'] == name:
                return vault['id']
        return None
    
    def delete_vault(self, vault_id: str) -> bool:
        """Delete vault by ID."""
        response = requests.delete(
            f"{self.api}/vaults/{vault_id}",
            headers=self.headers
        )
        return response.status_code in [200, 204]
    
    def create_vault(self, name: str) -> str:
        """Create new vault, return ID."""
        response = requests.post(
            f"{self.api}/vaults",
            headers=self.headers,
            json={"name": name}
        )
        return response.json()['id']
    
    def ensure_clean_vault(self, name: str) -> str:
        """Delete existing vault if present, create fresh one, return ID."""
        
        existing_id = self.find_vault_by_name(name)
        if existing_id:
            print(f"  Deleting existing vault: {name} ({existing_id})")
            self.delete_vault(existing_id)
            time.sleep(2)  # Brief pause after deletion
        
        print(f"  Creating new vault: {name}")
        new_id = self.create_vault(name)
        print(f"  Vault ID: {new_id}")
        
        return new_id
    
    def upload_document(self, vault_id: str, file_path: Path) -> bool:
        """Upload a single document to vault."""
        with open(file_path, 'rb') as f:
            files = {'file': (file_path.name, f)}
            response = requests.post(
                f"{self.api}/vaults/{vault_id}/documents",
                headers=self.headers,
                files=files
            )
        return response.status_code in [200, 201]
    
    def get_document_count(self, vault_id: str) -> int:
        """Get number of documents in vault."""
        response = requests.get(
            f"{self.api}/vaults/{vault_id}/documents",
            headers=self.headers
        )
        if response.status_code == 200:
            return len(response.json())
        return 0
    
    def get_extraction_status(self, vault_id: str) -> dict:
        """
        Get extraction status for vault.
        Returns: {total: int, pending: int, completed: int, failed: int}
        """
        response = requests.get(
            f"{self.api}/vaults/{vault_id}/extraction-status",
            headers=self.headers
        )
        if response.status_code == 200:
            return response.json()
        return {"total": 0, "pending": 0, "completed": 0, "failed": 0}
    
    def get_chunk_count(self, vault_id: str) -> int:
        """Get number of chunks stored for vault."""
        response = requests.get(
            f"{self.api}/vaults/{vault_id}/stats",
            headers=self.headers
        )
        if response.status_code == 200:
            return response.json().get('chunk_count', 0)
        return 0
    
    def wait_for_extraction(
        self, 
        vault_id: str, 
        expected_docs: int,
        timeout_minutes: int = 15,
        poll_interval: int = 5
    ) -> bool:
        """
        PROPERLY wait for extraction to complete.
        
        Three-phase wait:
        1. Wait for documents to be registered
        2. Wait for extraction requests to be created
        3. Wait for all requests to complete
        
        Args:
            vault_id: The vault to monitor
            expected_docs: Number of documents we uploaded (sanity check)
            timeout_minutes: Maximum time to wait
            poll_interval: Seconds between status checks
            
        Returns:
            True if extraction completed successfully
            
        Raises:
            TimeoutError: If extraction doesn't complete in time
            ValueError: If document count doesn't match expected
        """
        
        start = time.time()
        timeout = timeout_minutes * 60
        
        print(f"  Waiting for extraction (timeout: {timeout_minutes} min)...")
        
        # ============================================
        # PHASE 1: Wait for documents to be registered
        # ============================================
        print("  Phase 1: Waiting for documents to register...")
        phase1_start = time.time()
        
        while time.time() - start < timeout:
            doc_count = self.get_document_count(vault_id)
            
            if doc_count >= expected_docs:
                print(f"  ✓ {doc_count}/{expected_docs} documents registered")
                break
            
            if doc_count > 0:
                print(f"    {doc_count}/{expected_docs} documents registered...")
            
            time.sleep(poll_interval)
        else:
            raise TimeoutError("Timeout waiting for documents to register")
        
        # ============================================
        # PHASE 2: Wait for extraction requests to be created
        # ============================================
        print("  Phase 2: Waiting for extraction to start...")
        
        while time.time() - start < timeout:
            status = self.get_extraction_status(vault_id)
            total = status.get('total', 0)
            
            if total >= expected_docs:
                print(f"  ✓ {total} extraction requests created")
                break
            
            if total > 0:
                print(f"    {total}/{expected_docs} extraction requests created...")
            
            time.sleep(poll_interval)
        else:
            raise TimeoutError("Timeout waiting for extraction requests to be created")
        
        # ============================================
        # PHASE 3: Wait for all extractions to complete
        # ============================================
        print("  Phase 3: Waiting for extraction to complete...")
        
        while time.time() - start < timeout:
            status = self.get_extraction_status(vault_id)
            total = status.get('total', 0)
            completed = status.get('completed', 0)
            pending = status.get('pending', 0)
            failed = status.get('failed', 0)
            
            print(f"    Progress: {completed}/{total} complete, {pending} pending, {failed} failed")
            
            # Check completion: no pending AND we have results
            if total > 0 and pending == 0:
                if failed > 0:
                    print(f"  ⚠ Warning: {failed} extractions failed")
                print(f"  ✓ Extraction complete! ({completed} succeeded, {failed} failed)")
                return True
            
            time.sleep(poll_interval)
        
        raise TimeoutError(
            f"Extraction did not complete within {timeout_minutes} minutes. "
            f"Status: {completed}/{total} complete, {pending} pending"
        )
```

---

## Fuzzy Evaluator

```python
# evaluator.py

import re
from typing import Tuple

class FuzzyEvaluator:
    """
    Evaluate answers with semantic matching, not strict string matching.
    
    Handles:
    - Format differences ("30%" vs "30%+")
    - Prose vs exact value ("Revenue increased by $40M" vs "$40 million")
    - "I don't know" variations
    - Number extraction and comparison
    """
    
    def evaluate(self, expected: str, actual: str) -> Tuple[bool, str]:
        """
        Returns (passed, match_type)
        
        match_type is one of:
        - exact_match
        - uncertainty_match
        - number_match
        - entity_match
        - percentage_match
        - no_match
        """
        
        expected_lower = expected.lower().strip()
        actual_lower = actual.lower().strip()
        
        # Case 1: Exact match (expected appears in actual)
        if expected_lower in actual_lower:
            return True, "exact_match"
        
        # Case 2: "NOT IN DOCUMENTS" handling
        if expected_lower == "[not in documents]":
            uncertainty_phrases = [
                "not available",
                "not provided", 
                "does not provide",
                "does not specify",
                "no information",
                "not found in",
                "cannot find",
                "don't have information",
                "not in the documents",
                "not mentioned",
                "insufficient data",
                "no data",
                "unable to find",
                "could not find",
                "doesn't specify",
                "isn't specified",
                "not included"
            ]
            if any(phrase in actual_lower for phrase in uncertainty_phrases):
                return True, "uncertainty_match"
            return False, "should_say_unknown"
        
        # Case 3: Numeric extraction and comparison
        expected_numbers = self._extract_numbers(expected)
        actual_numbers = self._extract_numbers(actual)
        
        if expected_numbers:
            # Check if all expected numbers appear in actual
            if expected_numbers.issubset(actual_numbers):
                return True, "number_match"
            
            # Check if primary number matches (first/largest)
            expected_primary = self._get_primary_number(expected)
            actual_primary = self._get_primary_number(actual)
            if expected_primary and actual_primary:
                if self._numbers_match(expected_primary, actual_primary):
                    return True, "number_match"
        
        # Case 4: Percentage matching (30% vs 30%+)
        expected_pct = self._extract_percentage(expected)
        actual_pct = self._extract_percentage(actual)
        if expected_pct and actual_pct:
            # Strip + suffix for comparison
            if expected_pct.rstrip('+%') == actual_pct.rstrip('+%'):
                return True, "percentage_match"
        
        # Case 5: Key entity extraction
        expected_entities = self._extract_key_entities(expected)
        if expected_entities:
            matches = sum(1 for e in expected_entities if e.lower() in actual_lower)
            # If 70%+ of key entities present, consider it a match
            if matches >= len(expected_entities) * 0.7:
                return True, "entity_match"
        
        # Case 6: Boolean/Yes-No matching
        if self._is_boolean_match(expected_lower, actual_lower):
            return True, "boolean_match"
        
        return False, "no_match"
    
    def _extract_numbers(self, text: str) -> set:
        """Extract all numbers from text, normalized."""
        numbers = set()
        
        # Currency: $500,000 or $1.2M
        for match in re.findall(r'\$[\d,]+(?:\.\d+)?(?:[MmBbKk])?', text):
            numbers.add(self._normalize_number(match))
        
        # Plain numbers with optional commas/decimals
        for match in re.findall(r'\b[\d,]+(?:\.\d+)?\b', text):
            normalized = self._normalize_number(match)
            if normalized:  # Skip empty
                numbers.add(normalized)
        
        return numbers
    
    def _normalize_number(self, num_str: str) -> str:
        """Normalize number string for comparison."""
        # Remove $ and commas
        normalized = num_str.replace('$', '').replace(',', '')
        
        # Handle M/B/K suffixes
        if normalized.endswith(('M', 'm')):
            try:
                value = float(normalized[:-1]) * 1_000_000
                return str(int(value))
            except:
                pass
        elif normalized.endswith(('B', 'b')):
            try:
                value = float(normalized[:-1]) * 1_000_000_000
                return str(int(value))
            except:
                pass
        elif normalized.endswith(('K', 'k')):
            try:
                value = float(normalized[:-1]) * 1_000
                return str(int(value))
            except:
                pass
        
        return normalized
    
    def _get_primary_number(self, text: str) -> str:
        """Get the most significant number from text."""
        numbers = list(self._extract_numbers(text))
        if not numbers:
            return None
        # Return largest number (likely the main value)
        try:
            return max(numbers, key=lambda x: float(x) if x else 0)
        except:
            return numbers[0]
    
    def _numbers_match(self, a: str, b: str) -> bool:
        """Check if two number strings represent the same value."""
        try:
            return abs(float(a) - float(b)) < 0.01
        except:
            return a == b
    
    def _extract_percentage(self, text: str) -> str:
        """Extract percentage value."""
        match = re.search(r'(\d+(?:\.\d+)?%\+?)', text)
        return match.group(1) if match else None
    
    def _extract_key_entities(self, text: str) -> list:
        """Extract likely entity names."""
        entities = []
        
        # Quoted strings
        entities.extend(re.findall(r'"([^"]+)"', text))
        
        # Parenthetical names
        entities.extend(re.findall(r'\(([A-Z][^)]+)\)', text))
        
        # Capitalized multi-word names (e.g., "Boston Office")
        entities.extend(re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', text))
        
        # Single capitalized words that aren't common
        common_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'what', 'how', 'which'}
        for word in re.findall(r'\b[A-Z][a-z]+\b', text):
            if word.lower() not in common_words:
                entities.append(word)
        
        return entities
    
    def _is_boolean_match(self, expected: str, actual: str) -> bool:
        """Check if both express same yes/no meaning."""
        yes_words = {'yes', 'true', 'correct', 'affirmative', 'confirmed'}
        no_words = {'no', 'false', 'incorrect', 'negative', 'denied'}
        
        expected_yes = any(w in expected for w in yes_words)
        expected_no = any(w in expected for w in no_words)
        actual_yes = any(w in actual for w in yes_words)
        actual_no = any(w in actual for w in no_words)
        
        if expected_yes and actual_yes:
            return True
        if expected_no and actual_no:
            return True
        
        return False
```

---

## Test Executor

```python
# test_executor.py

import json
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from .evaluator import FuzzyEvaluator

class TestExecutor:
    """Run test questions against a vault."""
    
    def __init__(self, api_base_url: str, auth_token: str, evaluator: FuzzyEvaluator):
        self.api = api_base_url
        self.headers = {"Authorization": f"Bearer {auth_token}"}
        self.evaluator = evaluator
    
    def run_test(
        self, 
        vault_id: str, 
        questions_file: Path,
        results_dir: Path,
        corpus_name: str,
        min_chunks: int = 50
    ) -> dict:
        """
        Run all questions, evaluate answers, save results.
        
        Args:
            vault_id: Vault to query
            questions_file: Path to questions JSON
            results_dir: Where to save results
            corpus_name: For labeling output
            min_chunks: Minimum chunks required (sanity check)
            
        Returns:
            Summary dict with results
        """
        
        # Sanity check: verify vault has enough data
        chunk_count = self._get_chunk_count(vault_id)
        print(f"  Vault has {chunk_count} chunks")
        
        if chunk_count < min_chunks:
            raise ValueError(
                f"Only {chunk_count} chunks in vault (expected >= {min_chunks}). "
                f"Extraction likely incomplete. Aborting test."
            )
        
        # Load questions
        with open(questions_file) as f:
            data = json.load(f)
        
        # Handle both formats: list of questions or {questions: [...]}
        if isinstance(data, list):
            questions = data
        else:
            questions = data.get('questions', data.get('items', []))
        
        print(f"  Running {len(questions)} questions...")
        
        results = []
        passed = 0
        
        for i, q in enumerate(questions):
            q_num = q.get('id', q.get('q', i + 1))
            query = q.get('question', q.get('query', ''))
            expected = q.get('expected_answer', q.get('expected', ''))
            
            # Query the vault
            actual = self._query_vault(vault_id, query)
            
            # Evaluate
            is_pass, match_type = self.evaluator.evaluate(expected, actual)
            
            if is_pass:
                passed += 1
            
            results.append({
                "q": q_num,
                "passed": is_pass,
                "match_type": match_type,
                "query": query[:50],
                "expected": expected[:50],
                "answer": actual[:60] if actual else ""
            })
            
            # Progress indicator
            status = "✓" if is_pass else "✗"
            if (i + 1) % 25 == 0 or not is_pass:
                print(f"  [{q_num}] {status} {match_type}")
        
        # Build summary
        summary = {
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "corpus": corpus_name,
            "vault_id": vault_id,
            "chunk_count": chunk_count,
            "summary": {
                "total": len(questions),
                "passed": passed,
                "failed": len(questions) - passed,
                "accuracy_pct": round(100 * passed / len(questions), 1)
            },
            "breakdown": self._calculate_breakdown(results),
            "failures": [r for r in results if not r['passed']],
            "all_results": results
        }
        
        # Save results
        results_dir.mkdir(exist_ok=True)
        timestamp = summary['timestamp']
        safe_name = corpus_name.lower().replace(' ', '_')
        results_file = results_dir / f"{safe_name}_{timestamp}.json"
        
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"\n  Results saved: {results_file}")
        
        return summary
    
    def _query_vault(self, vault_id: str, query: str) -> str:
        """Send query to vault, return answer."""
        try:
            response = requests.post(
                f"{self.api}/vaults/{vault_id}/query",
                headers=self.headers,
                json={"query": query},
                timeout=60
            )
            if response.status_code == 200:
                return response.json().get('answer', '')
            else:
                return f"[ERROR: {response.status_code}]"
        except Exception as e:
            return f"[ERROR: {str(e)}]"
    
    def _get_chunk_count(self, vault_id: str) -> int:
        """Get chunk count for sanity check."""
        try:
            response = requests.get(
                f"{self.api}/vaults/{vault_id}/stats",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json().get('chunk_count', 0)
        except:
            pass
        return 0
    
    def _calculate_breakdown(self, results: list) -> dict:
        """Calculate pass/fail by question range."""
        ranges = [
            ("Q1-100", 1, 100),
            ("Q101-200", 101, 200),
            ("Q201-235", 201, 235)
        ]
        
        breakdown = {}
        for label, start, end in ranges:
            range_results = [r for r in results if start <= r['q'] <= end]
            if range_results:
                breakdown[label] = {
                    "passed": sum(1 for r in range_results if r['passed']),
                    "total": len(range_results)
                }
        
        return breakdown
```

---

## Main Runner

```python
# runner.py

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from .vault_manager import VaultManager
from .document_uploader import get_files_to_upload
from .test_executor import TestExecutor
from .evaluator import FuzzyEvaluator


def load_config(config_path: str) -> dict:
    with open(config_path) as f:
        return json.load(f)


def save_config(config: dict, config_path: str):
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)


def run_full_test(corpus_name: str, config_path: str = "test_config.json"):
    """
    Full test pipeline:
    1. Delete existing vault (if any)
    2. Create new vault
    3. Upload documents
    4. Wait for extraction (PROPERLY)
    5. Verify chunk count (sanity check)
    6. Run questions
    7. Save results
    8. Update config (DO NOT delete vault)
    """
    
    print(f"\n{'='*60}")
    print(f"CONTEXT FOUNDRY TEST RUNNER")
    print(f"Corpus: {corpus_name}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Load config
    config = load_config(config_path)
    
    if corpus_name not in config['corpora']:
        print(f"ERROR: Unknown corpus '{corpus_name}'")
        print(f"Available: {list(config['corpora'].keys())}")
        sys.exit(1)
    
    corpus_config = config['corpora'][corpus_name]
    extraction_config = config.get('extraction', {})
    
    # Initialize components
    vault_mgr = VaultManager(
        api_base_url=config['api_base_url'],
        auth_token=config['auth_token']
    )
    evaluator = FuzzyEvaluator()
    executor = TestExecutor(
        api_base_url=config['api_base_url'],
        auth_token=config['auth_token'],
        evaluator=evaluator
    )
    
    try:
        # Step 1: Prepare clean vault
        print("Step 1: Preparing vault...")
        vault_id = vault_mgr.ensure_clean_vault(corpus_name)
        
        # Update config immediately
        corpus_config['current_vault_id'] = vault_id
        save_config(config, config_path)
        
        # Step 2: Find and upload documents
        print("\nStep 2: Uploading documents...")
        corpus_root = Path(corpus_config['root_path'])
        
        if not corpus_root.exists():
            raise FileNotFoundError(f"Corpus root not found: {corpus_root}")
        
        files = get_files_to_upload(corpus_root)
        print(f"  Found {len(files)} files to upload")
        
        if len(files) == 0:
            raise ValueError(f"No files found to upload in {corpus_root}")
        
        for i, file_path in enumerate(files):
            relative = file_path.relative_to(corpus_root)
            print(f"  [{i+1}/{len(files)}] {relative}")
            vault_mgr.upload_document(vault_id, file_path)
        
        # Step 3: Wait for extraction (CRITICAL - must wait properly)
        print("\nStep 3: Waiting for extraction...")
        vault_mgr.wait_for_extraction(
            vault_id=vault_id,
            expected_docs=len(files),
            timeout_minutes=extraction_config.get('timeout_minutes', 15),
            poll_interval=extraction_config.get('poll_interval_seconds', 5)
        )
        
        # Step 4: Run test
        print("\nStep 4: Running test questions...")
        questions_file = Path(config['questions_dir']) / corpus_config['questions_file']
        results_dir = Path(config['results_dir'])
        
        if not questions_file.exists():
            raise FileNotFoundError(f"Questions file not found: {questions_file}")
        
        summary = executor.run_test(
            vault_id=vault_id,
            questions_file=questions_file,
            results_dir=results_dir,
            corpus_name=corpus_name,
            min_chunks=extraction_config.get('min_expected_chunks', 50)
        )
        
        # Step 5: Update config with results
        corpus_config['last_run'] = summary['timestamp']
        corpus_config['last_accuracy'] = summary['summary']['accuracy_pct']
        save_config(config, config_path)
        
        # Final summary
        print(f"\n{'='*60}")
        print(f"TEST COMPLETE")
        print(f"{'='*60}")
        print(f"Corpus:      {corpus_name}")
        print(f"Vault ID:    {vault_id}")
        print(f"Chunks:      {summary.get('chunk_count', 'N/A')}")
        print(f"Accuracy:    {summary['summary']['accuracy_pct']}%")
        print(f"Passed:      {summary['summary']['passed']}/{summary['summary']['total']}")
        print(f"")
        print(f"Breakdown:")
        for section, data in summary['breakdown'].items():
            pct = round(100 * data['passed'] / data['total'], 1) if data['total'] > 0 else 0
            print(f"  {section}: {data['passed']}/{data['total']} ({pct}%)")
        print(f"")
        print(f"Failures: {summary['summary']['failed']}")
        if summary['failures']:
            for f in summary['failures'][:5]:  # Show first 5
                print(f"  Q{f['q']}: {f['match_type']}")
            if len(summary['failures']) > 5:
                print(f"  ... and {len(summary['failures']) - 5} more")
        print(f"")
        print(f"Vault preserved for manual queries: {vault_id}")
        print(f"{'='*60}\n")
        
        return summary
        
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"TEST FAILED")
        print(f"{'='*60}")
        print(f"Error: {str(e)}")
        print(f"{'='*60}\n")
        raise


def list_corpora(config_path: str):
    """List available corpora and their status."""
    config = load_config(config_path)
    
    print("\nAvailable corpora:")
    print("-" * 50)
    
    for name, data in config['corpora'].items():
        accuracy = data.get('last_accuracy')
        last_run = data.get('last_run')
        vault_id = data.get('current_vault_id')
        
        status = f"{accuracy}%" if accuracy else "never tested"
        vault = f"({vault_id[:8]}...)" if vault_id else "(no vault)"
        
        print(f"  {name}")
        print(f"    Status: {status}")
        print(f"    Vault:  {vault}")
        if last_run:
            print(f"    Last:   {last_run}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Context Foundry Standardized Test Runner"
    )
    parser.add_argument(
        "--corpus", 
        help="Corpus name to test"
    )
    parser.add_argument(
        "--config", 
        default="test_config.json",
        help="Config file path"
    )
    parser.add_argument(
        "--list", 
        action="store_true",
        help="List available corpora"
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_corpora(args.config)
        return
    
    if not args.corpus:
        parser.print_help()
        print("\nError: --corpus is required (or use --list)")
        sys.exit(1)
    
    run_full_test(args.corpus, args.config)


if __name__ == "__main__":
    main()
```

---

## Usage

```bash
# List available corpora and their status
python -m test_runner.runner --list

# Run full test on a corpus (sequential - one at a time)
python -m test_runner.runner --corpus "Manus Healthtec"

# Run with custom config
python -m test_runner.runner --corpus "ClaudeCode Medsync" --config my_config.json
```

---

## Critical Rules

1. **RUN TESTS SEQUENTIALLY** — Never run multiple corpora in parallel. One at a time.

2. **WAIT FOR EXTRACTION PROPERLY** — Three phases:
   - Wait for documents to register
   - Wait for extraction requests to be created  
   - Wait for all requests to complete

3. **SANITY CHECK BEFORE TESTING** — If chunk count < 50, abort. Extraction is incomplete.

4. **DO NOT DELETE VAULT AFTER TEST** — User needs to query manually.

5. **USE FUZZY EVALUATOR** — Not strict string matching.

---

## Replit Button Configuration

Add to `.replit` for one-click testing:

```toml
[[workflows]]
name = "Test Manus Healthtec"
author = "agent"

[[workflows.tasks]]
task = "shell.exec"
args = "python -m test_runner.runner --corpus 'Manus Healthtec'"

[[workflows]]
name = "Test ClaudeCode Medsync"
author = "agent"

[[workflows.tasks]]
task = "shell.exec"
args = "python -m test_runner.runner --corpus 'ClaudeCode Medsync'"

[[workflows]]
name = "Test Manus Medsync"
author = "agent"

[[workflows.tasks]]
task = "shell.exec"
args = "python -m test_runner.runner --corpus 'Manus Medsync'"

[[workflows]]
name = "List Test Corpora"
author = "agent"

[[workflows.tasks]]
task = "shell.exec"
args = "python -m test_runner.runner --list"
```
