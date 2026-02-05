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

# Financial metric patterns - capture key financial values with optional period
FINANCIAL_METRIC_PATTERNS = [
    # FY2025 revenue was $1.2B
    (r'\b(?:FY\s?(\d{4})|fiscal year\s?(\d{4}))?\s*'
     r'(revenue|sales|income|profit|margin|backlog|budget|spend|cost|expense)\s*'
     r'(?:was|is|:|of|totaled|amounted to)?\s*\$?([0-9,]+(?:\.[0-9]+)?)\s*'
     r'(billion|million|bn|m)?\b',
     0.85),
]

# Agreement value patterns - capture agreement/contract values with counterparty
AGREEMENT_VALUE_PATTERNS = [
    # Shell hydrogen offtake agreement valued at $450M
    (r'\b([A-Z][A-Za-z0-9&.\-\s]{2,40}?)\s+'
     r'(?:agreement|contract|offtake|deal|partnership)\s+'
     r'(?:valued at|value of|worth|for|totaling)\s*\$?([0-9,]+(?:\.[0-9]+)?)\s*'
     r'(billion|million|bn|m)?\b',
     0.85),
]

INVESTMENT_PATTERNS = [
    (r'PORTFOLIO\s+COMPANY[:\s]+([A-Z][A-Za-z0-9&.-]*(?:[ \t]+[A-Z][A-Za-z0-9&.-]*)*)(?=\s*\n|\s*$)',
     "portfolio_header", 0.95),
    (r'([A-Z][A-Za-z0-9&.-]*(?:[ \t]+[A-Z][A-Za-z0-9&.-]*)*)\s+(?:has\s+)?invested\s+(?:\$[\d,.]+\s+)?in\s+([A-Z][A-Za-z0-9&.-]*(?:[ \t]+[A-Z][A-Za-z0-9&.-]*)*)',
     "invested_in", 0.92),
    (r'([A-Z][A-Za-z0-9&.-]*(?:[ \t]+[A-Z][A-Za-z0-9&.-]*)*)\s+is\s+(?:a\s+)?portfolio\s+company',
     "is_portfolio", 0.88),
    (r'([A-Z][A-Za-z0-9&.-]*(?:[ \t]+[A-Z][A-Za-z0-9&.-]*)*)\s+portfolio\s+includes?\s+([A-Z][A-Za-z0-9&.-]*(?:[ \t]+[A-Z][A-Za-z0-9&.-]*)*)',
     "portfolio_includes", 0.90),
]

PORTFOLIO_COMPANY_PATTERNS = [
    (r'^([A-Z][A-Za-z0-9&.-]*(?:\s+[A-Z][A-Za-z0-9&.-]*)*)\s*\(Cohort\s+\d+\)', 'PORTFOLIO_COMPANY', 0.95),
    (r'^([A-Z][A-Za-z0-9&.-]+)\s*\n\s*-\s*Sector:', 'PORTFOLIO_COMPANY', 0.92),
    (r'^\s*([A-Z][A-Za-z0-9&.-]+)\s*\n\s*-\s*Stage:', 'PORTFOLIO_COMPANY', 0.90),
]

# Supplier relationship patterns - Pattern captures: group(1)=supplier, group(2)=product/service, group(3)=recipient (if present)
SUPPLIER_PATTERNS = [
    # Active: "X supplies/provides Y to/for Z"
    (r"(\b[A-Z][a-zA-Z\s]{2,30}?)\s+(?:supplies?|provides?|delivers?|furnishes?)\s+(.+?)\s+(?:to|for)\s+([A-Z][a-zA-Z\s]+?)(?:\.|,|$)", "SUPPLIES_TO", 0.85),
    # Active without recipient: "X supplies/provides Y"
    (r"(\b[A-Z][a-zA-Z\s]{2,30}?)\s+(?:supplies?|provides?|delivers?)\s+([a-zA-Z\s]+?)(?:\.|,|$)", "SUPPLIES_TO", 0.80),
    # Passive: "Y supplied/provided by X"
    (r"([a-zA-Z\s]+?)\s+(?:supplied|provided|delivered|furnished)\s+by\s+(\b[A-Z][a-zA-Z\s]{2,30}?)(?:\.|,|$)", "SUPPLIES_TO", 0.80),
    # Role: "X as supplier/vendor of Y"
    (r"(\b[A-Z][a-zA-Z\s]{2,30}?)\s+as\s+(?:the\s+)?(?:primary\s+)?(?:supplier|vendor|provider)\s+(?:of|for)\s+(.+?)(?:\.|,|$)", "SUPPLIES_TO", 0.75),
    # Contract: "X contracted to supply Y"
    (r"(\b[A-Z][a-zA-Z\s]{2,30}?)\s+(?:contracted|engaged|selected)\s+to\s+(?:supply|provide|deliver)\s+(.+?)(?:\.|,|$)", "SUPPLIES_TO", 0.80),
]

