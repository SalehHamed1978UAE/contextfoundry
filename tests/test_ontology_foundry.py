"""
Unit tests for ontology_foundry workflows.
Tests SchemaService, schema validation, and dynamic entity type creation.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from collections import namedtuple

from src.context_foundry.ontology_foundry.schema_service import (
    OntologySchemaService,
    TypeMapping,
)
from src.context_foundry.config.domain_schema import (
    EntityTypeConfig,
    RelationshipTypeConfig,
    Cardinality,
    DomainSchema,
)


EntityTypeRow = namedtuple('EntityTypeRow', [
    'id', 'type_name', 'display_name', 'description', 
    'extraction_hints', 'properties_schema', 'layer', 'status'
])

RelationTypeRow = namedtuple('RelationTypeRow', [
    'id', 'relation_type', 'display_name', 'description',
    'cardinality', 'semantics', 'status', 'source_type', 'target_type'
])

TypeTranslationRow = namedtuple('TypeTranslationRow', ['deprecated_name', 'current_name'])


class TestSchemaServiceEntityTypeLoading:
    """Tests for SchemaService entity type loading."""

    def test_load_entity_types_with_list_hints(self):
        """Entity types with list extraction_hints should load keywords correctly."""
        mock_session = Mock()
        mock_result = [
            EntityTypeRow(
                id='1', type_name='SERVICE', display_name='Service',
                description='A software service', 
                extraction_hints=['api', 'microservice', 'application'],
                properties_schema=None, layer='core', status='ACTIVE'
            ),
        ]
        mock_session.execute.return_value = mock_result

        service = OntologySchemaService(session=mock_session, force_reload=True)
        service._load_entity_types()

        assert 'SERVICE' in service.entity_types
        entity = service.entity_types['SERVICE']
        assert entity.name == 'SERVICE'
        assert entity.description == 'A software service'
        assert entity.keywords == ['api', 'microservice', 'application']
        assert entity.required_fields == ['canonical_name']

    def test_load_entity_types_with_dict_hints(self):
        """Entity types with dict extraction_hints should parse all fields."""
        mock_session = Mock()
        mock_result = [
            EntityTypeRow(
                id='2', type_name='PERSON', display_name='Person',
                description='A person entity',
                extraction_hints={
                    'keywords': ['employee', 'user', 'staff'],
                    'required_fields': ['name', 'email'],
                    'optional_fields': ['phone', 'title']
                },
                properties_schema=None, layer='core', status='ACTIVE'
            ),
        ]
        mock_session.execute.return_value = mock_result

        service = OntologySchemaService(session=mock_session, force_reload=True)
        service._load_entity_types()

        assert 'PERSON' in service.entity_types
        entity = service.entity_types['PERSON']
        assert entity.keywords == ['employee', 'user', 'staff']
        assert entity.required_fields == ['name', 'email']
        assert entity.optional_fields == ['phone', 'title']

    def test_load_entity_types_with_no_hints(self):
        """Entity types with no extraction_hints should use defaults."""
        mock_session = Mock()
        mock_result = [
            EntityTypeRow(
                id='3', type_name='TEAM', display_name='Team',
                description='A team entity',
                extraction_hints=None,
                properties_schema=None, layer='core', status='ACTIVE'
            ),
        ]
        mock_session.execute.return_value = mock_result

        service = OntologySchemaService(session=mock_session, force_reload=True)
        service._load_entity_types()

        assert 'TEAM' in service.entity_types
        entity = service.entity_types['TEAM']
        assert entity.keywords == []
        assert entity.required_fields == ['canonical_name']
        assert entity.optional_fields == []

    def test_load_entity_types_uses_display_name_when_no_description(self):
        """Entity types should fall back to display_name if no description."""
        mock_session = Mock()
        mock_result = [
            EntityTypeRow(
                id='4', type_name='DATABASE', display_name='Database System',
                description=None,
                extraction_hints=None,
                properties_schema=None, layer='core', status='ACTIVE'
            ),
        ]
        mock_session.execute.return_value = mock_result

        service = OntologySchemaService(session=mock_session, force_reload=True)
        service._load_entity_types()

        entity = service.entity_types['DATABASE']
        assert entity.description == 'Database System'

    def test_get_valid_entity_types(self):
        """get_valid_entity_types should return set of loaded type names."""
        mock_session = Mock()
        mock_session.execute.return_value = [
            EntityTypeRow(
                id='1', type_name='SERVICE', display_name='Service',
                description='A service', extraction_hints=None,
                properties_schema=None, layer='core', status='ACTIVE'
            ),
            EntityTypeRow(
                id='2', type_name='TEAM', display_name='Team',
                description='A team', extraction_hints=None,
                properties_schema=None, layer='core', status='ACTIVE'
            ),
        ]

        service = OntologySchemaService(session=mock_session, force_reload=True)
        service._load_entity_types()

        valid_types = service.get_valid_entity_types()
        assert valid_types == {'SERVICE', 'TEAM'}


class TestSchemaServiceRelationshipTypeLoading:
    """Tests for SchemaService relationship type loading."""

    def test_load_relationship_types_basic(self):
        """Relationship types should load with source and target types."""
        mock_session = Mock()
        mock_result = [
            RelationTypeRow(
                id='1', relation_type='OWNS', display_name='Owns',
                description='Ownership relationship',
                cardinality='MANY_TO_ONE', semantics=None, status='ACTIVE',
                source_type='TEAM', target_type='SERVICE'
            ),
        ]
        mock_session.execute.return_value = mock_result

        service = OntologySchemaService(session=mock_session, force_reload=True)
        service._load_relationship_types()

        assert 'OWNS' in service.relationship_types
        rel = service.relationship_types['OWNS']
        assert rel.name == 'OWNS'
        assert rel.description == 'Ownership relationship'
        assert 'TEAM' in rel.source_types
        assert 'SERVICE' in rel.target_types
        assert rel.cardinality == Cardinality.MANY_TO_ONE

    def test_load_relationship_types_aggregates_source_target(self):
        """Multiple rows for same relation should aggregate source/target types."""
        mock_session = Mock()
        mock_result = [
            RelationTypeRow(
                id='1', relation_type='DEPENDS_ON', display_name='Depends On',
                description='Dependency relationship',
                cardinality='MANY_TO_MANY', semantics=None, status='ACTIVE',
                source_type='SERVICE', target_type='DATABASE'
            ),
            RelationTypeRow(
                id='2', relation_type='DEPENDS_ON', display_name='Depends On',
                description='Dependency relationship',
                cardinality='MANY_TO_MANY', semantics=None, status='ACTIVE',
                source_type='SERVICE', target_type='SERVICE'
            ),
            RelationTypeRow(
                id='3', relation_type='DEPENDS_ON', display_name='Depends On',
                description='Dependency relationship',
                cardinality='MANY_TO_MANY', semantics=None, status='ACTIVE',
                source_type='API', target_type='SERVICE'
            ),
        ]
        mock_session.execute.return_value = mock_result

        service = OntologySchemaService(session=mock_session, force_reload=True)
        service._load_relationship_types()

        rel = service.relationship_types['DEPENDS_ON']
        assert set(rel.source_types) == {'SERVICE', 'API'}
        assert set(rel.target_types) == {'DATABASE', 'SERVICE'}

    def test_load_relationship_types_parses_cardinality(self):
        """Cardinality strings should be parsed correctly."""
        mock_session = Mock()

        test_cases = [
            ('MANY_TO_MANY', Cardinality.MANY_TO_MANY),
            ('MANY_TO_ONE', Cardinality.MANY_TO_ONE),
            ('ONE_TO_MANY', Cardinality.ONE_TO_MANY),
            ('ONE_TO_ONE', Cardinality.ONE_TO_ONE),
            ('many-to-many', Cardinality.MANY_TO_MANY),
            ('many-to-one', Cardinality.MANY_TO_ONE),
            (None, Cardinality.MANY_TO_MANY),
            ('invalid', Cardinality.MANY_TO_MANY),
        ]

        for cardinality_str, expected in test_cases:
            mock_result = [
                RelationTypeRow(
                    id='1', relation_type='TEST_REL', display_name='Test',
                    description='Test', cardinality=cardinality_str,
                    semantics=None, status='ACTIVE',
                    source_type='A', target_type='B'
                ),
            ]
            mock_session.execute.return_value = mock_result

            service = OntologySchemaService(session=mock_session, force_reload=True)
            service._load_relationship_types()

            parsed = service._parse_cardinality(cardinality_str)
            assert parsed == expected, f"Expected {expected} for '{cardinality_str}', got {parsed}"

    def test_get_valid_relationship_types(self):
        """get_valid_relationship_types should return set of loaded type names."""
        mock_session = Mock()
        mock_session.execute.return_value = [
            RelationTypeRow(
                id='1', relation_type='OWNS', display_name='Owns',
                description='Owns', cardinality=None, semantics=None,
                status='ACTIVE', source_type='TEAM', target_type='SERVICE'
            ),
            RelationTypeRow(
                id='2', relation_type='MANAGES', display_name='Manages',
                description='Manages', cardinality=None, semantics=None,
                status='ACTIVE', source_type='PERSON', target_type='TEAM'
            ),
        ]

        service = OntologySchemaService(session=mock_session, force_reload=True)
        service._load_relationship_types()

        valid_types = service.get_valid_relationship_types()
        assert valid_types == {'OWNS', 'MANAGES'}


class TestSchemaValidation:
    """Tests for validate_relationship() method."""

    def setup_method(self):
        """Set up service with mock relationship types."""
        self.service = OntologySchemaService(session=None, force_reload=True)
        self.service._relationship_types = {
            'OWNS': RelationshipTypeConfig(
                name='OWNS',
                description='Ownership',
                source_types=['TEAM', 'PERSON'],
                target_types=['SERVICE', 'DATABASE'],
                cardinality=Cardinality.MANY_TO_ONE
            ),
            'WORKS_AT': RelationshipTypeConfig(
                name='WORKS_AT',
                description='Employment',
                source_types=['PERSON'],
                target_types=['ORGANIZATION'],
                cardinality=Cardinality.MANY_TO_ONE
            ),
            'RELATES_TO': RelationshipTypeConfig(
                name='RELATES_TO',
                description='Generic relation',
                source_types=[],
                target_types=[],
                cardinality=Cardinality.MANY_TO_MANY
            ),
        }

    def test_validate_relationship_valid_types(self):
        """Valid source and target types should pass validation."""
        is_valid, error = self.service.validate_relationship('OWNS', 'TEAM', 'SERVICE')
        assert is_valid is True
        assert error == ""

        is_valid, error = self.service.validate_relationship('OWNS', 'PERSON', 'DATABASE')
        assert is_valid is True
        assert error == ""

    def test_validate_relationship_invalid_source(self):
        """Invalid source type should fail validation."""
        is_valid, error = self.service.validate_relationship('OWNS', 'UNKNOWN', 'SERVICE')
        assert is_valid is False
        assert 'Invalid source type' in error

    def test_validate_relationship_invalid_target(self):
        """Invalid target type should fail validation."""
        is_valid, error = self.service.validate_relationship('OWNS', 'TEAM', 'UNKNOWN')
        assert is_valid is False
        assert 'Invalid target type' in error

    def test_validate_relationship_unknown_type(self):
        """Unknown relationship type should fail validation."""
        is_valid, error = self.service.validate_relationship('NONEXISTENT', 'A', 'B')
        assert is_valid is False
        assert 'Unknown relationship type' in error

    def test_validate_relationship_empty_constraints(self):
        """Relationship with no source/target constraints should accept any types."""
        is_valid, error = self.service.validate_relationship('RELATES_TO', 'ANY_TYPE', 'OTHER_TYPE')
        assert is_valid is True
        assert error == ""

    def test_validate_relationship_case_insensitive(self):
        """Validation should be case-insensitive."""
        is_valid, error = self.service.validate_relationship('owns', 'team', 'service')
        assert is_valid is True

        is_valid, error = self.service.validate_relationship('OWNS', 'Team', 'Service')
        assert is_valid is True

    def test_is_valid_relationship_type(self):
        """is_valid_relationship_type should check type existence."""
        assert self.service.is_valid_relationship_type('OWNS') is True
        assert self.service.is_valid_relationship_type('owns') is True
        assert self.service.is_valid_relationship_type('UNKNOWN') is False


class TestDynamicEntityTypeCreation:
    """Tests for dynamic entity type creation and management."""

    def test_add_entity_type_directly(self):
        """Entity types can be added directly to the service."""
        service = OntologySchemaService(session=None, force_reload=True)

        new_entity = EntityTypeConfig(
            name='CUSTOM_TYPE',
            description='A custom entity type',
            required_fields=['name'],
            optional_fields=['metadata'],
            keywords=['custom', 'dynamic']
        )
        service._entity_types['CUSTOM_TYPE'] = new_entity

        assert 'CUSTOM_TYPE' in service.entity_types
        assert service.is_valid_entity_type('CUSTOM_TYPE')
        assert service.is_valid_entity_type('custom_type')

    def test_add_relationship_type_directly(self):
        """Relationship types can be added directly to the service."""
        service = OntologySchemaService(session=None, force_reload=True)

        new_rel = RelationshipTypeConfig(
            name='CUSTOM_REL',
            description='A custom relationship',
            source_types=['CUSTOM_TYPE'],
            target_types=['SERVICE'],
            cardinality=Cardinality.MANY_TO_MANY
        )
        service._relationship_types['CUSTOM_REL'] = new_rel

        assert 'CUSTOM_REL' in service.relationship_types
        assert service.is_valid_relationship_type('CUSTOM_REL')

    def test_type_mappings_for_correction(self):
        """Type mappings should correct extracted types."""
        service = OntologySchemaService(session=None, force_reload=True)
        service._type_mappings = {
            'APPLICATION': 'SERVICE',
            'API': 'SERVICE',
            'SQUAD': 'TEAM',
        }

        assert service.correct_entity_type('APPLICATION') == 'SERVICE'
        assert service.correct_entity_type('api') == 'SERVICE'
        assert service.correct_entity_type('Squad') == 'TEAM'
        assert service.correct_entity_type('UNKNOWN') == 'UNKNOWN'

    def test_default_type_mappings(self):
        """Default type mappings should be available."""
        service = OntologySchemaService(session=None, force_reload=True)
        default_mappings = service._get_default_type_mappings()

        assert 'APPLICATION' in default_mappings
        assert default_mappings['APPLICATION'] == 'SERVICE'
        assert 'MICROSERVICE' in default_mappings
        assert 'SQUAD' in default_mappings
        assert default_mappings['SQUAD'] == 'TEAM'


class TestSchemaServiceToDomainSchema:
    """Tests for converting to DomainSchema."""

    def test_to_domain_schema(self):
        """to_domain_schema should create a valid DomainSchema."""
        service = OntologySchemaService(session=None, force_reload=True)
        service._entity_types = {
            'SERVICE': EntityTypeConfig(name='SERVICE', description='A service'),
            'TEAM': EntityTypeConfig(name='TEAM', description='A team'),
        }
        service._relationship_types = {
            'OWNS': RelationshipTypeConfig(
                name='OWNS',
                source_types=['TEAM'],
                target_types=['SERVICE']
            ),
        }

        schema = service.to_domain_schema(domain="Test Domain")

        assert isinstance(schema, DomainSchema)
        assert schema.domain == "Test Domain"
        assert schema.schema_version == "3.0"
        assert 'SERVICE' in schema.entity_types
        assert 'TEAM' in schema.entity_types
        assert 'OWNS' in schema.relationship_types

    def test_domain_schema_entity_access(self):
        """DomainSchema should provide entity type access methods."""
        service = OntologySchemaService(session=None, force_reload=True)
        service._entity_types = {
            'SERVICE': EntityTypeConfig(name='SERVICE', description='A service'),
        }
        service._relationship_types = {}

        schema = service.to_domain_schema()

        assert schema.get_entity_type('SERVICE') is not None
        assert schema.get_entity_type('service') is not None
        assert schema.get_entity_type('UNKNOWN') is None
        assert 'SERVICE' in schema.get_entity_type_names()


class TestSchemaServiceLoad:
    """Tests for the load() method."""

    def test_load_without_session_logs_warning(self):
        """Loading without session should log warning and return."""
        service = OntologySchemaService(session=None, force_reload=True)

        result = service.load()

        assert result is service
        assert service._loaded is False

    def test_load_with_session_calls_all_loaders(self):
        """Loading with session should call all load methods."""
        mock_session = Mock()
        mock_session.execute.return_value = []

        service = OntologySchemaService(session=mock_session, force_reload=True)
        service.load()

        assert mock_session.execute.call_count == 3

    def test_load_sets_loaded_flag(self):
        """Successful load should set _loaded to True."""
        mock_session = Mock()
        mock_session.execute.return_value = []

        service = OntologySchemaService(session=mock_session, force_reload=True)
        service.load()

        assert service._loaded is True

    def test_load_handles_exception(self):
        """Load should handle exceptions gracefully."""
        mock_session = Mock()
        mock_session.execute.side_effect = Exception("Database error")

        service = OntologySchemaService(session=mock_session, force_reload=True)
        service.load()

        assert service._loaded is False


class TestPromptBuilding:
    """Tests for LLM prompt building methods."""

    def test_build_entity_extraction_prompt(self):
        """Entity extraction prompt should include all entity types."""
        service = OntologySchemaService(session=None, force_reload=True)
        service._entity_types = {
            'SERVICE': EntityTypeConfig(
                name='SERVICE',
                description='A software service',
                keywords=['api', 'microservice']
            ),
            'TEAM': EntityTypeConfig(
                name='TEAM',
                description='A team of people',
                keywords=['squad', 'group']
            ),
        }

        prompt = service.build_entity_extraction_prompt()

        assert 'ENTITY TYPES:' in prompt
        assert 'SERVICE' in prompt
        assert 'A software service' in prompt
        assert 'TEAM' in prompt
        assert 'api' in prompt

    def test_build_relationship_extraction_prompt(self):
        """Relationship extraction prompt should include all relationship types."""
        service = OntologySchemaService(session=None, force_reload=True)
        service._relationship_types = {
            'OWNS': RelationshipTypeConfig(
                name='OWNS',
                description='Ownership relationship',
                source_types=['TEAM'],
                target_types=['SERVICE'],
                cardinality=Cardinality.MANY_TO_ONE
            ),
        }

        prompt = service.build_relationship_extraction_prompt()

        assert 'RELATIONSHIP TYPES' in prompt
        assert 'OWNS' in prompt
        assert 'TEAM' in prompt
        assert 'SERVICE' in prompt
        assert 'one target only' in prompt


class TestTypeMappingDataclass:
    """Tests for TypeMapping dataclass."""

    def test_type_mapping_creation(self):
        """TypeMapping should store mapping information."""
        mapping = TypeMapping(
            deprecated_name='APPLICATION',
            current_name='SERVICE',
            migration_type='alias'
        )

        assert mapping.deprecated_name == 'APPLICATION'
        assert mapping.current_name == 'SERVICE'
        assert mapping.migration_type == 'alias'

    def test_type_mapping_default_migration_type(self):
        """TypeMapping should default to 'alias' migration type."""
        mapping = TypeMapping(
            deprecated_name='API',
            current_name='SERVICE'
        )

        assert mapping.migration_type == 'alias'
