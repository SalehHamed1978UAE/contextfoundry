"""
Extraction Post-Processor for Context Foundry.

Phase 2.6: Extraction Hardening - Defense in Depth Layer 2.
Catches relationships the LLM missed using deterministic patterns.
Runs AFTER LLM extraction, BEFORE data is finalized.

This is a GENERALIZED solution that works for ANY domain:
- Technology (CEO, CTO, CFO, etc.)
- Law Firms (Managing Partner, Senior Partner, etc.)
- Healthcare (Chief Medical Officer, Department Head, etc.)
- Finance (Portfolio Manager, Investment Director, etc.)

The patterns are domain-agnostic and comprehensive.
"""
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from datetime import datetime

from ..utils.logger import logger


ROLE_ABBREVIATIONS = {
    "CEO": "Chief Executive Officer",
    "CFO": "Chief Financial Officer",
    "CTO": "Chief Technology Officer",
    "CIO": "Chief Information Officer",
    "COO": "Chief Operating Officer",
    "CDO": "Chief Data Officer",
    "CMO": "Chief Marketing Officer",
    "CNO": "Chief Nursing Officer",
    "CHRO": "Chief Human Resources Officer",
    "CLO": "Chief Legal Officer",
    "CSO": "Chief Security Officer",
    "CPO": "Chief Product Officer",
    "CRO": "Chief Revenue Officer",
    "VP": "Vice President",
    "SVP": "Senior Vice President",
    "EVP": "Executive Vice President",
    "AVP": "Assistant Vice President",
    "MD": "Managing Director",
    "GM": "General Manager",
    "PM": "Project Manager",
    "HR": "Human Resources",
    "IT": "Information Technology",
}

HEALTHCARE_ROLE_EXPANSIONS = {
    "CMO": "Chief Medical Officer",
    "CNO": "Chief Nursing Officer",
}

ROLE_C_SUITE_TITLES = list(ROLE_ABBREVIATIONS.keys())

ROLE_FULL_NAMES = {v: k for k, v in ROLE_ABBREVIATIONS.items()}


@dataclass
class RolePattern:
    """A pattern for extracting role relationships."""
    name: str
    pattern: str
    person_group: int
    role_group: int
    confidence: float = 0.90
    description: str = ""


ROLE_PATTERNS = [
    RolePattern(
        name="name_dash_title",
        pattern=r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*[-–—:]\s*'
                r'(Chief\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+Officer|'
                r'CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|CHRO|CLO|CSO|CPO|CRO|'
                r'Managing\s+Partner|Senior\s+Partner|Partner|'
                r'(?:Senior\s+|Executive\s+)?Vice\s+President(?:\s+of\s+[A-Z][a-z]+)?|'
                r'Director(?:\s+of\s+[A-Z][a-z]+)?|'
                r'Chairman|Chairwoman|Chairperson|'
                r'Head\s+of\s+[A-Z][a-z]+|'
                r'President)(?=[\s,.\n]|$)',
        person_group=1,
        role_group=2,
        confidence=0.95,
        description="Matches 'John Smith - Chief Executive Officer' patterns"
    ),
    RolePattern(
        name="title_before_name",
        pattern=r'\b(CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|CHRO)\s+'
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?=[\s,.\n]|$)',
        person_group=2,
        role_group=1,
        confidence=0.92,
        description="Matches 'CEO John Smith' patterns"
    ),
    RolePattern(
        name="name_comma_title",
        pattern=r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}),\s*'
                r'(Chief\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+Officer|'
                r'CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|'
                r'Managing\s+Partner|Senior\s+Partner|Partner)(?=[\s,.\n]|$)',
        person_group=1,
        role_group=2,
        confidence=0.90,
        description="Matches 'John Smith, CEO' patterns"
    ),
    RolePattern(
        name="name_is_title",
        pattern=r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s+(?:is|serves\s+as|acts\s+as|works\s+as)\s+(?:the\s+)?'
                r'(Chief\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?\s+Officer|'
                r'CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|'
                r'Managing\s+Partner|Senior\s+Partner|Partner|'
                r'Director(?:\s+of\s+[A-Z][a-z]+)?)(?=[\s,.\n]|$)',
        person_group=1,
        role_group=2,
        confidence=0.92,
        description="Matches 'John Smith is the CEO' patterns"
    ),
    RolePattern(
        name="possessive_title_name",
        pattern=r'(?:our|the|their)\s+'
                r'(CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|'
                r'Director|President|Chairman|Partner)\s+'
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?=[\s,.\n]|$)',
        person_group=2,
        role_group=1,
        confidence=0.85,
        description="Matches 'our CEO John Smith' patterns"
    ),
    RolePattern(
        name="parenthetical_title",
        pattern=r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*\(\s*'
                r'(CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|'
                r'Managing\s+Partner|Senior\s+Partner|Partner)\s*\)',
        person_group=1,
        role_group=2,
        confidence=0.93,
        description="Matches 'John Smith (CEO)' patterns"
    ),
]

