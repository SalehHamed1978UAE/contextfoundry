"""
Tests for pipeline progress tracking.

Tests:
1. start → update → update → complete flow
2. start → update → INTERRUPT → resume picks up correctly  
3. fail() marks document correctly
4. get_stalled() finds stuck documents
"""

import os
import sys
import uuid
import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_foundry.pipeline.progress import (
    ProgressTracker,
    DocumentProgress,
    IngestionStep,
    PipelineProgress,
    ensure_table_exists,
    STEP_ORDER,
)


@pytest.fixture(scope="module")
def setup_table():
    """Ensure pipeline_progress table exists before tests."""
    try:
        ensure_table_exists()
    except Exception as e:
        pytest.skip(f"Could not create table: {e}")


@pytest.fixture
def tracker(setup_table):
    """Create a fresh tracker for each test."""
    t = ProgressTracker()
    yield t
    t.close()


@pytest.fixture
def unique_doc_id():
    """Generate a unique document ID for each test."""
    return f"test-doc-{uuid.uuid4().hex[:8]}"


@pytest.fixture
def tenant_id():
    """Fixed tenant ID for tests."""
    return "test-tenant-001"


class TestProgressTrackerFlow:
    """Test the full start → update → complete flow."""
    
    def test_start_update_complete_flow(self, tracker, unique_doc_id, tenant_id):
        """Test: start → update → update → complete flow."""
        progress = tracker.start(unique_doc_id, tenant_id)
        assert progress.document_id == unique_doc_id
        assert progress.tenant_id == tenant_id
        assert progress.current_step == IngestionStep.QUEUED
        assert progress.steps_completed == []
        assert progress.error is None
        
        progress = tracker.update(unique_doc_id, IngestionStep.READING, {"size": 1024})
        assert progress.current_step == IngestionStep.READING
        assert IngestionStep.READING.value in progress.steps_completed
        assert progress.step_metadata.get("reading", {}).get("size") == 1024
        
        progress = tracker.update(unique_doc_id, IngestionStep.CHUNKING, {"chunks": 8})
        assert progress.current_step == IngestionStep.CHUNKING
        assert IngestionStep.CHUNKING.value in progress.steps_completed
        assert progress.step_metadata.get("chunking", {}).get("chunks") == 8
        
        progress = tracker.update(unique_doc_id, IngestionStep.EXTRACTING, {"entities": 51})
        assert progress.current_step == IngestionStep.EXTRACTING
        assert progress.step_metadata.get("extracting", {}).get("entities") == 51
        
        progress = tracker.complete(unique_doc_id)
        assert progress.current_step == IngestionStep.COMPLETED
        assert progress.completed_at is not None
        assert progress.error is None
        
        tracker.delete_progress(unique_doc_id)
    
    def test_start_returns_existing_if_duplicate(self, tracker, unique_doc_id, tenant_id):
        """Test that start() returns existing progress if document already tracked."""
        progress1 = tracker.start(unique_doc_id, tenant_id)
        tracker.update(unique_doc_id, IngestionStep.READING)
        
        progress2 = tracker.start(unique_doc_id, tenant_id)
        assert progress2.current_step == IngestionStep.READING
        
        tracker.delete_progress(unique_doc_id)


class TestResumeAfterInterrupt:
    """Test resume functionality after simulated interruption."""
    
    def test_resume_picks_up_correctly(self, tracker, unique_doc_id, tenant_id):
        """Test: start → update → INTERRUPT → resume picks up correctly."""
        progress = tracker.start(unique_doc_id, tenant_id)
        tracker.update(unique_doc_id, IngestionStep.READING, {"size": 2048})
        tracker.update(unique_doc_id, IngestionStep.CHUNKING, {"chunks": 5})
        
        tracker.close()
        new_tracker = ProgressTracker()
        
        resumed = new_tracker.resume(unique_doc_id)
        assert resumed is not None
        assert resumed.current_step == IngestionStep.CHUNKING
        assert resumed.step_metadata.get("chunking", {}).get("chunks") == 5
        assert IngestionStep.READING.value in resumed.steps_completed
        assert IngestionStep.CHUNKING.value in resumed.steps_completed
        
        next_step = resumed.get_next_step()
        assert next_step == IngestionStep.EXTRACTING
        
        new_tracker.delete_progress(unique_doc_id)
        new_tracker.close()
    
    def test_resume_returns_none_if_not_found(self, tracker):
        """Test that resume() returns None for unknown document."""
        result = tracker.resume("nonexistent-doc-id-12345")
        assert result is None


