"""
Extraction Post-Processor

Pattern-based post-processing for ALL known relationship types.
Catches relationships the LLM missed during extraction.
Config-driven — add patterns without code changes.
"""

import re
import yaml
from typing import List, Tuple, Set, Dict, Optional, Any
from pathlib import Path
from sqlalchemy.orm import Session

from src.context_foundry.utils.logger import logger


class ExtractionPostProcessor:
    """
    Pattern-based post-processing for ALL known relationship types.
    Config-driven — add patterns without code changes.
    """
    
    def __init__(self, session: Session, tenant_id: str, config_path: Optional[str] = None):
        self.session = session
        self.tenant_id = tenant_id
        self.patterns = self._load_patterns(config_path)
    
    def _load_patterns(self, config_path: Optional[str]) -> Dict:
        """Load relationship patterns from config."""
        if config_path and Path(config_path).exists():
            with open(config_path) as f:
                return yaml.safe_load(f)
        
        return {
            'HOLD_POSITION': {
                'patterns': [
                    {'regex': r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–—:]\s*(Chief\s+\w+\s+Officer|CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|VP\s+\w+|Director\s+\w+|Managing\s+Partner|Senior\s+Partner|Partner|Chair\w*)', 'inverted': False},
                    {'regex': r'^(?:Dr\.|Mr\.|Ms\.|Mrs\.)\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–—:]\s*(Chief\s+\w+\s+Officer|CEO|CFO|CTO|CIO|COO)', 'inverted': False},
                    {'regex': r'^(CEO|CFO|CTO|CIO|COO)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)', 'inverted': True},
                    {'regex': r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+),\s*(CEO|CFO|CTO|CIO|COO|Managing\s+Partner)', 'inverted': False},
                ],
                'source_type': 'PERSON',
                'target_type': 'ROLE',
            },
            'REPORTS_TO': {
                'patterns': [
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+reports\s+to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                    r'Reports\s+to:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
                ],
                'source_type': 'PERSON',
                'target_type': 'PERSON',
            },
            'INVESTED_IN': {
                'patterns': [
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+invested\s+.*?in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+has\s+(?:a\s+)?\d+%\s+(?:stake|ownership)\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                ],
                'source_type': 'ORGANIZATION',
                'target_type': 'ORGANIZATION',
            },
            'WORKS_AT': {
                'patterns': [
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:works|employed)\s+at\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+joined\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                ],
                'source_type': 'PERSON',
                'target_type': 'ORGANIZATION',
            },
            'LEADS': {
                'patterns': [
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+leads?\s+(?:the\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
                    r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s*[-–]\s*(?:Head|Chair|Lead)\s+(?:of\s+)?([A-Z][a-z]+)',
                ],
                'source_type': 'PERSON',
                'target_type': 'DEPARTMENT',
            },
        }
    
    def process(self, text: str, entities: List[Dict], relationships: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
        """
        Find relationships the LLM missed across ALL known types.
        
        Args:
            text: Document text to search
            entities: List of already-extracted entities
            relationships: List of already-extracted relationships
            
        Returns:
            Updated (entities, relationships) tuple
        """
        added_count = 0
        
        for rel_type, config in self.patterns.items():
            found = self._find_patterns_line_by_line(text, config['patterns'])
            
            for source_name, target_name in found:
                if not self._relationship_exists(source_name, target_name, rel_type, relationships):
                    source_entity = self._get_or_create_entity(
                        source_name, config['source_type'], entities
                    )
                    target_entity = self._get_or_create_entity(
                        target_name, config['target_type'], entities
                    )
                    
                    new_rel = self._create_relationship(source_entity, rel_type, target_entity)
                    relationships.append(new_rel)
                    added_count += 1
                    
                    logger.info(f"[POST-PROCESSOR] Added: {source_name} -[{rel_type}]-> {target_name}")
        
        if added_count > 0:
            logger.info(f"[POST-PROCESSOR] Total relationships added: {added_count}")
        
        return entities, relationships
    
    def _find_patterns_line_by_line(self, text: str, patterns: List) -> Set[Tuple[str, str]]:
        """
        Find all matches for given patterns, processing line-by-line.
        Prevents cross-line matching issues.
        
        Patterns can be:
        - Simple string: r'pattern'
        - Dict with inverted flag: {'regex': r'pattern', 'inverted': True/False}
        
        For inverted patterns (e.g., "CFO John Smith"), swap capture groups so
        PERSON is always source and ROLE is always target.
        """
        found = set()
        lines = text.split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            for pattern_config in patterns:
                if isinstance(pattern_config, dict):
                    pattern = pattern_config['regex']
                    inverted = pattern_config.get('inverted', False)
                else:
                    pattern = pattern_config
                    inverted = False
                
                for match in re.finditer(pattern, line, re.IGNORECASE):
                    groups = match.groups()
                    if len(groups) >= 2:
                        if inverted:
                            source = groups[1].strip()
                            target = groups[0].strip()
                        else:
                            source = groups[0].strip()
                            target = groups[1].strip()
                        
                        source_words = len(source.split())
                        if source_words >= 2 and source_words <= 4 and len(target) > 2:
                            found.add((source, target))
        
        return found
    
    def _relationship_exists(self, source: str, target: str, rel_type: str, relationships: List[Dict]) -> bool:
        """Check if relationship already exists (fuzzy match)."""
        source_lower = source.lower()
        target_lower = target.lower()
        
        for rel in relationships:
            if rel.get('relationship_type') != rel_type:
                continue
            rel_source = rel.get('source_name', '').lower()
            rel_target = rel.get('target_name', '').lower()
            if (source_lower in rel_source or rel_source in source_lower) and \
               (target_lower in rel_target or rel_target in target_lower):
                return True
        return False
    
    def _get_or_create_entity(self, name: str, entity_type: str, entities: List[Dict]) -> Dict:
        """Get existing entity or create new one."""
        for entity in entities:
            if entity.get('name', '').lower() == name.lower():
                return entity
        new_entity = {'name': name, 'entity_type': entity_type}
        entities.append(new_entity)
        return new_entity
    
    def _create_relationship(self, source: Dict, rel_type: str, target: Dict) -> Dict:
        """Create relationship dict."""
        return {
            'source_name': source.get('name') if isinstance(source, dict) else source,
            'relationship_type': rel_type,
            'target_name': target.get('name') if isinstance(target, dict) else target,
            'confidence': 0.8,
            'extraction_method': 'post_processor_pattern',
        }
