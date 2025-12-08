"""
Ingestion Runner

Handles document upload and extraction triggering with:
- Parallel batch processing
- Error handling and logging
- Progress tracking
"""
import os
import time
import json
import requests
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from stress_test.config import StressTestConfig
from stress_test.document_generator import GeneratedDocument

logger = logging.getLogger(__name__)

@dataclass
class IngestionResult:
    doc_id: str
    success: bool
    document_db_id: Optional[int] = None
    upload_time_ms: float = 0
    extraction_triggered: bool = False
    extraction_time_ms: float = 0
    entities_extracted: int = 0
    relationships_extracted: int = 0
    error: Optional[str] = None
    extracted_entities: List[Dict] = field(default_factory=list)
    extracted_relationships: List[Dict] = field(default_factory=list)

class IngestionRunner:
    def __init__(self, config: StressTestConfig):
        self.config = config
        self.base_url = config.base_url
        self.session = requests.Session()
        self.results = []
        self.lock = threading.Lock()
        self.authenticated = False
        
        self.total_docs = 0
        self.successful_docs = 0
        self.failed_docs = 0
        self.total_entities = 0
        self.total_relationships = 0
        
    def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid session with tenant context"""
        if self.authenticated:
            return True
            
        try:
            response = self.session.post(
                f"{self.base_url}/api/dev/auth",
                json={"email": "stress-test@context-foundry.local"},
                timeout=10
            )
            if response.status_code == 200:
                self.authenticated = True
                logger.info("Authenticated as stress test user")
                return True
                
            response = self.session.get(f"{self.base_url}/", timeout=10)
            if response.status_code == 200:
                self.authenticated = True
                return True
                
        except Exception as e:
            logger.error(f"Failed to authenticate: {e}")
        
        return False
    
    def upload_document(self, doc: GeneratedDocument) -> IngestionResult:
        """Upload a single document and trigger extraction"""
        start_time = time.time()
        
        self._ensure_authenticated()
        
        try:
            files = {
                'file': (f"{doc.doc_id}.txt", doc.content, 'text/plain')
            }
            
            data = {
                'auto_extract': 'true',
                'priority': 'normal'
            }
            
            response = self.session.post(
                f"{self.base_url}/documents",
                files=files,
                data=data,
                timeout=60
            )
            
            upload_time = (time.time() - start_time) * 1000
            
            if response.status_code not in [200, 201]:
                return IngestionResult(
                    doc_id=doc.doc_id,
                    success=False,
                    upload_time_ms=upload_time,
                    error=f"Upload failed: {response.status_code} - {response.text[:200]}"
                )
            
            result_data = response.json()
            document_id = result_data.get('document_id') or result_data.get('id')
            
            if not document_id:
                return IngestionResult(
                    doc_id=doc.doc_id,
                    success=False,
                    upload_time_ms=upload_time,
                    error="No document_id in response"
                )
            
            extraction_start = time.time()
            extraction_result = self._wait_for_extraction(document_id)
            extraction_time = (time.time() - extraction_start) * 1000
            
            result = IngestionResult(
                doc_id=doc.doc_id,
                success=True,
                document_db_id=document_id,
                upload_time_ms=upload_time,
                extraction_triggered=True,
                extraction_time_ms=extraction_time,
                entities_extracted=extraction_result.get('entity_count', 0),
                relationships_extracted=extraction_result.get('relationship_count', 0),
                extracted_entities=extraction_result.get('entities', []),
                extracted_relationships=extraction_result.get('relationships', [])
            )
            
            with self.lock:
                self.successful_docs += 1
                self.total_entities += result.entities_extracted
                self.total_relationships += result.relationships_extracted
            
            return result
            
        except Exception as e:
            upload_time = (time.time() - start_time) * 1000
            with self.lock:
                self.failed_docs += 1
            return IngestionResult(
                doc_id=doc.doc_id,
                success=False,
                upload_time_ms=upload_time,
                error=str(e)
            )
    
    def _wait_for_extraction(self, document_id: str, max_wait: int = 120) -> Dict:
        """Wait for extraction to complete and return results"""
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            try:
                response = self.session.get(
                    f"{self.base_url}/documents/{document_id}/status",
                    timeout=10
                )
                
                if response.status_code == 200:
                    status = response.json()
                    doc_status = status.get('document_status', '')
                    if doc_status in ['completed', 'extracted', 'failed', 'error']:
                        if doc_status in ['completed', 'extracted']:
                            entities = self._get_document_entities(document_id)
                            return {
                                'entity_count': len(entities),
                                'relationship_count': status.get('relationship_count', 0),
                                'entities': entities,
                                'relationships': []
                            }
                        else:
                            return {'entity_count': 0, 'relationship_count': 0, 'entities': [], 'relationships': []}
                
                time.sleep(3)
                
            except Exception as e:
                logger.warning(f"Error checking extraction status: {e}")
                time.sleep(3)
        
        return {'entity_count': 0, 'relationship_count': 0, 'entities': [], 'relationships': [], 'timeout': True}
    
    def _get_document_entities(self, document_id: str) -> List[Dict]:
        """Get entities extracted from a document"""
        try:
            response = self.session.get(
                f"{self.base_url}/documents/{document_id}/entities",
                timeout=10
            )
            if response.status_code == 200:
                return response.json().get('entities', [])
        except Exception:
            pass
        return []
    
    def ingest_batch(self, documents: List[GeneratedDocument]) -> List[IngestionResult]:
        """Ingest a batch of documents in parallel"""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.config.parallel_extractions) as executor:
            future_to_doc = {
                executor.submit(self.upload_document, doc): doc 
                for doc in documents
            }
            
            for future in as_completed(future_to_doc):
                doc = future_to_doc[future]
                try:
                    result = future.result()
                    results.append(result)
                    with self.lock:
                        self.total_docs += 1
                except Exception as e:
                    results.append(IngestionResult(
                        doc_id=doc.doc_id,
                        success=False,
                        error=str(e)
                    ))
                    with self.lock:
                        self.total_docs += 1
                        self.failed_docs += 1
        
        self.results.extend(results)
        return results
    
    def get_stats(self) -> Dict:
        """Get current ingestion statistics"""
        with self.lock:
            return {
                "total_documents": self.total_docs,
                "successful_documents": self.successful_docs,
                "failed_documents": self.failed_docs,
                "success_rate": self.successful_docs / max(1, self.total_docs),
                "total_entities": self.total_entities,
                "total_relationships": self.total_relationships,
                "avg_entities_per_doc": self.total_entities / max(1, self.successful_docs)
            }
    
    def get_latency_stats(self) -> Dict:
        """Get latency statistics"""
        if not self.results:
            return {}
        
        upload_times = [r.upload_time_ms for r in self.results if r.success]
        extraction_times = [r.extraction_time_ms for r in self.results if r.success and r.extraction_time_ms > 0]
        
        def percentile(data, p):
            if not data:
                return 0
            sorted_data = sorted(data)
            k = (len(sorted_data) - 1) * p / 100
            f = int(k)
            c = f + 1 if f + 1 < len(sorted_data) else f
            return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)
        
        return {
            "upload_p50_ms": percentile(upload_times, 50),
            "upload_p95_ms": percentile(upload_times, 95),
            "upload_p99_ms": percentile(upload_times, 99),
            "extraction_p50_ms": percentile(extraction_times, 50),
            "extraction_p95_ms": percentile(extraction_times, 95),
            "extraction_p99_ms": percentile(extraction_times, 99)
        }
