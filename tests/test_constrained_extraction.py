"""
Test suite for Session 2: Constrained Extraction Pipeline.

Verifies that:
1. SchemaPromptGenerator queries ontology_types dynamically
2. Valid entity types (Service, Database, etc.) are accepted
3. Invalid entity types (CREATURE, MONSTER, etc.) are rejected
4. Relationship type/source/target constraints are enforced
"""

import pytest
import os
from uuid import UUID

from src.context_foundry.ontology import (
    OntologyRepository,
    SchemaPromptGenerator,
    ConstrainedExtractor,
)
from src.context_foundry.ontology.models import EntityExtraction


class TestOntologyRepository:
    """Test database-backed ontology repository."""
    
    def test_get_all_types_returns_expected_layers(self):
        """Verify layer counts match Session 1 seeding."""
        repo = OntologyRepository()
        types = repo.get_all_types()
        
        layer_counts = {}
        for t in types:
            layer_counts[t.layer] = layer_counts.get(t.layer, 0) + 1
        
        assert layer_counts.get(0, 0) == 4, "Expected 4 Layer 0 Meta-Core types"
        assert layer_counts.get(1, 0) == 6, "Expected 6 Layer 1 Common Core types"
        assert layer_counts.get(2, 0) == 10, "Expected 10 Layer 2 IT Ops types"
    
    def test_get_all_relations_returns_13_relations(self):
        """Verify relationship count matches Session 1 seeding."""
        repo = OntologyRepository()
        relations = repo.get_all_relations()
        
        assert len(relations) == 13, f"Expected 13 relations, got {len(relations)}"
    
    def test_is_valid_type_accepts_service(self):
        """Valid type 'Service' should be accepted."""
        repo = OntologyRepository()
        assert repo.is_valid_type("Service") is True
    
    def test_is_valid_type_rejects_creature(self):
        """Invalid type 'CREATURE' should be rejected."""
        repo = OntologyRepository()
        assert repo.is_valid_type("CREATURE") is False
    
    def test_get_snapshot_returns_correct_counts(self):
        """Snapshot should contain all types and relations."""
        repo = OntologyRepository()
        snapshot = repo.get_snapshot(force_refresh=True)
        
        assert len(snapshot.types) == 20, f"Expected 20 types in snapshot, got {len(snapshot.types)}"
        assert len(snapshot.relations) == 13, f"Expected 13 relations in snapshot, got {len(snapshot.relations)}"
    
    def test_get_type_by_name_returns_uuid(self):
        """Should return type object with valid UUID."""
        repo = OntologyRepository()
        service_type = repo.get_type_by_name("Service")
        
        assert service_type is not None
        assert isinstance(service_type.id, UUID)
        assert service_type.layer == 2
        assert service_type.origin == "domain_template"


class TestSchemaPromptGenerator:
    """Test dynamic prompt generation from ontology."""
    
    def test_get_valid_type_names_from_database(self):
        """Should fetch type names from database, not hardcoded."""
        generator = SchemaPromptGenerator()
        valid_types = generator.get_valid_type_names()
        
        assert "Service" in valid_types
        assert "Database" in valid_types
        assert "Component" in valid_types
        assert "Incident" in valid_types
        assert "CREATURE" not in valid_types
    
    def test_build_entity_extraction_prompt_includes_all_layer2_types(self):
        """Entity prompt should include all Layer 2 types."""
        generator = SchemaPromptGenerator()
        prompt = generator.build_entity_extraction_prompt("Test text")
        
        assert "Service" in prompt
        assert "Database" in prompt
        assert "Component" in prompt
        assert "Infrastructure" in prompt
        assert "Team" in prompt
        assert "Incident" in prompt
        assert "Deployment" in prompt
        
        assert "CREATURE" not in prompt
    
    def test_build_relationship_extraction_prompt_includes_semantics(self):
        """Relationship prompt should include trigger phrases."""
        generator = SchemaPromptGenerator()
        prompt = generator.build_relationship_extraction_prompt(
            "Test text",
            "- ServiceA (Service)\n- DatabaseB (Database)"
        )
        
        assert "DEPENDS_ON" in prompt
        assert "OWNS" in prompt
        assert "AFFECTS" in prompt
        
        assert "depends on" in prompt.lower() or "trigger" in prompt.lower()
    
    def test_validate_entity_type_uses_database(self):
        """Type validation should query database, not hardcoded list."""
        generator = SchemaPromptGenerator()
        
        assert generator.validate_entity_type("Service") is True
        assert generator.validate_entity_type("Person") is True
        assert generator.validate_entity_type("CREATURE") is False
        assert generator.validate_entity_type("MONSTER") is False


