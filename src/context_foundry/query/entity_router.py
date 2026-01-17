"""
Entity Type Router - Map query intent to valid entity types.

Ensures only relevant entity types are retrieved based on query intent.
"""

from typing import Dict, List, Set, Optional, Any
from dataclasses import dataclass

from src.context_foundry.query.intent_classifier import QueryIntent, ClassifiedQuery
from src.context_foundry.utils.logger import logger


@dataclass
class EntityTypeFilter:
    """Specifies which entity types to include/exclude for retrieval."""
    include: Set[str]
    exclude: Set[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "include": list(self.include),
            "exclude": list(self.exclude),
        }


INTENT_TO_ENTITY_TYPES: Dict[QueryIntent, EntityTypeFilter] = {
    QueryIntent.PERSON: EntityTypeFilter(
        include={
            "PERSON", "ROLE", "POSITION", "EMPLOYEE", "EXECUTIVE",
            "BOARD_MEMBER", "FOUNDER", "TEAM_MEMBER",
        },
        exclude={
            "POLICY", "METRIC", "FINANCIAL_DATA", "REQUIREMENT",
            "SECURITY_CONTROL", "COMPLIANCE",
        }
    ),
    QueryIntent.METRIC: EntityTypeFilter(
        include={
            "METRIC", "FINANCIAL_METRIC", "KPI", "REVENUE", "NET_INCOME",
            "EBITDA", "MARGIN", "GROWTH_RATE", "RATIO", "QUOTA",
            "COMMISSION", "SALARY", "BUDGET", "FUNDING", "VALUATION",
            "CUSTOMER_COUNT", "EMPLOYEE_COUNT", "HEADCOUNT",
        },
        exclude={
            "POLICY", "REQUIREMENT", "SECURITY_CONTROL",
        }
    ),
    QueryIntent.POLICY: EntityTypeFilter(
        include={
            "POLICY", "REQUIREMENT", "RULE", "SECURITY_CONTROL",
            "COMPLIANCE", "CERTIFICATION", "STANDARD", "GUIDELINE",
            "PROCEDURE", "PROTOCOL",
        },
        exclude={
            "PERSON", "ROLE", "POSITION", "FINANCIAL_METRIC",
            "REVENUE", "NET_INCOME", "EBITDA",
        }
    ),
    QueryIntent.TEMPORAL: EntityTypeFilter(
        include={
            "EVENT", "MILESTONE", "DATE", "DEADLINE", "TIMELINE",
            "FOUNDING_DATE", "LAUNCH_DATE", "CONTRACT",
        },
        exclude=set()
    ),
    QueryIntent.DEFINITION: EntityTypeFilter(
        include={
            "PRODUCT", "PROJECT", "SERVICE", "ORGANIZATION", "COMPANY",
            "FEATURE", "PLATFORM", "INDUSTRY", "LOCATION",
        },
        exclude={
            "POLICY", "REQUIREMENT",
        }
    ),
    QueryIntent.LIST: EntityTypeFilter(
        include=set(),
        exclude=set()
    ),
    QueryIntent.RELATIONSHIP: EntityTypeFilter(
        include={
            "PERSON", "ROLE", "POSITION", "ORGANIZATION", "TEAM",
            "DEPARTMENT", "INVESTOR", "CUSTOMER", "PARTNER",
        },
        exclude={
            "POLICY", "FINANCIAL_METRIC",
        }
    ),
    QueryIntent.UNKNOWN: EntityTypeFilter(
        include=set(),
        exclude=set()
    ),
}

METADATA_ENTITY_BLACKLIST = {
    "DOCUMENT_OWNER",
    "FILE_AUTHOR", 
    "DOCUMENT_AUTHOR",
    "METADATA",
}


class EntityTypeRouter:
    """Routes queries to appropriate entity types based on intent."""
    
    def __init__(self):
        self.intent_mapping = INTENT_TO_ENTITY_TYPES
        self.metadata_blacklist = METADATA_ENTITY_BLACKLIST
    
    def get_filter(self, classified_query: ClassifiedQuery) -> EntityTypeFilter:
        """
        Get entity type filter for a classified query.
        
        Returns EntityTypeFilter with include/exclude sets.
        """
        intent = classified_query.primary_intent
        base_filter = self.intent_mapping.get(intent, EntityTypeFilter(set(), set()))
        
        combined_exclude = base_filter.exclude | self.metadata_blacklist
        
        result = EntityTypeFilter(
            include=base_filter.include.copy(),
            exclude=combined_exclude,
        )
        
        logger.info(f"[ENTITY_ROUTER] Intent: {intent.value} → Include: {len(result.include)} types, Exclude: {len(result.exclude)} types")
        
        return result
    
    def should_include_entity(self, entity_type: str, classified_query: ClassifiedQuery) -> bool:
        """
        Check if an entity type should be included in retrieval.
        
        Returns True if entity should be retrieved, False otherwise.
        """
        entity_filter = self.get_filter(classified_query)
        entity_type_upper = entity_type.upper()
        
        if entity_type_upper in entity_filter.exclude:
            return False
        
        if entity_filter.include and entity_type_upper not in entity_filter.include:
            return False
        
        return True
    
    def get_sql_type_conditions(self, classified_query: ClassifiedQuery, 
                                 type_column: str = "entity_type") -> Dict[str, Any]:
        """
        Get SQL conditions for entity type filtering.
        
        Returns dict with 'where_clause' and 'params' for SQL query.
        """
        entity_filter = self.get_filter(classified_query)
        
        conditions = []
        params = {}
        
        if entity_filter.include:
            conditions.append(f"{type_column} = ANY(:include_types)")
            params['include_types'] = list(entity_filter.include)
        
        if entity_filter.exclude:
            conditions.append(f"{type_column} != ALL(:exclude_types)")
            params['exclude_types'] = list(entity_filter.exclude)
        
        where_clause = " AND ".join(conditions) if conditions else "TRUE"
        
        return {
            "where_clause": where_clause,
            "params": params,
        }
    
    def filter_entities(self, entities: List[Dict[str, Any]], 
                        classified_query: ClassifiedQuery) -> List[Dict[str, Any]]:
        """
        Filter a list of entities based on query intent.
        
        Use this for post-retrieval filtering when database-level filtering isn't possible.
        """
        entity_filter = self.get_filter(classified_query)
        
        filtered = []
        for entity in entities:
            entity_type = entity.get("entity_type", entity.get("type", "")).upper()
            
            if entity_type in entity_filter.exclude:
                logger.debug(f"[ENTITY_ROUTER] Excluding entity type: {entity_type}")
                continue
            
            if entity_filter.include and entity_type not in entity_filter.include:
                logger.debug(f"[ENTITY_ROUTER] Entity type not in include list: {entity_type}")
                continue
            
            filtered.append(entity)
        
        logger.info(f"[ENTITY_ROUTER] Filtered {len(entities)} → {len(filtered)} entities")
        return filtered


_router_instance: Optional[EntityTypeRouter] = None


def get_entity_router() -> EntityTypeRouter:
    """Get singleton router instance."""
    global _router_instance
    if _router_instance is None:
        _router_instance = EntityTypeRouter()
    return _router_instance


def route_query(classified_query: ClassifiedQuery) -> EntityTypeFilter:
    """Convenience function to get entity filter for a query."""
    return get_entity_router().get_filter(classified_query)
