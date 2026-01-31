"""
Query Set Design for Context Foundry Evaluation.

100 diverse queries across 6 categories:
1. Impact Analysis - What breaks if X fails?
2. Escalation - Who to contact for issues?
3. Ownership - Who owns what?
4. Dependencies - What depends on what?
5. Incidents - Historical incident queries
6. Expertise - Who knows about what?

Each query has:
- Ground truth answer expectations
- Required entities/relationships
- Difficulty level (easy/medium/hard)
- Multi-hop indicator (single/multi)
"""
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass, field
import random


class QueryCategory(str, Enum):
    IMPACT_ANALYSIS = "impact_analysis"
    ESCALATION = "escalation"
    OWNERSHIP = "ownership"
    DEPENDENCIES = "dependencies"
    INCIDENTS = "incidents"
    EXPERTISE = "expertise"


class DifficultyLevel(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class HopCount(str, Enum):
    SINGLE = "single_hop"
    MULTI = "multi_hop"


@dataclass
class EvaluationQuery:
    """A single evaluation query with ground truth."""
    id: str
    query_text: str
    category: QueryCategory
    difficulty: DifficultyLevel
    hop_count: HopCount
    
    expected_entities: List[str] = field(default_factory=list)
    expected_relationships: List[str] = field(default_factory=list)
    expected_facts: List[str] = field(default_factory=list)
    
    notes: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "query_text": self.query_text,
            "category": self.category.value,
            "difficulty": self.difficulty.value,
            "hop_count": self.hop_count.value,
            "expected_entities": self.expected_entities,
            "expected_relationships": self.expected_relationships,
            "expected_facts": self.expected_facts,
            "notes": self.notes,
        }


