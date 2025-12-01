"""
Graph Loader Agent - Loads structured data into the tri-memory system.
Takes pre-structured data and ingests it into semantic, episodic, and symbolic memory.
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
import uuid

from ..models.schema import (
    Entity, Relationship, Document, Rule,
    LifecycleState, EntityType, RelationshipType, RuleType,
    get_session, init_database
)
from ..memory.semantic import SemanticMemory
from ..memory.episodic import EpisodicMemory
from ..memory.symbolic import SymbolicMemory
from ..utils.logger import logger


class GraphLoaderAgent:
    """
    Agent responsible for loading structured data into the tri-memory architecture.
    All loaded data starts in STAGING state and must be promoted to TRUSTED.
    """
    
    def __init__(self, session: Optional[Session] = None, auto_promote: bool = True):
        self.session = session or get_session()
        self.semantic = SemanticMemory(self.session)
        self.episodic = EpisodicMemory(self.session)
        self.symbolic = SymbolicMemory(self.session)
        self.auto_promote = auto_promote
        
        self.entity_map = {}
        
        self.stats = {
            "entities_loaded": 0,
            "relationships_loaded": 0,
            "documents_loaded": 0,
            "rules_loaded": 0,
            "errors": []
        }
        
        logger.info(f"GraphLoaderAgent initialized (auto_promote={auto_promote})")
    
    def load_synthetic_data(self, data: Dict) -> Dict:
        """
        Load synthetic IT operations data into the tri-memory system.
        
        Args:
            data: Dictionary with keys: entities, relationships, documents, rules
            
        Returns:
            Loading statistics and any errors
        """
        logger.info("Starting synthetic data load...")
        
        self._load_entities(data.get("entities", []))
        self._load_relationships(data.get("relationships", []))
        self._load_documents(data.get("documents", []))
        self._load_rules(data.get("rules", []))
        
        if self.auto_promote:
            self._promote_all_to_trusted()
        
        logger.info(f"Data load complete: {self.stats}")
        return self.stats
    
    def _load_entities(self, entities: List[Dict]):
        """Load entities into semantic memory."""
        logger.info(f"Loading {len(entities)} entities...")
        
        for entity_data in entities:
            try:
                entity_type_str = entity_data.get("entity_type", "SERVICE")
                entity_type = EntityType[entity_type_str]
                
                entity = self.semantic.add_entity(
                    name=entity_data["name"],
                    entity_type=entity_type,
                    properties=entity_data.get("properties", {}),
                    description=entity_data.get("description"),
                    confidence=entity_data.get("confidence", 0.9),
                    source_document_id="synthetic_data_v1",
                    source_sentence=entity_data.get("description", f"Entity: {entity_data['name']}"),
                    lifecycle_state=LifecycleState.STAGING
                )
                
                self.entity_map[entity_data["name"]] = entity.id
                
                if "id" in entity_data:
                    self.entity_map[entity_data["id"]] = entity.id
                
                self.stats["entities_loaded"] += 1
                
            except Exception as e:
                error_msg = f"Failed to load entity {entity_data.get('name')}: {str(e)}"
                logger.error(error_msg)
                self.stats["errors"].append(error_msg)
        
        logger.info(f"Loaded {self.stats['entities_loaded']} entities")
    
    def _load_relationships(self, relationships: List[Dict]):
        """Load relationships into semantic memory."""
        logger.info(f"Loading {len(relationships)} relationships...")
        
        for rel_data in relationships:
            try:
                source_name = rel_data.get("source_name")
                target_name = rel_data.get("target_name")
                
                if source_name not in self.entity_map:
                    logger.warning(f"Source entity not found: {source_name}")
                    continue
                if target_name not in self.entity_map:
                    logger.warning(f"Target entity not found: {target_name}")
                    continue
                
                source_id = self.entity_map[source_name]
                target_id = self.entity_map[target_name]
                
                rel_type_str = rel_data.get("relationship_type", "DEPENDS_ON")
                rel_type = RelationshipType[rel_type_str]
                
                self.semantic.add_relationship(
                    source_id=source_id,
                    target_id=target_id,
                    relationship_type=rel_type,
                    properties=rel_data.get("properties", {}),
                    description=rel_data.get("description"),
                    confidence=rel_data.get("confidence", 0.9),
                    source_document_id="synthetic_data_v1",
                    source_sentence=rel_data.get("source_sentence", f"{source_name} -> {target_name}"),
                    lifecycle_state=LifecycleState.STAGING
                )
                
                self.stats["relationships_loaded"] += 1
                
            except Exception as e:
                error_msg = f"Failed to load relationship {rel_data}: {str(e)}"
                logger.error(error_msg)
                self.stats["errors"].append(error_msg)
        
        logger.info(f"Loaded {self.stats['relationships_loaded']} relationships")
    
    def _load_documents(self, documents: List[Dict]):
        """Load documents into episodic memory."""
        logger.info(f"Loading {len(documents)} documents...")
        
        for doc_data in documents:
            try:
                self.episodic.add_document(
                    title=doc_data["title"],
                    doc_type=doc_data.get("doc_type", "DOCUMENTATION"),
                    content=doc_data["content"],
                    metadata=doc_data.get("metadata", {}),
                    source_document_id=doc_data.get("id", "synthetic_data_v1")
                )
                
                self.stats["documents_loaded"] += 1
                
            except Exception as e:
                error_msg = f"Failed to load document {doc_data.get('title')}: {str(e)}"
                logger.error(error_msg)
                self.stats["errors"].append(error_msg)
        
        logger.info(f"Loaded {self.stats['documents_loaded']} documents")
    
    def _load_rules(self, rules: List[Dict]):
        """Load rules into symbolic memory."""
        logger.info(f"Loading {len(rules)} rules...")
        
        for rule_data in rules:
            try:
                rule_type_str = rule_data.get("rule_type", "VALIDATION")
                rule_type = RuleType[rule_type_str]
                
                self.symbolic.add_rule(
                    name=rule_data["name"],
                    rule_type=rule_type,
                    description=rule_data["description"],
                    condition=rule_data["condition"],
                    action=rule_data["action"],
                    priority=rule_data.get("priority", 100),
                    entity_types=rule_data.get("entity_types", []),
                    relationship_types=rule_data.get("relationship_types", []),
                    metadata=rule_data.get("metadata", {})
                )
                
                self.stats["rules_loaded"] += 1
                
            except Exception as e:
                error_msg = f"Failed to load rule {rule_data.get('name')}: {str(e)}"
                logger.error(error_msg)
                self.stats["errors"].append(error_msg)
        
        logger.info(f"Loaded {self.stats['rules_loaded']} rules")
    
    def _promote_all_to_trusted(self):
        """Promote all STAGING entities and relationships to TRUSTED."""
        logger.info("Promoting all STAGING data to TRUSTED...")
        
        entities = self.session.query(Entity).filter(
            Entity.lifecycle_state == LifecycleState.STAGING
        ).all()
        
        for entity in entities:
            self.semantic.promote_to_trusted(entity.id)
            
        relationships = self.session.query(Relationship).filter(
            Relationship.lifecycle_state == LifecycleState.STAGING
        ).all()
        
        from datetime import datetime
        for rel in relationships:
            rel.lifecycle_state = LifecycleState.TRUSTED
        
        try:
            self.session.commit()
        except Exception as e:
            self.session.rollback()
            logger.error(f"Failed to promote relationships to TRUSTED: {e}")
            raise
        
        logger.info(f"Promoted {len(entities)} entities and {len(relationships)} relationships to TRUSTED")
    
    def get_entity_id(self, name: str) -> Optional[uuid.UUID]:
        """Get entity ID by name from the loaded entity map."""
        return self.entity_map.get(name)
    
    def get_loading_stats(self) -> Dict:
        """Get current loading statistics."""
        memory_stats = {
            "semantic": self.semantic.get_statistics(),
            "episodic": self.episodic.get_statistics(),
            "symbolic": self.symbolic.get_statistics()
        }
        return {
            **self.stats,
            "memory_stats": memory_stats
        }