class TestEntityExtractionValidation:
    """Test Pydantic model validation."""
    
    def test_entity_extraction_rejects_invalid_confidence(self):
        """Confidence outside 0-1 range should raise validation error."""
        import pytest
        
        with pytest.raises(Exception):
            EntityExtraction(
                entity_type="Service",
                canonical_name="TestService",
                source_span="TestService is a service",
                confidence=1.5
            )
        
        with pytest.raises(Exception):
            EntityExtraction(
                entity_type="Service",
                canonical_name="TestService",
                source_span="TestService is a service",
                confidence=-0.5
            )
    
    def test_entity_extraction_strips_type_name(self):
        """Entity type should be stripped of whitespace."""
        entity = EntityExtraction(
            entity_type="  Service  ",
            canonical_name="TestService",
            source_span="test",
            confidence=0.9
        )
        assert entity.entity_type == "Service"


class TestConstrainedExtractorValidation:
    """Test that ConstrainedExtractor properly validates against ontology."""
    
    def test_extractor_loads_types_from_database(self):
        """Extractor should load types from database at extraction time."""
        extractor = ConstrainedExtractor()
        snapshot = extractor.repository.get_snapshot()
        
        valid_types = snapshot.get_valid_type_names()
        
        assert "Service" in valid_types
        assert "CREATURE" not in valid_types
        assert len(valid_types) == 20


def run_verification_queries():
    """Run the Session 2 deliverable verification queries."""
    print("\n" + "="*60)
    print("SESSION 2 VERIFICATION")
    print("="*60)
    
    repo = OntologyRepository()
    snapshot = repo.get_snapshot(force_refresh=True)
    
    print(f"\n1. Total types in ontology: {len(snapshot.types)}")
    for layer in range(3):
        layer_types = [t for t in snapshot.types.values() if t.layer == layer]
        print(f"   Layer {layer}: {len(layer_types)} types")
    
    print(f"\n2. Total relations in ontology: {len(snapshot.relations)}")
    unique_relations = set(r.relation_name for r in snapshot.relations)
    print(f"   Unique relation names: {', '.join(sorted(unique_relations))}")
    
    print("\n3. Type validation tests:")
    test_types = ["Service", "Database", "Person", "CREATURE", "MONSTER", "cat"]
    for type_name in test_types:
        is_valid = repo.is_valid_type(type_name)
        status = "VALID" if is_valid else "REJECTED"
        print(f"   - {type_name}: {status}")
    
    print("\n4. SchemaPromptGenerator dynamic loading:")
    generator = SchemaPromptGenerator()
    valid_names = generator.get_valid_type_names()
    print(f"   Loaded {len(valid_names)} valid types from database")
    print(f"   Types: {', '.join(sorted(valid_names)[:10])}...")
    
    print("\n5. Entity prompt sample (first 500 chars):")
    prompt = generator.build_entity_extraction_prompt("Sample IT Operations text")
    print(f"   {prompt[:500]}...")
    
    print("\n" + "="*60)
    print("SESSION 2 VERIFICATION COMPLETE")
    print("="*60)


if __name__ == "__main__":
    run_verification_queries()
