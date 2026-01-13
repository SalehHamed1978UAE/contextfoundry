# Context Foundry Stabilization — Replit Execution Guide

> **Timeline**: 5 weeks
> **Executor**: Replit (all work)
> **Goal**: A system where every change can be made with confidence
> **Rule**: No new features until stabilization is complete

---

# WEEK 1: Component Contracts + Test Fixtures

## Objective
Define clear interfaces for every component. Create canonical test data.

---

## Day 1-2: Query Understanding Contract

### Create: `src/context_foundry/contracts/query_parser.py`

```python
from dataclasses import dataclass
from typing import Literal, Optional, Dict, Any

@dataclass
class QueryIntent:
    """The parsed intent of a user query."""
    query_type: Literal[
        "lookup",        # "What is X?"
        "dependency",    # "What does X depend on?"
        "management",    # "Who manages X?"
        "impact",        # "What was affected by X?"
        "blast_radius",  # "If X fails, what's affected?"
        "traversal",     # "Trace path from X to Y"
        "aggregation",   # "List all X" / "How many X?"
    ]
    target_entity: Optional[str]  # Entity being asked about
    secondary_entity: Optional[str]  # For path queries
    relationship_type: Optional[str]  # DEPENDS_ON, MANAGES, etc.
    direction: Literal["outgoing", "incoming", "both"]
    entity_type_filter: Optional[str]  # Filter by SERVICE, TEAM, etc.
    raw_query: str  # Original query text


class QueryParserContract:
    """Contract for query parsing implementations."""
    
    def parse(self, query: str) -> QueryIntent:
        """
        Parse natural language query into structured intent.
        
        MUST:
        - Extract target entity name accurately
        - NOT treat query words as entity names
        - Identify relationship type from query semantics
        - Determine direction (who depends on X vs what does X depend on)
        
        Examples:
        - "What does Order Service depend on?"
          → QueryIntent(type="dependency", target="Order Service", direction="outgoing")
        
        - "What was affected by INC-001?"
          → QueryIntent(type="impact", target="INC-001", direction="outgoing")
          → NOT: target="What Was Affected By"
        
        - "Who manages Payment Gateway?"
          → QueryIntent(type="management", target="Payment Gateway", direction="incoming")
        """
        raise NotImplementedError
```

### Create: `tests/contracts/test_query_parser_contract.py`

```python
import pytest
from context_foundry.contracts.query_parser import QueryIntent

class TestQueryParserContract:
    """Contract tests for query parsing. Implementation must pass ALL tests."""
    
    # === DEPENDENCY QUERIES ===
    
    def test_dependency_outgoing(self, query_parser):
        """'What does X depend on?' → outgoing dependencies"""
        intent = query_parser.parse("What does Order Service depend on?")
        
        assert intent.query_type == "dependency"
        assert intent.target_entity == "Order Service"
        assert intent.direction == "outgoing"
        assert intent.relationship_type == "DEPENDS_ON"
    
    def test_dependency_incoming(self, query_parser):
        """'What depends on X?' → incoming dependencies"""
        intent = query_parser.parse("What depends on Payment Service?")
        
        assert intent.query_type == "dependency"
        assert intent.target_entity == "Payment Service"
        assert intent.direction == "incoming"
    
    def test_dependency_variation_1(self, query_parser):
        """Alternative phrasing: 'What are the dependencies of X?'"""
        intent = query_parser.parse("What are the dependencies of Auth Gateway?")
        
        assert intent.query_type == "dependency"
        assert intent.target_entity == "Auth Gateway"
    
    # === MANAGEMENT QUERIES ===
    
    def test_management_who_manages(self, query_parser):
        """'Who manages X?' → incoming MANAGES relationship"""
        intent = query_parser.parse("Who manages the Payment Gateway?")
        
        assert intent.query_type == "management"
        assert intent.target_entity == "Payment Gateway"
        assert intent.direction == "incoming"
        assert intent.relationship_type == "MANAGES"
    
    def test_management_what_manages(self, query_parser):
        """'What does team X manage?' → outgoing MANAGES"""
        intent = query_parser.parse("What services does Platform Team manage?")
        
        assert intent.query_type == "management"
        assert intent.target_entity == "Platform Team"
        assert intent.direction == "outgoing"
    
    # === IMPACT QUERIES (Critical - this is broken) ===
    
    def test_impact_affected_by(self, query_parser):
        """'What was affected by X?' → AFFECTS relationship from X"""
        intent = query_parser.parse("What was affected by INC-001?")
        
        assert intent.query_type == "impact"
        assert intent.target_entity == "INC-001"
        # CRITICAL: Must NOT be "What Was Affected By"
        assert "what" not in intent.target_entity.lower()
        assert intent.direction == "outgoing"
    
    def test_impact_triggered_by(self, query_parser):
        """'What triggered X?' → TRIGGERED_BY relationship"""
        intent = query_parser.parse("What triggered incident INC-001?")
        
        assert intent.query_type == "impact"
        assert intent.target_entity == "INC-001"
        assert intent.relationship_type == "TRIGGERED_BY"
        assert intent.direction == "incoming"
    
    # === BLAST RADIUS QUERIES ===
    
    def test_blast_radius_if_fails(self, query_parser):
        """'If X fails, what's affected?' → blast radius analysis"""
        intent = query_parser.parse("If Payment Service fails, what's affected?")
        
        assert intent.query_type == "blast_radius"
        assert intent.target_entity == "Payment Service"
    
    def test_blast_radius_goes_down(self, query_parser):
        """'If X goes down...' → blast radius"""
        intent = query_parser.parse("If the database goes down, what services are impacted?")
        
        assert intent.query_type == "blast_radius"
        assert "database" in intent.target_entity.lower()
    
    # === LOOKUP QUERIES ===
    
    def test_lookup_what_is(self, query_parser):
        """'What is X?' → simple lookup"""
        intent = query_parser.parse("What is the Auth Service?")
        
        assert intent.query_type == "lookup"
        assert intent.target_entity == "Auth Service"
    
    def test_lookup_tell_me_about(self, query_parser):
        """'Tell me about X' → simple lookup"""
        intent = query_parser.parse("Tell me about the Order Database")
        
        assert intent.query_type == "lookup"
        assert intent.target_entity == "Order Database"
    
    # === AGGREGATION QUERIES ===
    
    def test_aggregation_list_all(self, query_parser):
        """'List all X' → aggregation"""
        intent = query_parser.parse("List all services")
        
        assert intent.query_type == "aggregation"
        assert intent.entity_type_filter == "SERVICE"
    
    def test_aggregation_how_many(self, query_parser):
        """'How many X?' → aggregation"""
        intent = query_parser.parse("How many incidents are there?")
        
        assert intent.query_type == "aggregation"
        assert intent.entity_type_filter == "INCIDENT"
    
    # === EDGE CASES ===
    
    def test_entity_with_special_chars(self, query_parser):
        """Entity names with special characters"""
        intent = query_parser.parse("What depends on Auth-Gateway-v2.0?")
        
        assert intent.target_entity == "Auth-Gateway-v2.0"
    
    def test_case_insensitivity(self, query_parser):
        """Query parsing should be case-insensitive"""
        intent1 = query_parser.parse("WHAT DOES ORDER SERVICE DEPEND ON?")
        intent2 = query_parser.parse("what does order service depend on?")
        
        assert intent1.query_type == intent2.query_type
        assert intent1.target_entity.lower() == intent2.target_entity.lower()
```

