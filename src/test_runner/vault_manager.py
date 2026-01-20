import time
import requests
from pathlib import Path
from typing import Optional, Dict, List

class VaultManager:
    """Manage vault lifecycle via CF API."""
    
    def __init__(self, api_base_url: str):
        self.api = api_base_url
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})
        self._authenticated = False
    
    def authenticate_dev(self, tenant_id: str = None, email: str = None) -> bool:
        """Authenticate with dev user for testing.
        
        Args:
            tenant_id: Optional tenant ID to set context for
            email: Email to authenticate as (default: saleh.hamed@gmail.com for visibility in UI)
        """
        try:
            payload = {'email': email or 'saleh.hamed@gmail.com'}
            if tenant_id:
                payload['tenant_id'] = tenant_id
            response = self.session.post(f'{self.api}/dev/auth', json=payload)
            self._authenticated = response.status_code == 200
            if not self._authenticated:
                print(f"  Auth response: {response.status_code} - {response.text[:200]}")
            return self._authenticated
        except Exception as e:
            print(f"  Auth failed: {e}")
            return False
    
    def find_vault_by_name(self, name: str) -> Optional[str]:
        """Find existing vault ID by name."""
        response = self.session.get(f"{self.api}/vaults")
        if response.status_code != 200:
            return None
        
        data = response.json()
        # API returns {'success': True, 'vaults': [...]}
        vaults = data.get('vaults', []) if isinstance(data, dict) else data
        for vault in vaults:
            if isinstance(vault, dict) and vault.get('name') == name:
                return vault.get('id')
        return None
    
    def delete_vault(self, vault_id: str, vault_name: str) -> bool:
        """Delete vault by ID with confirmation (requires vault name)."""
        # DELETE endpoint requires both confirm_delete AND confirmation_name matching vault name
        response = self.session.delete(
            f"{self.api}/vaults/{vault_id}",
            json={"confirm_delete": True, "confirmation_name": vault_name}
        )
        return response.status_code in [200, 204]
    
    def create_vault(self, name: str) -> str:
        """Create new vault, return ID."""
        response = self.session.post(
            f"{self.api}/vaults",
            json={"name": name}
        )
        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to create vault: {response.status_code} - {response.text}")
        data = response.json()
        # API returns {'success': True, 'vault': {'id': ..., 'name': ...}}
        if 'vault' in data:
            return data['vault'].get('id')
        return data.get('id')
    
    def ensure_clean_vault(self, name: str) -> str:
        """Delete existing vault if present, create fresh one."""
        existing_id = self.find_vault_by_name(name)
        if existing_id:
            print(f"  Deleting existing vault: {name} ({existing_id})")
            self.delete_vault(existing_id, name)
            time.sleep(3)
        
        print(f"  Creating new vault: {name}")
        new_id = self.create_vault(name)
        print(f"  Vault ID: {new_id}")
        return new_id
    
    def upload_document(self, vault_id: str, file_path: Path) -> bool:
        """Upload a single document to vault using session-based endpoint."""
        import mimetypes
        
        mime_type, _ = mimetypes.guess_type(str(file_path))
        if not mime_type:
            mime_type = 'application/octet-stream'
        
        with open(file_path, 'rb') as f:
            # Use list of tuples format for multipart file upload
            files = [('files', (file_path.name, f, mime_type))]
            # For file uploads: use fresh request with only cookies (not session headers)
            # This lets requests library set proper Content-Type with boundary
            response = requests.post(
                f"{self.api}/documents/upload/multi",
                files=files,
                cookies=self.session.cookies
            )
        return response.status_code in [200, 201, 302]
    
    def _get_vault_stats_with_retry(self, vault_id: str, max_retries: int = 5) -> Dict:
        """Get vault stats with retry logic for server restarts and connection issues."""
        import requests.exceptions
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(f"{self.api}/vaults/{vault_id}/stats", timeout=30)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    # Server may have restarted, re-authenticate
                    if attempt < max_retries - 1:
                        print(f"  [Retry {attempt+1}] Re-authenticating...")
                        time.sleep(2)
                        self.authenticate_dev(tenant_id=vault_id)
                else:
                    print(f"  [Retry {attempt+1}] Unexpected status: {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(3)
            except requests.exceptions.ConnectionError as e:
                if attempt < max_retries - 1:
                    print(f"  [Retry {attempt+1}] Connection error, retrying in 5s...")
                    time.sleep(5)
                    # Re-authenticate in case server restarted
                    try:
                        self.authenticate_dev(tenant_id=vault_id)
                    except:
                        pass
                else:
                    raise
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"  [Retry {attempt+1}] Timeout, retrying...")
                    time.sleep(2)
                else:
                    raise
        return {}
    
    def get_document_count(self, vault_id: str) -> int:
        """Get number of documents in vault using vault stats endpoint."""
        data = self._get_vault_stats_with_retry(vault_id)
        return data.get('document_count', 0)
    
    def get_extraction_status(self, vault_id: str) -> Dict:
        """Get extraction status using vault stats endpoint."""
        data = self._get_vault_stats_with_retry(vault_id)
        # Use extraction request counts from API
        return {
            "total": data.get('extraction_total', 0),
            "pending": data.get('extraction_pending', 0),
            "processing": data.get('extraction_processing', 0),
            "completed": data.get('extraction_completed', 0),
            "failed": data.get('extraction_failed', 0)
        }
    
    def get_vault_stats(self, vault_id: str) -> Dict:
        """Get vault statistics including chunk count (with retry logic)."""
        data = self._get_vault_stats_with_retry(vault_id)
        vault = data.get('vault', data)
        return {
            "chunk_count": vault.get('chunk_count', 0),
            "entity_count": vault.get('entity_count', 0),
            "relationship_count": vault.get('relationship_count', 0)
        }
    
    def wait_for_extraction(
        self, 
        vault_id: str, 
        expected_docs: int,
        timeout_minutes: int = 30,
        poll_interval: int = 10,
        heartbeat_callback=None
    ) -> bool:
        """PROPERLY wait for extraction with 3 phases.
        
        Args:
            heartbeat_callback: Optional callable to refresh heartbeat during long waits
        """
        start = time.time()
        timeout = timeout_minutes * 60
        
        print(f"  Waiting for extraction (timeout: {timeout_minutes} min)...")
        
        # PHASE 1: Wait for documents to be registered
        print("  Phase 1: Waiting for documents to register...")
        while time.time() - start < timeout:
            if heartbeat_callback:
                heartbeat_callback()
            doc_count = self.get_document_count(vault_id)
            if doc_count >= expected_docs:
                print(f"  Phase 1 complete: {doc_count}/{expected_docs} documents registered")
                break
            if doc_count > 0:
                print(f"    {doc_count}/{expected_docs} documents registered...")
            time.sleep(poll_interval)
        else:
            raise TimeoutError("Timeout waiting for documents to register")
        
        # PHASE 2: Wait for extraction requests to be created
        # Note: Spreadsheets don't create extraction requests (processed synchronously)
        print("  Phase 2: Waiting for extraction requests...")
        phase2_wait = 0
        last_total = 0
        stable_count = 0
        while time.time() - start < timeout:
            if heartbeat_callback:
                heartbeat_callback()
            status = self.get_extraction_status(vault_id)
            total = status.get('total', 0)
            
            # Check if count has stabilized (same for 3 consecutive polls)
            if total == last_total and total > 0:
                stable_count += 1
                if stable_count >= 3:
                    # Count stabilized - some docs may be spreadsheets
                    print(f"  Phase 2 complete: {total} extraction requests (some docs may be spreadsheets)")
                    break
            else:
                stable_count = 0
                last_total = total
            
            if total >= expected_docs:
                print(f"  Phase 2 complete: {total} extraction requests created")
                break
            if total > 0:
                print(f"    {total}/{expected_docs} extraction requests created...")
            time.sleep(poll_interval)
            phase2_wait += poll_interval
        else:
            # If we have some requests, continue to phase 3
            if last_total > 0:
                print(f"  Phase 2: Proceeding with {last_total} extraction requests")
            else:
                raise TimeoutError("Timeout waiting for extraction requests")
        
        # PHASE 3: Wait for all extractions to complete
        print("  Phase 3: Waiting for extraction to complete...")
        last_progress = ""
        while time.time() - start < timeout:
            if heartbeat_callback:
                heartbeat_callback()
            status = self.get_extraction_status(vault_id)
            total = status.get('total', 0)
            completed = status.get('completed', 0)
            pending = status.get('pending', 0)
            failed = status.get('failed', 0)
            processing = status.get('processing', 0)
            
            progress = f"{completed}/{total} complete, {pending} pending, {processing} processing, {failed} failed"
            if progress != last_progress:
                print(f"    Progress: {progress}")
                last_progress = progress
            
            # Done when no pending AND no processing
            if total > 0 and pending == 0 and processing == 0:
                if failed > 0:
                    print(f"  Warning: {failed} extractions failed")
                print(f"  Phase 3 complete: {completed} succeeded, {failed} failed")
                return True
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Extraction did not complete within {timeout_minutes} minutes")
    
    def query(self, vault_id: str, question: str, timeout: int = 60) -> tuple[str, str]:
        """Query the vault and return (answer, error_type).
        
        Args:
            vault_id: The vault to query
            question: The question to ask
            timeout: Timeout in seconds (default 60)
            
        Returns:
            Tuple of (answer, error_type) where error_type is None on success,
            'timeout' on timeout, or 'error' on other failures.
        """
        import sys
        from requests.exceptions import ReadTimeout, Timeout
        
        print(f"    [VM.query] Sending request (timeout={timeout}s)...", flush=True)
        sys.stdout.flush()
        try:
            response = self.session.post(
                f"{self.api}/vault/chat",
                json={"query": question, "vault_id": vault_id},
                timeout=timeout
            )
            print(f"    [VM.query] Response: {response.status_code}", flush=True)
            sys.stdout.flush()
            if response.status_code == 200:
                data = response.json()
                answer = data.get('answer', data.get('response', data.get('message', '')))
                return (answer, None)
            print(f"    [VM.query] Error: {response.text[:200]}", flush=True)
            return ("", "error")
        except (ReadTimeout, Timeout) as e:
            print(f"    [VM.query] TIMEOUT after {timeout}s: {question[:50]}...", flush=True)
            sys.stdout.flush()
            return ("", "timeout")
        except Exception as e:
            print(f"    [VM.query] Exception: {e}", flush=True)
            sys.stdout.flush()
            return ("", "error")
