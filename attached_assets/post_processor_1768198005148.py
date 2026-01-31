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


# =============================================================================
# ROLE NORMALIZATION MAPPINGS
# =============================================================================

# Canonical role mappings - normalize variations to standard forms
ROLE_ABBREVIATIONS = {
    # C-Suite
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

    # VP titles
    "VP": "Vice President",
    "SVP": "Senior Vice President",
    "EVP": "Executive Vice President",
    "AVP": "Assistant Vice President",

    # Other abbreviations
    "MD": "Managing Director",
    "GM": "General Manager",
    "PM": "Project Manager",
    "HR": "Human Resources",
    "IT": "Information Technology",
}

# Reverse mappings for bidirectional lookup
ROLE_FULL_NAMES = {v: k for k, v in ROLE_ABBREVIATIONS.items()}


# =============================================================================
# PATTERN DEFINITIONS - DOMAIN AGNOSTIC
# =============================================================================

@dataclass
class RolePattern:
    """A pattern for extracting role relationships."""
    name: str
    pattern: str  # Regex pattern
    person_group: int  # Capture group for person name
    role_group: int  # Capture group for role title
    confidence: float = 0.90
    description: str = ""


# Core role patterns that work across domains
# Note: Patterns use word boundaries and are designed to avoid over-matching
ROLE_PATTERNS = [
    # Pattern 1: "Name - Title" or "Name – Title" (em-dash)
    # Must be on same line, title ends at punctuation or newline
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

    # Pattern 2: "Title Name" (title before name, bounded)
    RolePattern(
        name="title_before_name",
        pattern=r'\b(CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|CHRO)\s+'
                r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?=[\s,.\n]|$)',
        person_group=2,
        role_group=1,
        confidence=0.92,
        description="Matches 'CEO John Smith' patterns"
    ),

    # Pattern 3: "Name, Title" (comma separated, title bounded)
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

    # Pattern 4: "Name is the Title" or "Name serves as Title"
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

    # Pattern 5: "our/the Title Name" (possessive)
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

    # Pattern 6: "Name (Title)" - parenthetical titles
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

# Reporting structure patterns
REPORTING_PATTERNS = [
    # "Name reports to Name" or "Name reporting to Name"
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+report(?:s|ing)\s+to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
     0.90, "reports_to"),

    # "Name manages Name" or "Name oversees Name"
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+(?:manages|oversees|supervises|leads)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
     0.85, "manages"),

    # "Name works under Name"
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\s+works?\s+under\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
     0.85, "reports_to"),
]

# Compensation patterns
COMPENSATION_PATTERNS = [
    # "$XXX,XXX salary/compensation/annual"
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)(?:\'s)?\s+(?:base\s+)?(?:salary|compensation|pay|annual\s+(?:salary|compensation))\s+(?:is|of|:)?\s*\$?([0-9,]+(?:\.[0-9]{2})?)',
     "compensation", 0.90),

    # "salary of $XXX,XXX for Name"
    (r'(?:salary|compensation)\s+of\s+\$?([0-9,]+(?:\.[0-9]{2})?)\s+(?:for|to)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
     "compensation", 0.90),
]

# Organization/employment patterns - captures WORKS_AT relationships
# These patterns extract Person -> Organization relationships for disambiguation context
ORGANIZATION_PATTERNS = [
    # "Name, CEO of OrgName" or "Name, CFO of OrgName" (comma before role)
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}),\s*(?:CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|CHRO|'
     r'Chief\s+\w+\s+Officer|Managing\s+Partner|Senior\s+Partner|Partner|'
     r'Director|President|Chairman)\s+(?:of|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
     "works_at", 0.95),

    # "Name is the CEO of OrgName" or "Name is CEO of OrgName"
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s+is\s+(?:the\s+)?'
     r'(?:CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|CHRO|Chief\s+\w+\s+Officer)\s+'
     r'(?:of|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
     "works_at", 0.95),

    # "Name - CEO of OrgName" or "Name - Chief Executive Officer of OrgName"
    (r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\s*[-–—]\s*'
     r'(?:CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|CHRO|Chief\s+\w+\s+Officer)\s+'
     r'(?:of|at)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
     "works_at", 0.95),

    # "OrgName's CEO Name" (possessive form, name bounded by lowercase or punctuation)
    (r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)(?:'s)\s+"
     r"(?:CEO|CFO|CTO|CIO|COO|CDO|CMO|CNO|CHRO|Chief\s+\w+\s+Officer)\s+"
     r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})(?=\s+[a-z]|\s*[.,\n]|\s*$)",
     "works_at_reverse", 0.92),

    # "the CEO of OrgName, Name" (role with org first, then name)
    (r'(?:the\s+)?(?:CEO|CFO|CTO|CIO|COO)\s+(?:of|at)\s+'
     r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*),?\s+'
     r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
     "works_at_reverse", 0.90),
]