---

## Day 2-3: Entity Resolution Contract

### Create: `src/context_foundry/contracts/entity_resolver.py`

```python
from dataclasses import dataclass
from typing import Literal, Optional, List

@dataclass
class ResolvedEntity:
    """A resolved entity from the knowledge graph."""
    id: str
    name: str
    entity_type: str
    confidence: float
    match_type: Literal["exact", "fuzzy", "semantic"]
    tenant_id: str


class EntityResolverContract:
    """Contract for entity resolution implementations."""
    
    def resolve(self, name: str, tenant_id: str) -> Optional[ResolvedEntity]:
        """
        Resolve entity name to entity in knowledge graph.
        
        MUST:
        - Filter by tenant_id (NEVER return other tenant's entities)
        - Try exact match first, then fuzzy, then semantic
        - Return None if no match found (not raise exception)
        - Return confidence score reflecting match quality
        
        MUST NOT:
        - Return entities from other tenants
        - Return STAGING entities (only TRUSTED)
        """
        raise NotImplementedError
    
    def resolve_multiple(self, names: List[str], tenant_id: str) -> List[Optional[ResolvedEntity]]:
        """Resolve multiple entity names efficiently."""
        raise NotImplementedError
```

### Create: `tests/contracts/test_entity_resolver_contract.py`

```python
import pytest

class TestEntityResolverContract:
    """Contract tests for entity resolution."""
    
    def test_exact_match(self, entity_resolver, test_knowledge_graph):
        """Exact name match returns entity with high confidence"""
        entity = entity_resolver.resolve("Order Service", TEST_TENANT_ID)
        
        assert entity is not None
        assert entity.name == "Order Service"
        assert entity.match_type == "exact"
        assert entity.confidence >= 0.95
    
    def test_case_insensitive_match(self, entity_resolver, test_knowledge_graph):
        """Should match regardless of case"""
        entity = entity_resolver.resolve("order service", TEST_TENANT_ID)
        
        assert entity is not None
        assert entity.name == "Order Service"
    
    def test_fuzzy_match(self, entity_resolver, test_knowledge_graph):
        """Slight misspelling should fuzzy match"""
        entity = entity_resolver.resolve("Order Servce", TEST_TENANT_ID)  # typo
        
        assert entity is not None
        assert entity.name == "Order Service"
        assert entity.match_type == "fuzzy"
        assert entity.confidence < 0.95  # Lower than exact
    
    def test_not_found_returns_none(self, entity_resolver, test_knowledge_graph):
        """Non-existent entity returns None, not exception"""
        entity = entity_resolver.resolve("NonExistent Service", TEST_TENANT_ID)
        
        assert entity is None
    
    def test_tenant_isolation(self, entity_resolver, test_knowledge_graph, other_tenant_entity):
        """MUST NOT return entities from other tenants"""
        # other_tenant_entity is created in different tenant
        entity = entity_resolver.resolve(
            other_tenant_entity.name, 
            TEST_TENANT_ID  # Different tenant
        )
        
        assert entity is None, "SECURITY: Returned entity from different tenant!"
    
    def test_only_trusted_entities(self, entity_resolver, staging_entity):
        """Should not return STAGING entities"""
        entity = entity_resolver.resolve(staging_entity.name, TEST_TENANT_ID)
        
        assert entity is None, "Returned STAGING entity, should only return TRUSTED"
```

---

## Day 3-4: Memory Class Contracts

### Create: `src/context_foundry/contracts/memory.py`

```python
from dataclasses import dataclass
from typing import List, Optional
from abc import ABC, abstractmethod

@dataclass
class EntityMatch:
    id: str
    name: str
    entity_type: str
    similarity_score: float

@dataclass 
class RelationshipResult:
    id: str
    source_entity_id: str
    source_entity_name: str  # MUST be populated, not None
    target_entity_id: str
    target_entity_name: str  # MUST be populated, not None
    relationship_type: str
    confidence: float


class SemanticMemoryContract(ABC):
    """Contract for semantic memory operations."""
    
    @abstractmethod
    def __init__(self, session, tenant_id: str):
        """
        Initialize with database session and tenant_id.
        
        tenant_id MUST be stored and used in ALL queries.
        """
        pass
    
    @abstractmethod
    def find_entity_by_name(self, name: str) -> Optional[EntityMatch]:
        """
        Find entity by exact name within tenant.
        
        MUST filter by self.tenant_id.
        """
        pass
    
    @abstractmethod
    def find_similar(self, query: str, k: int = 10) -> List[EntityMatch]:
        """
        Semantic similarity search within tenant.
        
        MUST filter by self.tenant_id.
        """
        pass
    
    @abstractmethod
    def get_relationships(
        self, 
        entity_id: str, 
        direction: str = "both",
        relationship_type: Optional[str] = None
    ) -> List[RelationshipResult]:
        """
        Get relationships for entity.
        
        MUST:
        - Filter by self.tenant_id
        - Populate source_entity_name and target_entity_name (not None)
        - Eager load related entities to avoid N+1
        """
        pass


class SymbolicMemoryAPIContract(ABC):
    """Contract for RLM symbolic memory API."""
    
    @abstractmethod
    def get_relationships(
        self,
        entity_id: str,
        relationship_type: Optional[str] = None
    ) -> List[RelationshipResult]:
        """
        Get relationships for entity (RLM path).
        
        MUST return SAME results as SemanticMemory.get_relationships()
        for the same inputs. This is the parity requirement.
        """
        pass
```

