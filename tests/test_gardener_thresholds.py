"""
Test Gardener agent loads promotion thresholds from database.
"""
import pytest
import os
from datetime import datetime

os.environ.setdefault("DATABASE_URL", os.environ.get("DATABASE_URL", ""))

from src.context_foundry.agents.gardener import GardenerAgent, GardenerConfig, PromotionThreshold
from src.context_foundry.models.schema import get_session


class TestGardenerThresholds:
    """Test database-backed promotion thresholds."""
    
    def test_thresholds_loaded_from_database(self):
        """Verify thresholds are loaded from promotion_thresholds table."""
        session = get_session()
        try:
            config = GardenerConfig(use_database_thresholds=True)
            gardener = GardenerAgent(session=session, config=config)
            
            assert gardener._default_threshold is not None
            assert gardener._default_threshold.min_confidence == 0.70
            assert gardener._default_threshold.min_corroboration_count == 1
            assert gardener._default_threshold.min_staging_hours == 1
            
        finally:
            session.close()
    
    def test_person_threshold_is_strict(self):
        """Person entities require higher thresholds."""
        session = get_session()
        try:
            gardener = GardenerAgent(session=session)
            
            person_threshold = gardener.get_threshold("Person")
            
            assert person_threshold.min_confidence == 0.85
            assert person_threshold.min_corroboration_count == 2
            assert person_threshold.min_staging_hours == 4
            
        finally:
            session.close()
    
    def test_incident_threshold(self):
        """Incident entities require corroboration."""
        session = get_session()
        try:
            gardener = GardenerAgent(session=session)
            
            incident_threshold = gardener.get_threshold("Incident")
            
            assert incident_threshold.min_confidence == 0.80
            assert incident_threshold.min_corroboration_count == 3
            assert incident_threshold.min_staging_hours == 2
            
        finally:
            session.close()
    
    def test_service_threshold_is_fast(self):
        """Service entities can promote quickly."""
        session = get_session()
        try:
            gardener = GardenerAgent(session=session)
            
            service_threshold = gardener.get_threshold("Service")
            
            assert service_threshold.min_confidence == 0.75
            assert service_threshold.min_corroboration_count == 1
            assert service_threshold.min_staging_hours == 1
            
        finally:
            session.close()
    
    def test_unknown_type_falls_back_to_default(self):
        """Unknown entity types use default threshold."""
        session = get_session()
        try:
            gardener = GardenerAgent(session=session)
            
            unknown_threshold = gardener.get_threshold("SomeUnknownType")
            
            assert unknown_threshold.min_confidence == 0.70
            assert unknown_threshold.min_corroboration_count == 1
            assert unknown_threshold.min_staging_hours == 1
            
        finally:
            session.close()
    
    def test_threshold_count(self):
        """Verify correct number of type-specific thresholds."""
        session = get_session()
        try:
            gardener = GardenerAgent(session=session)
            
            assert len(gardener._promotion_thresholds) == 3
            
        finally:
            session.close()


class TestGardenerConfigFlag:
    """Test use_database_thresholds flag."""
    
    def test_database_thresholds_enabled_by_default(self):
        """Database thresholds should be enabled by default."""
        config = GardenerConfig()
        assert config.use_database_thresholds is True
    
    def test_can_disable_database_thresholds(self):
        """Can disable database thresholds for testing."""
        config = GardenerConfig(use_database_thresholds=False)
        assert config.use_database_thresholds is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
