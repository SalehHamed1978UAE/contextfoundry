"""
Tests for RLM Memory APIs.

Tests the SemanticMemoryAPI, EpisodicMemoryAPI, and SymbolicMemoryAPI
wrappers that expose the tri-memory architecture to RLM.
"""

import pytest
import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, patch, PropertyMock
from uuid import uuid4

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.context_foundry.rlm.schemas import (
    LifecycleState,
    EntitySummary,
    EntityDetail,
    EntityMatch,
    ChunkSummary,
    ChunkDetail,
    ChunkMatch,
    ProvenanceInfo,
    Relationship,
    Path,
    PathStep,
    SubGraph,
    StaleEntityError,
    ProgressTracker,
    REPLExecutionResult,
    CircuitBreakerTripped,
)
from src.context_foundry.rlm.memory_apis.semantic import SemanticMemoryAPI
from src.context_foundry.rlm.memory_apis.episodic import EpisodicMemoryAPI
from src.context_foundry.rlm.memory_apis.symbolic import SymbolicMemoryAPI


class MockEntity:
    """Mock Entity for testing."""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid4())
        self.tenant_id = kwargs.get('tenant_id', uuid4())
        self.name = kwargs.get('name', 'Test Entity')
        self.entity_type = kwargs.get('entity_type', 'SERVICE')
        self.lifecycle_state = kwargs.get('lifecycle_state', LifecycleState.TRUSTED)
        self.validation_status = kwargs.get('validation_status', 'VALID')
        self.properties = kwargs.get('properties', {'status': 'active'})
        self.description = kwargs.get('description', 'Test description')
        self.confidence = kwargs.get('confidence', 0.85)
        self.source_document_id = kwargs.get('source_document_id', 'doc-123')
        self.extraction_method = kwargs.get('extraction_method', 'llm_extraction')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
        self.promoted_at = kwargs.get('promoted_at', None)
        self.last_validated_at = kwargs.get('last_validated_at', None)


class MockRelationship:
    """Mock Relationship for testing."""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid4())
        self.tenant_id = kwargs.get('tenant_id', uuid4())
        self.source_id = kwargs.get('source_id', uuid4())
        self.target_id = kwargs.get('target_id', uuid4())
        self.relationship_type = kwargs.get('relationship_type', 'DEPENDS_ON')
        self.lifecycle_state = kwargs.get('lifecycle_state', LifecycleState.TRUSTED)
        self.properties = kwargs.get('properties', {})
        self.confidence = kwargs.get('confidence', 0.8)
        self.source_document_id = kwargs.get('source_document_id', 'doc-123')
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.source_entity = kwargs.get('source_entity', MockEntity(name='Source'))
        self.target_entity = kwargs.get('target_entity', MockEntity(name='Target'))


class MockDocument:
    """Mock Document for testing."""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid4())
        self.tenant_id = kwargs.get('tenant_id', uuid4())
        self.title = kwargs.get('title', 'Test Document')
        self.doc_type = kwargs.get('doc_type', 'pdf')
        self.content = kwargs.get('content', 'Test content...')
        self.embedding = kwargs.get('embedding', [0.1] * 1536)
        self.doc_metadata = kwargs.get('doc_metadata', {'uploaded_by': 'user-123'})
        self.created_at = kwargs.get('created_at', datetime.utcnow())


class MockChunk:
    """Mock DocumentChunk for testing."""
    def __init__(self, **kwargs):
        self.id = kwargs.get('id', uuid4())
        self.document_id = kwargs.get('document_id', uuid4())
        self.tenant_id = kwargs.get('tenant_id', uuid4())
        self.chunk_index = kwargs.get('chunk_index', 0)
        self.text = kwargs.get('text', 'Test chunk content...')
        self.char_start = kwargs.get('char_start', 0)
        self.char_end = kwargs.get('char_end', 100)
        self.chunk_metadata = kwargs.get('chunk_metadata', {'page_numbers': [1, 2]})
        self.created_at = kwargs.get('created_at', datetime.utcnow())