REPORTING_PATTERNS = [
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+report(?:s|ing)\s+to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
     0.90, "reports_to"),
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:manages|oversees|supervises|leads)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
     0.85, "manages"),
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+works?\s+under\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
     0.85, "reports_to"),
]

COMPENSATION_PATTERNS = [
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\'s)?\s+(?:base\s+)?(?:salary|compensation|pay|annual\s+(?:salary|compensation))\s+(?:is|of|:)?\s*\$?([0-9,]+(?:\.[0-9]{2})?)',
     "compensation", 0.90),
    (r'(?:salary|compensation)\s+of\s+\$?([0-9,]+(?:\.[0-9]{2})?)\s+(?:for|to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
     "compensation", 0.90),
]

ROLE_COMPENSATION_PATTERNS = [
    (r'(?:the\s+)?(CEO|CFO|CTO|CIO|COO|CMO|CDO|CHRO|CLO|CSO|CPO|CRO|'
     r'Chief\s+Executive\s+Officer|Chief\s+Financial\s+Officer|Chief\s+Technology\s+Officer|'
     r'Chief\s+Information\s+Officer|Chief\s+Operating\s+Officer|Chief\s+Medical\s+Officer|'
     r'Chief\s+Marketing\s+Officer|Managing\s+Partner|Senior\s+Partner|President)\'?s?\s+'
     r'(?:base\s+)?(?:salary|compensation|pay|total\s+compensation)\s+'
     r'(?:is|of|:)?\s*\$?([0-9,]+(?:\.[0-9]{2})?)',
     "role_compensation", 0.92),
    (r'(?:base\s+)?(?:salary|compensation|pay)\s+(?:for|of)\s+(?:the\s+)?'
     r'(CEO|CFO|CTO|CIO|COO|CMO|CDO|CHRO|'
     r'Chief\s+Executive\s+Officer|Chief\s+Financial\s+Officer|Chief\s+Technology\s+Officer|'
     r'Chief\s+Medical\s+Officer|Managing\s+Partner|Senior\s+Partner|President)\s+'
     r'(?:is|:)?\s*\$?([0-9,]+(?:\.[0-9]{2})?)',
     "role_compensation", 0.90),
    (r'(?:the\s+)?(CEO|CFO|CTO|CIO|COO|CMO|CDO|Managing\s+Partner|Senior\s+Partner|President)\s+'
     r'(?:receives?|earns?|makes?|has)\s+(?:a\s+)?(?:base\s+)?(?:salary|compensation)\s+of\s+'
     r'\$?([0-9,]+(?:\.[0-9]{2})?)',
     "role_compensation", 0.90),
    (r'\$([0-9,]+(?:\.[0-9]{2})?)\s+(?:base\s+)?(?:salary|compensation)\s+'
     r'(?:for|to)\s+(?:the\s+)?(CEO|CFO|CTO|CIO|COO|CMO|Managing\s+Partner|President)',
     "role_compensation_reverse", 0.88),
]

ORGANIZATION_PATTERNS = [
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}),\s*(?:CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|CHRO|'
     r'Chief\s+\w+\s+Officer|Managing\s+Partner|Senior\s+Partner|Partner|'
     r'Director|President|Chairman)\s+(?:of|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
     "works_at", 0.95),
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s+is\s+(?:the\s+)?'
     r'(?:CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|CHRO|Chief\s+\w+\s+Officer)\s+'
     r'(?:of|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
     "works_at", 0.95),
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*[-–—]\s*'
     r'(?:CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|CHRO|Chief\s+\w+\s+Officer)\s+'
     r'(?:of|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
     "works_at", 0.95),
    (r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)(?:'s)\s+"
     r"(?:CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|CHRO|Chief\s+\w+\s+Officer)\s+"
     r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?=\s+[a-z]|\s*[.,\n]|\s*$)",
     "works_at_reverse", 0.92),
    (r'(?:the\s+)?(?:CEO|CFO|CTO|CIO|COO)\s+(?:of|at)\s+'
     r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+'
     r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
     "works_at_reverse", 0.90),
]