class TestFailedDocuments:
    """Test fail() and retry functionality."""
    
    def test_fail_marks_document_correctly(self, tracker, unique_doc_id, tenant_id):
        """Test: fail() marks document correctly."""
        tracker.start(unique_doc_id, tenant_id)
        tracker.update(unique_doc_id, IngestionStep.EXTRACTING)
        
        error_msg = "LLM timeout after 120 seconds"
        progress = tracker.fail(unique_doc_id, error_msg)
        
        assert progress.current_step == IngestionStep.FAILED
        assert progress.error == error_msg
        assert progress.retry_count == 1
        
        progress = tracker.fail(unique_doc_id, "Second failure")
        assert progress.retry_count == 2
        
        tracker.delete_progress(unique_doc_id)
    
    def test_reset_for_retry(self, tracker, unique_doc_id, tenant_id):
        """Test resetting a failed document for retry."""
        tracker.start(unique_doc_id, tenant_id)
        tracker.update(unique_doc_id, IngestionStep.CHUNKING)
        tracker.fail(unique_doc_id, "Some error")
        
        progress = tracker.reset_for_retry(unique_doc_id, IngestionStep.READING)
        assert progress.current_step == IngestionStep.READING
        assert progress.error is None
        
        tracker.delete_progress(unique_doc_id)
    
    def test_reset_for_retry_clears_stale_data(self, tracker, unique_doc_id, tenant_id):
        """Test that reset_for_retry clears stale steps and metadata."""
        tracker.start(unique_doc_id, tenant_id)
        tracker.update(unique_doc_id, IngestionStep.READING, {"size": 1024})
        tracker.update(unique_doc_id, IngestionStep.CHUNKING, {"chunks": 8})
        tracker.update(unique_doc_id, IngestionStep.EXTRACTING, {"entities": 50})
        tracker.fail(unique_doc_id, "Extraction failed")
        
        progress = tracker.reset_for_retry(unique_doc_id, IngestionStep.CHUNKING)
        
        assert progress.current_step == IngestionStep.CHUNKING
        assert progress.error is None
        
        assert IngestionStep.READING.value in progress.steps_completed
        assert IngestionStep.CHUNKING.value not in progress.steps_completed
        assert IngestionStep.EXTRACTING.value not in progress.steps_completed
        
        assert "reading" in progress.step_metadata
        assert "chunking" not in progress.step_metadata
        assert "extracting" not in progress.step_metadata
        
        tracker.delete_progress(unique_doc_id)
    
    def test_get_failed_documents(self, tracker, tenant_id):
        """Test getting failed documents for retry."""
        doc_ids = [f"fail-test-{uuid.uuid4().hex[:8]}" for _ in range(3)]
        
        try:
            for doc_id in doc_ids:
                tracker.start(doc_id, tenant_id)
                tracker.fail(doc_id, "Test failure")
            
            failed = tracker.get_failed(tenant_id, max_retries=3)
            failed_ids = [d.document_id for d in failed]
            
            for doc_id in doc_ids:
                assert doc_id in failed_ids
            
            for _ in range(3):
                tracker.fail(doc_ids[0], "More failures")
            
            failed_after = tracker.get_failed(tenant_id, max_retries=3)
            failed_ids_after = [d.document_id for d in failed_after]
            assert doc_ids[0] not in failed_ids_after
            
        finally:
            for doc_id in doc_ids:
                tracker.delete_progress(doc_id)


