"""
Domain Classifier - Semantic routing for automatic domain detection.

Uses embedding similarity to classify documents into domains without LLM calls.
Combines Core Foundation types with domain-specific types for comprehensive extraction.
"""
import os
import json
import numpy as np
from typing import Tuple, List, Dict, Optional
from pathlib import Path

from openai import OpenAI

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
DOMAIN_CONFIDENCE_THRESHOLD = 0.50

EMBEDDINGS_CACHE_PATH = Path(__file__).parent / "domain_embeddings.json"

DOMAIN_DESCRIPTIONS = {
    'core': 'Foundation ontology and shared taxonomy: entity-relationship dictionary, glossary of canonical types, definitions of person, organization, document, event, location, concept, process, date, schema reference, ontology specification, type hierarchy, abstract foundational classes, cross-cutting governance vocabulary. Domain-agnostic dictionary content, not vertical operational data.',
    'it_infrastructure': 'Servers, databases, deployments, incidents, APIs, microservices, cloud infrastructure, Kubernetes, Docker, DevOps, monitoring, alerts, outages, services, components, teams, on-call',
    'healthcare': 'Patients, diagnoses, treatments, medications, procedures, clinical trials, hospitals, doctors, nurses, medical records, prescriptions, symptoms, diseases, healthcare providers, clinics',
    'finance': 'Bonds, equities, transactions, accounts, portfolios, financial instruments, investments, trading, stocks, funds, securities, banks, loans, credit, interest rates, dividends',
    'aviation': 'Flights, aircraft, airports, crew, routes, maintenance, safety, pilots, passengers, runways, terminals, airlines, aviation, takeoff, landing, FAA, cargo',
    'supply_chain': 'Suppliers, shipments, warehouses, inventory, logistics, procurement, orders, delivery, tracking, freight, containers, distribution, vendors, purchase orders',
    'manufacturing': 'Products, machines, factories, quality control, production, assembly, batch, manufacturing plants, equipment, maintenance, defects, specifications, raw materials',
    'construction': 'Projects, sites, contractors, materials, permits, safety incidents, buildings, blueprints, inspections, subcontractors, milestones, budgets, engineering',
}

CORE_FOUNDATION_TYPES = [
    'PERSON', 'ORGANIZATION', 'DOCUMENT', 'LOCATION', 
    'EVENT', 'CONCEPT', 'PROCESS', 'DATE'
]

DOMAIN_TYPES = {
    'core': CORE_FOUNDATION_TYPES,
    'it_infrastructure': ['SERVICE', 'INCIDENT', 'DATABASE', 'COMPONENT', 'TEAM'],
    'healthcare': ['Patient', 'Diagnosis', 'Procedure', 'Medication', 'Hospital', 'HealthcareProvider'],
    'finance': ['Bond', 'Equity', 'FinancialAccount', 'SecuritiesTrade', 'Fund', 'Portfolio'],
    'aviation': ['Flight', 'Aircraft', 'Airport', 'Pilot', 'CrewMember', 'Route'],
    'supply_chain': ['Supplier', 'Shipment', 'Warehouse', 'Inventory', 'Container', 'Carrier'],
    'manufacturing': ['ProductionLine', 'ProductBatch', 'ManufacturingPlant', 'Equipment', 'QualityInspection'],
    'construction': ['ConstructionProject', 'ConstructionSite', 'Contractor', 'ConstructionMaterial', 'Permit'],
}

_openai_client: Optional[OpenAI] = None
_domain_embeddings: Optional[Dict[str, List[float]]] = None


def get_openai_client() -> OpenAI:
    """Get or create OpenAI client."""
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


def get_embedding(text: str) -> List[float]:
    """Generate embedding for text."""
    if not text or not text.strip():
        return [0.0] * EMBEDDING_DIM
    
    truncated = text[:8000]
    
    try:
        client = get_openai_client()
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=truncated,
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"[Classifier] Embedding error: {e}")
        return [0.0] * EMBEDDING_DIM


def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    
    norm_a = np.linalg.norm(a_arr)
    norm_b = np.linalg.norm(b_arr)
    
    if norm_a == 0 or norm_b == 0:
        return 0.0
    
    return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))


def generate_domain_embeddings() -> Dict[str, List[float]]:
    """Generate embeddings for all domain descriptions."""
    print("[Classifier] Generating domain embeddings...")
    embeddings = {}
    
    for domain, description in DOMAIN_DESCRIPTIONS.items():
        embeddings[domain] = get_embedding(description)
        print(f"[Classifier] Generated embedding for: {domain}")
    
    return embeddings


def save_domain_embeddings(embeddings: Dict[str, List[float]]):
    """Save domain embeddings to cache file."""
    with open(EMBEDDINGS_CACHE_PATH, 'w') as f:
        json.dump(embeddings, f)
    print(f"[Classifier] Saved embeddings to {EMBEDDINGS_CACHE_PATH}")


def load_domain_embeddings() -> Optional[Dict[str, List[float]]]:
    """Load domain embeddings from cache file."""
    if not EMBEDDINGS_CACHE_PATH.exists():
        return None
    
    try:
        with open(EMBEDDINGS_CACHE_PATH, 'r') as f:
            embeddings = json.load(f)
        print(f"[Classifier] Loaded cached embeddings from {EMBEDDINGS_CACHE_PATH}")
        return embeddings
    except Exception as e:
        print(f"[Classifier] Failed to load cached embeddings: {e}")
        return None