class TestSchemas:
    """Test Pydantic schema models."""
    
    def test_entity_summary_creation(self):
        """EntitySummary should be creatable with valid data."""
        summary = EntitySummary(
            id="test-id",
            name="Test Entity",
            entity_type="SERVICE",
            confidence=0.85,
            lifecycle_state=LifecycleState.TRUSTED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            primary_property="status: active",
            property_count=3,
            relationship_count=5
        )
        assert summary.name == "Test Entity"
        assert summary.confidence == 0.85
        assert summary.lifecycle_state == LifecycleState.TRUSTED
    
    def test_entity_detail_with_aliases(self):
        """EntityDetail should support aliases and provenance."""
        detail = EntityDetail(
            id="test-id",
            name="Network Monitor",
            entity_type="SERVICE",
            confidence=0.92,
            lifecycle_state=LifecycleState.TRUSTED,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            properties={"status": "active", "version": "2.0"},
            aliases=["NetMon", "NM"],
            source_document_ids=["doc-1", "doc-2"],
            extraction_method="llm_extraction",
            corroboration_count=3
        )
        assert len(detail.aliases) == 2
        assert "NetMon" in detail.aliases
        assert detail.corroboration_count == 3
    
    def test_chunk_match_with_highlight(self):
        """ChunkMatch should include similarity and highlight."""
        chunk = ChunkDetail(
            id="chunk-1",
            document_id="doc-1",
            chunk_index=0,
            content="The Network Monitor detected an anomaly at 14:32 UTC.",
            token_count=50,
            created_at=datetime.utcnow(),
            document_name="Incident_Report.pdf",
            document_type="pdf",
            upload_date=datetime.utcnow(),
            page_numbers=[5]
        )
        match = ChunkMatch(
            chunk=chunk,
            similarity_score=0.89,
            highlight="...Network Monitor detected an **anomaly**..."
        )
        assert match.similarity_score == 0.89
        assert match.highlight is not None
    
    def test_path_with_steps(self):
        """Path should track steps and confidence."""
        path = Path(
            source_entity_id="entity-a",
            source_entity_name="Service A",
            target_entity_id="entity-c",
            target_entity_name="Service C",
            steps=[
                PathStep(
                    entity_id="entity-b",
                    entity_name="Service B",
                    entity_type="SERVICE",
                    relationship_type="DEPENDS_ON",
                    relationship_id="rel-1"
                ),
                PathStep(
                    entity_id="entity-c",
                    entity_name="Service C",
                    entity_type="SERVICE",
                    relationship_type="TRIGGERS",
                    relationship_id="rel-2"
                )
            ],
            total_hops=2,
            min_confidence=0.75
        )
        assert path.total_hops == 2
        assert len(path.steps) == 2
        assert path.min_confidence == 0.75
    
    def test_subgraph_truncation(self):
        """SubGraph should indicate truncation."""
        subgraph = SubGraph(
            root_entity_id="root",
            root_entity_name="Root Entity",
            entities=[],
            relationships=[],
            depth_reached=2,
            truncated=True
        )
        assert subgraph.truncated == True
        assert subgraph.depth_reached == 2


class TestProgressTracker:
    """Test progress tracking for circuit breaker."""
    
    def test_progress_tracking_with_new_entities(self):
        """Progress should be recorded when new entities discovered."""
        tracker = ProgressTracker()
        
        result = REPLExecutionResult(
            success=True,
            output="Found 3 entities",
            new_entities_discovered=["entity-1", "entity-2", "entity-3"],
            new_relationships_discovered=[]
        )
        
        made_progress = tracker.record_iteration(result)
        
        assert made_progress == True
        assert tracker.iteration == 1
        assert len(tracker.entities_discovered) == 3
        assert tracker.iterations_without_progress == 0
    
    def test_no_progress_increments_counter(self):
        """Counter should increment when no progress made."""
        tracker = ProgressTracker()
        
        result = REPLExecutionResult(
            success=True,
            output="No new entities found",
            new_entities_discovered=[],
            new_relationships_discovered=[]
        )
        
        tracker.record_iteration(result)
        assert tracker.iterations_without_progress == 1
        
        tracker.record_iteration(result)
        assert tracker.iterations_without_progress == 2
    
    def test_circuit_breaker_trips_after_threshold(self):
        """Circuit breaker should trip after N iterations without progress."""
        tracker = ProgressTracker()
        
        empty_result = REPLExecutionResult(
            success=True,
            output="",
            new_entities_discovered=[],
            new_relationships_discovered=[]
        )
        
        for _ in range(3):
            tracker.record_iteration(empty_result)
        
        assert tracker.should_trip_breaker(threshold=3) == True
    
    def test_progress_resets_counter(self):
        """Counter should reset when progress is made."""
        tracker = ProgressTracker()
        
        empty_result = REPLExecutionResult(
            success=True,
            output="",
            new_entities_discovered=[],
            new_relationships_discovered=[]
        )
        
        tracker.record_iteration(empty_result)
        tracker.record_iteration(empty_result)
        assert tracker.iterations_without_progress == 2
        
        progress_result = REPLExecutionResult(
            success=True,
            output="Found relationship",
            new_entities_discovered=[],
            new_relationships_discovered=["rel-1"]
        )
        
        tracker.record_iteration(progress_result)
        assert tracker.iterations_without_progress == 0
        assert tracker.should_trip_breaker() == False


