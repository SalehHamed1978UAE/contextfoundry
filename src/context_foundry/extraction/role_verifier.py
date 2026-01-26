"""
Role Verification Module for Entity Extraction.

Verifies that extracted roles are explicitly stated in source text,
returning confidence levels rather than pass/fail.
"""
import re
from dataclasses import dataclass
from typing import List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)

FORMAL_TITLES = {
    "ceo", "chief executive officer",
    "cfo", "chief financial officer", 
    "coo", "chief operating officer",
    "cto", "chief technology officer",
    "ciso", "chief information security officer",
    "cio", "chief information officer",
    "cmo", "chief marketing officer",
    "chief engineer", "chief scientist", "chief architect",
    "president", "division president", "vice president", "vp",
    "director", "managing director", "executive director",
    "general counsel", "general manager",
    "svp", "evp", "avp",
}

INFERRED_PATTERNS = {
    "lead", "manager", "head", "coordinator", "specialist",
    "engineer", "analyst", "developer", "architect",
}


@dataclass
class RoleVerificationResult:
    """Result of role verification with confidence levels."""
    person_name: str
    extracted_role: Optional[str]
    verification_confidence: float
    verification_status: str
    matched_pattern: Optional[str]
    evidence_span: Optional[str]
    issues: List[str]
    
    def to_dict(self):
        return {
            "person_name": self.person_name,
            "extracted_role": self.extracted_role,
            "verification_confidence": self.verification_confidence,
            "verification_status": self.verification_status,
            "matched_pattern": self.matched_pattern,
            "evidence_span": self.evidence_span,
            "issues": self.issues,
        }


def normalize_name(name: str) -> str:
    """Normalize a name for matching (lowercase, strip titles)."""
    name = name.lower().strip()
    prefixes = ["dr.", "dr", "mr.", "mr", "ms.", "ms", "mrs.", "mrs", "prof.", "prof"]
    for prefix in prefixes:
        if name.startswith(prefix + " "):
            name = name[len(prefix):].strip()
    return name


def is_formal_title(role: str) -> bool:
    """Check if a role is a formal title."""
    role_lower = role.lower().strip()
    for title in FORMAL_TITLES:
        if title in role_lower:
            return True
    return False


def is_inferred_role(role: str) -> bool:
    """Check if a role appears to be inferred rather than formal."""
    role_lower = role.lower().strip()
    for pattern in INFERRED_PATTERNS:
        if pattern in role_lower and not is_formal_title(role):
            return True
    return False


