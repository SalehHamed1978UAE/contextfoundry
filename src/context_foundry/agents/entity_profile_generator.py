"""
Entity Profile Generator - Stage 4 demo application.

Demonstrates the "One Substrate, Many Applications" principle:
Uses the same World Model as the Q&A Agent but produces structured entity profiles.
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models.schema import get_session, Entity, Relationship, LifecycleState
from ..models.context_bundle import ContextBundle
from .sufficiency import compute_sufficiency

logger = logging.getLogger(__name__)


@dataclass
class EntityProfile:
    """Structured profile of an entity from the World Model."""
    entity_id: str
    name: str
    entity_type: str
    description: Optional[str]
    confidence: float
    properties: Dict[str, Any] = field(default_factory=dict)
    
    outgoing_relationships: List[Dict] = field(default_factory=list)
    incoming_relationships: List[Dict] = field(default_factory=list)
    
    sufficiency: Dict[str, float] = field(default_factory=dict)
    provenance_sources: List[str] = field(default_factory=list)
    
    generated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert profile to dictionary."""
        return {
            "entity_id": self.entity_id,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "confidence": self.confidence,
            "properties": self.properties,
            "outgoing_relationships": self.outgoing_relationships,
            "incoming_relationships": self.incoming_relationships,
            "relationship_count": len(self.outgoing_relationships) + len(self.incoming_relationships),
            "sufficiency": self.sufficiency,
            "provenance_sources": self.provenance_sources,
            "generated_at": self.generated_at.isoformat()
        }
    
    def to_markdown(self) -> str:
        """Format profile as readable Markdown summary."""
        lines = []
        lines.append(f"# {self.name}")
        lines.append(f"**Type:** {self.entity_type}")
        lines.append(f"**Confidence:** {self.confidence:.0%}")
        
        if self.description:
            lines.append(f"\n{self.description}")
        
        if self.properties:
            clean_props = {k: v for k, v in self.properties.items() if not k.startswith('_')}
            if clean_props:
                lines.append("\n## Properties")
                for k, v in clean_props.items():
                    lines.append(f"- **{k}:** {v}")
        
        if self.outgoing_relationships:
            lines.append("\n## Relationships (Outgoing)")
            for rel in self.outgoing_relationships:
                qual_str = ""
                if rel.get('qualifiers'):
                    quals = [f"{q['type']}={q['text']}" for q in rel['qualifiers']]
                    qual_str = f" [{', '.join(quals)}]"
                temporal = ""
                if rel.get('valid_from'):
                    temporal = f" (since {rel['valid_from'][:10]})"
                lines.append(f"- **{rel['relationship_type']}** → {rel['target_name']} ({rel['target_type']}){qual_str}{temporal}")
                if rel.get('provenance_text'):
                    lines.append(f"  - *Source: \"{rel['provenance_text'][:80]}...\"*")
        
        if self.incoming_relationships:
            lines.append("\n## Relationships (Incoming)")
            for rel in self.incoming_relationships:
                qual_str = ""
                if rel.get('qualifiers'):
                    quals = [f"{q['type']}={q['text']}" for q in rel['qualifiers']]
                    qual_str = f" [{', '.join(quals)}]"
                lines.append(f"- {rel['source_name']} ({rel['source_type']}) **{rel['relationship_type']}** → this{qual_str}")
        
        lines.append("\n## Knowledge Quality")
        lines.append(f"- **Coverage:** {self.sufficiency.get('coverage', 0):.0%}")
        lines.append(f"- **Freshness:** {self.sufficiency.get('freshness', 0):.0%}")
        lines.append(f"- **Source Agreement:** {self.sufficiency.get('source_agreement', 0):.0%}")
        lines.append(f"- **Relationship Density:** {self.sufficiency.get('relationship_density', 0):.0%}")
        lines.append(f"- **Overall Confidence:** {self.sufficiency.get('overall_confidence', 0):.0%}")
        
        if self.provenance_sources:
            lines.append("\n## Sources")
            for src in self.provenance_sources[:5]:
                lines.append(f"- {src}")
        
        return "\n".join(lines)


