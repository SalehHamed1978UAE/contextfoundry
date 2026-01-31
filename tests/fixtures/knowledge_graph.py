"""
Canonical Test Fixtures for Knowledge Graph Tests.

This module provides consistent, well-documented test data for:
- Entity resolution tests
- Relationship traversal tests
- Impact/blast radius analysis tests
- RLM memory parity tests

The test graph represents a typical IT service architecture:

    ┌─────────────────┐
    │   API Gateway   │
    │   (SERVICE)     │
    └────────┬────────┘
             │ DEPENDS_ON
             ▼
    ┌─────────────────┐       ┌─────────────────┐
    │ Payment Service │──────▶│  Auth Database  │
    │   (SERVICE)     │USES   │   (DATABASE)    │
    └────────┬────────┘       └─────────────────┘
             │ DEPENDS_ON            ▲
             ▼                       │ USES
    ┌─────────────────┐              │
    │ Order Service   │──────────────┘
    │   (SERVICE)     │
    └────────┬────────┘
             │ DEPENDS_ON
             ▼
    ┌─────────────────┐       ┌─────────────────┐
    │ Redis Cache     │       │   SRE Team      │
    │   (CACHE)       │       │   (TEAM)        │
    └─────────────────┘       └─────────────────┘
             ▲                       │
             │ OWNS                  │ OWNS
             └───────────────────────┘

Impact analysis: If "Auth Database" fails:
- Payment Service is affected (uses Auth Database)
- Order Service is affected (uses Auth Database)
- API Gateway is affected (depends on Payment Service)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from uuid import uuid4


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid4())


@dataclass
class TestEntity:
    """Test entity fixture."""
    id: str
    name: str
    entity_type: str
    description: str = ""
    confidence: float = 0.9
    lifecycle_state: str = "TRUSTED"
    tenant_id: str = "test-tenant-001"
    properties: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "confidence": self.confidence,
            "lifecycle_state": self.lifecycle_state,
            "tenant_id": self.tenant_id,
            "properties": self.properties,
        }


@dataclass
class TestRelationship:
    """Test relationship fixture."""
    id: str
    source_id: str
    source_name: str
    target_id: str
    target_name: str
    relationship_type: str
    confidence: float = 0.9
    lifecycle_state: str = "TRUSTED"
    tenant_id: str = "test-tenant-001"
    properties: Dict[str, Any] = field(default_factory=dict)
    source_document_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "source_entity_id": self.source_id,
            "source_entity_name": self.source_name,
            "target_entity_id": self.target_id,
            "target_entity_name": self.target_name,
            "relationship_type": self.relationship_type,
            "confidence": self.confidence,
            "lifecycle_state": self.lifecycle_state,
            "tenant_id": self.tenant_id,
            "properties": self.properties,
        }


TEST_TENANT_ID = "12345678-1234-1234-1234-123456789abc"

API_GATEWAY_ID = "ent-api-gateway-001"
PAYMENT_SERVICE_ID = "ent-payment-svc-001"
ORDER_SERVICE_ID = "ent-order-svc-001"
AUTH_DATABASE_ID = "ent-auth-db-001"
REDIS_CACHE_ID = "ent-redis-cache-001"
SRE_TEAM_ID = "ent-sre-team-001"

REL_GATEWAY_PAYMENT_ID = "rel-gw-pay-001"
REL_PAYMENT_ORDER_ID = "rel-pay-ord-001"
REL_PAYMENT_AUTH_ID = "rel-pay-auth-001"
REL_ORDER_AUTH_ID = "rel-ord-auth-001"
REL_ORDER_REDIS_ID = "rel-ord-redis-001"
REL_SRE_REDIS_ID = "rel-sre-redis-001"


CANONICAL_ENTITIES = [
    TestEntity(
        id=API_GATEWAY_ID,
        name="API Gateway",
        entity_type="SERVICE",
        description="Main entry point for all API requests",
        confidence=0.95,
        tenant_id=TEST_TENANT_ID,
    ),
    TestEntity(
        id=PAYMENT_SERVICE_ID,
        name="Payment Service",
        entity_type="SERVICE",
        description="Handles payment processing and transactions",
        confidence=0.95,
        tenant_id=TEST_TENANT_ID,
    ),
    TestEntity(
        id=ORDER_SERVICE_ID,
        name="Order Service",
        entity_type="SERVICE",
        description="Manages order lifecycle and fulfillment",
        confidence=0.92,
        tenant_id=TEST_TENANT_ID,
    ),
    TestEntity(
        id=AUTH_DATABASE_ID,
        name="Auth Database",
        entity_type="DATABASE",
        description="PostgreSQL database for authentication data",
        confidence=0.98,
        tenant_id=TEST_TENANT_ID,
    ),
    TestEntity(
        id=REDIS_CACHE_ID,
        name="Redis Cache",
        entity_type="CACHE",
        description="In-memory cache for session data",
        confidence=0.90,
        tenant_id=TEST_TENANT_ID,
    ),
    TestEntity(
        id=SRE_TEAM_ID,
        name="SRE Team",
        entity_type="TEAM",
        description="Site Reliability Engineering team",
        confidence=0.85,
        tenant_id=TEST_TENANT_ID,
    ),
]

CANONICAL_RELATIONSHIPS = [
    TestRelationship(
        id=REL_GATEWAY_PAYMENT_ID,
        source_id=API_GATEWAY_ID,
        source_name="API Gateway",
        target_id=PAYMENT_SERVICE_ID,
        target_name="Payment Service",
        relationship_type="DEPENDS_ON",
        confidence=0.95,
        tenant_id=TEST_TENANT_ID,
    ),
    TestRelationship(
        id=REL_PAYMENT_ORDER_ID,
        source_id=PAYMENT_SERVICE_ID,
        source_name="Payment Service",
        target_id=ORDER_SERVICE_ID,
        target_name="Order Service",
        relationship_type="DEPENDS_ON",
        confidence=0.92,
        tenant_id=TEST_TENANT_ID,
    ),
    TestRelationship(
        id=REL_PAYMENT_AUTH_ID,
        source_id=PAYMENT_SERVICE_ID,
        source_name="Payment Service",
        target_id=AUTH_DATABASE_ID,
        target_name="Auth Database",
        relationship_type="USES",
        confidence=0.98,
        tenant_id=TEST_TENANT_ID,
    ),
    TestRelationship(
        id=REL_ORDER_AUTH_ID,
        source_id=ORDER_SERVICE_ID,
        source_name="Order Service",
        target_id=AUTH_DATABASE_ID,
        target_name="Auth Database",
        relationship_type="USES",
        confidence=0.96,
        tenant_id=TEST_TENANT_ID,
    ),
    TestRelationship(
        id=REL_ORDER_REDIS_ID,
        source_id=ORDER_SERVICE_ID,
        source_name="Order Service",
        target_id=REDIS_CACHE_ID,
        target_name="Redis Cache",
        relationship_type="DEPENDS_ON",
        confidence=0.88,
        tenant_id=TEST_TENANT_ID,
    ),
    TestRelationship(
        id=REL_SRE_REDIS_ID,
        source_id=SRE_TEAM_ID,
        source_name="SRE Team",
        target_id=REDIS_CACHE_ID,
        target_name="Redis Cache",
        relationship_type="OWNS",
        confidence=0.90,
        tenant_id=TEST_TENANT_ID,
    ),
]


STAGING_ENTITY = TestEntity(
    id="ent-staging-001",
    name="Staging Service",
    entity_type="SERVICE",
    description="A service in staging state (not yet trusted)",
    confidence=0.6,
    lifecycle_state="STAGING",
    tenant_id=TEST_TENANT_ID,
)

STAGING_RELATIONSHIP = TestRelationship(
    id="rel-staging-001",
    source_id="ent-staging-001",
    source_name="Staging Service",
    target_id=PAYMENT_SERVICE_ID,
    target_name="Payment Service",
    relationship_type="DEPENDS_ON",
    confidence=0.6,
    lifecycle_state="STAGING",
    tenant_id=TEST_TENANT_ID,
)


def get_entity_by_id(entity_id: str) -> Optional[TestEntity]:
    """Get entity by ID from canonical fixtures."""
    for entity in CANONICAL_ENTITIES:
        if entity.id == entity_id:
            return entity
    if STAGING_ENTITY.id == entity_id:
        return STAGING_ENTITY
    return None


def get_entity_by_name(name: str) -> Optional[TestEntity]:
    """Get entity by name from canonical fixtures (case-insensitive)."""
    name_lower = name.lower()
    for entity in CANONICAL_ENTITIES:
        if entity.name.lower() == name_lower:
            return entity
    if STAGING_ENTITY.name.lower() == name_lower:
        return STAGING_ENTITY
    return None


def get_relationships_for_entity(
    entity_id: str,
    direction: str = "both",
    include_staging: bool = False
) -> List[TestRelationship]:
    """Get relationships for an entity from canonical fixtures."""
    results = []
    
    for rel in CANONICAL_RELATIONSHIPS:
        if direction in ["outgoing", "both"]:
            if rel.source_id == entity_id:
                results.append(rel)
        if direction in ["incoming", "both"]:
            if rel.target_id == entity_id:
                results.append(rel)
    
    if include_staging and STAGING_RELATIONSHIP.source_id == entity_id:
        results.append(STAGING_RELATIONSHIP)
    
    return results


def get_impact_chain(entity_name: str, max_depth: int = 3) -> Dict[str, Any]:
    """
    Get entities impacted if the given entity fails.
    
    For Auth Database failure:
    - Payment Service is affected (uses Auth Database)
    - Order Service is affected (uses Auth Database)
    - API Gateway is affected (depends on Payment Service transitively)
    """
    entity = get_entity_by_name(entity_name)
    if not entity:
        return {"entity": entity_name, "error": "Entity not found", "impacted": []}
    
    impacted = []
    visited = {entity.id}
    
    def traverse_incoming(eid: str, depth: int, path: List[str]):
        if depth > max_depth:
            return
        
        for rel in CANONICAL_RELATIONSHIPS:
            if rel.target_id == eid and rel.source_id not in visited:
                source = get_entity_by_id(rel.source_id)
                if source:
                    visited.add(source.id)
                    new_path = path + [source.name]
                    impacted.append({
                        "entity": source.to_dict(),
                        "relationship": rel.to_dict(),
                        "depth": depth,
                        "path": new_path,
                    })
                    traverse_incoming(source.id, depth + 1, new_path)
    
    traverse_incoming(entity.id, 1, [entity.name])
    
    return {
        "entity": entity.to_dict(),
        "impacted": impacted,
    }


def expected_auth_database_impact() -> List[str]:
    """
    Expected entities impacted by Auth Database failure.
    
    Direct: Payment Service, Order Service
    Transitive: API Gateway (via Payment Service)
    """
    return ["Payment Service", "Order Service", "API Gateway"]


def expected_payment_service_impact() -> List[str]:
    """
    Expected entities impacted by Payment Service failure.
    
    Direct: API Gateway
    """
    return ["API Gateway"]


def expected_redis_cache_impact() -> List[str]:
    """
    Expected entities impacted by Redis Cache failure.
    
    Direct: Order Service
    Transitive: Payment Service (via Order Service), API Gateway
    """
    return ["Order Service", "Payment Service", "API Gateway"]


ENTITY_NAMES_FOR_EXTRACTION_TESTS = [
    "Payment Service",
    "Order Service",
    "Auth Database",
    "API Gateway",
    "Redis Cache",
    "SRE Team",
]

RELATIONSHIP_TYPES_FOR_TESTS = [
    "DEPENDS_ON",
    "USES",
    "OWNS",
    "MANAGES",
    "REPORTS_TO",
]

QUERY_TEST_CASES = [
    {
        "query": "What was affected by Payment Service failure?",
        "expected_type": "impact",
        "expected_entity": "Payment Service",
        "expected_impacted": ["API Gateway"],
    },
    {
        "query": "What is the blast radius of Auth Database?",
        "expected_type": "impact",
        "expected_entity": "Auth Database",
        "expected_impacted": ["Payment Service", "Order Service", "API Gateway"],
    },
    {
        "query": "What does Order Service depend on?",
        "expected_type": "dependency",
        "expected_entity": "Order Service",
        "expected_dependencies": ["Auth Database", "Redis Cache"],
    },
    {
        "query": "Who owns Redis Cache?",
        "expected_type": "ownership",
        "expected_entity": "Redis Cache",
        "expected_owner": "SRE Team",
    },
]