### Create: `tests/contracts/test_memory_contracts.py`

```python
class TestSemanticMemoryContract:
    """Contract tests for SemanticMemory."""
    
    def test_tenant_filter_find_entity(self, semantic_memory, test_knowledge_graph):
        """find_entity_by_name must filter by tenant"""
        # Entity exists in test tenant
        entity = semantic_memory.find_entity_by_name("Order Service")
        assert entity is not None
        assert entity.name == "Order Service"
    
    def test_tenant_filter_find_similar(self, semantic_memory, test_knowledge_graph):
        """find_similar must filter by tenant"""
        results = semantic_memory.find_similar("order", k=10)
        
        for entity in results:
            # All results must be from correct tenant
            assert entity.tenant_id == TEST_TENANT_ID
    
    def test_relationships_have_names(self, semantic_memory, test_knowledge_graph):
        """Relationships must have entity names populated"""
        entity = semantic_memory.find_entity_by_name("Order Service")
        relationships = semantic_memory.get_relationships(entity.id)
        
        for rel in relationships:
            assert rel.source_entity_name is not None, "source_entity_name is None"
            assert rel.target_entity_name is not None, "target_entity_name is None"
            assert rel.source_entity_name != "Unknown"
            assert rel.target_entity_name != "Unknown"
    
    def test_relationships_filter_by_type(self, semantic_memory, test_knowledge_graph):
        """Can filter relationships by type"""
        entity = semantic_memory.find_entity_by_name("Order Service")
        
        all_rels = semantic_memory.get_relationships(entity.id)
        depends_rels = semantic_memory.get_relationships(
            entity.id, 
            relationship_type="DEPENDS_ON"
        )
        
        assert len(depends_rels) <= len(all_rels)
        for rel in depends_rels:
            assert rel.relationship_type == "DEPENDS_ON"


class TestRLMMemoryParity:
    """
    RLM Memory APIs must return same data as Tier 1 memory classes.
    THIS IS THE TEST THAT WILL CATCH THE BUG.
    """
    
    def test_symbolic_returns_same_as_semantic(
        self, 
        semantic_memory, 
        symbolic_memory_api,
        test_knowledge_graph
    ):
        """SymbolicMemoryAPI must return same relationships as SemanticMemory"""
        entity = semantic_memory.find_entity_by_name("Order Service")
        
        # Tier 1 path
        tier1_rels = semantic_memory.get_relationships(
            entity.id, 
            relationship_type="DEPENDS_ON"
        )
        
        # RLM path
        rlm_rels = symbolic_memory_api.get_relationships(
            entity.id,
            relationship_type="DEPENDS_ON"
        )
        
        # MUST MATCH
        assert len(rlm_rels) == len(tier1_rels), \
            f"PARITY FAILURE: Tier 1 found {len(tier1_rels)}, RLM found {len(rlm_rels)}"
        
        tier1_targets = {r.target_entity_name for r in tier1_rels}
        rlm_targets = {r.target_entity_name for r in rlm_rels}
        
        assert tier1_targets == rlm_targets, \
            f"PARITY FAILURE: Different targets. Tier1={tier1_targets}, RLM={rlm_targets}"
```

---

## Day 4-5: Test Fixtures

### Create: `tests/fixtures/knowledge_graph.py`