SUPPLIER_BLOCKLIST = {'the', 'a', 'an', 'this', 'that', 'these', 'their', 'our', 'its'}

# Technical specification patterns - Pattern captures specifications from tables and text
# These are domain-agnostic patterns that work for any technical domain
SPEC_PATTERNS = [
    # Energy density: "400 Wh/kg", "1000 Wh/L"
    (r'(\d+(?:\.\d+)?)\s*(Wh/kg|Wh/L|kWh/kg|MWh/L)', 'ENERGY_DENSITY', 0.95),
    # Temperature ranges: "-30 to 60°C", "-40°C to 80°C"
    (r'(-?\d+)\s*(?:°C|degrees?(?:\s+C)?|C)?\s*(?:to|-)\s*(-?\d+)\s*(?:°C|degrees?(?:\s+C)?|C)', 'TEMPERATURE_RANGE', 0.90),
    # Production capacity: "425 kg/hr", "850 kg/hour", "10,200 kg/day"
    (r'(\d+(?:,\d{3})*(?:\.\d+)?)\s*(kg/hr|kg/hour|kg/day|kg/year|kg per hour|kg per day|MW|GW|GWh|MWh)', 'PRODUCTION_CAPACITY', 0.92),
    # Material composition: "Li₇La₃Zr₂O₁₂", "Li7La3Zr2O12", "LiNi₀.₈Mn₀.₁Co₀.₁O₂", "NMC811"
    # Handles both Unicode subscripts and regular numbers
    (r'(Li[₀-₉0-9a-zA-Z₀₁₂₃₄₅₆₇₈₉]+(?:[A-Z][a-z]?[₀-₉0-9]*)+O[₀-₉₁₂0-9]+(?:\s*\([^)]+\))?)', 'MATERIAL_COMPOSITION', 0.93),
    # Efficiency: "95%", "99.7% detection rate"
    (r'(\d+(?:\.\d+)?)\s*%\s*(efficiency|detection rate|availability|purity|uptime)', 'EFFICIENCY_SPEC', 0.88),
    # Cycle life: "1,500 cycles", "3,000 cycle life"
    (r'(\d+(?:,\d{3})*)\s*(?:cycles?|cycle life)', 'CYCLE_LIFE', 0.90),
    # Charge time: "15 min", "30 minutes charge", "Fast Charge (10-80%) | 15 min"
    (r'(?:fast\s+)?charge[^|]*\|?\s*(\d+)\s*(min|minutes|hours?|hr)', 'CHARGE_TIME', 0.88),
    # Conductivity: "≥1 mS/cm", "10⁻² S/cm"
    (r'([≥<>]?\s*\d+(?:\.\d+)?(?:⁻?\d*)?)\s*(mS/cm|S/cm|μS/cm)', 'CONDUCTIVITY', 0.92),
    # Thickness: "20-30 μm", "15 μm"
    (r'(\d+(?:-\d+)?)\s*(μm|nm|mm|microns?)', 'THICKNESS', 0.90),
    # Pressure: "30 bar", "138 kV"
    (r'(\d+(?:\.\d+)?)\s*(bar|kV|MPa|PSI|psi)', 'PRESSURE_SPEC', 0.88),
    # Table row with Phase distinction: "Phase 1 | 425 kg/hr | Full Capacity | 850 kg/hr"
    (r'\|\s*Phase\s+1\s*\|\s*([^|]+)\s*\|', 'PHASE_1_VALUE', 0.95),
]