INVESTMENT_PATTERNS = [
    (r'PORTFOLIO\s+COMPANY[:\s]+([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)*)',
     "portfolio_header", 0.95),
    (r'([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)*)\s+(?:has\s+)?invested\s+(?:\$[\d,.]+\s+)?in\s+([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)*)',
     "invested_in", 0.92),
    (r'([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)*)\s+is\s+(?:a\s+)?portfolio\s+company',
     "is_portfolio", 0.88),
    (r'([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)*)\s+portfolio\s+includes?\s+([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*)*)',
     "portfolio_includes", 0.90),
]


@dataclass
class ExtractedRelationshipFromPattern:
    """A relationship discovered by pattern matching."""
    relationship_type: str
    source_name: str
    target_name: str
    confidence: float
    pattern_name: str
    source_text: str
    extracted_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict:
        return {
            "relationship_type": self.relationship_type,
            "source_name": self.source_name,
            "target_name": self.target_name,
            "confidence": self.confidence,
            "pattern_name": self.pattern_name,
            "source_text": self.source_text[:200],
            "extracted_at": self.extracted_at.isoformat()
        }


@dataclass
class PostProcessorResult:
    """Result of post-processing extraction."""
    new_entities: List[Dict]
    new_relationships: List[ExtractedRelationshipFromPattern]
    patterns_matched: int
    processing_time_ms: float

    def to_dict(self) -> Dict:
        return {
            "new_entities": self.new_entities,
            "new_relationships": [r.to_dict() for r in self.new_relationships],
            "patterns_matched": self.patterns_matched,
            "processing_time_ms": round(self.processing_time_ms, 2)
        }


