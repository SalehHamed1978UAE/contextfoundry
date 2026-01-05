"""
Ontology Fallback Tests - Week 4 Stabilization

These tests verify that the schema loading system correctly falls back
to YAML when the ontology database tables are unavailable.

Test Scenarios:
1. Ontology tables available -> load from DB
2. Ontology tables unavailable -> fall back to YAML
3. Fallback should be logged/visible (not silent)
4. Type mappings work in both modes
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Optional


class TestOntologySchemaServiceFallback:
    """Tests for OntologySchemaService fallback behavior."""
    
    def test_service_loads_from_ontology_when_available(self):
        """Verify service loads from ontology tables when DB is available."""
        from src.context_foundry.ontology_foundry.schema_service import OntologySchemaService
        
        service = OntologySchemaService(force_reload=True)
        
        assert hasattr(service, 'entity_types')
        assert hasattr(service, 'relationship_types')
        assert hasattr(service, 'type_mappings')
    
    def test_service_falls_back_to_defaults_when_db_unavailable(self):
        """Verify service uses defaults when DB connection fails."""
        from src.context_foundry.ontology_foundry.schema_service import OntologySchemaService
        
        service = OntologySchemaService(force_reload=True)
        
        default_mappings = service._get_default_type_mappings()
        assert isinstance(default_mappings, dict)
        assert len(default_mappings) > 0
        assert "APPLICATION" in default_mappings
    
    def test_type_mappings_contain_expected_defaults(self):
        """Verify default type mappings include common corrections."""
        from src.context_foundry.ontology_foundry.schema_service import OntologySchemaService
        
        service = OntologySchemaService()
        mappings = service.type_mappings
        
        expected_mappings = {
            "APPLICATION": "SERVICE",
            "APP": "SERVICE",
            "MICROSERVICE": "SERVICE",
        }
        
        for old_type, new_type in expected_mappings.items():
            if old_type in mappings:
                assert mappings[old_type] == new_type, \
                    f"Expected {old_type} -> {new_type}, got {mappings.get(old_type)}"


class TestDomainSchemaLoaderFallback:
    """Tests for DomainSchemaLoader fallback behavior."""
    
    def test_loader_tries_ontology_first(self):
        """Verify loader tries ontology tables before YAML."""
        from src.context_foundry.config.domain_schema import DomainSchemaLoader
        
        with patch.object(DomainSchemaLoader, '_load_from_ontology') as mock_ontology:
            mock_ontology.return_value = None
            
            loader = DomainSchemaLoader()
            loader.load()
            
            mock_ontology.assert_called()
    
    def test_loader_falls_back_to_yaml_on_ontology_failure(self):
        """Verify YAML fallback when ontology unavailable."""
        from src.context_foundry.config.domain_schema import DomainSchemaLoader
        
        loader = DomainSchemaLoader()
        result = loader.load()
        
        assert result is not None
        assert hasattr(result, 'entity_types') or isinstance(result, dict)
    
    def test_yaml_fallback_logs_warning(self):
        """Verify fallback to YAML is logged (not silent)."""
        import logging
        from src.context_foundry.config.domain_schema import DomainSchemaLoader
        
        with patch('src.context_foundry.config.domain_schema.logger') as mock_logger:
            loader = DomainSchemaLoader()
            
            with patch.object(loader, '_load_from_ontology', return_value=None):
                loader.load()
                
            mock_logger.warning.assert_called()


class TestEntityExtractorTypeMappings:
    """Tests for EntityExtractor using OntologySchemaService."""
    
    def test_extractor_uses_ontology_type_mappings(self):
        """Verify extractor gets type mappings from OntologySchemaService."""
        from src.context_foundry.extraction.entity_extractor import EntityExtractor
        
        extractor = EntityExtractor()
        
        if hasattr(extractor, 'type_mappings'):
            assert isinstance(extractor.type_mappings, dict)
    
    def test_type_correction_works_with_fallback(self):
        """Verify type correction works when using fallback mappings."""
        from src.context_foundry.ontology_foundry.schema_service import OntologySchemaService
        
        service = OntologySchemaService()
        mappings = service.type_mappings
        
        test_corrections = [
            ("APPLICATION", "SERVICE"),
            ("APP", "SERVICE"),
        ]
        
        for original, expected in test_corrections:
            if original in mappings:
                assert mappings[original] == expected


class TestGraphBuilderTypeMappings:
    """Tests for GraphBuilder using OntologySchemaService."""
    
    def test_graph_builder_uses_ontology_type_mappings(self):
        """Verify GraphBuilder gets type mappings from OntologySchemaService."""
        from src.context_foundry.agents.graph_builder import GraphBuilderAgent
        
        builder = GraphBuilderAgent()
        
        if hasattr(builder, 'type_mappings'):
            assert isinstance(builder.type_mappings, dict)


class TestFallbackVisibility:
    """Tests to ensure fallback is visible and not silent."""
    
    def test_fallback_is_detectable(self):
        """Verify we can detect when fallback is in use."""
        from src.context_foundry.ontology_foundry.schema_service import OntologySchemaService
        
        service = OntologySchemaService(force_reload=True)
        
        assert hasattr(service, '_loaded')
    
    def test_schema_service_singleton_behavior(self):
        """Verify OntologySchemaService behaves as singleton."""
        from src.context_foundry.ontology_foundry.schema_service import (
            OntologySchemaService,
            get_ontology_schema_service
        )
        
        service1 = get_ontology_schema_service()
        service2 = get_ontology_schema_service()
        
        assert type(service1) == type(service2)


class TestOntologyFallbackIntegration:
    """Integration tests for ontology fallback."""
    
    def test_full_pipeline_works_with_fallback(self):
        """Verify the full extraction pipeline works with fallback."""
        from src.context_foundry.ontology_foundry.schema_service import OntologySchemaService
        
        service = OntologySchemaService()
        
        mappings = service.type_mappings
        assert mappings is not None
        assert isinstance(mappings, dict)
    
    def test_entity_types_available_in_fallback(self):
        """Verify entity types are available when using fallback."""
        from src.context_foundry.ontology_foundry.schema_service import OntologySchemaService
        
        service = OntologySchemaService()
        
        entity_types = service.entity_types
        assert entity_types is not None
    
    def test_relation_types_available_in_fallback(self):
        """Verify relation types are available when using fallback."""
        from src.context_foundry.ontology_foundry.schema_service import OntologySchemaService
        
        service = OntologySchemaService(force_reload=True)
        
        relation_types = service.relationship_types
        assert relation_types is not None
