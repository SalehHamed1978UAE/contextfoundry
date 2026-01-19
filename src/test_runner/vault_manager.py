"""
Vault manager for vault lifecycle and extraction waiting.

Handles:
- Vault creation/deletion via API
- Document upload
- Three-phase extraction waiting
"""

import time
import requests
from pathlib import Path
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)


class VaultManager:
    """Manage vault lifecycle via CF API."""
    
    def __init__(self, api_base_url: str, auth_token: str):
        self.api = api_base_url.rstrip('/')
        self.token = auth_token
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def find_vault_by_name(self, name: str) -> Optional[str]:
        """Find existing vault ID by name. Returns None if not found."""
        try:
            response = requests.get(f"{self.api}/api/vaults", headers=self.headers)
            response.raise_for_status()
            vaults = response.json()
            
            for vault in vaults:
                if vault.get('name') == name:
                    return vault.get('id')
            return None
        except requests.RequestException as e:
            logger.error(f"Error finding vault: {e}")
            return None
    
    def delete_vault(self, vault_id: str) -> bool:
        """Delete vault by ID."""
        try:
            response = requests.delete(
                f"{self.api}/api/vaults/{vault_id}",
                headers=self.headers
            )
            return response.status_code in [200, 204]
        except requests.RequestException as e:
            logger.error(f"Error deleting vault: {e}")
            return False
    
    def create_vault(self, name: str) -> str:
        """Create new vault, return ID."""
        response = requests.post(
            f"{self.api}/api/vaults",
            headers=self.headers,
            json={"name": name}
        )
        response.raise_for_status()
        return response.json()['id']
    
    def ensure_clean_vault(self, name: str) -> str:
        """Delete existing vault if present, create fresh one, return ID."""
        
        existing_id = self.find_vault_by_name(name)
        if existing_id:
            print(f"  Deleting existing vault: {name} ({existing_id})")
            self.delete_vault(existing_id)
            time.sleep(2)
        
        print(f"  Creating new vault: {name}")
        new_id = self.create_vault(name)
        print(f"  Vault ID: {new_id}")
        
        return new_id
    
    def upload_document(self, vault_id: str, file_path: Path) -> bool:
        """Upload a single document to vault."""
        try:
            with open(file_path, 'rb') as f:
                files = {'file': (file_path.name, f)}
                response = requests.post(
                    f"{self.api}/documents",
                    headers=self.headers,
                    files=files,
                    params={'vault_id': vault_id}
                )
            return response.status_code in [200, 201]
        except Exception as e:
            logger.error(f"Error uploading {file_path}: {e}")
            return False
    
    def upload_documents(self, vault_id: str, files: List[Path], show_progress: bool = True) -> dict:
        """Upload multiple documents to vault."""
        uploaded = 0
        failed = 0
        
        for i, file_path in enumerate(files):
            if show_progress:
                print(f"  Uploading [{i+1}/{len(files)}]: {file_path.name}")
            
            if self.upload_document(vault_id, file_path):
                uploaded += 1
            else:
                failed += 1
                print(f"  ⚠ Failed: {file_path.name}")
        
        return {"uploaded": uploaded, "failed": failed}
    
    def get_document_count(self, vault_id: str) -> int:
        """Get number of documents in vault."""
        try:
            response = requests.get(
                f"{self.api}/api/vault/{vault_id}/documents",
                headers=self.headers
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    return len(data)
                return data.get('count', 0)
            return 0
        except requests.RequestException:
            return 0
    
    def get_extraction_status(self, vault_id: str) -> dict:
        """
        Get extraction status for vault.
        Returns: {total: int, pending: int, completed: int, failed: int}
        """
        try:
            response = requests.get(
                f"{self.api}/api/vault/{vault_id}/extraction/status",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json()
            return {"total": 0, "pending": 0, "completed": 0, "failed": 0}
        except requests.RequestException:
            return {"total": 0, "pending": 0, "completed": 0, "failed": 0}
    
    def get_chunk_count(self, vault_id: str) -> int:
        """Get number of chunks stored for vault."""
        try:
            response = requests.get(
                f"{self.api}/api/vaults/{vault_id}/stats",
                headers=self.headers
            )
            if response.status_code == 200:
                return response.json().get('chunk_count', 0)
            return 0
        except requests.RequestException:
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
        """
        
        start = time.time()
        timeout = timeout_minutes * 60
        
        print(f"  Waiting for extraction (timeout: {timeout_minutes} min)...")
        
        # ============================================
        # PHASE 1: Wait for documents to be registered
        # ============================================
        print("  Phase 1: Waiting for documents to register...")
        
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
        
        completed = 0
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
    
    def query_vault(self, vault_id: str, query: str) -> str:
        """Query the vault and return the answer."""
        try:
            response = requests.post(
                f"{self.api}/api/query",
                headers={**self.headers, "Content-Type": "application/json"},
                json={
                    "query": query,
                    "vault_id": vault_id
                }
            )
            response.raise_for_status()
            result = response.json()
            return result.get('answer', result.get('response', ''))
        except requests.RequestException as e:
            logger.error(f"Query error: {e}")
            return f"Error: {e}"