class TestStaleEntityError:
    """Test StaleEntityError exception."""
    
    def test_stale_entity_error_message(self):
        """StaleEntityError should have informative message."""
        error = StaleEntityError("entity-123")
        assert "entity-123" in str(error)
        assert "archived" in str(error).lower() or "exists" in str(error).lower()
    
    def test_stale_entity_error_preserves_id(self):
        """StaleEntityError should preserve entity ID."""
        error = StaleEntityError("entity-xyz")
        assert error.entity_id == "entity-xyz"


class TestSemanticMemoryAPI:
    """Test SemanticMemoryAPI methods."""
    
    def test_access_tracking(self):
        """API should track accessed entity IDs."""
        mock_session = MagicMock()
        api = SemanticMemoryAPI("tenant-123", mock_session)
        
        api._accessed_entity_ids.append("entity-1")
        api._accessed_entity_ids.append("entity-2")
        api._accessed_entity_ids.append("entity-1")
        
        accessed = api.get_accessed_entity_ids()
        assert len(accessed) == 2
        assert "entity-1" in accessed
        assert "entity-2" in accessed
    
    def test_clear_access_tracking(self):
        """API should clear tracking on request."""
        mock_session = MagicMock()
        api = SemanticMemoryAPI("tenant-123", mock_session)
        
        api._accessed_entity_ids.append("entity-1")
        api.clear_access_tracking()
        
        assert len(api._accessed_entity_ids) == 0
    
    def test_find_entities_initializes_correctly(self):
        """find_entities API should initialize with correct tenant."""
        mock_session = MagicMock()
        tenant_id = str(uuid4())
        api = SemanticMemoryAPI(tenant_id, mock_session)
        
        assert api.tenant_id == tenant_id
        assert api.session == mock_session
        assert len(api._accessed_entity_ids) == 0


class TestEpisodicMemoryAPI:
    """Test EpisodicMemoryAPI methods."""
    
    def test_access_tracking(self):
        """API should track accessed chunk IDs."""
        mock_session = MagicMock()
        api = EpisodicMemoryAPI("tenant-123", mock_session)
        
        api._accessed_chunk_ids.append("chunk-1")
        api._accessed_chunk_ids.append("chunk-2")
        
        accessed = api.get_accessed_chunk_ids()
        assert len(accessed) == 2
    
    def test_clear_access_tracking(self):
        """API should clear tracking on request."""
        mock_session = MagicMock()
        api = EpisodicMemoryAPI("tenant-123", mock_session)
        
        api._accessed_chunk_ids.append("chunk-1")
        api.clear_access_tracking()
        
        assert len(api._accessed_chunk_ids) == 0


class TestSymbolicMemoryAPI:
    """Test SymbolicMemoryAPI methods."""
    
    def test_access_tracking(self):
        """API should track accessed relationship IDs."""
        mock_session = MagicMock()
        api = SymbolicMemoryAPI("tenant-123", mock_session)
        
        api._accessed_relationship_ids.append("rel-1")
        api._accessed_relationship_ids.append("rel-2")
        
        accessed = api.get_accessed_relationship_ids()
        assert len(accessed) == 2
    
    def test_clear_access_tracking(self):
        """API should clear tracking on request."""
        mock_session = MagicMock()
        api = SymbolicMemoryAPI("tenant-123", mock_session)
        
        api._accessed_relationship_ids.append("rel-1")
        api.clear_access_tracking()
        
        assert len(api._accessed_relationship_ids) == 0


class TestRelationshipSchema:
    """Test Relationship schema."""
    
    def test_relationship_with_properties(self):
        """Relationship should support properties dict."""
        rel = Relationship(
            id="rel-1",
            source_entity_id="entity-a",
            source_entity_name="Service A",
            target_entity_id="entity-b",
            target_entity_name="Service B",
            relationship_type="DEPENDS_ON",
            confidence=0.92,
            lifecycle_state=LifecycleState.TRUSTED,
            properties={"critical": True, "latency_ms": 50},
            created_at=datetime.utcnow(),
            source_document_ids=["doc-1"]
        )
        assert rel.properties["critical"] == True
        assert rel.properties["latency_ms"] == 50


class TestProvenanceInfo:
    """Test ProvenanceInfo schema."""
    
    def test_provenance_with_processing_steps(self):
        """ProvenanceInfo should track processing chain."""
        provenance = ProvenanceInfo(
            chunk_id="chunk-1",
            document_id="doc-1",
            document_name="Report.pdf",
            document_type="pdf",
            upload_date=datetime.utcnow(),
            uploaded_by="user-123",
            page_numbers=[1, 2, 3],
            section_title="Executive Summary",
            processing_steps=["pdf_extraction", "ocr", "chunking", "embedding"]
        )
        assert len(provenance.processing_steps) == 4
        assert "ocr" in provenance.processing_steps
        assert provenance.section_title == "Executive Summary"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
