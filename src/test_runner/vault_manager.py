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
        """Get vault stats with retry logic for server restarts and connection issues.
        
        Raises RuntimeError if all retries fail - never returns empty data silently.
        """
        import requests.exceptions
        
        last_error = None
        last_status = None
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(f"{self.api}/vaults/{vault_id}/stats", timeout=30)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 401:
                    last_status = 401
                    last_error = "Authentication failed"
                    if attempt < max_retries - 1:
                        print(f"  [Retry {attempt+1}] Re-authenticating...")
                        time.sleep(2)
                        self.authenticate_dev(tenant_id=vault_id)
                else:
                    last_status = response.status_code
                    last_error = f"HTTP {response.status_code}"
                    print(f"  [Retry {attempt+1}] Unexpected status: {response.status_code}")
                    if attempt < max_retries - 1:
                        time.sleep(3)
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {e}"
                if attempt < max_retries - 1:
                    print(f"  [Retry {attempt+1}] Connection error, retrying in 5s...")
                    time.sleep(5)
                    try:
                        self.authenticate_dev(tenant_id=vault_id)
                    except:
                        pass
                else:
                    raise
            except requests.exceptions.Timeout:
                last_error = "Request timeout"
                if attempt < max_retries - 1:
                    print(f"  [Retry {attempt+1}] Timeout, retrying...")
                    time.sleep(2)
                else:
                    raise
        
        raise RuntimeError(f"Failed to get vault stats after {max_retries} retries: {last_error}")
    
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

    def preflight_vault(self, vault_id: str) -> Dict:
        """Run DB-backed preflight check for vault consistency."""
        response = self.session.get(f"{self.api}/extraction/preflight/{vault_id}", timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"Preflight failed ({response.status_code}): {response.text[:300]}")
        return response.json()
    
    def verify_extraction_complete(self, vault_id: str, timeout_minutes: int = 30, poll_interval: int = 10) -> bool:
        """Verify extraction is complete before starting Q&A.
        
        Returns True if extraction is complete, raises TimeoutError if not complete within timeout.
        Handles edge cases like spreadsheet-only vaults where extraction_total may be 0.
        """
        import time
        start = time.time()
        timeout = timeout_minutes * 60
        first_check = True
        
        print(f"  Verifying extraction is complete (timeout: {timeout_minutes} min)...")
        print(f"  Vault ID: {vault_id}")
        preflight = self.preflight_vault(vault_id)
        if not preflight.get('exists'):
            raise ValueError(f"Vault UUID not found in DB: {vault_id}")
        doc_total = preflight.get('documents', {}).get('total', 0)
        if doc_total <= 0:
            raise ValueError(f"Vault has no documents in platform.documents: {vault_id}")
        dbi = preflight.get('db_identity', {})
        print(f"  Preflight DB: {dbi.get('database_name')}@{dbi.get('server_addr')}:{dbi.get('server_port')} | docs={doc_total}")
        
        while time.time() - start < timeout:
            status = self.get_extraction_status(vault_id)
            total = status.get('total', 0)
            pending = status.get('pending', 0)
            processing = status.get('processing', 0)
            completed = status.get('completed', 0)
            failed = status.get('failed', 0)
            
            elapsed = int(time.time() - start)
            print(f"  [{elapsed}s] Extraction status: total={total}, pending={pending}, processing={processing}, completed={completed}, failed={failed}")
            
            # If no extractions at all, check vault stats for content
            if total == 0:
                doc_count = self.get_document_count(vault_id)
                if doc_count == 0:
                    raise ValueError("No documents found in vault - cannot run Q&A")
                
                # Check if vault has chunks/entities (spreadsheet extraction may skip extraction_requests)
                stats = self.get_vault_stats(vault_id)
                chunk_count = stats.get('chunk_count', 0)
                entity_count = stats.get('entity_count', 0)
                
                if chunk_count > 0 or entity_count > 0:
                    # Vault has content from spreadsheet or other sync extraction
                    print(f"  Extraction complete (spreadsheet mode): {chunk_count} chunks, {entity_count} entities")
                    return True
                
                elapsed = int(time.time() - start)
                print(f"  Waiting for extraction to start: {doc_count} docs, {chunk_count} chunks ({elapsed}s elapsed)")
            else:
                # Done when no pending AND no processing
                if pending == 0 and processing == 0:
                    if failed > 0:
                        print(f"  Warning: {failed} extractions failed")
                    print(f"  Extraction verified complete: {completed}/{total} succeeded")
                    return True
                    
                elapsed = int(time.time() - start)
                print(f"  Extraction in progress: {completed}/{total} complete, {pending} pending, {processing} processing ({elapsed}s elapsed)")
            
            time.sleep(poll_interval)
        
        raise TimeoutError(f"Extraction did not complete within {timeout_minutes} minutes")
    
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
    
    def query(self, vault_id: str, question: str, timeout: int = 60, return_metadata: bool = False, max_retries: int = 3, tree_based_retrieval: bool = None) -> tuple:
        """Query the vault and return (answer, error_type) or (answer, error_type, metadata).

        Args:
            vault_id: The vault to query
            question: The question to ask
            timeout: Timeout in seconds (default 60)
            return_metadata: If True, also return retrieval metadata for tracing
            max_retries: Maximum number of retry attempts for connection failures (default 3)
            tree_based_retrieval: If provided, override tree retrieval setting for this request

        Returns:
            If return_metadata=False: Tuple of (answer, error_type)
            If return_metadata=True: Tuple of (answer, error_type, metadata_dict)

            error_type is None on success, 'timeout' on timeout, or 'error' on other failures.
        """
        import sys
        import traceback
        from requests.exceptions import ReadTimeout, Timeout, ConnectionError, RequestException
        
        empty_metadata = {
            'chunk_sources': [],
            'tool_calls': [],
            'confidence': 0,
            'query_type': 'unknown',
            'gate_blocked': False,
            'gate_name': None
        }
        
        last_error = None
        print(f"    [VM.query] ENTRY: vault={vault_id[:8]}..., q='{question[:40]}...' timeout={timeout}s", flush=True)
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    backoff = min(2 ** attempt, 10)  # Exponential backoff: 2s, 4s, 8s, max 10s
                    print(f"    [VM.query] Retry {attempt}/{max_retries-1} after {backoff}s backoff...", flush=True)
                    time.sleep(backoff)
                
                print(f"    [VM.query] Sending POST to {self.api}/vault/chat...", flush=True)
                sys.stdout.flush()

                # Build request payload
                request_data = {"query": question, "vault_id": vault_id}
                if tree_based_retrieval is not None:
                    request_data["tree_based_retrieval"] = tree_based_retrieval
                    print(f"    [VM.query] Tree-based retrieval: {tree_based_retrieval}", flush=True)

                response = self.session.post(
                    f"{self.api}/vault/chat",
                    json=request_data,
                    timeout=timeout
                )
                print(f"    [VM.query] Response: {response.status_code}", flush=True)
                sys.stdout.flush()
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get('answer', data.get('response', data.get('message', '')))
                    
                    if return_metadata:
                        metadata = {
                            'chunk_sources': data.get('chunk_sources', []),
                            'tool_calls': data.get('tool_calls', []),
                            'confidence': data.get('confidence', 0),
                            'query_type': data.get('query_type', 'unknown'),
                            'gate_blocked': data.get('gate_blocked', False),
                            'gate_name': data.get('gate_name'),
                            'answer_source': data.get('answer_source', 'unknown'),
                            'time_ms': data.get('time_ms', 0)
                        }
                        return (answer, None, metadata)
                    return (answer, None)
                
                # 401 Unauthorized - try re-authenticating
                if response.status_code == 401:
                    last_error = "HTTP 401 Unauthorized"
                    print(f"    [VM.query] Auth expired, re-authenticating...", flush=True)
                    self.authenticate_dev(tenant_id=vault_id)
                    continue
                
                # Non-200 response - check if retryable
                if response.status_code in (429, 502, 503, 504):  # Rate limit or server errors
                    last_error = f"HTTP {response.status_code}"
                    print(f"    [VM.query] Retryable error: {response.status_code}", flush=True)
                    continue
                
                # Non-retryable error
                print(f"    [VM.query] Error: {response.text[:200]}", flush=True)
                if return_metadata:
                    return ("", "error", empty_metadata)
                return ("", "error")
                
            except (ReadTimeout, Timeout) as e:
                print(f"    [VM.query] TIMEOUT after {timeout}s: {question[:50]}...", flush=True)
                sys.stdout.flush()
                if return_metadata:
                    return ("", "timeout", empty_metadata)
                return ("", "timeout")
                
            except (ConnectionError, RequestException) as e:
                # Broader exception handling for connection pool exhaustion, SSL errors, etc.
                last_error = f"Request error: {type(e).__name__}: {e}"
                print(f"    [VM.query] Request error (attempt {attempt+1}/{max_retries}): {type(e).__name__}: {e}", flush=True)
                sys.stdout.flush()
                continue
                
            except Exception as e:
                print(f"    [VM.query] Unexpected exception: {e}", flush=True)
                print(f"    [VM.query] Traceback:\n{traceback.format_exc()}", flush=True)
                sys.stdout.flush()
                if return_metadata:
                    return ("", "error", empty_metadata)
                return ("", "error")
        
        # All retries exhausted
        print(f"    [VM.query] All {max_retries} retries failed: {last_error}", flush=True)
        if return_metadata:
            return ("", "error", empty_metadata)
        return ("", "error")
