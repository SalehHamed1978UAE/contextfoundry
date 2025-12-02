"""
Org Chart Loader Agent.

Loads org chart synthetic data into Context Foundry's tri-memory system.
Demonstrates domain-agnostic architecture by using the same memory layers
for a completely different domain (HR/Org structure instead of IT Ops).
"""

import uuid
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ..models.schema import (
    Entity, Relationship, Document, Rule, EntityType, 
    RelationshipType, RuleType, LifecycleState, get_session
)
from ..data.org_chart_generator import generate_org_chart_data
from ..memory.episodic import EpisodicMemory
import logging

logger = logging.getLogger(__name__)


class OrgChartLoader:
    """Loads org chart data into the tri-memory system."""
    
    ORG_ENTITY_TYPE_MAP = {
        "VP": EntityType.PERSON,
        "Director": EntityType.PERSON,
        "Manager": EntityType.PERSON,
        "IC": EntityType.PERSON,
    }
    
    ORG_REL_TYPE_MAP = {
        "REPORTS_TO": RelationshipType.ESCALATES_TO,
        "MEMBER_OF": RelationshipType.MEMBER_OF,
        "LEADS": RelationshipType.OWNS,
        "COLLABORATES_WITH": RelationshipType.DEPENDS_ON,
    }
    
    def __init__(self, session: Optional[Session] = None):
        self.session = session or get_session()
        self.episodic = EpisodicMemory(self.session)
        self.entity_map: Dict[str, Entity] = {}
        
    def load_all(self, clear_existing: bool = False) -> Dict:
        """Load all org chart data into the tri-memory system."""
        
        if clear_existing:
            self._clear_org_data()
        
        data = generate_org_chart_data()
        
        stats = {
            "departments": 0,
            "teams": 0,
            "people": 0,
            "relationships": 0,
            "rules": 0,
            "documents": 0,
        }
        
        for dept in data["departments"]:
            if self._load_department(dept):
                stats["departments"] += 1
        
        for team in data["teams"]:
            if self._load_team(team):
                stats["teams"] += 1
        
        for person in data["people"]:
            if self._load_person(person):
                stats["people"] += 1
        
        self.session.commit()
        
        for rel in data["relationships"]:
            if self._load_relationship(rel):
                stats["relationships"] += 1
        
        for rule in data["rules"]:
            if self._load_rule(rule):
                stats["rules"] += 1
        
        for doc in data["documents"]:
            if self._load_document(doc):
                stats["documents"] += 1
        
        self.session.commit()
        
        logger.info(f"Org chart loaded: {stats}")
        return stats
    
    def _clear_org_data(self):
        """Clear existing org chart data (by source prefix)."""
        pass
    
    def _entity_exists(self, name: str) -> bool:
        """Check if entity already exists."""
        existing = self.session.query(Entity).filter(
            Entity.name == name,
            Entity.lifecycle_state == LifecycleState.TRUSTED.value
        ).first()
        if existing:
            self.entity_map[name] = existing
            return True
        return False
    
    def _load_department(self, dept: Dict) -> bool:
        """Load a department as a TEAM entity."""
        name = f"{dept['name']} Department"
        
        if self._entity_exists(name):
            logger.debug(f"Department already exists: {name}")
            return False
        
        entity = Entity(
            id=uuid.uuid4(),
            name=name,
            entity_type=EntityType.TEAM,
            description=dept["mission"],
            properties={
                "domain": "org_chart",
                "head": dept["head"],
                "type": "department",
            },
            confidence=1.0,
            source_document_id="org_chart_synthetic",
            source_sentence=f"{name} - {dept['mission']}",
            lifecycle_state=LifecycleState.TRUSTED,
        )
        
        self.session.add(entity)
        self.entity_map[name] = entity
        self.entity_map[dept["name"]] = entity
        
        return True
    
    def _load_team(self, team: Dict) -> bool:
        """Load a team as a TEAM entity."""
        name = team["name"]
        
        if self._entity_exists(name):
            logger.debug(f"Team already exists: {name}")
            return False
        
        entity = Entity(
            id=uuid.uuid4(),
            name=name,
            entity_type=EntityType.TEAM,
            description=team["focus"],
            properties={
                "domain": "org_chart",
                "department": team["department"],
                "headcount": team["headcount"],
                "type": "team",
            },
            confidence=1.0,
            source_document_id="org_chart_synthetic",
            source_sentence=f"{name} ({team['headcount']} members) - {team['focus']}",
            lifecycle_state=LifecycleState.TRUSTED,
        )
        
        self.session.add(entity)
        self.entity_map[name] = entity
        
        return True
    
    def _load_person(self, person: Dict) -> bool:
        """Load a person as a PERSON entity."""
        name = person["name"]
        
        if self._entity_exists(name):
            logger.debug(f"Person already exists: {name}")
            return False
        
        entity = Entity(
            id=uuid.uuid4(),
            name=name,
            entity_type=EntityType.PERSON,
            description=f"{person['role']} in {person['department']}",
            properties={
                "domain": "org_chart",
                "role": person["role"],
                "level": person["level"],
                "department": person["department"],
                "expertise": person["expertise"],
            },
            confidence=1.0,
            source_document_id="org_chart_synthetic",
            source_sentence=f"{name} is a {person['role']} ({person['level']}) in {person['department']}.",
            lifecycle_state=LifecycleState.TRUSTED,
        )
        
        self.session.add(entity)
        self.entity_map[name] = entity
        
        return True
    
    def _load_relationship(self, rel: Dict) -> bool:
        """Load an org chart relationship."""
        from_name = rel["from"]
        to_name = rel["to"]
        rel_type = rel["type"]
        source = rel["source"]
        
        from_entity = self.entity_map.get(from_name)
        to_entity = self.entity_map.get(to_name)
        
        if not from_entity:
            logger.warning(f"From entity not found: {from_name}")
            return False
        if not to_entity:
            logger.warning(f"To entity not found: {to_name}")
            return False
        
        mapped_type = self.ORG_REL_TYPE_MAP.get(rel_type)
        if not mapped_type:
            logger.warning(f"Unknown relationship type: {rel_type}")
            return False
        
        existing = self.session.query(Relationship).filter(
            Relationship.source_id == from_entity.id,
            Relationship.target_id == to_entity.id,
            Relationship.relationship_type == mapped_type,
        ).first()
        
        if existing:
            return False
        
        relationship = Relationship(
            id=uuid.uuid4(),
            source_id=from_entity.id,
            target_id=to_entity.id,
            relationship_type=mapped_type,
            properties={
                "domain": "org_chart",
                "original_type": rel_type,
            },
            confidence=0.98,
            source_document_id="org_chart_synthetic",
            source_sentence=source,
            lifecycle_state=LifecycleState.TRUSTED,
        )
        
        self.session.add(relationship)
        return True
    
    def _load_rule(self, rule: Dict) -> bool:
        """Load an org chart business rule."""
        name = rule["name"]
        
        existing = self.session.query(Rule).filter(Rule.name == name).first()
        if existing:
            logger.debug(f"Rule already exists: {name}")
            return False
        
        type_map = {
            "INVARIANT": RuleType.INVARIANT,
            "ESCALATION_POLICY": RuleType.ESCALATION_POLICY,
            "VALIDATION": RuleType.VALIDATION,
            "SAFETY_CHECK": RuleType.SAFETY_CHECK,
        }
        
        rule_type = type_map.get(rule["type"], RuleType.VALIDATION)
        
        db_rule = Rule(
            id=uuid.uuid4(),
            name=name,
            rule_type=rule_type.value,
            condition=rule["condition"],
            action=rule["action"],
            priority=rule["priority"],
            is_active=True,
            description=rule["description"],
        )
        
        self.session.add(db_rule)
        return True
    
    def _load_document(self, doc: Dict) -> bool:
        """Load an org chart document into episodic memory."""
        title = doc["title"]
        
        existing = self.session.query(Document).filter(Document.title == title).first()
        if existing:
            logger.debug(f"Document already exists: {title}")
            return False
        
        self.episodic.add_document(
            title=title,
            doc_type="RUNBOOK",
            content=doc["content"],
            metadata={
                "domain": "org_chart",
                "original_type": doc["type"],
            },
            source_document_id="org_chart_synthetic"
        )
        
        return True


def load_org_chart(clear_existing: bool = False) -> Dict:
    """Convenience function to load org chart data."""
    session = get_session()
    try:
        loader = OrgChartLoader(session)
        return loader.load_all(clear_existing)
    finally:
        session.close()


if __name__ == "__main__":
    stats = load_org_chart()
    print(f"Org chart loaded: {stats}")