def verify_role_assignment(
    person_name: str,
    extracted_role: Optional[str],
    source_text: str,
) -> RoleVerificationResult:
    """
    Verify that an extracted role is explicitly stated in source text.
    
    Returns a RoleVerificationResult with confidence levels:
    - 1.0: Explicit pattern match found (e.g., "John Smith, CEO")
    - 0.9: Strong pattern match (e.g., "CEO John Smith announced")
    - 0.7: Weak pattern match (role and name in proximity)
    - 0.5: Role is inferred/non-formal
    - 0.3: Role found but no explicit association
    - 0.0: No evidence of role in text
    """
    issues = []
    
    if not extracted_role:
        return RoleVerificationResult(
            person_name=person_name,
            extracted_role=None,
            verification_confidence=1.0,
            verification_status="NO_ROLE_TO_VERIFY",
            matched_pattern=None,
            evidence_span=None,
            issues=[],
        )
    
    role = extracted_role.lower().strip()
    name = normalize_name(person_name)
    name_parts = name.split()
    last_name = name_parts[-1] if name_parts else name
    first_name = name_parts[0] if name_parts else name
    text_lower = source_text.lower()
    
    if not is_formal_title(extracted_role):
        issues.append(f"Role '{extracted_role}' is not a formal title")
    
    if is_inferred_role(extracted_role):
        issues.append(f"Role '{extracted_role}' appears to be inferred, not explicit")
    
    explicit_patterns = [
        (rf'{re.escape(name)}\s*,\s*{re.escape(role)}', 1.0, "NAME, ROLE"),
        (rf'{re.escape(name)}\s+(?:is|serves as|as)\s+(?:the\s+)?{re.escape(role)}', 1.0, "NAME is/serves as ROLE"),
        (rf'{re.escape(role)}\s*:\s*{re.escape(name)}', 1.0, "ROLE: NAME"),
        (rf'{re.escape(role)}\s+{re.escape(name)}', 0.9, "ROLE NAME"),
        (rf'{re.escape(name)}\s*\(\s*{re.escape(role)}\s*\)', 0.95, "NAME (ROLE)"),
        (rf'(?:the\s+)?{re.escape(role)}\s*,?\s*{re.escape(name)}', 0.9, "the ROLE NAME"),
    ]
    
    last_name_patterns = [
        (rf'{re.escape(last_name)}\s*,\s*{re.escape(role)}', 0.85, "LASTNAME, ROLE"),
        (rf'{re.escape(role)}\s+(?:dr\.?\s+)?{re.escape(last_name)}', 0.85, "ROLE LASTNAME"),
    ]
    
    all_patterns = explicit_patterns + last_name_patterns
    
    for pattern, confidence, pattern_name in all_patterns:
        match = re.search(pattern, text_lower)
        if match:
            start = max(0, match.start() - 20)
            end = min(len(source_text), match.end() + 20)
            evidence = source_text[start:end]
            
            if not is_formal_title(extracted_role):
                confidence *= 0.7
            
            return RoleVerificationResult(
                person_name=person_name,
                extracted_role=extracted_role,
                verification_confidence=confidence,
                verification_status="VERIFIED" if confidence >= 0.8 else "WEAK_MATCH",
                matched_pattern=pattern_name,
                evidence_span=evidence,
                issues=issues,
            )
    
    if role in text_lower and (name in text_lower or last_name in text_lower):
        role_pos = text_lower.find(role)
        name_pos = text_lower.find(name) if name in text_lower else text_lower.find(last_name)
        distance = abs(role_pos - name_pos)
        
        if distance < 100:
            confidence = 0.6 if distance < 50 else 0.4
            issues.append(f"Role and name found {distance} chars apart but no explicit pattern")
            
            start = min(role_pos, name_pos)
            end = max(role_pos + len(role), name_pos + len(name))
            evidence = source_text[max(0, start-10):min(len(source_text), end+10)]
            
            return RoleVerificationResult(
                person_name=person_name,
                extracted_role=extracted_role,
                verification_confidence=confidence,
                verification_status="PROXIMITY_ONLY",
                matched_pattern=None,
                evidence_span=evidence,
                issues=issues,
            )
    
    if role in text_lower:
        issues.append(f"Role '{extracted_role}' found in text but not associated with '{person_name}'")
        return RoleVerificationResult(
            person_name=person_name,
            extracted_role=extracted_role,
            verification_confidence=0.3,
            verification_status="ROLE_FOUND_NO_ASSOCIATION",
            matched_pattern=None,
            evidence_span=None,
            issues=issues,
        )
    
    issues.append(f"Role '{extracted_role}' not found in source text")
    return RoleVerificationResult(
        person_name=person_name,
        extracted_role=extracted_role,
        verification_confidence=0.0,
        verification_status="NOT_FOUND",
        matched_pattern=None,
        evidence_span=None,
        issues=issues,
    )


def verify_all_person_entities(
    entities: List[dict],
    source_text: str,
) -> List[RoleVerificationResult]:
    """Verify roles for all PERSON entities in a list."""
    results = []
    for entity in entities:
        if entity.get("entity_type") == "PERSON":
            name = entity.get("canonical_name", "")
            role = entity.get("properties", {}).get("role")
            result = verify_role_assignment(name, role, source_text)
            results.append(result)
    return results