```python
import pytest
from uuid import uuid4

# Canonical test tenant - used for ALL tests
TEST_TENANT_ID = "test-tenant-00000000-0000-0000-0000-000000000001"
OTHER_TENANT_ID = "other-tenant-00000000-0000-0000-0000-000000000002"

# Canonical test entities
TEST_ENTITIES = [
    # Services
    {"name": "Order Service", "type": "SERVICE"},
    {"name": "Payment Service", "type": "SERVICE"},
    {"name": "Inventory Service", "type": "SERVICE"},
    {"name": "Auth Service", "type": "SERVICE"},
    {"name": "Customer Portal", "type": "SERVICE"},
    {"name": "Notification Service", "type": "SERVICE"},
    
    # Databases
    {"name": "Order Database", "type": "DATABASE"},
    {"name": "Inventory Database", "type": "DATABASE"},
    {"name": "User Database", "type": "DATABASE"},
    
    # Teams
    {"name": "Platform Team", "type": "TEAM"},
    {"name": "Security Team", "type": "TEAM"},
    {"name": "Commerce Team", "type": "TEAM"},
    
    # Incidents
    {"name": "INC-001", "type": "INCIDENT"},
    {"name": "INC-002", "type": "INCIDENT"},
]

# Canonical test relationships
TEST_RELATIONSHIPS = [
    # Service dependencies (DEPENDS_ON)
    {"source": "Customer Portal", "target": "Order Service", "type": "DEPENDS_ON"},
    {"source": "Customer Portal", "target": "Auth Service", "type": "DEPENDS_ON"},
    {"source": "Order Service", "target": "Payment Service", "type": "DEPENDS_ON"},
    {"source": "Order Service", "target": "Inventory Service", "type": "DEPENDS_ON"},
    {"source": "Order Service", "target": "Order Database", "type": "DEPENDS_ON"},
    {"source": "Order Service", "target": "Notification Service", "type": "DEPENDS_ON"},
    {"source": "Payment Service", "target": "Auth Service", "type": "DEPENDS_ON"},
    {"source": "Inventory Service", "target": "Inventory Database", "type": "DEPENDS_ON"},
    {"source": "Auth Service", "target": "User Database", "type": "DEPENDS_ON"},
    
    # Team management (MANAGES)
    {"source": "Platform Team", "target": "Order Service", "type": "MANAGES"},
    {"source": "Platform Team", "target": "Payment Service", "type": "MANAGES"},
    {"source": "Platform Team", "target": "Inventory Service", "type": "MANAGES"},
    {"source": "Security Team", "target": "Auth Service", "type": "MANAGES"},
    {"source": "Commerce Team", "target": "Customer Portal", "type": "MANAGES"},
    
    # Incidents
    {"source": "INC-001", "target": "Payment Service", "type": "TRIGGERED_BY"},
    {"source": "INC-001", "target": "Order Service", "type": "AFFECTS"},
    {"source": "INC-001", "target": "Customer Portal", "type": "AFFECTS"},
    {"source": "INC-002", "target": "Auth Service", "type": "TRIGGERED_BY"},
    {"source": "INC-002", "target": "Payment Service", "type": "AFFECTS"},
]


@pytest.fixture
def test_db_session():
    """Create a test database session."""
    # Implementation depends on your DB setup
    # Could use test database or in-memory SQLite
    pass


@pytest.fixture
def test_knowledge_graph(test_db_session):
    """
    Create canonical test data. Used by ALL tests.
    
    This fixture:
    1. Clears any existing test tenant data
    2. Creates all TEST_ENTITIES
    3. Creates all TEST_RELATIONSHIPS
    4. Promotes everything to TRUSTED
    5. Generates embeddings
    """
    session = test_db_session
    
    # Clear existing test data
    session.execute(
        "DELETE FROM relationships WHERE tenant_id = :tid",
        {"tid": TEST_TENANT_ID}
    )
    session.execute(
        "DELETE FROM entities WHERE tenant_id = :tid",
        {"tid": TEST_TENANT_ID}
    )
    
    # Create entities
    entity_ids = {}
    for entity_data in TEST_ENTITIES:
        entity = Entity(
            id=str(uuid4()),
            name=entity_data["name"],
            entity_type=entity_data["type"],
            tenant_id=TEST_TENANT_ID,
            lifecycle_state="TRUSTED",
            confidence=0.95,
        )
        session.add(entity)
        entity_ids[entity_data["name"]] = entity.id
    
    session.flush()
    
    # Create relationships
    for rel_data in TEST_RELATIONSHIPS:
        rel = Relationship(
            id=str(uuid4()),
            source_entity_id=entity_ids[rel_data["source"]],
            target_entity_id=entity_ids[rel_data["target"]],
            relationship_type=rel_data["type"],
            tenant_id=TEST_TENANT_ID,
            lifecycle_state="TRUSTED",
            confidence=0.95,
        )
        session.add(rel)
    
    session.commit()
    
    # Generate embeddings for semantic search
    generate_embeddings_for_tenant(session, TEST_TENANT_ID)
    
    yield {
        "tenant_id": TEST_TENANT_ID,
        "entity_ids": entity_ids,
        "entity_count": len(TEST_ENTITIES),
        "relationship_count": len(TEST_RELATIONSHIPS),
    }
    
    # Cleanup after test
    session.execute(
        "DELETE FROM relationships WHERE tenant_id = :tid",
        {"tid": TEST_TENANT_ID}
    )
    session.execute(
        "DELETE FROM entities WHERE tenant_id = :tid",
        {"tid": TEST_TENANT_ID}
    )
    session.commit()


@pytest.fixture
def other_tenant_entity(test_db_session):
    """Create an entity in a different tenant for isolation tests."""
    entity = Entity(
        id=str(uuid4()),
        name="Secret Service",
        entity_type="SERVICE",
        tenant_id=OTHER_TENANT_ID,
        lifecycle_state="TRUSTED",
        confidence=0.95,
    )
    test_db_session.add(entity)
    test_db_session.commit()
    
    yield entity
    
    test_db_session.delete(entity)
    test_db_session.commit()


@pytest.fixture
def staging_entity(test_db_session):
    """Create a STAGING entity that should not be returned."""
    entity = Entity(
        id=str(uuid4()),
        name="Staging Only Service",
        entity_type="SERVICE",
        tenant_id=TEST_TENANT_ID,
        lifecycle_state="STAGING",  # Not TRUSTED
        confidence=0.95,
    )
    test_db_session.add(entity)
    test_db_session.commit()
    
    yield entity
    
    test_db_session.delete(entity)
    test_db_session.commit()
```

---

## Day 5: Verify Week 1 Complete

### Checklist

```
□ Query parser contract defined
□ Query parser contract tests written (expect failures)
□ Entity resolver contract defined
□ Entity resolver contract tests written
□ Memory contracts defined
□ Memory contract tests written (including parity test)
□ Test fixtures created
□ All contract tests run (document which fail)
```

### Report Template

```markdown
## Week 1 Complete: Contracts + Fixtures

### Contracts Defined
- [ ] QueryParserContract
- [ ] EntityResolverContract
- [ ] SemanticMemoryContract
- [ ] SymbolicMemoryAPIContract

### Test Counts
| Suite | Tests | Passing | Failing |
|-------|-------|---------|---------|
| Query Parser | X | Y | Z |
| Entity Resolver | X | Y | Z |
| Memory | X | Y | Z |
| RLM Parity | X | Y | Z |

### Known Failures (Expected)
1. test_impact_affected_by - Query parsing treats "What Was Affected By" as entity
2. test_symbolic_returns_same_as_semantic - RLM returns 0 relationships
3. ...

### Ready for Week 2
```

---

# WEEK 2: E2E Test Suite

## Objective
Build end-to-end tests that validate the complete system.

---

## Day 1-2: Query E2E Tests

### Create: `tests/e2e/test_dependency_queries.py`