# Context patterns for identifying what a spec relates to
SPEC_CONTEXT_PATTERNS = [
    # Energy density context
    (r'(Energy\s+Density)\s*\|?\s*(\d+)\s*(Wh/kg|Wh/L)', 'ENERGY_DENSITY'),
    # Operating temperature context
    (r'(Operating\s+Temp(?:erature)?)\s*\|?\s*(-?\d+\s*(?:to|-)\s*-?\d+\s*°?C)', 'OPERATING_TEMPERATURE'),
    # Hydrogen output context
    (r'(Hydrogen\s+Output)\s*\|?\s*(\d+(?:,\d{3})*\s*kg/hr)', 'HYDROGEN_OUTPUT'),
    # Electrolyte composition context
    (r'(Composition)\s*\|?\s*(Li[₀-₉a-zA-Z₀₁₂₃₄₅₆₇₈₉]+[^|]*(?:\([^)]+\))?)', 'ELECTROLYTE_COMPOSITION'),
]


def extract_technical_specifications(text: str) -> List[Dict]:
    """
    Standalone function to extract technical specifications from text using patterns.
    
    Returns a list of dicts with keys: spec_type, value, unit, context, confidence, source_text
    """
    results = []
    seen = set()
    
    for pattern, spec_type, confidence in SPEC_PATTERNS:
        try:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                groups = match.groups()
                value = groups[0].strip() if groups[0] else ""
                unit = groups[1].strip() if len(groups) > 1 and groups[1] else ""
                
                # Avoid duplicates
                key = (spec_type, value, unit)
                if key in seen:
                    continue
                seen.add(key)
                
                # Try to find context (what this spec is for)
                context = _find_spec_context(text, match.start(), match.end())
                
                result = {
                    "spec_type": spec_type,
                    "value": value,
                    "unit": unit,
                    "context": context,
                    "confidence": confidence,
                    "source_text": match.group(0)[:100]
                }
                results.append(result)
        except Exception as e:
            logger.warning(f"Spec pattern {spec_type} failed: {e}")
    
    return results


def _find_spec_context(text: str, start: int, end: int, window: int = 200) -> str:
    """Find context around a specification match to understand what it relates to."""
    # Look at text before the match
    context_start = max(0, start - window)
    context_text = text[context_start:start]
    
    # Look for table headers or labels
    # Pattern: "| Header |" or "Parameter: value"
    header_patterns = [
        r'\|\s*([A-Z][a-zA-Z\s]+?)\s*\|[^|]*$',  # Table header before value
        r'([A-Z][a-zA-Z\s]+?)\s*:\s*$',  # Label: value
        r'([A-Z][a-zA-Z\s]+?)\s*\|\s*$',  # Label | value
    ]
    
    for pattern in header_patterns:
        match = re.search(pattern, context_text)
        if match:
            return match.group(1).strip()
    
    # Look for row label in markdown table: "| Label | value |"
    row_pattern = r'\|\s*([A-Z][a-zA-Z\s/]+?)\s*\|[^|]*' + re.escape(text[start:end])
    row_match = re.search(row_pattern, text[max(0, start-100):end+50])
    if row_match:
        return row_match.group(1).strip()
    
    return ""


