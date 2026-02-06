from __future__ import annotations

import re
from typing import List

STOPWORDS = {
    "who", "what", "when", "where", "why", "how", "is", "are", "the",
    "a", "an", "of", "for", "to", "in", "on", "and", "or", "with",
}

ROLE_TOKENS = {
    "ceo", "cfo", "cto", "coo", "ciso", "cio", "vp", "svp", "evp",
}

def extract_named_entities(query: str) -> List[str]:
    if not query:
        return []
    entities: List[str] = []

    # Quoted phrases
    entities.extend(re.findall(r'"([^"]+)"', query))
    entities.extend(re.findall(r"'([^']+)'", query))

    # Title-case sequences
    for match in re.findall(r"(?:[A-Z][a-zA-Z0-9-]+(?:\s+[A-Z][a-zA-Z0-9-]+){0,4})", query):
        lowered = match.lower()
        if lowered in STOPWORDS or lowered in ROLE_TOKENS:
            continue
        entities.append(match.strip())

    # Deduplicate
    seen = set()
    deduped = []
    for e in entities:
        key = e.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(e)

    return deduped


def build_fallback_queries(query: str) -> List[str]:
    entities = extract_named_entities(query)
    if not entities:
        return [query]

    # Require all entities when possible
    if len(entities) <= 2:
        return [" ".join(entities)]

    # Multi-entity: build pairwise queries with primary entity
    primary = entities[0]
    queries = [f"{primary} {e}" for e in entities[1:]]
    return queries