```python
import pytest
from context_foundry.core import ContextFoundry

class TestDependencyQueries:
    """E2E tests for dependency queries."""
    
    @pytest.fixture
    def cf(self, test_knowledge_graph):
        """ContextFoundry instance with test data."""
        return ContextFoundry(tenant_id=TEST_TENANT_ID)
    
    def test_direct_dependency_tier1(self, cf):
        """Tier 1: What does X depend on?"""
        result = cf.query("What does Order Service depend on?")
        
        assert result["response_mode"] in ["FULL_ANSWER", "PARTIAL_ANSWER"]
        assert result["confidence"] >= 0.7
        
        answer = result["answer"].lower()
        assert "payment service" in answer
        assert "inventory service" in answer
        assert "order database" in answer
        assert "notification service" in answer
    
    def test_reverse_dependency_tier1(self, cf):
        """Tier 1: What depends on X?"""
        result = cf.query("What services depend on Order Service?")
        
        assert "customer portal" in result["answer"].lower()
    
    def test_dependency_chain_tier2(self, cf):
        """Tier 2: Trace full dependency chain."""
        result = cf.query(
            "Trace all dependencies from Customer Portal to databases",
            force_tier="tier2"
        )
        
        assert result["tier"] == "tier2_rlm"
        assert len(result.get("entities_discovered", [])) >= 3
        assert len(result.get("relationships_discovered", [])) >= 2
        
        answer = result["answer"].lower()
        # Should find path: Customer Portal → Order Service → Order Database
        assert "order database" in answer or "inventory database" in answer
    
    def test_dependency_with_type_filter(self, cf):
        """Dependencies filtered by target type."""
        result = cf.query("What databases does Order Service depend on?")
        
        answer = result["answer"].lower()
        assert "order database" in answer
        # Should NOT mention services
        assert "payment service" not in answer or "database" in answer
```

### Create: `tests/e2e/test_management_queries.py`

```python
class TestManagementQueries:
    """E2E tests for management/ownership queries."""
    
    def test_who_manages(self, cf):
        """Who manages X?"""
        result = cf.query("Who manages Order Service?")
        
        assert "platform team" in result["answer"].lower()
    
    def test_what_team_manages(self, cf):
        """What does team X manage?"""
        result = cf.query("What services does Platform Team manage?")
        
        answer = result["answer"].lower()
        assert "order service" in answer
        assert "payment service" in answer
        assert "inventory service" in answer
    
    def test_management_across_teams(self, cf):
        """Different teams manage different services."""
        result = cf.query("Who manages Auth Service?")
        assert "security team" in result["answer"].lower()
        
        result = cf.query("Who manages Customer Portal?")
        assert "commerce team" in result["answer"].lower()
```

### Create: `tests/e2e/test_impact_queries.py`

```python
class TestImpactQueries:
    """E2E tests for incident impact queries."""
    
    def test_incident_affects(self, cf):
        """What was affected by incident X?"""
        result = cf.query("What was affected by INC-001?")
        
        answer = result["answer"].lower()
        assert "order service" in answer
        assert "customer portal" in answer
    
    def test_incident_triggered_by(self, cf):
        """What triggered incident X?"""
        result = cf.query("What triggered INC-001?")
        
        assert "payment service" in result["answer"].lower()
    
    def test_blast_radius_tier2(self, cf):
        """If X fails, what's the full impact?"""
        result = cf.query(
            "If Payment Service fails, what services are affected?",
            force_tier="tier2"
        )
        
        # Payment Service failure affects:
        # - Order Service (depends on Payment)
        # - Customer Portal (depends on Order Service)
        blast_radius = result.get("blast_radius_entities", [])
        answer = result["answer"].lower()
        
        assert "order service" in answer or "Order Service" in blast_radius
```

### Create: `tests/e2e/test_lookup_queries.py`

```python
class TestLookupQueries:
    """E2E tests for simple lookup queries."""
    
    def test_what_is(self, cf):
        """What is X?"""
        result = cf.query("What is the Order Service?")
        
        assert result["response_mode"] != "NOT_FOUND"
        assert "order" in result["answer"].lower()
    
    def test_entity_not_found(self, cf):
        """Query for non-existent entity."""
        result = cf.query("What is the FooBar Service?")
        
        # Should indicate not found, not hallucinate
        assert result["response_mode"] == "NOT_FOUND" or \
               "not found" in result["answer"].lower() or \
               "no information" in result["answer"].lower()
```

---

## Day 3: Tenant Isolation E2E Tests

### Create: `tests/e2e/test_tenant_isolation.py`

```python
class TestTenantIsolation:
    """E2E tests for multi-tenant security."""
    
    def test_cannot_query_other_tenant(self, test_knowledge_graph, other_tenant_entity):
        """Queries must not return other tenant's data."""
        cf = ContextFoundry(tenant_id=TEST_TENANT_ID)
        
        result = cf.query(f"What is {other_tenant_entity.name}?")
        
        # Must not find it
        assert result["response_mode"] == "NOT_FOUND" or \
               other_tenant_entity.name not in result["answer"]
    
    def test_cannot_traverse_to_other_tenant(self, test_knowledge_graph, other_tenant_entity):
        """Graph traversal must not cross tenant boundaries."""
        cf = ContextFoundry(tenant_id=TEST_TENANT_ID)
        
        result = cf.query(
            "List all services in the system",
            force_tier="tier2"
        )
        
        # other_tenant_entity should not appear
        assert other_tenant_entity.name not in result["answer"]
        assert other_tenant_entity.name not in str(result.get("entities_discovered", []))
    
    def test_relationship_isolation(self, test_db_session):
        """Relationships across tenants must not be visible."""
        # Create cross-tenant relationship (should never happen, but test defense)
        # Then verify it's not returned
        pass
```

---

## Day 4: Integration Tests

### Create: `tests/integration/test_pipeline.py`

```python
class TestQueryPipeline:
    """Integration tests for the full query pipeline."""
    
    def test_tier1_pipeline_stages(self, cf, test_knowledge_graph):
        """Verify all Tier 1 stages execute."""
        result = cf.query("What does Order Service depend on?")
        
        # Verify pipeline metadata
        assert result["tier"] == "tier1"
        assert "evidence" in result
        assert len(result["evidence"]) > 0
    
    def test_tier2_pipeline_stages(self, cf, test_knowledge_graph):
        """Verify all Tier 2 stages execute."""
        result = cf.query(
            "Trace dependencies from Customer Portal",
            force_tier="tier2"
        )
        
        assert result["tier"] == "tier2_rlm"
        assert "entities_discovered" in result
        assert "execution_trace" in result
    
    def test_router_selects_correct_tier(self, cf, test_knowledge_graph):
        """Router should select appropriate tier."""
        # Simple query → Tier 1
        result1 = cf.query("What is Order Service?")
        assert result1["tier"] == "tier1"
        
        # Complex query → Tier 2 (if not forced)
        # This depends on router threshold
```

