"""
Authority configuration loader for source hierarchy and folder weighting.

Loads config/authority_map.json and provides utilities for:
- Getting folder priority weights
- Determining authoritative sources for fact types
- Per-corpus overrides
"""
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "config" / "authority_map.json"
_cached_config: Optional[Dict] = None


def load_authority_config() -> Dict:
    """Load authority configuration from JSON file."""
    global _cached_config
    
    if _cached_config is not None:
        return _cached_config
    
    if not _CONFIG_PATH.exists():
        logger.warning(f"[AUTHORITY] Config file not found: {_CONFIG_PATH}, using defaults")
        _cached_config = _get_default_config()
        return _cached_config
    
    try:
        with open(_CONFIG_PATH) as f:
            _cached_config = json.load(f)
        logger.info(f"[AUTHORITY] Loaded authority config from {_CONFIG_PATH}")
        return _cached_config
    except Exception as e:
        logger.error(f"[AUTHORITY] Failed to load config: {e}, using defaults")
        _cached_config = _get_default_config()
        return _cached_config


def _get_default_config() -> Dict:
    """Return default authority configuration."""
    return {
        "default_folder_priority": {
            "strategy": 1.0,
            "finances": 0.95,
            "operations": 0.90,
            "engineering": 0.85,
            "projects": 0.85,
            "legal": 0.80,
            "compliance": 0.80,
            "customers": 0.75,
            "policies": 0.75,
            "meeting_notes": 0.60
        },
        "fact_type_authorities": {},
        "corpus_overrides": {}
    }


def get_folder_priority(folder_name: str, corpus_name: Optional[str] = None) -> float:
    """Get priority weight for a folder.
    
    Args:
        folder_name: Name of the folder (e.g., 'strategy', 'finances')
        corpus_name: Optional corpus name for per-corpus overrides
        
    Returns:
        Priority weight between 0.0 and 1.0
    """
    config = load_authority_config()
    priorities = config.get("default_folder_priority", {})
    
    if corpus_name and corpus_name in config.get("corpus_overrides", {}):
        corpus_config = config["corpus_overrides"][corpus_name]
        if "folder_priority" in corpus_config:
            priorities = {**priorities, **corpus_config["folder_priority"]}
    
    folder_lower = folder_name.lower()
    return priorities.get(folder_lower, 0.70)


def get_authoritative_folders(fact_type: str) -> Tuple[List[str], List[str]]:
    """Get primary and secondary authoritative folders for a fact type.
    
    Args:
        fact_type: Type of fact (e.g., 'program_ownership', 'budget_financial')
        
    Returns:
        Tuple of (primary_folders, secondary_folders)
    """
    config = load_authority_config()
    authorities = config.get("fact_type_authorities", {})
    
    if fact_type not in authorities:
        return [], []
    
    fact_config = authorities[fact_type]
    return (
        fact_config.get("primary_folders", []),
        fact_config.get("secondary_folders", [])
    )


def get_authoritative_doc_patterns(fact_type: str) -> List[str]:
    """Get document name patterns that are authoritative for a fact type.
    
    Args:
        fact_type: Type of fact
        
    Returns:
        List of document name patterns (substrings to match)
    """
    config = load_authority_config()
    authorities = config.get("fact_type_authorities", {})
    
    if fact_type not in authorities:
        return []
    
    return authorities[fact_type].get("doc_patterns", [])


def is_authoritative_source(doc_path: str, fact_type: str) -> bool:
    """Check if a document is an authoritative source for a fact type.
    
    Args:
        doc_path: Document path/name
        fact_type: Type of fact
        
    Returns:
        True if the document is in a primary or secondary folder, or matches patterns
    """
    primary, secondary = get_authoritative_folders(fact_type)
    patterns = get_authoritative_doc_patterns(fact_type)
    
    doc_lower = doc_path.lower()
    
    for folder in primary + secondary:
        if f"/{folder}/" in doc_lower or doc_lower.startswith(f"{folder}/"):
            return True
    
    for pattern in patterns:
        if pattern.lower() in doc_lower:
            return True
    
    return False


def detect_fact_type(query: str) -> Optional[str]:
    """Attempt to detect fact type from query text.
    
    Args:
        query: The search query
        
    Returns:
        Detected fact type or None
    """
    query_lower = query.lower()
    
    patterns = {
        'program_ownership': ['who owns', 'program owner', 'initiative owner', 'responsible for program'],
        'budget_financial': ['budget', 'cost', 'revenue', 'financial', 'spend', 'investment', 'roi'],
        'executive_roles': ['ceo', 'cfo', 'cto', 'coo', 'executive', 'leadership', 'who is the'],
        'project_timeline': ['timeline', 'deadline', 'milestone', 'schedule', 'when will', 'target date'],
        'compliance_regulatory': ['compliance', 'regulatory', 'audit', 'certification', 'standard'],
        'customer_contracts': ['customer', 'client', 'contract', 'sla', 'agreement'],
        'technical_specs': ['specification', 'architecture', 'design', 'technical', 'engineering'],
        'supplier_vendor': ['supplier', 'vendor', 'procurement', 'sourcing', 'partner']
    }
    
    for fact_type, keywords in patterns.items():
        for keyword in keywords:
            if keyword in query_lower:
                return fact_type
    
    return None


def get_canonical_terms(corpus_name: Optional[str] = None) -> Dict[str, List[str]]:
    """Get canonical terms for keyword boosting.
    
    Args:
        corpus_name: Optional corpus name for per-corpus overrides
        
    Returns:
        Dict with keys like 'project_names', 'business_units', 'executives'
    """
    config = load_authority_config()
    terms = config.get("canonical_terms", {})
    
    if corpus_name and corpus_name in config.get("corpus_overrides", {}):
        corpus_config = config["corpus_overrides"][corpus_name]
        if "canonical_terms" in corpus_config:
            corpus_terms = corpus_config["canonical_terms"]
            for key, values in corpus_terms.items():
                if key in terms:
                    terms[key] = list(set(terms[key] + values))
                else:
                    terms[key] = values
    
    return {k: v for k, v in terms.items() if not k.startswith('_')}


def reload_config():
    """Force reload of configuration (useful for testing)."""
    global _cached_config
    _cached_config = None
    load_authority_config()