class QuerySet:
    """
    Manages the 100-query evaluation set.
    
    Distribution:
    - Impact Analysis: 20 queries
    - Escalation: 15 queries
    - Ownership: 15 queries
    - Dependencies: 20 queries
    - Incidents: 15 queries
    - Expertise: 15 queries
    
    Difficulty:
    - Easy (single-hop, direct lookup): 30%
    - Medium (2-hop, some inference): 45%
    - Hard (3+ hop, complex reasoning): 25%
    """
    
    def __init__(self):
        self.queries: List[EvaluationQuery] = []
        self._generate_queries()
    
    def _generate_queries(self):
        """Generate the 100 evaluation queries."""
        self.queries.extend(self._impact_analysis_queries())
        self.queries.extend(self._escalation_queries())
        self.queries.extend(self._ownership_queries())
        self.queries.extend(self._dependency_queries())
        self.queries.extend(self._incident_queries())
        self.queries.extend(self._expertise_queries())
    
    def _impact_analysis_queries(self) -> List[EvaluationQuery]:
        """Generate 20 impact analysis queries."""
        return [
            EvaluationQuery(
                id="IA-001",
                query_text="What services are affected if the Payments Database goes down?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Payments Database", "Payment Service", "Fraud Detection Service"],
                expected_relationships=["DEPENDS_ON"],
                expected_facts=["Payment Service depends on Payments Database"],
            ),
            EvaluationQuery(
                id="IA-002",
                query_text="If the Auth Service fails, what downstream services will be impacted?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Auth Service"],
                expected_relationships=["DEPENDS_ON"],
                expected_facts=["Multiple services depend on Auth Service for authentication"],
            ),
            EvaluationQuery(
                id="IA-003",
                query_text="What is the blast radius if the API Gateway becomes unavailable?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["API Gateway"],
                expected_relationships=["DEPENDS_ON", "ROUTES_TO"],
                expected_facts=["API Gateway is a critical chokepoint"],
            ),
            EvaluationQuery(
                id="IA-004",
                query_text="Which teams would be affected by a Checkout Service outage?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Checkout Service"],
                expected_relationships=["OWNS", "DEPENDS_ON"],
                expected_facts=["Checkout Service is owned by specific team"],
            ),
            EvaluationQuery(
                id="IA-005",
                query_text="What happens to order processing if Redis Cache fails?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Redis Cache", "Order Service"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="IA-006",
                query_text="If the User Database is corrupted, which services need to be notified?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["User Database"],
                expected_relationships=["DEPENDS_ON", "OWNS"],
            ),
            EvaluationQuery(
                id="IA-007",
                query_text="What services depend on the Notification Service?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Notification Service"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="IA-008",
                query_text="If the Message Queue goes down, what background jobs will fail?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Message Queue"],
                expected_relationships=["DEPENDS_ON", "PUBLISHES_TO"],
            ),
            EvaluationQuery(
                id="IA-009",
                query_text="Which customer-facing features break if the Search Service fails?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["Search Service"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="IA-010",
                query_text="What is the impact of losing connectivity to the third-party payment processor?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["Payment Gateway"],
                expected_relationships=["INTEGRATES_WITH", "DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="IA-011",
                query_text="If the Logging Service crashes, what monitoring capabilities are lost?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.SINGLE,
                expected_entities=["Logging Service"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="IA-012",
                query_text="What services are impacted if the CDN becomes unavailable?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["CDN"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="IA-013",
                query_text="Which databases are affected if the primary data center goes offline?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["Primary Data Center"],
                expected_relationships=["HOSTED_IN", "DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="IA-014",
                query_text="What breaks if the Inventory Service times out?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Inventory Service"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="IA-015",
                query_text="If the Config Server fails, which services cannot start?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["Config Server"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="IA-016",
                query_text="What customer workflows are blocked if the Email Service is down?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Email Service"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="IA-017",
                query_text="Which services fail if the Session Store becomes read-only?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Session Store"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="IA-018",
                query_text="What happens to analytics if the Data Warehouse is unavailable?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Data Warehouse"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="IA-019",
                query_text="If the Load Balancer fails, which services become unreachable?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["Load Balancer"],
                expected_relationships=["ROUTES_TO"],
            ),
            EvaluationQuery(
                id="IA-020",
                query_text="What is the customer impact if the Recommendation Engine fails?",
                category=QueryCategory.IMPACT_ANALYSIS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Recommendation Engine"],
                expected_relationships=["DEPENDS_ON"],
            ),
        ]
    
    def _escalation_queries(self) -> List[EvaluationQuery]:
        """Generate 15 escalation queries."""
        return [
            EvaluationQuery(
                id="ES-001",
                query_text="Who should I escalate to for a SEV1 on the Auth Service?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Auth Service", "Auth Team"],
                expected_relationships=["OWNS", "MEMBER_OF", "MANAGES"],
                expected_facts=["Auth Team owns Auth Service"],
            ),
            EvaluationQuery(
                id="ES-002",
                query_text="Who is the on-call engineer for the Payment Service right now?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Payment Service"],
                expected_relationships=["ON_CALL_FOR"],
            ),
            EvaluationQuery(
                id="ES-003",
                query_text="If a database incident occurs at 3 AM, who gets paged first?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Database", "DBA Team"],
                expected_relationships=["ON_CALL_FOR", "ESCALATES_TO"],
            ),
            EvaluationQuery(
                id="ES-004",
                query_text="What is the escalation path for a critical checkout failure?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Checkout Service"],
                expected_relationships=["OWNS", "ESCALATES_TO"],
            ),
            EvaluationQuery(
                id="ES-005",
                query_text="Who should be notified if we detect a security breach?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["Security Team"],
                expected_relationships=["NOTIFIED_FOR", "ESCALATES_TO"],
            ),
            EvaluationQuery(
                id="ES-006",
                query_text="Who is the manager of the Platform Team?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Platform Team"],
                expected_relationships=["MANAGES"],
            ),
            EvaluationQuery(
                id="ES-007",
                query_text="If the SRE team is unresponsive, who is the backup escalation?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["SRE Team"],
                expected_relationships=["ESCALATES_TO", "BACKUP_FOR"],
            ),
            EvaluationQuery(
                id="ES-008",
                query_text="Who should approve a production deployment at midnight?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Release Manager"],
                expected_relationships=["APPROVES", "ON_CALL_FOR"],
            ),
            EvaluationQuery(
                id="ES-009",
                query_text="What is the escalation chain for a customer data breach?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["Security Team", "Legal Team", "Executive Team"],
                expected_relationships=["ESCALATES_TO", "NOTIFIED_FOR"],
            ),
            EvaluationQuery(
                id="ES-010",
                query_text="Who do I contact for an issue with the CDN?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["CDN", "Infrastructure Team"],
                expected_relationships=["OWNS", "SUPPORTS"],
            ),
            EvaluationQuery(
                id="ES-011",
                query_text="Who is responsible for third-party API outages?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Integration Team"],
                expected_relationships=["RESPONSIBLE_FOR"],
            ),
            EvaluationQuery(
                id="ES-012",
                query_text="If a SEV2 is not resolved in 2 hours, who should be escalated to?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_relationships=["ESCALATES_TO"],
            ),
            EvaluationQuery(
                id="ES-013",
                query_text="Who handles compliance-related incidents?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Compliance Team"],
                expected_relationships=["HANDLES"],
            ),
            EvaluationQuery(
                id="ES-014",
                query_text="What is the notification order for a major service degradation?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_relationships=["NOTIFIED_FOR", "ESCALATES_TO"],
            ),
            EvaluationQuery(
                id="ES-015",
                query_text="Who should be paged if the monitoring system itself fails?",
                category=QueryCategory.ESCALATION,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Monitoring Service", "SRE Team"],
                expected_relationships=["OWNS", "ON_CALL_FOR"],
            ),
        ]
    
    def _ownership_queries(self) -> List[EvaluationQuery]:
        """Generate 15 ownership queries."""
        return [
            EvaluationQuery(
                id="OW-001",
                query_text="What team owns the Payment Service?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Payment Service", "Payments Team"],
                expected_relationships=["OWNS"],
                expected_facts=["Payments Team owns Payment Service"],
            ),
            EvaluationQuery(
                id="OW-002",
                query_text="Who is responsible for the Checkout Service?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Checkout Service"],
                expected_relationships=["OWNS", "RESPONSIBLE_FOR"],
            ),
            EvaluationQuery(
                id="OW-003",
                query_text="Which team maintains the API Gateway?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["API Gateway"],
                expected_relationships=["OWNS", "MAINTAINS"],
            ),
            EvaluationQuery(
                id="OW-004",
                query_text="What services does the Platform Team own?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.SINGLE,
                expected_entities=["Platform Team"],
                expected_relationships=["OWNS"],
            ),
            EvaluationQuery(
                id="OW-005",
                query_text="Who owns all the databases in the payments domain?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Payments Database"],
                expected_relationships=["OWNS"],
            ),
            EvaluationQuery(
                id="OW-006",
                query_text="Which engineer is the primary owner of the Auth Service codebase?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Auth Service"],
                expected_relationships=["OWNS", "MAINTAINS"],
            ),
            EvaluationQuery(
                id="OW-007",
                query_text="What does the SRE team own?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["SRE Team"],
                expected_relationships=["OWNS"],
            ),
            EvaluationQuery(
                id="OW-008",
                query_text="Who is the owner of the user notification pipeline?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Notification Service"],
                expected_relationships=["OWNS"],
            ),
            EvaluationQuery(
                id="OW-009",
                query_text="Which team is responsible for the machine learning models?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["ML Team"],
                expected_relationships=["OWNS", "RESPONSIBLE_FOR"],
            ),
            EvaluationQuery(
                id="OW-010",
                query_text="Who maintains the shared libraries?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_relationships=["MAINTAINS"],
            ),
            EvaluationQuery(
                id="OW-011",
                query_text="What infrastructure components does the DevOps team manage?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.SINGLE,
                expected_entities=["DevOps Team"],
                expected_relationships=["MANAGES", "OWNS"],
            ),
            EvaluationQuery(
                id="OW-012",
                query_text="Who owns the customer-facing mobile app?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Mobile App"],
                expected_relationships=["OWNS"],
            ),
            EvaluationQuery(
                id="OW-013",
                query_text="Which team is accountable for data privacy compliance?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Compliance Team", "Legal Team"],
                expected_relationships=["ACCOUNTABLE_FOR"],
            ),
            EvaluationQuery(
                id="OW-014",
                query_text="Who manages the Kubernetes clusters?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Kubernetes", "Platform Team"],
                expected_relationships=["MANAGES"],
            ),
            EvaluationQuery(
                id="OW-015",
                query_text="What services are jointly owned by multiple teams?",
                category=QueryCategory.OWNERSHIP,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_relationships=["OWNS"],
            ),
        ]
    
    def _dependency_queries(self) -> List[EvaluationQuery]:
        """Generate 20 dependency queries."""
        return [
            EvaluationQuery(
                id="DP-001",
                query_text="What does the Checkout Service depend on?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Checkout Service"],
                expected_relationships=["DEPENDS_ON"],
                expected_facts=["Checkout Service depends on multiple services"],
            ),
            EvaluationQuery(
                id="DP-002",
                query_text="What are the upstream dependencies of the Payment Service?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Payment Service"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="DP-003",
                query_text="Which services call the Auth Service?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.SINGLE,
                expected_entities=["Auth Service"],
                expected_relationships=["DEPENDS_ON", "CALLS"],
            ),
            EvaluationQuery(
                id="DP-004",
                query_text="What databases does the Order Service use?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Order Service"],
                expected_relationships=["DEPENDS_ON", "USES"],
            ),
            EvaluationQuery(
                id="DP-005",
                query_text="List all services that depend on the User Database",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.SINGLE,
                expected_entities=["User Database"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="DP-006",
                query_text="What is the full dependency chain from the Web App to the database?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="DP-007",
                query_text="Which external APIs does the Payment Service integrate with?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.SINGLE,
                expected_entities=["Payment Service"],
                expected_relationships=["INTEGRATES_WITH"],
            ),
            EvaluationQuery(
                id="DP-008",
                query_text="What message queues does the Notification Service publish to?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Notification Service"],
                expected_relationships=["PUBLISHES_TO"],
            ),
            EvaluationQuery(
                id="DP-009",
                query_text="Which services have circular dependencies?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="DP-010",
                query_text="What caching layers does the Search Service use?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Search Service", "Redis Cache"],
                expected_relationships=["DEPENDS_ON", "USES"],
            ),
            EvaluationQuery(
                id="DP-011",
                query_text="Which services share the same database?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="DP-012",
                query_text="What are the critical path dependencies for checkout?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["Checkout Service"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="DP-013",
                query_text="Which services depend on Kafka?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Kafka"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="DP-014",
                query_text="What are the downstream consumers of the Order Service events?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Order Service"],
                expected_relationships=["SUBSCRIBES_TO", "DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="DP-015",
                query_text="Which services can operate in degraded mode without the Cache?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["Cache"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="DP-016",
                query_text="What are the transitive dependencies of the Mobile Gateway?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["Mobile Gateway"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="DP-017",
                query_text="Which services require the Config Service at startup?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.SINGLE,
                expected_entities=["Config Service"],
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="DP-018",
                query_text="What third-party services does our system integrate with?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.SINGLE,
                expected_relationships=["INTEGRATES_WITH"],
            ),
            EvaluationQuery(
                id="DP-019",
                query_text="Which services have the most dependencies?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_relationships=["DEPENDS_ON"],
            ),
            EvaluationQuery(
                id="DP-020",
                query_text="What are the runtime dependencies vs build dependencies for the Order Service?",
                category=QueryCategory.DEPENDENCIES,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["Order Service"],
                expected_relationships=["DEPENDS_ON"],
            ),
        ]
    
    def _incident_queries(self) -> List[EvaluationQuery]:
        """Generate 15 incident queries."""
        return [
            EvaluationQuery(
                id="IN-001",
                query_text="What incidents have affected the Auth Service?",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Auth Service"],
                expected_relationships=["AFFECTS", "CAUSED_BY"],
            ),
            EvaluationQuery(
                id="IN-002",
                query_text="How many SEV1 incidents occurred in the last month?",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=[],
                expected_relationships=["AFFECTS"],
            ),
            EvaluationQuery(
                id="IN-003",
                query_text="What was the root cause of the last Payment Service outage?",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Payment Service"],
                expected_relationships=["CAUSED_BY", "AFFECTS"],
            ),
            EvaluationQuery(
                id="IN-004",
                query_text="Which team resolved the most incidents last quarter?",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_relationships=["RESOLVED_BY"],
            ),
            EvaluationQuery(
                id="IN-005",
                query_text="What incidents were caused by database failures?",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.SINGLE,
                expected_relationships=["CAUSED_BY"],
            ),
            EvaluationQuery(
                id="IN-006",
                query_text="Show me all incidents that affected customer checkouts",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Checkout Service"],
                expected_relationships=["AFFECTS"],
            ),
            EvaluationQuery(
                id="IN-007",
                query_text="What is the average time to resolution for SEV2 incidents?",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
            ),
            EvaluationQuery(
                id="IN-008",
                query_text="Which services have had repeated incidents?",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_relationships=["AFFECTS"],
            ),
            EvaluationQuery(
                id="IN-009",
                query_text="What incidents happened during the last deployment?",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_relationships=["TRIGGERED_BY", "AFFECTS"],
            ),
            EvaluationQuery(
                id="IN-010",
                query_text="Who was involved in resolving the last major outage?",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_relationships=["RESOLVED_BY", "PARTICIPATED_IN"],
            ),
            EvaluationQuery(
                id="IN-011",
                query_text="What preventive measures were taken after the Auth Service incident?",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_entities=["Auth Service"],
            ),
            EvaluationQuery(
                id="IN-012",
                query_text="Which incidents required executive escalation?",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_relationships=["ESCALATED_TO"],
            ),
            EvaluationQuery(
                id="IN-013",
                query_text="What was the customer impact of incident INC-2024-001?",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
            ),
            EvaluationQuery(
                id="IN-014",
                query_text="Show me incidents related to network issues",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_relationships=["CAUSED_BY"],
            ),
            EvaluationQuery(
                id="IN-015",
                query_text="What patterns exist in our incident history?",
                category=QueryCategory.INCIDENTS,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
            ),
        ]
    
    def _expertise_queries(self) -> List[EvaluationQuery]:
        """Generate 15 expertise queries."""
        return [
            EvaluationQuery(
                id="EX-001",
                query_text="Who are the experts on payment processing?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Payments Team"],
                expected_relationships=["EXPERT_IN", "MEMBER_OF"],
            ),
            EvaluationQuery(
                id="EX-002",
                query_text="Who knows the most about the Auth Service codebase?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Auth Service"],
                expected_relationships=["EXPERT_IN", "MAINTAINS"],
            ),
            EvaluationQuery(
                id="EX-003",
                query_text="Which engineers have Kubernetes expertise?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Kubernetes"],
                expected_relationships=["EXPERT_IN"],
            ),
            EvaluationQuery(
                id="EX-004",
                query_text="Who should I ask about database performance tuning?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_relationships=["EXPERT_IN"],
            ),
            EvaluationQuery(
                id="EX-005",
                query_text="What technologies does Alice Smith specialize in?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_relationships=["EXPERT_IN"],
            ),
            EvaluationQuery(
                id="EX-006",
                query_text="Who has experience with message queue systems?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Message Queue", "Kafka"],
                expected_relationships=["EXPERT_IN"],
            ),
            EvaluationQuery(
                id="EX-007",
                query_text="Which team members have machine learning expertise?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["ML Team"],
                expected_relationships=["EXPERT_IN", "MEMBER_OF"],
            ),
            EvaluationQuery(
                id="EX-008",
                query_text="Who can help with security vulnerabilities?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Security Team"],
                expected_relationships=["EXPERT_IN"],
            ),
            EvaluationQuery(
                id="EX-009",
                query_text="What skills are represented on the Platform Team?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["Platform Team"],
                expected_relationships=["MEMBER_OF", "EXPERT_IN"],
            ),
            EvaluationQuery(
                id="EX-010",
                query_text="Who has experience debugging distributed systems?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_relationships=["EXPERT_IN"],
            ),
            EvaluationQuery(
                id="EX-011",
                query_text="Which engineers have worked on similar problems before?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_relationships=["WORKED_ON", "EXPERT_IN"],
            ),
            EvaluationQuery(
                id="EX-012",
                query_text="Who can review code changes to the API Gateway?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.MEDIUM,
                hop_count=HopCount.MULTI,
                expected_entities=["API Gateway"],
                expected_relationships=["EXPERT_IN", "MAINTAINS"],
            ),
            EvaluationQuery(
                id="EX-013",
                query_text="What domains does the SRE team have expertise in?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["SRE Team"],
                expected_relationships=["EXPERT_IN"],
            ),
            EvaluationQuery(
                id="EX-014",
                query_text="Who are the subject matter experts for compliance?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.EASY,
                hop_count=HopCount.SINGLE,
                expected_entities=["Compliance Team"],
                expected_relationships=["EXPERT_IN"],
            ),
            EvaluationQuery(
                id="EX-015",
                query_text="Which engineers have both frontend and backend expertise?",
                category=QueryCategory.EXPERTISE,
                difficulty=DifficultyLevel.HARD,
                hop_count=HopCount.MULTI,
                expected_relationships=["EXPERT_IN"],
            ),
        ]
    
    def get_all_queries(self) -> List[EvaluationQuery]:
        """Get all 100 evaluation queries."""
        return self.queries
    
    def get_by_category(self, category: QueryCategory) -> List[EvaluationQuery]:
        """Get queries by category."""
        return [q for q in self.queries if q.category == category]
    
    def get_by_difficulty(self, difficulty: DifficultyLevel) -> List[EvaluationQuery]:
        """Get queries by difficulty level."""
        return [q for q in self.queries if q.difficulty == difficulty]
    
    def get_random_sample(self, n: int = 10) -> List[EvaluationQuery]:
        """Get a random sample of queries."""
        return random.sample(self.queries, min(n, len(self.queries)))
    
    def get_statistics(self) -> Dict:
        """Get statistics about the query set."""
        stats = {
            "total": len(self.queries),
            "by_category": {},
            "by_difficulty": {},
            "by_hop_count": {},
        }
        
        for cat in QueryCategory:
            count = len(self.get_by_category(cat))
            stats["by_category"][cat.value] = count
        
        for diff in DifficultyLevel:
            count = len(self.get_by_difficulty(diff))
            stats["by_difficulty"][diff.value] = count
        
        for hop in HopCount:
            count = len([q for q in self.queries if q.hop_count == hop])
            stats["by_hop_count"][hop.value] = count
        
        return stats