class ExtractionPostProcessor:
    """
    Catches relationships the LLM missed using deterministic patterns.
    Runs AFTER LLM extraction, BEFORE data is finalized.
    """

    def __init__(self, role_patterns: List[RolePattern] = None):
        """Initialize with patterns. Uses default patterns if none provided."""
        self.role_patterns = role_patterns or ROLE_PATTERNS
        self.reporting_patterns = REPORTING_PATTERNS
        self.compensation_patterns = COMPENSATION_PATTERNS
        self.role_compensation_patterns = ROLE_COMPENSATION_PATTERNS
        self.organization_patterns = ORGANIZATION_PATTERNS
        self.investment_patterns = INVESTMENT_PATTERNS

    def process(
        self,
        document_text: str,
        existing_entities: List[Dict],
        existing_relationships: List[Dict]
    ) -> PostProcessorResult:
        """
        Process document text to find relationships the LLM missed.
        """
        import time
        start = time.time()

        new_entities = []
        new_relationships = []
        patterns_matched = 0

        existing_entity_names = self._build_entity_name_set(existing_entities)
        existing_rel_keys = self._build_relationship_keys(existing_relationships)

        role_rels, role_entities = self._extract_role_relationships(
            document_text, existing_entity_names, existing_rel_keys
        )
        new_relationships.extend(role_rels)
        new_entities.extend(role_entities)
        patterns_matched += len(role_rels)

        reporting_rels = self._extract_reporting_relationships(
            document_text, existing_entity_names, existing_rel_keys
        )
        new_relationships.extend(reporting_rels)
        patterns_matched += len(reporting_rels)

        comp_rels = self._extract_compensation_relationships(
            document_text, existing_entity_names, existing_rel_keys
        )
        new_relationships.extend(comp_rels)
        patterns_matched += len(comp_rels)

        role_comp_rels = self._extract_role_compensation_relationships(
            document_text, existing_entity_names, existing_rel_keys
        )
        new_relationships.extend(role_comp_rels)
        patterns_matched += len(role_comp_rels)

        org_rels, org_entities = self._extract_organization_relationships(
            document_text, existing_entity_names, existing_rel_keys
        )
        new_relationships.extend(org_rels)
        new_entities.extend(org_entities)
        patterns_matched += len(org_rels)

        invest_rels, invest_entities = self._extract_investment_relationships(
            document_text, existing_entity_names, existing_rel_keys
        )
        new_relationships.extend(invest_rels)
        new_entities.extend(invest_entities)
        patterns_matched += len(invest_rels)

        elapsed_ms = (time.time() - start) * 1000

        if new_relationships:
            logger.info(f"[PostProcessor] Found {len(new_relationships)} relationships "
                       f"LLM missed in {elapsed_ms:.1f}ms")

        return PostProcessorResult(
            new_entities=new_entities,
            new_relationships=new_relationships,
            patterns_matched=patterns_matched,
            processing_time_ms=elapsed_ms
        )

    def _build_entity_name_set(self, entities: List[Dict]) -> Set[str]:
        """Build a set of normalized entity names for lookup."""
        names = set()
        for e in entities:
            name = e.get('name') or e.get('canonical_name', '')
            if name:
                names.add(name.lower().strip())
        return names

    def _build_relationship_keys(self, relationships: List[Dict]) -> Set[Tuple[str, str, str]]:
        """Build relationship lookup keys: (source_lower, target_lower, type_upper)."""
        keys = set()
        for r in relationships:
            source = (r.get('source_name') or '').lower().strip()
            target = (r.get('target_name') or '').lower().strip()
            rel_type = (r.get('relationship_type') or r.get('type', '')).upper().strip()
            if source and target and rel_type:
                keys.add((source, target, rel_type))
        return keys

    def _normalize_role(self, role: str) -> str:
        """Normalize role title to canonical form."""
        role = role.strip()
        role_upper = role.upper()
        if role_upper in ROLE_ABBREVIATIONS:
            return ROLE_ABBREVIATIONS[role_upper]
        return role

    def _is_valid_person_name(self, name: str) -> bool:
        """Check if a string looks like a valid person name."""
        words = name.split()
        if len(words) < 2:
            return False
        for word in words:
            if not word[0].isupper():
                return False
        INVALID_WORDS = {
            'the', 'our', 'their', 'and', 'or', 'for', 'to', 'of', 'in', 'on',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
            'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'responsible', 'leads', 'manages', 'announced', 'presented'
        }
        if any(w.lower() in INVALID_WORDS for w in words):
            return False
        if len(words) > 4:
            return False
        return True

    def _extract_role_relationships(
        self, text: str, existing_entity_names: Set[str], existing_rel_keys: Set[Tuple[str, str, str]]
    ) -> Tuple[List[ExtractedRelationshipFromPattern], List[Dict]]:
        """Extract HOLDS_POSITION relationships from text."""
        relationships = []
        new_entities = []
        seen_pairs = set()

        for pattern in self.role_patterns:
            try:
                matches = re.finditer(pattern.pattern, text, re.IGNORECASE)
                for match in matches:
                    person_name = match.group(pattern.person_group).strip()
                    role_title = match.group(pattern.role_group).strip()
                    if not self._is_valid_person_name(person_name):
                        continue
                    role_title = self._normalize_role(role_title)
                    pair_key = (person_name.lower(), role_title.lower())
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    rel_key = (person_name.lower(), role_title.lower(), "HOLDS_POSITION")
                    if rel_key in existing_rel_keys:
                        continue
                    rel = ExtractedRelationshipFromPattern(
                        relationship_type="HOLDS_POSITION",
                        source_name=person_name,
                        target_name=role_title,
                        confidence=pattern.confidence,
                        pattern_name=pattern.name,
                        source_text=match.group(0)
                    )
                    relationships.append(rel)
                    if person_name.lower() not in existing_entity_names:
                        new_entities.append({
                            "name": person_name, "entity_type": "PERSON",
                            "confidence": pattern.confidence, "source": "post_processor"
                        })
                        existing_entity_names.add(person_name.lower())
                    if role_title.lower() not in existing_entity_names:
                        new_entities.append({
                            "name": role_title, "entity_type": "JOB_TITLE",
                            "confidence": pattern.confidence, "source": "post_processor"
                        })
                        existing_entity_names.add(role_title.lower())
            except Exception as e:
                logger.warning(f"[PostProcessor] Pattern '{pattern.name}' failed: {e}")
        return relationships, new_entities

    def _extract_reporting_relationships(
        self, text: str, existing_entity_names: Set[str], existing_rel_keys: Set[Tuple[str, str, str]]
    ) -> List[ExtractedRelationshipFromPattern]:
        """Extract REPORTS_TO relationships from text."""
        relationships = []
        seen_pairs = set()
        for pattern, confidence, rel_type in self.reporting_patterns:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    if rel_type == "reports_to":
                        subordinate = match.group(1).strip()
                        manager = match.group(2).strip()
                    else:
                        manager = match.group(1).strip()
                        subordinate = match.group(2).strip()
                    pair_key = (subordinate.lower(), manager.lower())
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    rel_key = (subordinate.lower(), manager.lower(), "REPORTS_TO")
                    if rel_key in existing_rel_keys:
                        continue
                    rel = ExtractedRelationshipFromPattern(
                        relationship_type="REPORTS_TO",
                        source_name=subordinate,
                        target_name=manager,
                        confidence=confidence,
                        pattern_name="reporting_pattern",
                        source_text=match.group(0)
                    )
                    relationships.append(rel)
            except Exception as e:
                logger.warning(f"[PostProcessor] Reporting pattern failed: {e}")
        return relationships

    def _extract_compensation_relationships(
        self, text: str, existing_entity_names: Set[str], existing_rel_keys: Set[Tuple[str, str, str]]
    ) -> List[ExtractedRelationshipFromPattern]:
        """Extract HAS_COMPENSATION relationships from text."""
        relationships = []
        seen_names = set()
        for pattern, rel_type, confidence in self.compensation_patterns:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    groups = match.groups()
                    if groups[0] and not groups[0].replace(',', '').replace('.', '').isdigit():
                        person_name = groups[0].strip()
                        amount = groups[1].strip()
                    else:
                        amount = groups[0].strip()
                        person_name = groups[1].strip()
                    if person_name.lower() in seen_names:
                        continue
                    seen_names.add(person_name.lower())
                    rel_key = (person_name.lower(), amount, "HAS_COMPENSATION")
                    if rel_key in existing_rel_keys:
                        continue
                    rel = ExtractedRelationshipFromPattern(
                        relationship_type="HAS_COMPENSATION",
                        source_name=person_name,
                        target_name=amount,
                        confidence=confidence,
                        pattern_name="compensation_pattern",
                        source_text=match.group(0)
                    )
                    relationships.append(rel)
            except Exception as e:
                logger.warning(f"[PostProcessor] Compensation pattern failed: {e}")
        return relationships

    def _extract_role_compensation_relationships(
        self, text: str, existing_entity_names: Set[str], existing_rel_keys: Set[Tuple[str, str, str]]
    ) -> List[ExtractedRelationshipFromPattern]:
        """
        Extract ROLE_HAS_COMPENSATION relationships from text.
        
        Handles patterns like "CEO's salary is $850,000" where the role
        (not person name) is mentioned. Creates a ROLE_HAS_COMPENSATION
        relationship that links the role title to the compensation amount.
        
        These relationships can later be joined with HOLDS_POSITION to answer
        queries like "What is the CEO's salary?"
        """
        relationships = []
        seen_roles = set()
        for pattern, rel_type, confidence in self.role_compensation_patterns:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    groups = match.groups()
                    if rel_type == "role_compensation_reverse":
                        amount = groups[0].strip()
                        role_title = groups[1].strip()
                    else:
                        role_title = groups[0].strip()
                        amount = groups[1].strip()
                    role_normalized = self._normalize_role(role_title)
                    if role_normalized.lower() in seen_roles:
                        continue
                    seen_roles.add(role_normalized.lower())
                    rel_key = (role_normalized.lower(), amount, "ROLE_HAS_COMPENSATION")
                    if rel_key in existing_rel_keys:
                        continue
                    rel = ExtractedRelationshipFromPattern(
                        relationship_type="ROLE_HAS_COMPENSATION",
                        source_name=role_normalized,
                        target_name=amount,
                        confidence=confidence,
                        pattern_name="role_compensation_pattern",
                        source_text=match.group(0)
                    )
                    relationships.append(rel)
                    logger.info(f"[PostProcessor] Found role compensation: {role_normalized} → ${amount}")
            except Exception as e:
                logger.warning(f"[PostProcessor] Role compensation pattern failed: {e}")
        return relationships

    def _extract_organization_relationships(
        self, text: str, existing_entity_names: Set[str], existing_rel_keys: Set[Tuple[str, str, str]]
    ) -> Tuple[List[ExtractedRelationshipFromPattern], List[Dict]]:
        """Extract WORKS_AT/EMPLOYED_BY relationships from text."""
        relationships = []
        new_entities = []
        seen_pairs = set()
        for pattern, rel_type, confidence in self.organization_patterns:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    if rel_type == "works_at_reverse":
                        org_name = match.group(1).strip()
                        person_name = match.group(2).strip()
                    else:
                        person_name = match.group(1).strip()
                        org_name = match.group(2).strip()
                    if not self._is_valid_person_name(person_name):
                        continue
                    org_lower = org_name.lower()
                    if org_lower in {'the', 'a', 'an', 'and', 'or', 'at', 'for', 'of'}:
                        continue
                    pair_key = (person_name.lower(), org_name.lower())
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    rel_key = (person_name.lower(), org_name.lower(), "WORKS_AT")
                    employed_key = (person_name.lower(), org_name.lower(), "EMPLOYED_BY")
                    if rel_key in existing_rel_keys or employed_key in existing_rel_keys:
                        continue
                    rel = ExtractedRelationshipFromPattern(
                        relationship_type="WORKS_AT",
                        source_name=person_name,
                        target_name=org_name,
                        confidence=confidence,
                        pattern_name="organization_pattern",
                        source_text=match.group(0)
                    )
                    relationships.append(rel)
                    if org_name.lower() not in existing_entity_names:
                        new_entities.append({
                            "name": org_name, "entity_type": "ORGANIZATION",
                            "confidence": confidence, "source": "post_processor"
                        })
                        existing_entity_names.add(org_name.lower())
            except Exception as e:
                logger.warning(f"[PostProcessor] Organization pattern failed: {e}")
        return relationships, new_entities

    def _extract_investment_relationships(
        self, text: str, existing_entity_names: Set[str], existing_rel_keys: Set[Tuple[str, str, str]]
    ) -> Tuple[List[ExtractedRelationshipFromPattern], List[Dict]]:
        """Extract INVESTED_IN relationships from text for portfolio companies."""
        relationships = []
        new_entities = []
        seen_companies = set()
        
        investor_name = self._detect_investor_from_text(text)
        
        for pattern, pattern_type, confidence in self.investment_patterns:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE if pattern_type != "portfolio_header" else 0)
                for match in matches:
                    company_name = None
                    
                    if pattern_type == "portfolio_header":
                        company_name = match.group(1).strip()
                    elif pattern_type == "portfolio_label":
                        company_name = match.group(1).strip()
                    elif pattern_type == "invested_in":
                        investor_name = match.group(1).strip()
                        company_name = match.group(2).strip()
                    elif pattern_type == "is_portfolio":
                        company_name = match.group(1).strip()
                    elif pattern_type == "investment_in":
                        company_name = match.group(1).strip()
                    elif pattern_type == "portfolio_includes":
                        investor_name = match.group(1).strip()
                        company_name = match.group(2).strip()
                    
                    if not company_name or len(company_name) < 3:
                        continue
                    
                    company_lower = company_name.lower()
                    if company_lower in seen_companies:
                        continue
                    if company_lower in {'the', 'a', 'an', 'and', 'or', 'at', 'for', 'of', 'portfolio', 'company'}:
                        continue
                    
                    seen_companies.add(company_lower)
                    
                    if not investor_name:
                        continue
                    
                    rel_key = (investor_name.lower(), company_lower, "INVESTED_IN")
                    if rel_key in existing_rel_keys:
                        continue
                    
                    rel = ExtractedRelationshipFromPattern(
                        relationship_type="INVESTED_IN",
                        source_name=investor_name,
                        target_name=company_name,
                        confidence=confidence,
                        pattern_name=f"investment_{pattern_type}",
                        source_text=match.group(0)
                    )
                    relationships.append(rel)
                    logger.info(f"[PostProcessor] Found investment: {investor_name} → {company_name}")
                    
                    if company_lower not in existing_entity_names:
                        new_entities.append({
                            "name": company_name, "entity_type": "ORGANIZATION",
                            "confidence": confidence, "source": "post_processor"
                        })
                        existing_entity_names.add(company_lower)
                        
            except Exception as e:
                logger.warning(f"[PostProcessor] Investment pattern '{pattern_type}' failed: {e}")
        
        return relationships, new_entities

    def _detect_investor_from_text(self, text: str) -> Optional[str]:
        """Detect the investor organization name from document text."""
        patterns = [
            r'^([A-Z][A-Z]+(?:\s+[A-Z]+)*)\s+PORTFOLIO',
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+Portfolio',
            r'Prepared\s+by[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
            r'^([A-Z][a-z]+(?:Ventures|Capital|Partners|Fund|Investments))',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                return match.group(1).strip()
        return None


class RoleNormalizer:
    """Normalizes role titles for semantic matching."""
    SEMANTIC_EQUIVALENTS = [
        {"CEO", "Chief Executive Officer", "President and CEO", "Chief Exec"},
        {"CFO", "Chief Financial Officer", "Finance Director", "VP Finance"},
        {"CTO", "Chief Technology Officer", "VP Engineering", "Head of Engineering", "VP Technology"},
        {"CIO", "Chief Information Officer", "IT Director", "VP IT", "Head of IT"},
        {"COO", "Chief Operating Officer", "VP Operations", "Head of Operations"},
        {"CMO", "Chief Marketing Officer", "VP Marketing", "Head of Marketing", "Marketing Director"},
        {"CMO-Healthcare", "Chief Medical Officer", "Medical Director", "Head of Medical"},
        {"CNO", "Chief Nursing Officer", "Nursing Director", "VP Nursing"},
        {"CHRO", "Chief Human Resources Officer", "VP HR", "Head of HR", "HR Director"},
        {"Managing Partner", "Senior Partner", "Name Partner"},
        {"Partner", "Equity Partner", "Full Partner"},
        {"Chairman", "Chairwoman", "Chairperson", "Chair", "Board Chair"},
    ]
    
    CMO_CONTEXT_AWARE = {
        "healthcare": "Chief Medical Officer",
        "medical": "Chief Medical Officer",
        "hospital": "Chief Medical Officer",
        "clinic": "Chief Medical Officer",
        "marketing": "Chief Marketing Officer",
        "default": "Chief Marketing Officer",
    }

    def __init__(self):
        self._canonical_map: Dict[str, str] = {}
        self._equivalents_map: Dict[str, Set[str]] = {}
        for equiv_set in self.SEMANTIC_EQUIVALENTS:
            canonical = list(equiv_set)[0]
            for variant in equiv_set:
                self._canonical_map[variant.lower()] = canonical
                self._equivalents_map[variant.lower()] = equiv_set
        for abbrev, full in ROLE_ABBREVIATIONS.items():
            self._canonical_map[abbrev.lower()] = full
            self._canonical_map[full.lower()] = full

    def normalize(self, role: str) -> str:
        """Normalize a role to its canonical form."""
        return self._canonical_map.get(role.lower().strip(), role)

    def are_equivalent(self, role1: str, role2: str) -> bool:
        """Check if two roles are semantically equivalent."""
        r1_lower = role1.lower().strip()
        r2_lower = role2.lower().strip()
        if self.normalize(role1).lower() == self.normalize(role2).lower():
            return True
        equiv1 = self._equivalents_map.get(r1_lower, set())
        equiv2 = self._equivalents_map.get(r2_lower, set())
        if equiv1 and equiv2:
            return bool(equiv1.intersection(equiv2))
        if r1_lower in r2_lower or r2_lower in r1_lower:
            return True
        return False

    def expand_query(self, role: str) -> List[str]:
        """Expand a role query to include all equivalent forms."""
        role_lower = role.lower().strip()
        equivalents = self._equivalents_map.get(role_lower, set())
        if equivalents:
            return list(equivalents)
        if role.upper() in ROLE_ABBREVIATIONS:
            return [role, ROLE_ABBREVIATIONS[role.upper()]]
        if role in ROLE_FULL_NAMES:
            return [role, ROLE_FULL_NAMES[role]]
        return [role]


def get_post_processor() -> ExtractionPostProcessor:
    """Get a configured post-processor instance."""
    return ExtractionPostProcessor()


def get_role_normalizer() -> RoleNormalizer:
    """Get a configured role normalizer instance."""
    return RoleNormalizer()