### Create: `tests/integration/test_rlm_integration.py`

```python
class TestRLMIntegration:
    """Integration tests for RLM with real data."""
    
    def test_rlm_discovers_relationships(self, cf, test_knowledge_graph):
        """RLM should discover relationships in graph."""
        result = cf.query(
            "What does Order Service depend on?",
            force_tier="tier2"
        )
        
        # This is the bug - RLM finds entities but not relationships
        assert len(result.get("relationships_discovered", [])) > 0, \
            "RLM discovered 0 relationships - PARITY BUG"
    
    def test_rlm_matches_tier1(self, cf, test_knowledge_graph):
        """RLM should find same info as Tier 1."""
        query = "What services does Order Service depend on?"
        
        tier1 = cf.query(query, force_tier="tier1")
        tier2 = cf.query(query, force_tier="tier2")
        
        # Both should mention the same dependencies
        tier1_answer = tier1["answer"].lower()
        tier2_answer = tier2["answer"].lower()
        
        # At minimum, both should find Payment Service
        assert "payment service" in tier1_answer
        assert "payment service" in tier2_answer
```

---

## Day 5: Run All Tests + Document Failures

### Run Tests

```bash
# Run all E2E tests
pytest tests/e2e/ -v --tb=short > e2e_results.txt

# Run all contract tests
pytest tests/contracts/ -v --tb=short > contract_results.txt

# Run all integration tests
pytest tests/integration/ -v --tb=short > integration_results.txt
```

### Document Results

```markdown
## Week 2 Complete: E2E Test Suite

### Test Counts
| Suite | Tests | Passing | Failing |
|-------|-------|---------|---------|
| E2E Dependency | X | Y | Z |
| E2E Management | X | Y | Z |
| E2E Impact | X | Y | Z |
| E2E Lookup | X | Y | Z |
| E2E Tenant Isolation | X | Y | Z |
| Integration Pipeline | X | Y | Z |
| Integration RLM | X | Y | Z |

### Bug Backlog (from test failures)
| Test | Failure | Root Cause | Priority |
|------|---------|------------|----------|
| test_incident_affects | Wrong entity parsed | Query parser bug | HIGH |
| test_rlm_discovers_relationships | 0 relationships | RLM parity bug | HIGH |
| ... | ... | ... | ... |

### Ready for Week 3
```

---

# WEEK 3: Schema Consolidation

## Objective
One source of truth for schema: ontology tables.

---

## Day 1: Audit Current State

```bash
# Find all YAML schema references
grep -rn "domain_schema\|DomainSchemaLoader\|yaml" src/

# Find all ontology references
grep -rn "OntologyRepository\|ontology_types\|ontology_relations" src/

# Find all TYPE_MAPPING references
grep -rn "TYPE_MAPPING\|SPECIFIC_TYPE_PATTERNS" src/
```

### Document Current Usage

| File | Uses YAML | Uses Ontology | Uses TYPE_MAPPING |
|------|-----------|---------------|-------------------|
| graph_builder.py | ? | ? | ? |
| entity_extractor.py | ? | ? | ? |
| retrieval.py | ? | ? | ? |
| ... | ... | ... | ... |

---

## Day 2: Migrate YAML to Ontology

### Export YAML to ontology tables

```python
# scripts/migrate_yaml_to_ontology.py

def migrate_yaml_to_ontology():
    """One-time migration of YAML schema to ontology tables."""
    
    yaml_schema = load_yaml_schema()
    session = get_session()
    
    # Migrate entity types
    for entity_type in yaml_schema.get('entity_types', []):
        existing = session.query(OntologyType).filter(
            OntologyType.name == entity_type['name']
        ).first()
        
        if not existing:
            ontology_type = OntologyType(
                name=entity_type['name'],
                description=entity_type.get('description', ''),
                extraction_keywords=entity_type.get('keywords', []),
                extraction_priority=entity_type.get('priority', 5),
                status='ACTIVE',
            )
            session.add(ontology_type)
            print(f"Added entity type: {entity_type['name']}")
    
    # Migrate relationship types
    for rel_type in yaml_schema.get('relationship_types', []):
        existing = session.query(OntologyRelation).filter(
            OntologyRelation.relation_type == rel_type['name']
        ).first()
        
        if not existing:
            ontology_rel = OntologyRelation(
                relation_type=rel_type['name'],
                description=rel_type.get('description', ''),
                source_types=rel_type.get('source_types', []),
                target_types=rel_type.get('target_types', []),
                semantics=rel_type.get('semantics', {}),
                status='ACTIVE',
            )
            session.add(ontology_rel)
            print(f"Added relationship type: {rel_type['name']}")
    
    session.commit()
    print("Migration complete")


if __name__ == "__main__":
    migrate_yaml_to_ontology()
```

---

## Day 3: Update GraphBuilderAgent

### Replace YAML with OntologyRepository

```python
# Before (graph_builder.py)
from context_foundry.config.schema_loader import DomainSchemaLoader

class GraphBuilderAgent:
    def __init__(self):
        self.schema = DomainSchemaLoader.load()
        self.entity_types = self.schema['entity_types']

# After
from context_foundry.ontology.repository import OntologyRepository

class GraphBuilderAgent:
    def __init__(self, session):
        self.ontology = OntologyRepository(session)
        self.entity_types = self.ontology.get_entity_types()
        self.relationship_types = self.ontology.get_relationship_types()
```

### Remove TYPE_MAPPING

The extraction prompt should use ontology types directly:

```python
def _build_extraction_prompt(self, content: str) -> str:
    """Build extraction prompt from ontology."""
    
    # Get types from ontology
    entity_types = self.ontology.get_entity_types()
    
    type_instructions = []
    for et in entity_types:
        keywords = ", ".join(et.extraction_keywords or [])
        type_instructions.append(
            f"- {et.name}: {et.description}. Keywords: {keywords}"
        )
    
    prompt = f"""
Extract entities from the following document.

Classify each entity as ONE of these types:
{chr(10).join(type_instructions)}

DO NOT use any other types. If unsure, use the closest matching type.

Document:
{content}
"""
    return prompt
```

