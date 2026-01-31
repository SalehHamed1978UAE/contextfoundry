"""
Smoke tests for synchronous extraction functionality.

Tests the sync_extract parameter and related methods in document_service.py.
"""
import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from uuid import uuid4

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'platform_foundation', 'src'))


class TestSyncExtractionParameter:
    """Test the sync_extract parameter in upload_document."""
    
    def test_upload_document_has_sync_extract_parameter(self):
        """upload_document should accept sync_extract parameter."""
        from document_service import DocumentService
        
        import inspect
        sig = inspect.signature(DocumentService.upload_document)
        params = list(sig.parameters.keys())
        
        assert 'sync_extract' in params
    
    def test_sync_extract_defaults_to_false(self):
        """sync_extract should default to False."""
        from document_service import DocumentService
        
        import inspect
        sig = inspect.signature(DocumentService.upload_document)
        sync_extract_param = sig.parameters['sync_extract']
        
        assert sync_extract_param.default == False


class TestExtractSyncMethod:
    """Test the _extract_sync private method."""
    
    def test_extract_sync_method_exists(self):
        """DocumentService should have _extract_sync method."""
        from document_service import DocumentService
        
        assert hasattr(DocumentService, '_extract_sync')
        assert callable(getattr(DocumentService, '_extract_sync'))
    
    def test_extract_sync_returns_dict(self):
        """_extract_sync should return a dictionary."""
        from document_service import DocumentService
        
        service = DocumentService(database_url='postgres://fake:fake@localhost/fake')
        
        with patch.object(service, 'queue_for_extraction') as mock_queue:
            with patch.object(service, 'get_extraction_status') as mock_status:
                mock_queue.return_value = {'request_id': 'test-123'}
                mock_status.return_value = {
                    'result_status': 'success',
                    'entities_extracted': 5,
                    'relationships_extracted': 3,
                    'total_tokens': 1000,
                    'error_message': None
                }
                
                document = {'id': str(uuid4())}
                tenant_id = uuid4()
                
                result = service._extract_sync(document, tenant_id)
                
                assert isinstance(result, dict)
                assert 'request_id' in result
                assert 'status' in result


class TestCountPendingExtractions:
    """Test the _count_pending_extractions health check method."""
    
    def test_count_pending_extractions_method_exists(self):
        """DocumentService should have _count_pending_extractions method."""
        from document_service import DocumentService
        
        assert hasattr(DocumentService, '_count_pending_extractions')
        assert callable(getattr(DocumentService, '_count_pending_extractions'))


class TestSyncExtractionIntegration:
    """Integration tests for sync extraction flow."""
    
    def test_sync_extract_with_timeout_returns_timeout_status(self):
        """When extraction times out, status should be 'timeout'."""
        from document_service import DocumentService
        
        service = DocumentService(database_url='postgres://fake:fake@localhost/fake')
        
        with patch.object(service, 'queue_for_extraction') as mock_queue:
            with patch.object(service, 'get_extraction_status') as mock_status:
                with patch('time.sleep'):
                    mock_queue.return_value = {'request_id': 'test-timeout'}
                    mock_status.return_value = {'result_status': None}
                    
                    document = {'id': str(uuid4())}
                    tenant_id = uuid4()
                    
                    result = service._extract_sync(document, tenant_id)
                    
                    assert result['status'] == 'timeout'
                    assert 'error_message' in result


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
