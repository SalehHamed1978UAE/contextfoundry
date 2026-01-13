"""
Entity Hygiene for Context Foundry.

Provides validation and normalization functions to ensure clean entities
are stored in the knowledge graph.

Phase 2.7: Entity Hygiene - Filters garbage names and normalizes titles.
"""
import re
from typing import Optional, Set

INVALID_ENTITY_NAMES: Set[str] = {
    'CA', 'NY', 'TX', 'FL', 'WA', 'MA', 'IL', 'PA', 'OH', 'GA', 'NC', 'NJ',
    'VA', 'AZ', 'CO', 'TN', 'MI', 'MD', 'MN', 'WI', 'MO', 'OR', 'SC', 'IN',
    'AL', 'AK', 'AR', 'CT', 'DE', 'HI', 'ID', 'IA', 'KS', 'KY', 'LA', 'ME',
    'MS', 'MT', 'NE', 'NV', 'NH', 'NM', 'ND', 'OK', 'RI', 'SD', 'UT', 'VT',
    'WV', 'WY', 'DC',
    'N/A', 'TBD', 'NA', 'TBA', 'NULL', 'NONE', 'UNKNOWN', 'OTHER',
    'YES', 'NO', 'TRUE', 'FALSE',
    'USA', 'US', 'UK',
}

TITLE_PREFIXES = [
    'Dr.', 'Dr', 'Mr.', 'Mr', 'Mrs.', 'Mrs', 'Ms.', 'Ms', 
    'Prof.', 'Prof', 'Rev.', 'Rev', 'Hon.', 'Hon',
    'Sir', 'Dame', 'Lord', 'Lady',
]


def is_valid_entity_name(name: str) -> bool:
    """
    Check if an entity name is valid and not garbage.
    
    Filters out:
    - Empty or very short names (< 2 chars)
    - State abbreviations (CA, NY, etc.)
    - Common garbage tokens (N/A, TBD, etc.)
    - Pure numbers
    - Names with embedded newlines (malformed extraction)
    
    Args:
        name: Entity name to validate
        
    Returns:
        True if valid, False if garbage
    """
    if not name:
        return False
    
    name = name.strip()
    
    if len(name) < 2:
        return False
    
    if '\n' in name or '\r' in name:
        return False
    
    if name.upper() in INVALID_ENTITY_NAMES:
        return False
    
    if name.isdigit():
        return False
    
    if re.match(r'^[\d\W]+$', name):
        return False
    
    if re.match(r'^[A-Z]{1,2}$', name):
        return False
    
    return True


def normalize_name_for_matching(name: str) -> str:
    """
    Normalize an entity name for fuzzy matching and deduplication.
    
    - Strips whitespace
    - Removes common title prefixes (Dr., Mr., Mrs., etc.)
    - Preserves case for proper matching
    
    Args:
        name: Entity name to normalize
        
    Returns:
        Normalized name with prefixes stripped
    """
    if not name:
        return ""
    
    normalized = name.strip()
    
    for prefix in TITLE_PREFIXES:
        if normalized.startswith(prefix + ' '):
            normalized = normalized[len(prefix):].strip()
            break
        if normalized.startswith(prefix + '. '):
            normalized = normalized[len(prefix) + 1:].strip()
            break
    
    return normalized


def normalize_name_for_comparison(name: str) -> str:
    """
    Normalize name for strict comparison (lowercase, stripped, no prefix).
    
    Args:
        name: Entity name to normalize
        
    Returns:
        Lowercase normalized name for comparison
    """
    return normalize_name_for_matching(name).lower().strip()


def clean_entity_name(name: str) -> Optional[str]:
    """
    Clean and validate an entity name.
    
    Returns cleaned name if valid, None if garbage.
    
    IMPORTANT: Validates BEFORE whitespace normalization to catch newline garbage.
    
    Args:
        name: Raw entity name from extraction
        
    Returns:
        Cleaned name or None if invalid
    """
    if not name:
        return None
    
    raw_stripped = name.strip()
    
    if not is_valid_entity_name(raw_stripped):
        return None
    
    cleaned = ' '.join(raw_stripped.split())
    
    return cleaned


def should_merge_entities(name1: str, name2: str) -> bool:
    """
    Check if two entity names should be merged (are duplicates).
    
    Handles cases like:
    - "Dr. James Wilson" vs "James Wilson"
    - "James Wilson" vs "james wilson" (case insensitive)
    
    Args:
        name1: First entity name
        name2: Second entity name
        
    Returns:
        True if entities should be merged
    """
    norm1 = normalize_name_for_comparison(name1)
    norm2 = normalize_name_for_comparison(name2)
    
    if norm1 == norm2:
        return True
    
    if norm1 in norm2 or norm2 in norm1:
        if abs(len(norm1) - len(norm2)) <= 4:
            return True
    
    return False