---

## Day 4: Update All Other Components

### Files to update:
- retrieval.py
- reasoning.py  
- staging_validator.py
- semantic.py
- inference.py
- entity_extractor.py
- relation_extractor.py

### Pattern for each:

```python
# Before
from config.schema_loader import get_schema
schema = get_schema()
valid_types = schema['entity_types']

# After
from ontology.repository import OntologyRepository
ontology = OntologyRepository(session)
valid_types = [t.name for t in ontology.get_entity_types()]
```

---

## Day 5: Remove YAML + Verify

### Delete YAML files

```bash
rm config/domain_schema.yaml
rm config/schema_loader.py  # or deprecate
```

### Verify no references remain

```bash
grep -rn "domain_schema\|DomainSchemaLoader" src/
# Should return nothing

grep -rn "TYPE_MAPPING\|SPECIFIC_TYPE_PATTERNS" src/
# Should return nothing
```

### Run tests

```bash
pytest tests/ -v
```

### Report

```markdown
## Week 3 Complete: Schema Consolidation

### Changes Made
- [ ] YAML schema migrated to ontology tables
- [ ] GraphBuilderAgent uses OntologyRepository
- [ ] All components updated to use ontology
- [ ] TYPE_MAPPING removed
- [ ] YAML files deleted

### Test Results After Migration
| Suite | Before | After |
|-------|--------|-------|
| Contracts | X/Y | X/Y |
| E2E | X/Y | X/Y |
| Integration | X/Y | X/Y |

### Ontology Table Counts
- Entity types: X
- Relationship types: Y
```

---

# WEEK 4: Fix Identified Issues

## Objective
Fix all failing tests from Weeks 1-2.

---

## Day 1-2: Query Parser Fix

### Implement QueryParser

```python
# src/context_foundry/query/parser.py

import re
from dataclasses import dataclass
from typing import Literal, Optional

@dataclass
class QueryIntent:
    query_type: str
    target_entity: Optional[str]
    secondary_entity: Optional[str]
    relationship_type: Optional[str]
    direction: str
    entity_type_filter: Optional[str]
    raw_query: str


class QueryParser:
    """
    Pattern-based query parser with LLM fallback.
    """
    
    PATTERNS = [
        # Dependency - outgoing
        (r"what does (.+?) depend on", "dependency", "DEPENDS_ON", "outgoing"),
        (r"what are the dependencies of (.+)", "dependency", "DEPENDS_ON", "outgoing"),
        (r"(.+?) depends on what", "dependency", "DEPENDS_ON", "outgoing"),
        
        # Dependency - incoming
        (r"what depends on (.+)", "dependency", "DEPENDS_ON", "incoming"),
        (r"what services depend on (.+)", "dependency", "DEPENDS_ON", "incoming"),
        
        # Management - incoming (who manages X)
        (r"who manages (.+)", "management", "MANAGES", "incoming"),
        (r"who owns (.+)", "management", "MANAGES", "incoming"),
        (r"which team (?:manages|owns) (.+)", "management", "MANAGES", "incoming"),
        
        # Management - outgoing (what does team manage)
        (r"what does (.+?) manage", "management", "MANAGES", "outgoing"),
        (r"what services does (.+?) manage", "management", "MANAGES", "outgoing"),
        
        # Impact - affected by (outgoing from incident)
        (r"what was affected by (.+)", "impact", "AFFECTS", "outgoing"),
        (r"what did (.+?) affect", "impact", "AFFECTS", "outgoing"),
        (r"impact of (.+)", "impact", "AFFECTS", "outgoing"),
        
        # Impact - triggered by (incoming to incident)
        (r"what triggered (.+)", "impact", "TRIGGERED_BY", "incoming"),
        (r"what caused (.+)", "impact", "TRIGGERED_BY", "incoming"),
        
        # Blast radius
        (r"if (.+?) fails", "blast_radius", None, "incoming"),
        (r"if (.+?) goes down", "blast_radius", None, "incoming"),
        (r"blast radius of (.+)", "blast_radius", None, "incoming"),
        (r"impact if (.+?) fails", "blast_radius", None, "incoming"),
        
        # Lookup
        (r"what is (.+)", "lookup", None, "both"),
        (r"tell me about (.+)", "lookup", None, "both"),
        (r"describe (.+)", "lookup", None, "both"),
        
        # Aggregation
        (r"list all (.+)", "aggregation", None, "both"),
        (r"how many (.+)", "aggregation", None, "both"),
        (r"show all (.+)", "aggregation", None, "both"),
    ]
    
    def parse(self, query: str) -> QueryIntent:
        query_lower = query.lower().strip()
        query_lower = re.sub(r'\?+$', '', query_lower)  # Remove trailing ?
        query_lower = re.sub(r'^(the|a|an)\s+', '', query_lower)  # Remove articles
        
        for pattern, query_type, rel_type, direction in self.PATTERNS:
            match = re.search(pattern, query_lower)
            if match:
                target = self._clean_entity_name(match.group(1))
                return QueryIntent(
                    query_type=query_type,
                    target_entity=target,
                    secondary_entity=None,
                    relationship_type=rel_type,
                    direction=direction,
                    entity_type_filter=self._extract_type_filter(query_lower),
                    raw_query=query,
                )
        
        # Fallback to LLM parsing
        return self._llm_parse(query)
    
    def _clean_entity_name(self, name: str) -> str:
        """Clean extracted entity name."""
        name = name.strip()
        # Remove trailing articles
        name = re.sub(r'\s+(the|a|an)$', '', name)
        # Remove leading articles
        name = re.sub(r'^(the|a|an)\s+', '', name)
        # Title case for proper nouns
        return name.strip()
    
    def _extract_type_filter(self, query: str) -> Optional[str]:
        """Extract entity type filter from query."""
        type_keywords = {
            "service": "SERVICE",
            "services": "SERVICE",
            "database": "DATABASE",
            "databases": "DATABASE",
            "team": "TEAM",
            "teams": "TEAM",
            "incident": "INCIDENT",
            "incidents": "INCIDENT",
        }
        for keyword, entity_type in type_keywords.items():
            if keyword in query:
                return entity_type
        return None
    
    def _llm_parse(self, query: str) -> QueryIntent:
        """Fallback to LLM for complex queries."""
        # Implementation uses LLM to extract intent
        # Should still produce structured QueryIntent
        pass
```