@dataclass
class ExtractedRelationshipFromPattern:
    """A relationship discovered by pattern matching."""
    relationship_type: str  # HOLDS_POSITION, REPORTS_TO, HAS_COMPENSATION
    source_name: str
    target_name: str  # For HOLDS_POSITION: role title; For REPORTS_TO: manager name
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

    This is defense-in-depth: LLM extracts most things, patterns catch the rest.

    Process:
    1. Scan document text for role patterns (Person -> Title)
    2. Scan for reporting patterns (Person -> Person)
    3. Scan for compensation patterns (Person -> Amount)
    4. Scan for organization patterns (Person -> Organization)
    5. Compare against existing extractions
    6. Return only NEW relationships not already captured
    """

    def __init__(self, role_patterns: List[RolePattern] = None):
        """Initialize with patterns. Uses default patterns if none provided."""
        self.role_patterns = role_patterns or ROLE_PATTERNS
        self.reporting_patterns = REPORTING_PATTERNS
        self.compensation_patterns = COMPENSATION_PATTERNS
        self.organization_patterns = ORGANIZATION_PATTERNS

    def process(
        self,
        document_text: str,
        existing_entities: List[Dict],
        existing_relationships: List[Dict]
    ) -> PostProcessorResult:
        """
        Process document text to find relationships the LLM missed.

        Args:
            document_text: Full document text to scan
            existing_entities: Entities already extracted by LLM
            existing_relationships: Relationships already extracted by LLM

        Returns:
            PostProcessorResult with new entities and relationships
        """
        import time
        start = time.time()

        new_entities = []
        new_relationships = []
        patterns_matched = 0

        # Build lookup sets for existing data
        existing_entity_names = self._build_entity_name_set(existing_entities)
        existing_rel_keys = self._build_relationship_keys(existing_relationships)

        # Stage 1: Extract role relationships
        role_rels, role_entities = self._extract_role_relationships(
            document_text,
            existing_entity_names,
            existing_rel_keys
        )
        new_relationships.extend(role_rels)
        new_entities.extend(role_entities)
        patterns_matched += len(role_rels)

        # Stage 2: Extract reporting relationships
        reporting_rels = self._extract_reporting_relationships(
            document_text,
            existing_entity_names,
            existing_rel_keys
        )
        new_relationships.extend(reporting_rels)
        patterns_matched += len(reporting_rels)

        # Stage 3: Extract compensation relationships
        comp_rels = self._extract_compensation_relationships(
            document_text,
            existing_entity_names,
            existing_rel_keys
        )
        new_relationships.extend(comp_rels)
        patterns_matched += len(comp_rels)

        # Stage 4: Extract organization/employment relationships
        org_rels, org_entities = self._extract_organization_relationships(
            document_text,
            existing_entity_names,
            existing_rel_keys
        )
        new_relationships.extend(org_rels)
        new_entities.extend(org_entities)
        patterns_matched += len(org_rels)

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

        # Check if it's an abbreviation
        role_upper = role.upper()
        if role_upper in ROLE_ABBREVIATIONS:
            return ROLE_ABBREVIATIONS[role_upper]

        # Already full form
        return role

    def _is_valid_person_name(self, name: str) -> bool:
        """Check if a string looks like a valid person name."""
        # Must have at least 2 words
        words = name.split()
        if len(words) < 2:
            return False

        # Each word should start with capital letter
        for word in words:
            if not word[0].isupper():
                return False

        # Common non-name words to reject
        INVALID_WORDS = {
            'the', 'our', 'their', 'and', 'or', 'for', 'to', 'of', 'in', 'on',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has',
            'had', 'do', 'does', 'did', 'will', 'would', 'could', 'should',
            'responsible', 'leads', 'manages', 'announced', 'presented'
        }
        if any(w.lower() in INVALID_WORDS for w in words):
            return False

        # Name should be relatively short (2-4 words typical)
        if len(words) > 4:
            return False

        return True

    def _extract_role_relationships(
        self,
        text: str,
        existing_entity_names: Set[str],
        existing_rel_keys: Set[Tuple[str, str, str]]
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

                    # Validate that the person name looks like a real name
                    if not self._is_valid_person_name(person_name):
                        logger.debug(f"[PostProcessor] Skipping invalid name: {person_name}")
                        continue

                    # Normalize the role
                    role_title = self._normalize_role(role_title)

                    # Skip if already seen this pair
                    pair_key = (person_name.lower(), role_title.lower())
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    # Check if relationship already exists
                    rel_key = (person_name.lower(), role_title.lower(), "HOLDS_POSITION")
                    if rel_key in existing_rel_keys:
                        continue

                    # Create new relationship
                    rel = ExtractedRelationshipFromPattern(
                        relationship_type="HOLDS_POSITION",
                        source_name=person_name,
                        target_name=role_title,
                        confidence=pattern.confidence,
                        pattern_name=pattern.name,
                        source_text=match.group(0)
                    )
                    relationships.append(rel)

                    # Check if we need to create entities
                    if person_name.lower() not in existing_entity_names:
                        new_entities.append({
                            "name": person_name,
                            "entity_type": "PERSON",
                            "confidence": pattern.confidence,
                            "source": "post_processor",
                            "pattern": pattern.name
                        })
                        existing_entity_names.add(person_name.lower())

                    if role_title.lower() not in existing_entity_names:
                        new_entities.append({
                            "name": role_title,
                            "entity_type": "JOB_TITLE",
                            "confidence": pattern.confidence,
                            "source": "post_processor",
                            "pattern": pattern.name
                        })
                        existing_entity_names.add(role_title.lower())

            except Exception as e:
                logger.warning(f"[PostProcessor] Pattern '{pattern.name}' failed: {e}")
                continue

        return relationships, new_entities

    def _extract_reporting_relationships(
        self,
        text: str,
        existing_entity_names: Set[str],
        existing_rel_keys: Set[Tuple[str, str, str]]
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
                    else:  # manages
                        manager = match.group(1).strip()
                        subordinate = match.group(2).strip()

                    # Skip if already seen
                    pair_key = (subordinate.lower(), manager.lower())
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    # Check if relationship already exists
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
                continue

        return relationships

    def _extract_compensation_relationships(
        self,
        text: str,
        existing_entity_names: Set[str],
        existing_rel_keys: Set[Tuple[str, str, str]]
    ) -> List[ExtractedRelationshipFromPattern]:
        """Extract HAS_COMPENSATION relationships from text."""
        relationships = []
        seen_names = set()

        for pattern, rel_type, confidence in self.compensation_patterns:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE)

                for match in matches:
                    # Determine which group is name vs amount based on pattern
                    groups = match.groups()

                    # First pattern: Name's salary $XXX
                    if groups[0] and not groups[0].replace(',', '').replace('.', '').isdigit():
                        person_name = groups[0].strip()
                        amount = groups[1].strip()
                    else:
                        # Second pattern: salary of $XXX for Name
                        amount = groups[0].strip()
                        person_name = groups[1].strip()

                    # Skip if already seen
                    if person_name.lower() in seen_names:
                        continue
                    seen_names.add(person_name.lower())

                    # Check if relationship already exists
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
                continue

        return relationships

    def _extract_organization_relationships(
        self,
        text: str,
        existing_entity_names: Set[str],
        existing_rel_keys: Set[Tuple[str, str, str]]
    ) -> Tuple[List[ExtractedRelationshipFromPattern], List[Dict]]:
        """
        Extract WORKS_AT/EMPLOYED_BY relationships from text.

        This is CRITICAL for disambiguation - it captures which organization
        a person belongs to, enabling proper context like:
        "Sarah Chen (CEO of TechVentures)" instead of "Sarah Chen (CEO)"
        """
        relationships = []
        new_entities = []
        seen_pairs = set()

        for pattern, rel_type, confidence in self.organization_patterns:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE)

                for match in matches:
                    # Handle reverse patterns where org comes first
                    if rel_type == "works_at_reverse":
                        org_name = match.group(1).strip()
                        person_name = match.group(2).strip()
                    else:
                        person_name = match.group(1).strip()
                        org_name = match.group(2).strip()

                    # Validate person name
                    if not self._is_valid_person_name(person_name):
                        continue

                    # Skip common false positives for org names
                    org_lower = org_name.lower()
                    if org_lower in {'the', 'a', 'an', 'and', 'or', 'at', 'for', 'of'}:
                        continue

                    # Skip if already seen
                    pair_key = (person_name.lower(), org_name.lower())
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)

                    # Check if relationship already exists
                    rel_key = (person_name.lower(), org_name.lower(), "WORKS_AT")
                    employed_key = (person_name.lower(), org_name.lower(), "EMPLOYED_BY")
                    if rel_key in existing_rel_keys or employed_key in existing_rel_keys:
                        continue

                    # Create relationship
                    rel = ExtractedRelationshipFromPattern(
                        relationship_type="WORKS_AT",
                        source_name=person_name,
                        target_name=org_name,
                        confidence=confidence,
                        pattern_name="organization_pattern",
                        source_text=match.group(0)
                    )
                    relationships.append(rel)

                    # Add organization entity if not exists
                    if org_name.lower() not in existing_entity_names:
                        new_entities.append({
                            "name": org_name,
                            "entity_type": "ORGANIZATION",
                            "confidence": confidence,
                            "source": "post_processor",
                            "pattern": "organization_pattern"
                        })
                        existing_entity_names.add(org_name.lower())

            except Exception as e:
                logger.warning(f"[PostProcessor] Organization pattern failed: {e}")
                continue

        return relationships, new_entities


# =============================================================================
# ROLE NORMALIZER - Semantic matching for role queries
# =============================================================================

class RoleNormalizer:
    """
    Normalizes role titles for semantic matching.
    Handles abbreviations, variations, and semantic equivalence.

    Examples:
    - "CEO" ↔ "Chief Executive Officer"
    - "CFO" ↔ "Chief Financial Officer"
    - "Head of Engineering" ↔ "VP Engineering"
    """

    # Semantic equivalence classes - roles that mean the same thing
    SEMANTIC_EQUIVALENTS = [
        {"CEO", "Chief Executive Officer", "President and CEO", "Chief Exec"},
        {"CFO", "Chief Financial Officer", "Finance Director", "VP Finance"},
        {"CTO", "Chief Technology Officer", "VP Engineering", "Head of Engineering", "VP Technology"},
        {"CIO", "Chief Information Officer", "IT Director", "VP IT", "Head of IT"},
        {"COO", "Chief Operating Officer", "VP Operations", "Head of Operations"},
        {"CMO", "Chief Marketing Officer", "VP Marketing", "Head of Marketing", "Marketing Director"},
        {"CHRO", "Chief Human Resources Officer", "VP HR", "Head of HR", "HR Director"},
        {"Managing Partner", "Senior Partner", "Name Partner"},
        {"Partner", "Equity Partner", "Full Partner"},
        {"Chairman", "Chairwoman", "Chairperson", "Chair", "Board Chair"},
    ]

    def __init__(self):
        # Build lookup maps
        self._canonical_map: Dict[str, str] = {}
        self._equivalents_map: Dict[str, Set[str]] = {}

        for equiv_set in self.SEMANTIC_EQUIVALENTS:
            # First item is canonical
            canonical = list(equiv_set)[0]
            for variant in equiv_set:
                self._canonical_map[variant.lower()] = canonical
                self._equivalents_map[variant.lower()] = equiv_set

        # Add abbreviation mappings
        for abbrev, full in ROLE_ABBREVIATIONS.items():
            self._canonical_map[abbrev.lower()] = full
            self._canonical_map[full.lower()] = full

    def normalize(self, role: str) -> str:
        """Normalize a role to its canonical form."""
        role_lower = role.lower().strip()
        return self._canonical_map.get(role_lower, role)

    def are_equivalent(self, role1: str, role2: str) -> bool:
        """Check if two roles are semantically equivalent."""
        r1_lower = role1.lower().strip()
        r2_lower = role2.lower().strip()

        # Same after normalization
        if self.normalize(role1).lower() == self.normalize(role2).lower():
            return True

        # In same equivalence class
        equiv1 = self._equivalents_map.get(r1_lower, set())
        equiv2 = self._equivalents_map.get(r2_lower, set())

        if equiv1 and equiv2:
            return bool(equiv1.intersection(equiv2))

        # Substring match for partial matches
        if r1_lower in r2_lower or r2_lower in r1_lower:
            return True

        return False

    def expand_query(self, role: str) -> List[str]:
        """Expand a role query to include all equivalent forms."""
        role_lower = role.lower().strip()

        equivalents = self._equivalents_map.get(role_lower, set())
        if equivalents:
            return list(equivalents)

        # Check abbreviations
        if role.upper() in ROLE_ABBREVIATIONS:
            full = ROLE_ABBREVIATIONS[role.upper()]
            return [role, full]

        if role in ROLE_FULL_NAMES:
            abbrev = ROLE_FULL_NAMES[role]
            return [role, abbrev]

        return [role]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def get_post_processor() -> ExtractionPostProcessor:
    """Get a configured post-processor instance."""
    return ExtractionPostProcessor()


def get_role_normalizer() -> RoleNormalizer:
    """Get a configured role normalizer instance."""
    return RoleNormalizer()