class TestStalledDocuments:
    """Test get_stalled() functionality."""
    
    def test_get_stalled_finds_stuck_documents(self, setup_table, tenant_id):
        """Test: get_stalled() finds stuck documents."""
        tracker = ProgressTracker()
        doc_id = f"stalled-test-{uuid.uuid4().hex[:8]}"
        
        try:
            tracker.start(doc_id, tenant_id)
            tracker.update(doc_id, IngestionStep.EXTRACTING)
            
            stalled = tracker.get_stalled(threshold_mins=0)
            stalled_ids = [d.document_id for d in stalled]
            assert doc_id in stalled_ids
            
            progress = tracker.update(doc_id, IngestionStep.STAGING)
            
            stalled_after = tracker.get_stalled(threshold_mins=60)
            stalled_ids_after = [d.document_id for d in stalled_after]
            assert doc_id not in stalled_ids_after
            
        finally:
            tracker.delete_progress(doc_id)
            tracker.close()


class TestPendingAndSummary:
    """Test get_pending() and get_summary()."""
    
    def test_get_pending_excludes_completed_and_failed(self, tracker, tenant_id):
        """Test that get_pending excludes completed and failed documents."""
        doc_ids = {
            "pending": f"pending-{uuid.uuid4().hex[:8]}",
            "completed": f"completed-{uuid.uuid4().hex[:8]}",
            "failed": f"failed-{uuid.uuid4().hex[:8]}",
        }
        
        try:
            tracker.start(doc_ids["pending"], tenant_id)
            tracker.update(doc_ids["pending"], IngestionStep.CHUNKING)
            
            tracker.start(doc_ids["completed"], tenant_id)
            tracker.complete(doc_ids["completed"])
            
            tracker.start(doc_ids["failed"], tenant_id)
            tracker.fail(doc_ids["failed"], "Test failure")
            
            pending = tracker.get_pending(tenant_id)
            pending_ids = [d.document_id for d in pending]
            
            assert doc_ids["pending"] in pending_ids
            assert doc_ids["completed"] not in pending_ids
            assert doc_ids["failed"] not in pending_ids
            
        finally:
            for doc_id in doc_ids.values():
                tracker.delete_progress(doc_id)
    
    def test_get_summary(self, tracker, tenant_id):
        """Test summary counts by step."""
        doc_ids = [f"summary-{uuid.uuid4().hex[:8]}" for _ in range(4)]
        
        try:
            tracker.start(doc_ids[0], tenant_id)
            
            tracker.start(doc_ids[1], tenant_id)
            tracker.update(doc_ids[1], IngestionStep.EXTRACTING)
            
            tracker.start(doc_ids[2], tenant_id)
            tracker.complete(doc_ids[2])
            
            tracker.start(doc_ids[3], tenant_id)
            tracker.fail(doc_ids[3], "Error")
            
            summary = tracker.get_summary(tenant_id)
            
            assert "queued" in summary or "extracting" in summary or "completed" in summary
            
        finally:
            for doc_id in doc_ids:
                tracker.delete_progress(doc_id)


class TestDocumentProgressHelpers:
    """Test DocumentProgress helper methods."""
    
    def test_get_next_step(self, tracker, unique_doc_id, tenant_id):
        """Test getting the next step in the pipeline."""
        progress = tracker.start(unique_doc_id, tenant_id)
        assert progress.get_next_step() == IngestionStep.READING
        
        progress = tracker.update(unique_doc_id, IngestionStep.READING)
        assert progress.get_next_step() == IngestionStep.CLASSIFYING
        
        progress = tracker.complete(unique_doc_id)
        assert progress.get_next_step() is None
        
        tracker.delete_progress(unique_doc_id)
    
    def test_step_order(self):
        """Test that STEP_ORDER is correctly defined."""
        assert STEP_ORDER[0] == IngestionStep.QUEUED
        assert STEP_ORDER[-1] == IngestionStep.COMPLETED
        assert IngestionStep.EXTRACTING in STEP_ORDER
        assert IngestionStep.FAILED not in STEP_ORDER


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