### Verify tests pass

```bash
pytest tests/contracts/test_query_parser_contract.py -v
```

---

## Day 3-4: RLM Relationship Parity Fix

### Debug: Compare code paths

```python
# Add logging to both paths

# Tier 1 path (SemanticMemory.get_relationships)
def get_relationships(self, entity_id, ...):
    logger.debug(f"SemanticMemory.get_relationships: entity={entity_id}, tenant={self.tenant_id}")
    query = self.session.query(Relationship).filter(...)
    logger.debug(f"SQL: {query}")
    results = query.all()
    logger.debug(f"Results: {len(results)}")
    return results

# RLM path (SymbolicMemoryAPI.get_relationships)
def get_relationships(self, entity_id, ...):
    logger.debug(f"SymbolicMemoryAPI.get_relationships: entity={entity_id}, tenant={self.tenant_id}")
    # ... compare SQL and results
```

### Likely issues:

1. **Tenant ID not passed to RLM API**
2. **Different filter logic**
3. **lifecycle_state filter mismatch**
4. **Entity ID format mismatch (str vs UUID)**

### Fix and verify

```bash
pytest tests/contracts/test_memory_contracts.py::TestRLMMemoryParity -v
```

---

## Day 5: Fix Remaining Failures

Run full test suite, fix any remaining failures:

```bash
pytest tests/ -v --tb=short
```

### Report

```markdown
## Week 4 Complete: Issue Fixes

### Query Parser
- [x] Implemented pattern-based parser
- [x] All contract tests pass
- [x] "What was affected by X" correctly parses

### RLM Parity
- [x] Root cause identified: [describe]
- [x] Fix applied: [describe]
- [x] Parity test passes

### Full Test Suite
| Suite | Tests | Passing |
|-------|-------|---------|
| Contracts | X | X |
| E2E | X | X |
| Integration | X | X |
| RLS | 16 | 16 |

### Remaining Issues (if any)
- ...
```

---

# WEEK 5: CI/CD + Documentation

## Objective
Automate testing. Document architecture.

---

## Day 1-2: CI Pipeline

### Create: `.github/workflows/test.yml` (or Replit equivalent)

```yaml
name: Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_DB: cf_test
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      
      - name: Run migrations
        run: alembic upgrade head
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/cf_test
      
      - name: Run contract tests
        run: pytest tests/contracts/ -v
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/cf_test
      
      - name: Run E2E tests
        run: pytest tests/e2e/ -v
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/cf_test
      
      - name: Run integration tests
        run: pytest tests/integration/ -v
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/cf_test
      
      - name: Run RLS security tests
        run: pytest tests/test_rls_security.py -v
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/cf_test
```

---

## Day 3: Pre-commit Hooks

### Create: `.pre-commit-config.yaml`

```yaml
repos:
  - repo: local
    hooks:
      - id: contract-tests
        name: Contract Tests
        entry: pytest tests/contracts/ -q
        language: system
        pass_filenames: false
        always_run: true
      
      - id: lint
        name: Lint
        entry: ruff check src/
        language: system
        pass_filenames: false
```

---

## Day 4-5: Documentation

### Create: `docs/architecture.md`

```markdown
# Context Foundry Architecture

## Overview

Context Foundry is a multi-tenant knowledge graph system that:
- Extracts entities and relationships from documents
- Stores them in a secure, tenant-isolated graph
- Answers natural language queries using graph traversal

## Components

### Query Pipeline

```
User Query
    ↓
QueryParser (parse intent)
    ↓
QueryRouter (select tier)
    ↓
┌─────────────────────────────────────┐
│ Tier 1 (Simple)  │ Tier 2 (Complex) │
│ - EntityResolver │ - RLM Executor   │
│ - SemanticMemory │ - Memory APIs    │
│ - ReasoningAgent │ - Sandbox        │
└─────────────────────────────────────┘
    ↓
QueryResponse
```

### Data Model

- **Entities**: Named objects (SERVICE, DATABASE, TEAM, INCIDENT)
- **Relationships**: Typed connections (DEPENDS_ON, MANAGES, AFFECTS)
- **Documents**: Source material
- **Chunks**: Document segments with embeddings

### Security Model

- **RLS (Authoritative)**: PostgreSQL row-level security
- **Defense-in-depth**: Application tenant_id filters
- **Tenant isolation**: Complete data separation

## Component Contracts

See `src/context_foundry/contracts/` for interface definitions.

## Testing

- Contract tests: Verify component interfaces
- E2E tests: Verify user-facing behavior
- Integration tests: Verify component interaction
- RLS tests: Verify security
```

### Create: `docs/api.md`

Document all API endpoints.

### Create: `docs/deployment.md`

Document deployment process.

---

## Final Report

```markdown
# Context Foundry Stabilization Complete

## Test Coverage

| Suite | Tests | Passing | Coverage |
|-------|-------|---------|----------|
| Contracts | X | X | Core interfaces |
| E2E | X | X | User queries |
| Integration | X | X | Component interaction |
| RLS | 16 | 16 | Security |
| **Total** | **X** | **X** | |

## Architecture

- Single schema source: Ontology tables
- No hardcoded mappings
- Clear component contracts
- Full tenant isolation

## CI/CD

- Tests run on every push
- Pre-commit hooks for contracts
- Automated deployment (if configured)

## Documentation

- Architecture overview
- API reference
- Deployment guide
- Component contracts

## Known Limitations

1. ...
2. ...

## Ready for Production

- [ ] All tests pass
- [ ] CI pipeline active
- [ ] Documentation complete
- [ ] Security audit passed
```

---

# Summary

| Week | Focus | Deliverable |
|------|-------|-------------|
| 1 | Contracts | Component interfaces + test fixtures |
| 2 | E2E Tests | Full test suite + bug backlog |
| 3 | Schema | Single source of truth (ontology) |
| 4 | Fixes | All tests passing |
| 5 | CI/CD | Automated testing + docs |

**After Week 5**: Changes can be made with confidence. New features can be added knowing tests will catch regressions.