def get_domain_embeddings() -> Dict[str, List[float]]:
    """Get domain embeddings (from cache or generate new)."""
    global _domain_embeddings
    
    if _domain_embeddings is not None:
        return _domain_embeddings
    
    _domain_embeddings = load_domain_embeddings()
    
    if _domain_embeddings is None:
        _domain_embeddings = generate_domain_embeddings()
        save_domain_embeddings(_domain_embeddings)
    
    return _domain_embeddings


def classify_document(text: str, threshold: float = DOMAIN_CONFIDENCE_THRESHOLD) -> Tuple[str, float]:
    """
    Classify document into a domain using semantic routing.
    
    Args:
        text: Document text to classify
        threshold: Minimum similarity score to assign a domain (default 0.75)
    
    Returns:
        Tuple of (domain_name, confidence_score).

        `core` is emitted ONLY when its embedding is the closest match to the
        document (i.e., explicitly classified as foundation/cross-domain), per
        Piece 0 / ADR-002. It is NOT used as a below-threshold or
        embedding-failure fallback. In those degenerate cases we return the
        best-scoring domain (or `'unknown'` if no embedding could be produced)
        with the actual low score so the caller can decide.
    """
    sample = text[:2000]
    
    doc_embedding = get_embedding(sample)
    
    if all(v == 0.0 for v in doc_embedding):
        print("[Classifier] Failed to generate document embedding (API failure); returning 'unknown'")
        return 'unknown', 0.0
    
    domain_embeddings = get_domain_embeddings()
    
    scores = {}
    for domain, domain_embedding in domain_embeddings.items():
        scores[domain] = cosine_similarity(doc_embedding, domain_embedding)
    
    best_domain = max(scores, key=scores.get)
    best_score = scores[best_domain]
    
    all_scores_str = ", ".join([f"{d}:{s:.3f}" for d, s in sorted(scores.items(), key=lambda x: -x[1])])
    print(f"[Classifier] Scores: {all_scores_str}")
    
    if best_score >= threshold:
        print(f"[Classifier] Document classified as: {best_domain} (confidence: {best_score:.3f})")
        return best_domain, best_score
    else:
        print(f"[Classifier] Below threshold {threshold}, returning best-match {best_domain} ({best_score:.3f}) with low confidence")
        return best_domain, best_score


def score_domains(text: str) -> Tuple[str, float, Dict[str, float]]:
    """Score `text` against all domain embeddings.

    Returns (best_domain, best_score, all_scores). This is an additive
    helper introduced for the Piece 1 classification wrapper so it can build
    classification_evidence with the full per-domain score breakdown. It
    does NOT change the behavior of classify_document() — that function
    still returns (best_domain, best_score) and is unchanged.

    Returns ('unknown', 0.0, {}) if the embedding API fails.
    """
    sample = text[:2000]
    doc_embedding = get_embedding(sample)
    if all(v == 0.0 for v in doc_embedding):
        return 'unknown', 0.0, {}
    domain_embeddings = get_domain_embeddings()
    scores: Dict[str, float] = {
        d: cosine_similarity(doc_embedding, e) for d, e in domain_embeddings.items()
    }
    best = max(scores, key=scores.get)
    return best, scores[best], scores


def get_entity_types_for_domain(domain: str) -> List[str]:
    """
    Get combined entity types for extraction.
    
    Always includes Core Foundation types.
    Adds domain-specific types if a domain is specified.
    
    Args:
        domain: Domain name or 'core' for foundation only
    
    Returns:
        List of entity type names for extraction
    """
    entity_types = CORE_FOUNDATION_TYPES.copy()
    
    if domain != 'core' and domain in DOMAIN_TYPES:
        entity_types.extend(DOMAIN_TYPES[domain])
    
    entity_types = entity_types[:25]
    
    return entity_types


def classify_and_get_types(text: str) -> Tuple[str, float, List[str]]:
    """
    Convenience function: classify document and get entity types in one call.
    
    Args:
        text: Document text
    
    Returns:
        Tuple of (domain, confidence, entity_types)
    """
    domain, confidence = classify_document(text)
    entity_types = get_entity_types_for_domain(domain)
    
    print(f"[Classifier] Using {len(entity_types)} entity types: {entity_types}")
    
    return domain, confidence, entity_types


if __name__ == "__main__":
    print("Initializing domain embeddings...")
    embeddings = get_domain_embeddings()
    print(f"Loaded {len(embeddings)} domain embeddings")
    
    test_texts = [
        "The Kubernetes cluster is experiencing high CPU usage. The Auth Service deployed on pod-auth-001 is timing out. On-call engineer John Smith was paged.",
        "Patient John Doe presented with chest pain. Dr. Smith ordered an ECG and blood tests. Diagnosis: acute myocardial infarction.",
        "Q3 earnings report shows 15% growth. The equity portfolio outperformed benchmarks. Bond yields remain stable at 4.2%.",
        "The Boeing 737 departed from JFK terminal 4 at 0800. Captain Williams completed the pre-flight checklist. ETA at LAX is 1145.",
    ]
    
    for text in test_texts:
        domain, confidence, types = classify_and_get_types(text)
        print(f"  -> Domain: {domain}, Confidence: {confidence:.3f}, Types: {len(types)}")
        print()