class EntityProfileGenerator:
    """
    Generates structured profiles for entities using the World Model.
    
    This is a Stage 4 demo showing the same World Model can power different applications.
    Uses the same underlying data (entities, relationships) and same sufficiency computation
    as the Q&A Agent, but outputs structured profiles instead of answers.
    """
    
    def __init__(self, session: Session = None, tenant_id: str = None):
        self.session = session or get_session()
        self.tenant_id = tenant_id
    
    def generate_profile(self, entity_name: str, tenant_id: str = None) -> Optional[EntityProfile]:
        """
        Generate a profile for the given entity.
        
        Args:
            entity_name: Name of the entity to profile
            tenant_id: Tenant ID (uses default if not provided)
            
        Returns:
            EntityProfile or None if entity not found
        """
        tid = tenant_id or self.tenant_id
        if not tid:
            raise ValueError("tenant_id must be provided")
        
        self.session.execute(text(f"SET app.current_tenant_id = '{tid}'"))
        
        entity = self.session.query(Entity).filter(
            Entity.tenant_id == tid,
            Entity.name.ilike(entity_name),
            Entity.lifecycle_state == LifecycleState.TRUSTED
        ).first()
        
        if not entity:
            fuzzy = self.session.query(Entity).filter(
                Entity.tenant_id == tid,
                Entity.name.ilike(f"%{entity_name}%"),
                Entity.lifecycle_state == LifecycleState.TRUSTED
            ).first()
            if fuzzy:
                logger.info(f"Fuzzy match: '{entity_name}' -> '{fuzzy.name}'")
                entity = fuzzy
            else:
                logger.warning(f"Entity not found: {entity_name}")
                return None
        
        outgoing = self.session.query(Relationship).filter(
            Relationship.tenant_id == tid,
            Relationship.source_id == entity.id,
            Relationship.lifecycle_state == LifecycleState.TRUSTED
        ).all()
        
        incoming = self.session.query(Relationship).filter(
            Relationship.tenant_id == tid,
            Relationship.target_id == entity.id,
            Relationship.lifecycle_state == LifecycleState.TRUSTED
        ).all()
        
        outgoing_rels = []
        provenance_sources = set()
        
        for rel in outgoing:
            target = self.session.query(Entity).filter(Entity.id == rel.target_id).first()
            if target:
                rel_dict = {
                    'id': str(rel.id),
                    'relationship_type': rel.relationship_type,
                    'source_id': str(rel.source_id),
                    'source_name': entity.name,
                    'source_type': entity.entity_type,
                    'target_id': str(rel.target_id),
                    'target_name': target.name,
                    'target_type': target.entity_type,
                    'valid_from': str(rel.valid_from) if rel.valid_from else None,
                    'valid_to': str(rel.valid_to) if rel.valid_to else None,
                    'event_context': rel.event_context,
                    'provenance_text': rel.provenance_text,
                    'confidence': rel.confidence,
                    'qualifiers': rel.qualifiers or [],
                    'lifecycle_state': str(rel.lifecycle_state.value) if rel.lifecycle_state else 'TRUSTED'
                }
                outgoing_rels.append(rel_dict)
                if rel.provenance_text:
                    provenance_sources.add(rel.provenance_text[:100])
        
        incoming_rels = []
        for rel in incoming:
            source = self.session.query(Entity).filter(Entity.id == rel.source_id).first()
            if source:
                rel_dict = {
                    'id': str(rel.id),
                    'relationship_type': rel.relationship_type,
                    'source_id': str(rel.source_id),
                    'source_name': source.name,
                    'source_type': source.entity_type,
                    'target_id': str(rel.target_id),
                    'target_name': entity.name,
                    'target_type': entity.entity_type,
                    'valid_from': str(rel.valid_from) if rel.valid_from else None,
                    'valid_to': str(rel.valid_to) if rel.valid_to else None,
                    'provenance_text': rel.provenance_text,
                    'confidence': rel.confidence,
                    'qualifiers': rel.qualifiers or [],
                    'lifecycle_state': str(rel.lifecycle_state.value) if rel.lifecycle_state else 'TRUSTED'
                }
                incoming_rels.append(rel_dict)
                if rel.provenance_text:
                    provenance_sources.add(rel.provenance_text[:100])
        
        all_entities = self.session.query(Entity).filter(
            Entity.tenant_id == tid,
            Entity.lifecycle_state == LifecycleState.TRUSTED
        ).all()
        all_rels = self.session.query(Relationship).filter(
            Relationship.tenant_id == tid,
            Relationship.lifecycle_state == LifecycleState.TRUSTED
        ).all()
        
        entity_dicts = [{'id': str(e.id), 'name': e.name, 'entity_type': e.entity_type} for e in all_entities]
        rel_dicts = [{'id': str(r.id), 'relationship_type': r.relationship_type,
                      'source_entity_id': str(r.source_id), 'target_entity_id': str(r.target_id),
                      'valid_from': str(r.valid_from) if r.valid_from else None} for r in all_rels]
        
        suf = compute_sufficiency([entity.name], entity_dicts, rel_dicts)
        
        profile = EntityProfile(
            entity_id=str(entity.id),
            name=entity.name,
            entity_type=entity.entity_type,
            description=entity.description,
            confidence=entity.confidence or 0.5,
            properties=entity.properties or {},
            outgoing_relationships=outgoing_rels,
            incoming_relationships=incoming_rels,
            sufficiency={
                'coverage': suf.coverage,
                'freshness': suf.freshness,
                'source_agreement': suf.source_agreement,
                'relationship_density': suf.relationship_density,
                'overall_confidence': suf.overall_confidence
            },
            provenance_sources=list(provenance_sources)
        )
        
        logger.info(f"Generated profile for {entity.name}: {len(outgoing_rels)} outgoing, {len(incoming_rels)} incoming relationships")
        
        return profile
    
    def build_context_bundle(self, entity_name: str, tenant_id: str = None) -> Optional[ContextBundle]:
        """
        Build a ContextBundle for an entity (same as Q&A Agent would use).
        
        This demonstrates that both applications use the identical data retrieval path.
        """
        tid = tenant_id or self.tenant_id
        profile = self.generate_profile(entity_name, tid)
        
        if not profile:
            bundle = ContextBundle(
                query_id=f"profile-{datetime.utcnow().isoformat()}",
                query_text=f"Profile for {entity_name}",
                target_entity_name=entity_name,
                target_entity_found=False
            )
            bundle.calculate_uncertainty()
            return bundle
        
        bundle = ContextBundle(
            query_id=f"profile-{profile.entity_id}",
            query_text=f"Profile for {profile.name}",
            target_entity_name=profile.name,
            target_entity_found=True,
            target_entity_match={
                'id': profile.entity_id,
                'name': profile.name,
                'type': profile.entity_type
            }
        )
        
        bundle.semantic_entities = [{
            'id': profile.entity_id,
            'name': profile.name,
            'entity_type': profile.entity_type,
            'description': profile.description,
            'confidence': profile.confidence,
            'properties': profile.properties
        }]
        
        bundle.semantic_relationships = profile.outgoing_relationships + profile.incoming_relationships
        
        bundle.calculate_uncertainty()
        
        return bundle
