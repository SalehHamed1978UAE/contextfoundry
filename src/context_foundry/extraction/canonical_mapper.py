"""
Canonical Mapper - Normalizes raw LLM types to canonical uppercase types.

Part of the Open Capture architecture:
1. LLM extracts with natural language types (e.g., "invests in", "company")
2. CanonicalMapper normalizes to canonical types (e.g., "INVESTED_IN", "ORGANIZATION")
3. Unmapped types are queued for governance review
"""
import os
import logging
from typing import Dict, Optional, Tuple
import yaml

logger = logging.getLogger(__name__)


class CanonicalMapper:
    """Maps raw LLM-generated types to canonical uppercase types."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize with mappings from config file."""
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), 
                "..", "..", "..", "config", "canonical_mappings.yaml"
            )
        
        self._entity_mappings: Dict[str, str] = {}
        self._relationship_mappings: Dict[str, str] = {}
        self._load_config(config_path)
    
    def _load_config(self, config_path: str) -> None:
        """Load mappings from YAML config."""
        try:
            with open(config_path, 'r') as f:
                config = yaml.safe_load(f)
            
            for raw, canonical in config.get('entity_types', {}).items():
                self._entity_mappings[raw.lower().strip()] = canonical
            
            for raw, canonical in config.get('relationship_types', {}).items():
                self._relationship_mappings[raw.lower().strip()] = canonical
            
            logger.info(
                f"Loaded {len(self._entity_mappings)} entity mappings and "
                f"{len(self._relationship_mappings)} relationship mappings"
            )
        except FileNotFoundError:
            logger.warning(f"Canonical mappings config not found: {config_path}")
        except Exception as e:
            logger.error(f"Error loading canonical mappings: {e}")
    
    def _normalize_key(self, raw_type: str) -> str:
        """Normalize key for lookup - handles spaces, underscores, hyphens."""
        return raw_type.lower().strip().replace("_", " ").replace("-", " ")
    
    def map_entity_type(self, raw_type: str) -> Tuple[str, bool]:
        """
        Map raw entity type to canonical form.
        
        Returns:
            Tuple of (canonical_type, is_mapped)
            - If mapped: canonical type from config, True
            - If not mapped: uppercase raw type, False
        """
        normalized = self._normalize_key(raw_type)
        
        if normalized in self._entity_mappings:
            return self._entity_mappings[normalized], True
        
        return raw_type.upper().replace(" ", "_"), False
    
    def map_relationship_type(self, raw_type: str) -> Tuple[str, bool]:
        """
        Map raw relationship type to canonical form.
        
        Returns:
            Tuple of (canonical_type, is_mapped)
            - If mapped: canonical type from config, True
            - If not mapped: uppercase raw type, False
        """
        normalized = self._normalize_key(raw_type)
        
        if normalized in self._relationship_mappings:
            return self._relationship_mappings[normalized], True
        
        return raw_type.upper().replace(" ", "_"), False
    
    def add_entity_mapping(self, raw_type: str, canonical_type: str) -> None:
        """Add a new entity type mapping (runtime only)."""
        self._entity_mappings[raw_type.lower().strip()] = canonical_type
    
    def add_relationship_mapping(self, raw_type: str, canonical_type: str) -> None:
        """Add a new relationship type mapping (runtime only)."""
        self._relationship_mappings[raw_type.lower().strip()] = canonical_type


_mapper_instance: Optional[CanonicalMapper] = None


def get_canonical_mapper() -> CanonicalMapper:
    """Get singleton instance of CanonicalMapper."""
    global _mapper_instance
    if _mapper_instance is None:
        _mapper_instance = CanonicalMapper()
    return _mapper_instance
