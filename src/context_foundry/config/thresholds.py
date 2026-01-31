"""
Shared configuration for thresholds and constants.
Single source of truth for values used in both implementation and tests.
"""

SUFFICIENCY_THRESHOLDS = {
    "STALE_DATA_THRESHOLD": 0.3,
    "HIGH_CONFIDENCE_THRESHOLD": 0.8,
    "LOW_CONFIDENCE_THRESHOLD": 0.3,
    "FRESHNESS_HIGH": 0.8,
    "FRESHNESS_LOW": 0.3,
}

LEARNING_TICKET_CONFIG = {
    "PRIORITY_CAP": 1.0,
    "HIT_COUNT_MULTIPLIER": 0.2,
    "BASE_SEVERITY": {
        "missing_entity": 0.8,
        "sparse_relationships": 0.6,
        "stale_data": 0.5,
        "conflicting_sources": 0.7,
    },
}

ENTITY_RESOLUTION_CONFIG = {
    "SIMILARITY_THRESHOLD": 0.85,
    "EXACT_MATCH_THRESHOLD": 0.80,
    "FUZZY_MATCH_THRESHOLD": 0.70,
}

CONFIDENCE_WEIGHTS = {
    "COVERAGE_WEIGHT": 0.35,
    "FRESHNESS_WEIGHT": 0.25,
    "SOURCE_AGREEMENT_WEIGHT": 0.20,
    "RELATIONSHIP_DENSITY_WEIGHT": 0.20,
}