def extract_supplier_relationships(text: str) -> List[Dict]:
    """
    Standalone function to extract supplier relationships from text using patterns.
    
    Returns a list of dicts with keys: supplier, product, recipient (if present), 
    relationship_type, confidence, pattern_index
    """
    results = []
    seen = set()
    
    for idx, (pattern, rel_type, confidence) in enumerate(SUPPLIER_PATTERNS):
        try:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                groups = match.groups()
                
                if idx == 2:  # Passive voice pattern
                    product = groups[0].strip() if groups[0] else ""
                    supplier = groups[1].strip() if groups[1] else ""
                    recipient = None
                else:
                    supplier = groups[0].strip() if groups[0] else ""
                    product = groups[1].strip() if groups[1] else ""
                    recipient = groups[2].strip() if len(groups) > 2 and groups[2] else None
                
                supplier_lower = supplier.lower()
                if supplier_lower in SUPPLIER_BLOCKLIST:
                    continue
                if not supplier or len(supplier) < 2:
                    continue
                
                key = (supplier_lower, product.lower())
                if key in seen:
                    continue
                seen.add(key)
                
                result = {
                    "supplier": supplier,
                    "product": product,
                    "relationship_type": rel_type,
                    "confidence": confidence,
                    "pattern_index": idx,
                    "source_text": match.group(0)
                }
                if recipient:
                    result["recipient"] = recipient
                
                results.append(result)
        except Exception as e:
            logger.warning(f"Supplier pattern {idx} failed: {e}")
    
    return results


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

        portfolio_entities = self._extract_portfolio_companies(
            document_text, existing_entity_names
        )
        for pe in portfolio_entities:
            if pe['name'].lower() not in existing_entity_names:
                new_entities.append(pe)
                existing_entity_names.add(pe['name'].lower())
                patterns_matched += 1

        supplier_rels, supplier_entities = self._extract_supplier_relationships(
            document_text, existing_entity_names, existing_rel_keys
        )
        new_relationships.extend(supplier_rels)
        new_entities.extend(supplier_entities)
        patterns_matched += len(supplier_rels)

        # Financial metric and agreement extraction (org-linked)
        primary_org = self._get_primary_organization(existing_entities)
        fin_entities, fin_rels = self._extract_financial_metrics(
            document_text, existing_entity_names, existing_rel_keys, primary_org
        )
        new_entities.extend(fin_entities)
        new_relationships.extend(fin_rels)
        patterns_matched += len(fin_rels)

        # Extract technical specifications (energy density, temperature ranges, capacities, etc.)
        spec_entities = self._extract_specification_entities(
            document_text, existing_entity_names
        )
        for se in spec_entities:
            if se['name'].lower() not in existing_entity_names:
                new_entities.append(se)
                existing_entity_names.add(se['name'].lower())
                patterns_matched += 1

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

    def _get_primary_organization(self, entities: List[Dict]) -> Optional[str]:
        """Pick a primary organization name from existing entities."""
        for e in entities:
            entity_type = (e.get('entity_type') or '').upper()
            if entity_type in ('ORGANIZATION', 'COMPANY', 'BUSINESS_UNIT', 'DIVISION'):
                name = e.get('name') or e.get('canonical_name')
                if name:
                    return name
        return None

    def _extract_financial_metrics(
        self,
        document_text: str,
        existing_entity_names: Set[str],
        existing_rel_keys: Set[Tuple[str, str, str]],
        primary_org: Optional[str]
    ) -> Tuple[List[Dict], List[ExtractedRelationshipFromPattern]]:
        """
        Extract financial metric and agreement relationships.
        Creates FINANCIAL_METRIC / AGREEMENT entities and links them to the primary org.
        """
        if not primary_org:
            return [], []

        new_entities: List[Dict] = []
        new_relationships: List[ExtractedRelationshipFromPattern] = []

        # Financial metrics
        for pattern, confidence in FINANCIAL_METRIC_PATTERNS:
            for match in re.finditer(pattern, document_text, flags=re.IGNORECASE):
                fy1, fy2, metric_type, value, unit = match.groups()
                period = f"FY{fy1 or fy2}" if (fy1 or fy2) else "UNKNOWN"
                metric_type_norm = (metric_type or "metric").lower()
                unit_norm = (unit or "").lower()
                metric_name = f"{primary_org} {metric_type_norm} ({period})"
                canonical_name = f"{primary_org}_{metric_type_norm}_{period}".replace(" ", "_")

                if canonical_name.lower() not in existing_entity_names:
                    new_entities.append({
                        "name": metric_name,
                        "entity_type": "FINANCIAL_METRIC",
                        "confidence": confidence,
                        "attributes": {
                            "metric_type": metric_type_norm,
                            "value": value.replace(",", ""),
                            "unit": unit_norm,
                            "time_period": period,
                        }
                    })
                    existing_entity_names.add(canonical_name.lower())

                rel_type = {
                    "revenue": "HAS_REVENUE",
                    "sales": "HAS_REVENUE",
                    "budget": "HAS_BUDGET",
                    "spend": "HAS_COST",
                    "cost": "HAS_COST",
                    "expense": "HAS_COST",
                    "profit": "HAS_METRIC",
                    "margin": "HAS_METRIC",
                    "backlog": "HAS_METRIC",
                    "income": "HAS_METRIC",
                }.get(metric_type_norm, "HAS_METRIC")

                rel_key = (primary_org.lower(), rel_type, metric_name.lower())
                if rel_key not in existing_rel_keys:
                    new_relationships.append(ExtractedRelationshipFromPattern(
                        relationship_type=rel_type,
                        source_name=primary_org,
                        target_name=metric_name,
                        confidence=confidence,
                        pattern_name="financial_metric",
                        source_text=match.group(0),
                    ))
                    existing_rel_keys.add(rel_key)

        # Agreements with value
        for pattern, confidence in AGREEMENT_VALUE_PATTERNS:
            for match in re.finditer(pattern, document_text, flags=re.IGNORECASE):
                counterparty, value, unit = match.groups()
                counterparty = (counterparty or "Counterparty").strip()
                unit_norm = (unit or "").lower()
                agreement_name = f"{counterparty} Agreement"
                canonical_name = f"{primary_org}_{counterparty}_agreement".replace(" ", "_")

                if canonical_name.lower() not in existing_entity_names:
                    new_entities.append({
                        "name": agreement_name,
                        "entity_type": "AGREEMENT",
                        "confidence": confidence,
                        "attributes": {
                            "counterparty": counterparty,
                            "value": value.replace(",", ""),
                            "unit": unit_norm,
                        }
                    })
                    existing_entity_names.add(canonical_name.lower())

                rel_key = (primary_org.lower(), "HAS_AGREEMENT", agreement_name.lower())
                if rel_key not in existing_rel_keys:
                    new_relationships.append(ExtractedRelationshipFromPattern(
                        relationship_type="HAS_AGREEMENT",
                        source_name=primary_org,
                        target_name=agreement_name,
                        confidence=confidence,
                        pattern_name="agreement_value",
                        source_text=match.group(0),
                    ))
                    existing_rel_keys.add(rel_key)

        return new_entities, new_relationships

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
            r'^([A-Z][A-Za-z]+(?:Ventures|Capital|Partners|Fund|Investments))\b',
            r'^([A-Z][A-Z]+)(?:\s+PORTFOLIO)',
            r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)(?:\s+Portfolio)',
            r'Prepared\s+by[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.MULTILINE)
            if match:
                result = match.group(1).strip()
                if result and result.upper() not in {'PORTFOLIO', 'COMPANY', 'SUMMARY', 'REPORT'}:
                    return result
        return None

    def _extract_portfolio_companies(
        self, text: str, existing_entity_names: Set[str]
    ) -> List[Dict]:
        """
        Extract portfolio companies using patterns that catch cohort format.
        Catches "CLOUDAI (Cohort 8)", "CloudAI (Cohort 8)", or "COMPANYNAME\n- Sector:" patterns.
        Preserves original casing from the document.
        """
        entities = []
        seen = set()
        
        for pattern, entity_type, confidence in PORTFOLIO_COMPANY_PATTERNS:
            try:
                matches = re.finditer(pattern, text, re.MULTILINE)
                for match in matches:
                    name = match.group(1).strip()
                    if not name or len(name) < 3:
                        continue
                    name_key = name.lower()
                    if name_key in seen:
                        continue
                    if name_key in existing_entity_names:
                        continue
                    if name.upper() in {'THE', 'AND', 'FOR', 'PORTFOLIO', 'COMPANY', 'ACTIVE'}:
                        continue
                    seen.add(name_key)
                    entities.append({
                        'name': name,
                        'entity_type': entity_type,
                        'confidence': confidence,
                        'source': 'post_processor',
                        'source_text': match.group(0)[:100]
                    })
                    logger.info(f"[PostProcessor] Found portfolio company: {name}")
            except Exception as e:
                logger.warning(f"[PostProcessor] Portfolio company pattern failed: {e}")
        
        return entities

    def _extract_supplier_relationships(
        self, text: str, existing_entity_names: Set[str], existing_rel_keys: Set[Tuple[str, str, str]]
    ) -> Tuple[List[ExtractedRelationshipFromPattern], List[Dict]]:
        """Extract SUPPLIES_TO relationships from text."""
        relationships = []
        new_entities = []
        seen_pairs = set()
        
        for idx, (pattern, rel_type, confidence) in enumerate(SUPPLIER_PATTERNS):
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    groups = match.groups()
                    
                    if idx == 2:  # Passive voice pattern (Y supplied by X)
                        product = groups[0].strip() if groups[0] else ""
                        supplier = groups[1].strip() if groups[1] else ""
                        recipient = None
                    else:
                        supplier = groups[0].strip() if groups[0] else ""
                        product = groups[1].strip() if groups[1] else ""
                        recipient = groups[2].strip() if len(groups) > 2 and groups[2] else None
                    
                    supplier_lower = supplier.lower()
                    if supplier_lower in SUPPLIER_BLOCKLIST:
                        continue
                    if not supplier or len(supplier) < 2:
                        continue
                    if not product or len(product) < 2:
                        continue
                    
                    pair_key = (supplier_lower, product.lower())
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    
                    rel_key = (supplier_lower, product.lower(), "SUPPLIES_TO")
                    if rel_key in existing_rel_keys:
                        continue
                    
                    rel = ExtractedRelationshipFromPattern(
                        relationship_type="SUPPLIES_TO",
                        source_name=supplier,
                        target_name=product,
                        confidence=confidence,
                        pattern_name=f"supplier_pattern_{idx}",
                        source_text=match.group(0)
                    )
                    relationships.append(rel)
                    logger.info(f"[PostProcessor] Found supplier: {supplier} → {product}")
                    
                    if supplier_lower not in existing_entity_names:
                        new_entities.append({
                            "name": supplier, "entity_type": "ORGANIZATION",
                            "confidence": confidence, "source": "post_processor"
                        })
                        existing_entity_names.add(supplier_lower)
                    
                    product_lower = product.lower()
                    if product_lower not in existing_entity_names:
                        new_entities.append({
                            "name": product, "entity_type": "PRODUCT",
                            "confidence": confidence, "source": "post_processor"
                        })
                        existing_entity_names.add(product_lower)
                        
            except Exception as e:
                logger.warning(f"[PostProcessor] Supplier pattern {idx} failed: {e}")
        
        logger.info(f"[PostProcessor] SUPPLIES_TO matches found: {len(relationships)}")
        for rel in relationships:
            logger.info(f"  - {rel.source_name} SUPPLIES_TO {rel.target_name}")
        
        return relationships, new_entities

    def _extract_specification_entities(
        self, text: str, existing_entity_names: Set[str]
    ) -> List[Dict]:
        """
        Extract technical specifications as SPECIFICATION entities.
        Captures energy density, temperature ranges, capacities, material compositions, etc.
        """
        entities = []
        seen = set()
        
        for pattern, spec_type, confidence in SPEC_PATTERNS:
            try:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
                for match in matches:
                    groups = match.groups()
                    
                    if spec_type == 'TEMPERATURE_RANGE':
                        # Special handling for temperature ranges
                        temp_low = groups[0] if groups[0] else ""
                        temp_high = groups[1] if len(groups) > 1 and groups[1] else ""
                        value = f"{temp_low} to {temp_high}°C"
                        unit = "°C"
                        name = f"Operating Temperature {value}"
                    elif spec_type == 'MATERIAL_COMPOSITION':
                        # Material composition (e.g., Li₇La₃Zr₂O₁₂)
                        value = groups[0].strip() if groups[0] else ""
                        unit = ""
                        name = f"Material Composition {value}"
                    elif spec_type == 'PHASE_1_VALUE':
                        # Phase-specific value from table
                        value = groups[0].strip() if groups[0] else ""
                        unit = ""
                        name = f"Phase 1 {value}"
                    else:
                        # Standard pattern: value + unit
                        value = groups[0].strip() if groups[0] else ""
                        unit = groups[1].strip() if len(groups) > 1 and groups[1] else ""
                        name = f"{value} {unit}".strip()
                    
                    if not value or len(value) < 1:
                        continue
                    
                    # Find context to understand what this spec relates to
                    context = _find_spec_context(text, match.start(), match.end())
                    
                    # Create a unique key
                    key = (spec_type, value, unit, context)
                    if key in seen:
                        continue
                    seen.add(key)
                    
                    # Skip if already exists
                    name_lower = name.lower()
                    if name_lower in existing_entity_names:
                        continue
                    
                    # Build properties dict
                    properties = {
                        "spec_type": spec_type,
                        "value": value,
                        "source": "post_processor",
                    }
                    if unit:
                        properties["unit"] = unit
                    if context:
                        properties["context"] = context
                    
                    entity = {
                        "name": name,
                        "entity_type": "SPECIFICATION",
                        "confidence": confidence,
                        "source": "post_processor",
                        "properties": properties,
                        "source_text": match.group(0)[:100]
                    }
                    entities.append(entity)
                    
                    logger.info(f"[PostProcessor] Found spec: {spec_type} = {value} {unit} (context: {context})")
                    
            except Exception as e:
                logger.warning(f"[PostProcessor] Spec pattern {spec_type} failed: {e}")
        
        logger.info(f"[PostProcessor] SPECIFICATION entities found: {len(entities)}")
        return entities


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
