"""
Sufficiency Signals Module for Stage 3: Learning from Interaction

Computes explicit sufficiency signals for queries:
- Coverage: entities found / entities in query
- Freshness: how recent is the data
- Source Agreement: do multiple sources agree
- Relationship Density: relationships per entity

These signals drive gap detection and learning ticket creation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, timedelta
import re


@dataclass
class SufficiencySignals:
    """Explicit sufficiency signals for a query."""
    coverage: float              # 0-1: entities found / entities in query
    freshness: float             # 0-1: how recent is the data
    source_agreement: float      # 0-1: do sources agree
    relationship_density: float  # 0-1: relationships per entity
    overall_confidence: float    # Weighted combination
    gaps_detected: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'coverage': round(self.coverage, 3),
            'freshness': round(self.freshness, 3),
            'source_agreement': round(self.source_agreement, 3),
            'relationship_density': round(self.relationship_density, 3),
            'overall_confidence': round(self.overall_confidence, 3),
            'gaps_detected': self.gaps_detected
        }


def parse_date(date_value: Any) -> Optional[datetime]:
    """Parse various date formats to datetime."""
    if date_value is None:
        return None
    if isinstance(date_value, datetime):
        return date_value
    if isinstance(date_value, str):
        for fmt in ['%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y-%m']:
            try:
                return datetime.strptime(date_value[:len(fmt.replace('%', ''))], fmt)
            except (ValueError, IndexError):
                continue
    return None


def extract_entities_from_query(query: str) -> List[str]:
    """Extract potential entity names from a query string."""
    capitalized = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', query)
    
    stop_words = {'What', 'Who', 'When', 'Where', 'How', 'Why', 'Which', 
                  'Tell', 'List', 'Show', 'Find', 'Get', 'The', 'And', 'For'}
    
    entities = [e for e in capitalized if e not in stop_words]
    
    return entities


def compute_sufficiency(
    query_entities: List[str],
    found_entities: List[Dict[str, Any]],
    relationships: List[Dict[str, Any]],
    query_timestamp: datetime = None
) -> SufficiencySignals:
    """
    Compute explicit sufficiency signals for a query.
    
    Args:
        query_entities: Entity names mentioned in the query
        found_entities: Entities found in the knowledge graph
        relationships: Relationships retrieved for those entities
        query_timestamp: When the query was made (defaults to now)
    
    Returns:
        SufficiencySignals with coverage, freshness, source_agreement, 
        relationship_density, overall_confidence, and gaps_detected
    """
    query_timestamp = query_timestamp or datetime.utcnow()
    gaps_detected = []
    
    # 1. Coverage: Did we find all entities mentioned?
    found_names = {e.get('name', '').lower() for e in found_entities if e.get('name')}
    query_names = {name.lower() for name in query_entities if name}
    
    if query_names:
        matched = found_names & query_names
        coverage = len(matched) / len(query_names)
        
        missing_entities = query_names - found_names
        for entity in missing_entities:
            gaps_detected.append({
                'type': 'missing_entity',
                'entity_name': entity,
                'severity': 0.8
            })
    else:
        coverage = 1.0 if found_entities else 0.0
    
    # 2. Freshness: How old is our data?
    if relationships:
        dates = []
        for r in relationships:
            for date_field in ['valid_from', 'valid_to', 'updated_at', 'created_at']:
                dt = parse_date(r.get(date_field))
                if dt:
                    dates.append(dt)
        
        if dates:
            most_recent = max(dates)
            age_days = max(0, (query_timestamp - most_recent).days)
            freshness = max(0.1, 1.0 / (1 + age_days / 365))
        else:
            freshness = 0.5
    else:
        freshness = 0.0
    
    if freshness < 0.5:
        gaps_detected.append({
            'type': 'stale_data',
            'freshness_score': freshness,
            'severity': 0.5
        })
    
    # 3. Source Agreement: Do multiple sources say the same thing?
    if relationships:
        fact_sources: Dict[tuple, Set[str]] = {}
        for r in relationships:
            key = (
                r.get('source_entity_id') or r.get('source_id'),
                r.get('relationship_type'),
                r.get('target_entity_id') or r.get('target_id')
            )
            if key not in fact_sources:
                fact_sources[key] = set()
            
            chunk_id = r.get('provenance_chunk_id') or r.get('source_document_id')
            if chunk_id:
                fact_sources[key].add(str(chunk_id))
        
        if fact_sources:
            avg_sources = sum(len(s) for s in fact_sources.values()) / len(fact_sources)
            source_agreement = min(1.0, avg_sources / 2)
        else:
            source_agreement = 0.5
    else:
        source_agreement = 0.0
    
    # 4. Relationship Density: Do entities have enough connections?
    if found_entities and relationships:
        density = len(relationships) / len(found_entities)
        relationship_density = min(1.0, density / 5)
        
        for entity in found_entities:
            entity_id = entity.get('id')
            entity_rels = [
                r for r in relationships 
                if (r.get('source_entity_id') == entity_id or 
                    r.get('target_entity_id') == entity_id or
                    r.get('source_id') == entity_id or
                    r.get('target_id') == entity_id)
            ]
            if len(entity_rels) < 2:
                gaps_detected.append({
                    'type': 'sparse_relationships',
                    'entity_id': str(entity_id) if entity_id else None,
                    'entity_name': entity.get('name'),
                    'relationship_count': len(entity_rels),
                    'severity': 0.6
                })
    else:
        relationship_density = 0.0
        if found_entities:
            for entity in found_entities:
                gaps_detected.append({
                    'type': 'sparse_relationships',
                    'entity_id': str(entity.get('id')) if entity.get('id') else None,
                    'entity_name': entity.get('name'),
                    'relationship_count': 0,
                    'severity': 0.6
                })
    
    # 5. Compute overall confidence (weighted combination)
    overall_confidence = (
        coverage * 0.35 +
        freshness * 0.20 +
        source_agreement * 0.20 +
        relationship_density * 0.25
    )
    
    return SufficiencySignals(
        coverage=coverage,
        freshness=freshness,
        source_agreement=source_agreement,
        relationship_density=relationship_density,
        overall_confidence=overall_confidence,
        gaps_detected=gaps_detected
    )


def qualify_answer(answer: str, sufficiency: SufficiencySignals) -> str:
    """Add qualification to low-confidence answers."""
    qualifiers = []
    
    if sufficiency.coverage < 0.8:
        qualifiers.append("based on partial information")
    
    if sufficiency.freshness < 0.5:
        qualifiers.append("data may be outdated")
    
    if sufficiency.relationship_density < 0.3:
        qualifiers.append("limited relationship data")
    
    if qualifiers:
        qualifier_text = ", ".join(qualifiers)
        confidence_pct = f"{sufficiency.overall_confidence:.0%}"
        return f"Based on current knowledge ({qualifier_text}): {answer}\n\n[Confidence: {confidence_pct}. Checking for completeness...]"
    
    return answer
