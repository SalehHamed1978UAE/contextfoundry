"""
Canonical Name Normalizer

Maps LLM-proposed relationship/entity names to canonical forms.
Prevents fragmented candidates for semantically equivalent patterns.

Example:
    "INVESTS_IN", "MADE_INVESTMENT", "FUNDED" → all normalize to "INVESTED_IN"
"""

import re
from typing import Dict

from src.context_foundry.utils.logger import logger

RELATIONSHIP_SYNONYMS: Dict[str, str] = {
    "INVESTS_IN": "INVESTED_IN",
    "MADE_INVESTMENT_IN": "INVESTED_IN",
    "MADE_INVESTMENT": "INVESTED_IN",
    "FUNDED": "INVESTED_IN",
    "BACKS": "INVESTED_IN",
    "BACKED": "INVESTED_IN",
    "PORTFOLIO_COMPANY_OF": "INVESTED_IN",
    "LED_ROUND_IN": "INVESTED_IN",
    "PARTICIPATED_IN_ROUND": "INVESTED_IN",
    
    "EMPLOYED_BY": "WORKS_AT",
    "EMPLOYEE_OF": "WORKS_AT",
    "WORKS_FOR": "WORKS_AT",
    "MEMBER_OF": "WORKS_AT",
    "JOINED": "WORKS_AT",
    "EMPLOYED_AT": "WORKS_AT",
    
    "OWNED_BY": "OWNS",
    "SUBSIDIARY_OF": "OWNS",
    "PARENT_OF": "OWNS",
    "HAS_SUBSIDIARY": "OWNS",
    "CONTROLS": "OWNS",
    "PARENT_COMPANY_OF": "OWNS",
    
    "LEADS": "HOLDS_POSITION",
    "MANAGES": "HOLDS_POSITION",
    "HEADS": "HOLDS_POSITION",
    "RUNS": "HOLDS_POSITION",
    "IS_CEO_OF": "HOLDS_POSITION",
    "IS_CTO_OF": "HOLDS_POSITION",
    "IS_CFO_OF": "HOLDS_POSITION",
    "SERVES_AS": "HOLDS_POSITION",
    "APPOINTED_AS": "HOLDS_POSITION",
    "PROMOTED_TO": "HOLDS_POSITION",
    
    "ON_BOARD_OF": "BOARD_MEMBER_OF",
    "BOARD_DIRECTOR_OF": "BOARD_MEMBER_OF",
    "SERVES_ON_BOARD": "BOARD_MEMBER_OF",
    "SITS_ON_BOARD": "BOARD_MEMBER_OF",
    "BOARD_SEAT_AT": "BOARD_MEMBER_OF",
    
    "MANAGED_BY": "REPORTS_TO",
    "SUPERVISED_BY": "REPORTS_TO",
    "REPORTS_INTO": "REPORTS_TO",
    
    "HEADQUARTERED_IN": "LOCATED_IN",
    "BASED_IN": "LOCATED_IN",
    "HAS_OFFICE_IN": "LOCATED_IN",
    "OPERATES_IN": "LOCATED_IN",
    
    "STARTED": "FOUNDED",
    "CREATED": "FOUNDED",
    "ESTABLISHED": "FOUNDED",
    "CO_FOUNDED": "FOUNDED",
    
    "BOUGHT": "ACQUIRED",
    "PURCHASED": "ACQUIRED",
    "TOOK_OVER": "ACQUIRED",
    
    "PARTNERS_WITH": "PARTNERED_WITH",
    "COLLABORATES_WITH": "PARTNERED_WITH",
    "ALLIED_WITH": "PARTNERED_WITH",
}

ENTITY_SYNONYMS: Dict[str, str] = {
    "COMPANY": "ORGANIZATION",
    "CORPORATION": "ORGANIZATION",
    "FIRM": "ORGANIZATION",
    "STARTUP": "ORGANIZATION",
    "ENTERPRISE": "ORGANIZATION",
    "BUSINESS": "ORGANIZATION",
    "INSTITUTION": "ORGANIZATION",
    "AGENCY": "ORGANIZATION",
    
    "INDIVIDUAL": "PERSON",
    "EMPLOYEE": "PERSON",
    "EXECUTIVE": "PERSON",
    "FOUNDER": "PERSON",
    "LEADER": "PERSON",
    
    "POSITION": "JOB_TITLE",
    "TITLE": "JOB_TITLE",
    "ROLE": "JOB_TITLE",
    
    "SALARY": "COMPENSATION",
    "PAY": "COMPENSATION",
    "EARNINGS": "COMPENSATION",
    "REMUNERATION": "COMPENSATION",
}


class CandidateNormalizer:
    """Normalizes candidate names to canonical forms."""
    
    def __init__(self):
        self.relationship_synonyms = RELATIONSHIP_SYNONYMS.copy()
        self.entity_synonyms = ENTITY_SYNONYMS.copy()
    
    def normalize_relationship(self, name: str) -> str:
        """Normalize a relationship type name."""
        normalized = self._clean_name(name)
        
        if normalized in self.relationship_synonyms:
            logger.debug(f"[Normalizer] {name} → {self.relationship_synonyms[normalized]}")
            return self.relationship_synonyms[normalized]
        
        return normalized
    
    def normalize_entity(self, name: str) -> str:
        """Normalize an entity type name."""
        normalized = self._clean_name(name)
        
        if normalized in self.entity_synonyms:
            logger.debug(f"[Normalizer] {name} → {self.entity_synonyms[normalized]}")
            return self.entity_synonyms[normalized]
        
        return normalized
    
    def _clean_name(self, name: str) -> str:
        """Clean and standardize a name."""
        name = re.sub(r'([a-z])([A-Z])', r'\1_\2', name)
        name = name.upper()
        name = re.sub(r'[\s\-]+', '_', name)
        name = re.sub(r'[^A-Z0-9_]', '', name)
        name = re.sub(r'_+', '_', name)
        name = name.strip('_')
        return name
    
    def add_synonym(self, synonym: str, canonical: str, type: str = "RELATIONSHIP"):
        """Add a custom synonym mapping."""
        synonym = self._clean_name(synonym)
        canonical = self._clean_name(canonical)
        
        if type == "RELATIONSHIP":
            self.relationship_synonyms[synonym] = canonical
        else:
            self.entity_synonyms[synonym] = canonical
        
        logger.info(f"[Normalizer] Added synonym: {synonym} → {canonical}")
