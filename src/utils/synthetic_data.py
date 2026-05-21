"""
Synthetic data generator for Context Foundry MVP

Generates realistic IT operations data for testing the tri-memory architecture.
Walking skeleton: minimal but complete dataset
Full dataset: comprehensive testing dataset
"""

import json
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
from pathlib import Path


def generate_walking_skeleton_data() -> Dict[str, List[Dict[str, Any]]]:
    """
    Generate minimal synthetic data for walking skeleton testing

    Returns:
        Dict containing entities, relationships, documents, and rules
    """

    entities = []
    relationships = []
    documents = []
    rules = []

    # ============================================
    # SERVICES (5)
    # ============================================

    services = [
        {
            "id": str(uuid.uuid4()),
            "type": "Service",
            "name": "payment-api",
            "properties": {
                "description": "Handles payment processing",
                "environment": "production",
                "port": 8080,
                "health_endpoint": "/health"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "type": "Service",
            "name": "user-service",
            "properties": {
                "description": "User authentication and management",
                "environment": "production",
                "port": 8081,
                "health_endpoint": "/health"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "type": "Service",
            "name": "notification-service",
            "properties": {
                "description": "Sends email and SMS notifications",
                "environment": "production",
                "port": 8082,
                "health_endpoint": "/health"
            }
        }
    ]

    # ============================================
    # INFRASTRUCTURE COMPONENTS (3)
    # ============================================

    components = [
        {
            "id": str(uuid.uuid4()),
            "type": "Database",
            "name": "payments-db",
            "properties": {
                "engine": "PostgreSQL",
                "version": "14.5",
                "host": "db-prod-01.internal",
                "port": 5432
            }
        },
        {
            "id": str(uuid.uuid4()),
            "type": "Cache",
            "name": "session-cache",
            "properties": {
                "engine": "Redis",
                "version": "7.0",
                "host": "redis-prod-01.internal",
                "port": 6379
            }
        },
        {
            "id": str(uuid.uuid4()),
            "type": "Queue",
            "name": "notification-queue",
            "properties": {
                "engine": "RabbitMQ",
                "version": "3.11",
                "host": "mq-prod-01.internal",
                "port": 5672
            }
        }
    ]

    # ============================================
    # TEAMS (2)
    # ============================================

    teams = [
        {
            "id": str(uuid.uuid4()),
            "type": "Team",
            "name": "payments-team",
            "properties": {
                "slack_channel": "#payments",
                "on_call_schedule": "PagerDuty Schedule A"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "type": "Team",
            "name": "platform-team",
            "properties": {
                "slack_channel": "#platform",
                "on_call_schedule": "PagerDuty Schedule B"
            }
        }
    ]

    # ============================================
    # PEOPLE (4)
    # ============================================

    people = [
        {
            "id": str(uuid.uuid4()),
            "type": "Person",
            "name": "Alice Chen",
            "properties": {
                "email": "alice.chen@example.com",
                "role": "Senior Engineer"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "type": "Person",
            "name": "Bob Martinez",
            "properties": {
                "email": "bob.martinez@example.com",
                "role": "Staff Engineer"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "type": "Person",
            "name": "Carol Johnson",
            "properties": {
                "email": "carol.johnson@example.com",
                "role": "Platform Engineer"
            }
        },
        {
            "id": str(uuid.uuid4()),
            "type": "Person",
            "name": "David Kim",
            "properties": {
                "email": "david.kim@example.com",
                "role": "SRE"
            }
        }
    ]

    # Combine all entities
    entities = services + components + teams + people

    # ============================================
    # RELATIONSHIPS (15)
    # ============================================

    # Service dependencies
    relationships.append({
        "id": str(uuid.uuid4()),
        "source_id": next(s["id"] for s in services if s["name"] == "payment-api"),
        "target_id": next(c["id"] for c in components if c["name"] == "payments-db"),
        "type": "DEPENDS_ON",
        "properties": {
            "description": "Payment API uses PostgreSQL for persistence",
            "criticality": "high"
        }
    })

    relationships.append({
        "id": str(uuid.uuid4()),
        "source_id": next(s["id"] for s in services if s["name"] == "user-service"),
        "target_id": next(c["id"] for c in components if c["name"] == "session-cache"),
        "type": "DEPENDS_ON",
        "properties": {
            "description": "User service uses Redis for session management",
            "criticality": "high"
        }
    })

    relationships.append({
        "id": str(uuid.uuid4()),
        "source_id": next(s["id"] for s in services if s["name"] == "notification-service"),
        "target_id": next(c["id"] for c in components if c["name"] == "notification-queue"),
        "type": "DEPENDS_ON",
        "properties": {
            "description": "Notification service consumes from RabbitMQ queue",
            "criticality": "medium"
        }
    })

    # Service-to-service dependencies
    relationships.append({
        "id": str(uuid.uuid4()),
        "source_id": next(s["id"] for s in services if s["name"] == "payment-api"),
        "target_id": next(s["id"] for s in services if s["name"] == "user-service"),
        "type": "CALLS",
        "properties": {
            "description": "Payment API calls user service for authentication",
            "protocol": "HTTP"
        }
    })

    relationships.append({
        "id": str(uuid.uuid4()),
        "source_id": next(s["id"] for s in services if s["name"] == "payment-api"),
        "target_id": next(s["id"] for s in services if s["name"] == "notification-service"),
        "type": "CALLS",
        "properties": {
            "description": "Payment API triggers notifications on successful payment",
            "protocol": "async"
        }
    })

    # Team ownership
    relationships.append({
        "id": str(uuid.uuid4()),
        "source_id": next(t["id"] for t in teams if t["name"] == "payments-team"),
        "target_id": next(s["id"] for s in services if s["name"] == "payment-api"),
        "type": "OWNS",
        "properties": {}
    })

    relationships.append({
        "id": str(uuid.uuid4()),
        "source_id": next(t["id"] for t in teams if t["name"] == "payments-team"),
        "target_id": next(s["id"] for s in services if s["name"] == "user-service"),
        "type": "OWNS",
        "properties": {}
    })

    relationships.append({
        "id": str(uuid.uuid4()),
        "source_id": next(t["id"] for t in teams if t["name"] == "platform-team"),
        "target_id": next(c["id"] for c in components if c["name"] == "payments-db"),
        "type": "OWNS",
        "properties": {}
    })

    relationships.append({
        "id": str(uuid.uuid4()),
        "source_id": next(t["id"] for t in teams if t["name"] == "platform-team"),
        "target_id": next(c["id"] for c in components if c["name"] == "session-cache"),
        "type": "OWNS",
        "properties": {}
    })

    # Team membership
    relationships.append({
        "id": str(uuid.uuid4()),
        "source_id": next(p["id"] for p in people if p["name"] == "Alice Chen"),
        "target_id": next(t["id"] for t in teams if t["name"] == "payments-team"),
        "type": "MEMBER_OF",
        "properties": {}
    })

    relationships.append({
        "id": str(uuid.uuid4()),
        "source_id": next(p["id"] for p in people if p["name"] == "Bob Martinez"),
        "target_id": next(t["id"] for t in teams if t["name"] == "payments-team"),
        "type": "MEMBER_OF",
        "properties": {}
    })

    relationships.append({
        "id": str(uuid.uuid4()),
        "source_id": next(p["id"] for p in people if p["name"] == "Carol Johnson"),
        "target_id": next(t["id"] for t in teams if t["name"] == "platform-team"),
        "type": "MEMBER_OF",
        "properties": {}
    })

    relationships.append({
        "id": str(uuid.uuid4()),
        "source_id": next(p["id"] for p in people if p["name"] == "David Kim"),
        "target_id": next(t["id"] for t in teams if t["name"] == "platform-team"),
        "type": "MEMBER_OF",
        "properties": {}
    })

    # ============================================
    # DOCUMENTS (Incidents + Runbooks)
    # ============================================

    # Incident 1: Database connection pool exhaustion
    incident1_id = str(uuid.uuid4())
    documents.append({
        "id": incident1_id,
        "type": "incident",
        "title": "INC-2024-001: Payment API Database Connection Pool Exhausted",
        "content": """
Incident Summary:
On January 15, 2024, the payment-api service experienced degraded performance due to database connection pool exhaustion. The payments-db PostgreSQL instance was running at maximum connections.

Timeline:
- 14:23 UTC: Alert triggered for high latency on payment-api
- 14:25 UTC: On-call engineer Alice Chen investigated
- 14:30 UTC: Identified connection pool exhaustion in payments-db
- 14:35 UTC: Increased max_connections from 100 to 200
- 14:40 UTC: Service recovered

Root Cause:
A recent code change introduced a connection leak in the payment processing logic. Connections were not being properly released back to the pool after transactions completed.

Resolution:
1. Increased database max_connections as temporary mitigation
2. Deployed hotfix to fix connection leak
3. Monitored for 24 hours to confirm stability

Affected Services: payment-api, payments-db
Owner: Alice Chen
Status: Resolved
        """,
        "metadata": {
            "severity": "high",
            "created_at": "2024-01-15T14:23:00Z",
            "resolved_at": "2024-01-15T15:00:00Z",
            "responders": ["Alice Chen"],
            "services_affected": ["payment-api", "payments-db"]
        }
    })

    # Incident 2: Redis cache eviction causing cascading failures
    incident2_id = str(uuid.uuid4())
    documents.append({
        "id": incident2_id,
        "type": "incident",
        "title": "INC-2024-002: Session Cache Eviction Cascade",
        "content": """
Incident Summary:
On January 20, 2024, the session-cache Redis instance experienced memory pressure and began aggressively evicting keys. This caused the user-service to make excessive database queries, which then impacted the payment-api service.

Timeline:
- 10:15 UTC: Monitoring alerts for high Redis eviction rate
- 10:17 UTC: user-service latency increased from 50ms to 2000ms
- 10:20 UTC: payment-api started timing out on authentication calls
- 10:25 UTC: David Kim scaled Redis instance vertically
- 10:35 UTC: Services recovered

Root Cause:
Session cache was undersized for current traffic levels. No capacity alerts were configured.

Resolution:
1. Increased Redis memory from 8GB to 16GB
2. Added capacity monitoring alerts
3. Implemented circuit breaker in payment-api for user-service calls

Affected Services: session-cache, user-service, payment-api
Owner: David Kim
Status: Resolved
        """,
        "metadata": {
            "severity": "critical",
            "created_at": "2024-01-20T10:15:00Z",
            "resolved_at": "2024-01-20T11:00:00Z",
            "responders": ["David Kim", "Carol Johnson"],
            "services_affected": ["session-cache", "user-service", "payment-api"]
        }
    })

    # Runbook 1: Database connection troubleshooting
    runbook1_id = str(uuid.uuid4())
    documents.append({
        "id": runbook1_id,
        "type": "runbook",
        "title": "RUNBOOK: Troubleshooting Database Connection Issues",
        "content": """
Purpose: Diagnose and resolve database connection problems

Common Symptoms:
- High latency in services that depend on database
- Connection timeout errors in application logs
- Database connection pool exhaustion

Diagnostic Steps:

1. Check Current Connections:
   - Run: SELECT count(*) FROM pg_stat_activity;
   - Compare against max_connections setting

2. Identify Long-Running Queries:
   - Run: SELECT pid, query, state, query_start FROM pg_stat_activity WHERE state != 'idle' ORDER BY query_start;

3. Check Connection Pool Settings:
   - Verify application pool size configuration
   - Typical: min_size=2, max_size=10 per instance

Remediation:

If connection pool exhausted:
1. TEMPORARY: Increase max_connections on database
   - ALTER SYSTEM SET max_connections = 200;
   - Requires restart: systemctl restart postgresql

2. LONG-TERM: Fix connection leaks in application code
   - Ensure connections are properly closed in finally blocks
   - Add connection timeout settings

If long-running queries blocking connections:
1. Identify blocking query PID
2. Terminate if safe: SELECT pg_terminate_backend(PID);
3. Investigate query performance

Escalation:
Contact platform-team (#platform channel) if database-level intervention needed.

Related Services: payment-api, user-service, payments-db
Owner: Platform Team
        """,
        "metadata": {
            "category": "database",
            "last_updated": "2024-01-16T00:00:00Z",
            "author": "Carol Johnson"
        }
    })

    # Runbook 2: Redis cache operations
    runbook2_id = str(uuid.uuid4())
    documents.append({
        "id": runbook2_id,
        "type": "runbook",
        "title": "RUNBOOK: Redis Cache Operations and Troubleshooting",
        "content": """
Purpose: Manage and troubleshoot Redis cache instances

Common Issues:

1. High Eviction Rate
   Symptom: Increased cache misses, degraded application performance
   Cause: Cache is full and evicting keys to make room

   Diagnostic:
   - Check memory usage: INFO memory
   - Check eviction count: INFO stats | grep evicted_keys

   Resolution:
   - Short-term: Increase maxmemory setting
   - Long-term: Scale Redis instance or optimize cache usage

2. Connection Timeouts
   Symptom: Application logs show Redis connection errors
   Cause: Network issues or Redis overloaded

   Diagnostic:
   - Check Redis latency: redis-cli --latency
   - Check connection count: INFO clients

   Resolution:
   - Verify network connectivity
   - Check for slow commands: SLOWLOG GET 10
   - Consider read replicas for high read loads

Best Practices:
- Set appropriate TTLs on all keys
- Monitor memory usage and set alerts at 75%
- Use connection pooling in applications
- Implement circuit breakers for cache failures

Service Dependencies:
- user-service depends on session-cache for session management
- Payment flows remain functional even if cache unavailable (degraded performance)

Escalation:
Contact platform-team if scaling required.

Related Services: session-cache, user-service
Owner: Platform Team
        """,
        "metadata": {
            "category": "cache",
            "last_updated": "2024-01-21T00:00:00Z",
            "author": "David Kim"
        }
    })

    # ============================================
    # SYMBOLIC RULES
    # ============================================

    rules = [
        {
            "id": str(uuid.uuid4()),
            "name": "service_must_have_owner",
            "type": "invariant",
            "expression": {
                "condition": "ALL services MUST have at least one OWNS relationship from a team"
            },
            "description": "Every service must be owned by at least one team",
            "priority": 10,
            "applies_to": ["Service"]
        },
        {
            "id": str(uuid.uuid4()),
            "name": "database_single_primary",
            "type": "invariant",
            "expression": {
                "condition": "Each service can DEPENDS_ON at most one Database with role=primary"
            },
            "description": "Services should have a single primary database",
            "priority": 8,
            "applies_to": ["Service", "Database"]
        },
        {
            "id": str(uuid.uuid4()),
            "name": "critical_dependency_requires_circuit_breaker",
            "type": "safety",
            "expression": {
                "condition": "If service A DEPENDS_ON service B with criticality=high, A must implement circuit breaker"
            },
            "description": "High criticality dependencies require circuit breakers",
            "priority": 7,
            "applies_to": ["Service"]
        },
        {
            "id": str(uuid.uuid4()),
            "name": "incident_severity_escalation",
            "type": "escalation",
            "expression": {
                "condition": "Critical incidents unresolved for >30min require manager escalation"
            },
            "description": "Critical incidents have time-based escalation policy",
            "priority": 9,
            "applies_to": ["Incident"]
        }
    ]

    return {
        "entities": entities,
        "relationships": relationships,
        "documents": documents,
        "rules": rules,
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "dataset_type": "walking_skeleton",
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "document_count": len(documents),
            "rule_count": len(rules)
        }
    }


def save_walking_skeleton_data(output_dir: str = "data"):
    """Generate and save walking skeleton data to JSON files"""

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    data = generate_walking_skeleton_data()

    # Save each component separately
    with open(f"{output_dir}/entities.json", "w") as f:
        json.dump(data["entities"], f, indent=2)

    with open(f"{output_dir}/relationships.json", "w") as f:
        json.dump(data["relationships"], f, indent=2)

    with open(f"{output_dir}/documents.json", "w") as f:
        json.dump(data["documents"], f, indent=2)

    with open(f"{output_dir}/rules.json", "w") as f:
        json.dump(data["rules"], f, indent=2)

    # Save combined dataset
    with open(f"{output_dir}/walking_skeleton.json", "w") as f:
        json.dump(data, f, indent=2)

    print("\n" + "="*50)
    print("Walking Skeleton Data Generated")
    print("="*50)
    print(f"Entities: {data['metadata']['entity_count']}")
    print(f"Relationships: {data['metadata']['relationship_count']}")
    print(f"Documents: {data['metadata']['document_count']}")
    print(f"Rules: {data['metadata']['rule_count']}")
    print(f"\nFiles saved to: {output_dir}/")
    print("="*50 + "\n")

    return data


def generate_scaled_data() -> Dict[str, List[Dict[str, Any]]]:
    """
    Generate scaled synthetic data for MVP 2 (500 entities)

    Includes:
    - Realistic IT ops scenarios
    - Incident chains (incidents causing other incidents)
    - Deployment dependencies (services that deploy together)
    - Runbook coverage gaps (some services lack runbooks)

    Returns:
        Dict containing entities, relationships, documents, and rules
    """

    entities = []
    relationships = []
    documents = []
    rules = []

    # ============================================
    # SERVICES (50 total)
    # ============================================

    # Core services
    core_services = [
        ("auth-service", "Authentication and authorization", 8080, "core"),
        ("user-service", "User profile management", 8081, "core"),
        ("account-service", "Account management", 8082, "core"),
        ("session-service", "Session management", 8083, "core"),
    ]

    # Payment services
    payment_services = [
        ("payment-api", "Payment processing API", 9000, "payments"),
        ("payment-processor", "Background payment processor", 9001, "payments"),
        ("refund-service", "Refund processing", 9002, "payments"),
        ("invoice-service", "Invoice generation", 9003, "payments"),
        ("billing-service", "Subscription billing", 9004, "payments"),
        ("payment-gateway", "External payment gateway integration", 9005, "payments"),
    ]

    # Notification services
    notification_services = [
        ("notification-service", "Notification orchestrator", 10000, "notifications"),
        ("email-worker", "Email sending worker", 10001, "notifications"),
        ("sms-worker", "SMS sending worker", 10002, "notifications"),
        ("push-worker", "Push notification worker", 10003, "notifications"),
        ("webhook-dispatcher", "Webhook delivery service", 10004, "notifications"),
    ]

    # Data services
    data_services = [
        ("analytics-ingestion", "Analytics event ingestion", 11000, "data"),
        ("analytics-processor", "Analytics data processor", 11001, "data"),
        ("reporting-service", "Report generation", 11002, "data"),
        ("data-export-service", "Data export API", 11003, "data"),
        ("search-indexer", "Search index builder", 11004, "data"),
        ("search-api", "Search query API", 11005, "data"),
    ]

    # Integration services
    integration_services = [
        ("crm-sync", "CRM synchronization", 12000, "integrations"),
        ("erp-connector", "ERP system connector", 12001, "integrations"),
        ("marketplace-api", "Marketplace integration", 12002, "integrations"),
        ("partner-api", "Partner API gateway", 12003, "integrations"),
    ]

    # Infrastructure services
    infra_services = [
        ("api-gateway", "Main API gateway", 8000, "platform"),
        ("service-mesh-control", "Service mesh control plane", 8500, "platform"),
        ("config-service", "Configuration management", 8600, "platform"),
        ("secrets-service", "Secrets management", 8700, "platform"),
        ("monitoring-collector", "Metrics collector", 8800, "platform"),
        ("log-aggregator", "Log aggregation service", 8900, "platform"),
    ]

    # Background jobs
    background_jobs = [
        ("daily-report-job", "Daily report generation cron", 0, "jobs"),
        ("cleanup-job", "Data cleanup cron", 0, "jobs"),
        ("backup-job", "Database backup cron", 0, "jobs"),
        ("health-check-job", "Service health checker", 0, "jobs"),
        ("cache-warmer-job", "Cache warming cron", 0, "jobs"),
        ("reconciliation-job", "Data reconciliation", 0, "jobs"),
    ]

    # ML services
    ml_services = [
        ("fraud-detection", "Fraud detection model service", 13000, "ml"),
        ("recommendation-engine", "Product recommendation engine", 13001, "ml"),
        ("churn-predictor", "Customer churn prediction", 13002, "ml"),
        ("sentiment-analyzer", "Sentiment analysis service", 13003, "ml"),
    ]

    # Customer-facing services
    customer_services = [
        ("web-frontend", "Main web application", 3000, "frontend"),
        ("mobile-api", "Mobile app backend", 4000, "frontend"),
        ("admin-portal", "Admin dashboard", 5000, "frontend"),
        ("customer-support-portal", "Support portal", 5001, "frontend"),
    ]

    all_service_defs = (core_services + payment_services + notification_services +
                       data_services + integration_services + infra_services +
                       background_jobs + ml_services + customer_services)

    services = []
    for name, desc, port, category in all_service_defs:
        services.append({
            "id": str(uuid.uuid4()),
            "type": "Service",
            "name": name,
            "properties": {
                "description": desc,
                "environment": "production",
                "port": port if port > 0 else None,
                "category": category,
                "health_endpoint": "/health" if port > 0 else None
            }
        })

    # ============================================
    # INFRASTRUCTURE COMPONENTS (100+)
    # ============================================

    # Databases
    databases = [
        ("auth-db", "PostgreSQL", "14.5", "Stores user credentials and sessions"),
        ("users-db", "PostgreSQL", "14.5", "User profile data"),
        ("payments-db", "PostgreSQL", "14.5", "Payment transactions"),
        ("billing-db", "PostgreSQL", "14.5", "Subscription and billing data"),
        ("analytics-db", "PostgreSQL", "14.5", "Analytics data warehouse"),
        ("reporting-db", "PostgreSQL", "13.8", "Reporting database"),
        ("audit-db", "PostgreSQL", "14.5", "Audit logs"),
        ("config-db", "PostgreSQL", "14.5", "Configuration data"),
        ("products-db", "MySQL", "8.0", "Product catalog"),
        ("inventory-db", "MySQL", "8.0", "Inventory management"),
        ("orders-db", "PostgreSQL", "14.5", "Order history"),
        ("crm-db", "PostgreSQL", "14.5", "CRM data"),
    ]

    # Read replicas
    read_replicas = [
        ("auth-db-replica-1", "PostgreSQL", "14.5", "Auth DB read replica"),
        ("auth-db-replica-2", "PostgreSQL", "14.5", "Auth DB read replica"),
        ("payments-db-replica-1", "PostgreSQL", "14.5", "Payments DB read replica"),
        ("users-db-replica-1", "PostgreSQL", "14.5", "Users DB read replica"),
        ("analytics-db-replica-1", "PostgreSQL", "14.5", "Analytics DB read replica"),
    ]

    # Caches
    caches = [
        ("session-cache", "Redis", "7.0", "User session cache"),
        ("api-cache", "Redis", "7.0", "API response cache"),
        ("auth-cache", "Redis", "7.0", "Authentication cache"),
        ("product-cache", "Redis", "7.0", "Product catalog cache"),
        ("search-cache", "Redis", "7.0", "Search results cache"),
        ("rate-limit-cache", "Redis", "7.0", "Rate limiting state"),
    ]

    # Message queues
    queues = [
        ("notification-queue", "RabbitMQ", "3.11", "Notification messages"),
        ("email-queue", "RabbitMQ", "3.11", "Email sending queue"),
        ("payment-events", "Kafka", "3.4", "Payment event stream"),
        ("audit-events", "Kafka", "3.4", "Audit event stream"),
        ("analytics-events", "Kafka", "3.4", "Analytics event stream"),
        ("webhook-queue", "RabbitMQ", "3.11", "Webhook delivery queue"),
        ("dead-letter-queue", "RabbitMQ", "3.11", "Failed message DLQ"),
    ]

    # Load balancers
    load_balancers = [
        ("api-lb-1", "HAProxy", "2.6", "API gateway load balancer"),
        ("web-lb-1", "HAProxy", "2.6", "Web frontend load balancer"),
        ("internal-lb-1", "HAProxy", "2.6", "Internal services load balancer"),
    ]

    # Object storage
    object_stores = [
        ("user-uploads-bucket", "S3", "n/a", "User uploaded files"),
        ("backups-bucket", "S3", "n/a", "Database backups"),
        ("logs-bucket", "S3", "n/a", "Archived logs"),
        ("reports-bucket", "S3", "n/a", "Generated reports"),
    ]

    # Service mesh
    service_mesh = [
        ("istio-ingress", "Istio", "1.18", "Service mesh ingress gateway"),
        ("istio-egress", "Istio", "1.18", "Service mesh egress gateway"),
    ]

    # Monitoring
    monitoring = [
        ("prometheus-1", "Prometheus", "2.45", "Metrics storage"),
        ("grafana-1", "Grafana", "10.0", "Metrics visualization"),
        ("alertmanager-1", "Alertmanager", "0.26", "Alert routing"),
        ("jaeger-1", "Jaeger", "1.47", "Distributed tracing"),
    ]

    components = []
    for name, engine, version, desc in (databases + read_replicas):
        components.append({
            "id": str(uuid.uuid4()),
            "type": "Database",
            "name": name,
            "properties": {
                "engine": engine,
                "version": version,
                "description": desc,
                "replica": "replica" in name
            }
        })

    for name, engine, version, desc in caches:
        components.append({
            "id": str(uuid.uuid4()),
            "type": "Cache",
            "name": name,
            "properties": {
                "engine": engine,
                "version": version,
                "description": desc
            }
        })

    for name, engine, version, desc in queues:
        components.append({
            "id": str(uuid.uuid4()),
            "type": "Queue",
            "name": name,
            "properties": {
                "engine": engine,
                "version": version,
                "description": desc
            }
        })

    for name, engine, version, desc in (load_balancers + service_mesh + monitoring):
        components.append({
            "id": str(uuid.uuid4()),
            "type": "Infrastructure",
            "name": name,
            "properties": {
                "engine": engine,
                "version": version,
                "description": desc
            }
        })

    for name, engine, version, desc in object_stores:
        components.append({
            "id": str(uuid.uuid4()),
            "type": "Storage",
            "name": name,
            "properties": {
                "engine": engine,
                "version": version,
                "description": desc
            }
        })

    # ============================================
    # TEAMS (20)
    # ============================================

    team_defs = [
        ("platform-team", "#platform", "PagerDuty Schedule Platform", "Platform infrastructure and services"),
        ("payments-team", "#payments", "PagerDuty Schedule Payments", "Payment processing services"),
        ("auth-team", "#auth", "PagerDuty Schedule Auth", "Authentication and authorization"),
        ("data-team", "#data", "PagerDuty Schedule Data", "Analytics and reporting"),
        ("notifications-team", "#notifications", "PagerDuty Schedule Notifications", "Notification services"),
        ("integrations-team", "#integrations", "PagerDuty Schedule Integrations", "Third-party integrations"),
        ("ml-team", "#ml", "PagerDuty Schedule ML", "Machine learning services"),
        ("frontend-team", "#frontend", "PagerDuty Schedule Frontend", "Web and mobile frontends"),
        ("api-team", "#api", "PagerDuty Schedule API", "API gateway and infrastructure"),
        ("sre-team", "#sre", "PagerDuty Schedule SRE", "Site reliability engineering"),
        ("data-platform-team", "#data-platform", "PagerDuty Schedule Data Platform", "Data infrastructure"),
        ("security-team", "#security", "PagerDuty Schedule Security", "Security services"),
        ("devops-team", "#devops", "PagerDuty Schedule DevOps", "CI/CD and deployment"),
        ("monitoring-team", "#monitoring", "PagerDuty Schedule Monitoring", "Observability stack"),
        ("customer-success-team", "#customer-success", "PagerDuty Schedule CS", "Customer-facing services"),
        ("product-team", "#product", "PagerDuty Schedule Product", "Product management"),
        ("billing-team", "#billing", "PagerDuty Schedule Billing", "Billing and subscriptions"),
        ("search-team", "#search", "PagerDuty Schedule Search", "Search infrastructure"),
        ("support-tools-team", "#support-tools", "PagerDuty Schedule Support", "Internal tools"),
        ("compliance-team", "#compliance", "PagerDuty Schedule Compliance", "Compliance and audit"),
    ]

    teams = []
    for name, slack, pagerduty, desc in team_defs:
        teams.append({
            "id": str(uuid.uuid4()),
            "type": "Team",
            "name": name,
            "properties": {
                "slack_channel": slack,
                "on_call_schedule": pagerduty,
                "description": desc
            }
        })

    # ============================================
    # PEOPLE (150+)
    # ============================================

    # Generate realistic names and roles
    first_names = [
        "Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Henry",
        "Iris", "Jack", "Kate", "Leo", "Maria", "Nathan", "Olivia", "Peter",
        "Quinn", "Rachel", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xavier",
        "Yara", "Zoe", "Alex", "Blake", "Cameron", "Drew", "Eli", "Finn",
        "Gia", "Harper", "Ira", "Jordan", "Kai", "Logan", "Morgan", "Nico",
        "Parker", "Quinn", "Riley", "Sage", "Taylor", "Avery", "Bailey", "Casey"
    ]

    last_names = [
        "Chen", "Martinez", "Johnson", "Kim", "Patel", "Garcia", "Rodriguez", "Lee",
        "Davis", "Wilson", "Anderson", "Taylor", "Thomas", "Moore", "Jackson", "Martin",
        "Thompson", "White", "Harris", "Clark", "Lewis", "Walker", "Hall", "Allen",
        "Young", "King", "Wright", "Lopez", "Hill", "Scott", "Green", "Adams",
        "Baker", "Nelson", "Carter", "Mitchell", "Roberts", "Turner", "Phillips", "Campbell"
    ]

    roles = [
        "Senior Engineer", "Staff Engineer", "Principal Engineer", "Engineering Manager",
        "Senior SRE", "SRE", "Platform Engineer", "Backend Engineer", "Frontend Engineer",
        "Data Engineer", "ML Engineer", "Security Engineer", "DevOps Engineer",
        "Tech Lead", "Architect", "VP Engineering"
    ]

    people = []
    import random
    random.seed(42)  # For reproducibility

    for i in range(150):
        first = random.choice(first_names)
        last = random.choice(last_names)
        role = random.choice(roles)
        name = f"{first} {last}"
        email = f"{first.lower()}.{last.lower()}{i}@example.com"

        people.append({
            "id": str(uuid.uuid4()),
            "type": "Person",
            "name": name,
            "properties": {
                "email": email,
                "role": role
            }
        })

    # Combine all entities
    entities = services + components + teams + people

    print(f"Generated {len(services)} services")
    print(f"Generated {len(components)} infrastructure components")
    print(f"Generated {len(teams)} teams")
    print(f"Generated {len(people)} people")
    print(f"Total entities: {len(entities)}")

    # ============================================
    # RELATIONSHIPS
    # ============================================

    # Helper function to find entity by name
    def find_entity(name, entity_list=entities):
        for e in entity_list:
            if e["name"] == name:
                return e["id"]
        return None

    # Service dependencies on databases
    service_db_deps = [
        ("auth-service", "auth-db", "high"),
        ("user-service", "users-db", "high"),
        ("payment-api", "payments-db", "critical"),
        ("payment-processor", "payments-db", "critical"),
        ("billing-service", "billing-db", "high"),
        ("analytics-processor", "analytics-db", "medium"),
        ("reporting-service", "reporting-db", "medium"),
        ("search-api", "products-db", "medium"),
    ]

    for svc, db, crit in service_db_deps:
        svc_id = find_entity(svc)
        db_id = find_entity(db)
        if svc_id and db_id:
            relationships.append({
                "id": str(uuid.uuid4()),
                "source_id": svc_id,
                "target_id": db_id,
                "type": "DEPENDS_ON",
                "properties": {"criticality": crit}
            })

    # Service dependencies on caches
    cache_deps = [
        ("auth-service", "auth-cache"),
        ("user-service", "session-cache"),
        ("payment-api", "api-cache"),
        ("search-api", "search-cache"),
    ]

    for svc, cache in cache_deps:
        svc_id = find_entity(svc)
        cache_id = find_entity(cache)
        if svc_id and cache_id:
            relationships.append({
                "id": str(uuid.uuid4()),
                "source_id": svc_id,
                "target_id": cache_id,
                "type": "DEPENDS_ON",
                "properties": {"criticality": "medium"}
            })

    # Service-to-service calls
    service_calls = [
        ("payment-api", "user-service"),
        ("payment-api", "notification-service"),
        ("billing-service", "payment-api"),
        ("refund-service", "payment-api"),
        ("api-gateway", "auth-service"),
        ("api-gateway", "user-service"),
        ("api-gateway", "payment-api"),
        ("web-frontend", "api-gateway"),
        ("mobile-api", "api-gateway"),
    ]

    for src, tgt in service_calls:
        src_id = find_entity(src)
        tgt_id = find_entity(tgt)
        if src_id and tgt_id:
            relationships.append({
                "id": str(uuid.uuid4()),
                "source_id": src_id,
                "target_id": tgt_id,
                "type": "CALLS",
                "properties": {}
            })

    # Team ownership (assign services to teams)
    ownership_map = {
        "platform-team": ["api-gateway", "config-service", "secrets-service"],
        "payments-team": ["payment-api", "payment-processor", "refund-service", "billing-service"],
        "auth-team": ["auth-service", "session-service"],
        "data-team": ["analytics-processor", "reporting-service", "data-export-service"],
        "notifications-team": ["notification-service", "email-worker", "sms-worker"],
        "frontend-team": ["web-frontend", "mobile-api", "admin-portal"],
        "sre-team": ["monitoring-collector", "log-aggregator"],
    }

    for team_name, svc_list in ownership_map.items():
        team_id = find_entity(team_name)
        if team_id:
            for svc_name in svc_list:
                svc_id = find_entity(svc_name)
                if svc_id:
                    relationships.append({
                        "id": str(uuid.uuid4()),
                        "source_id": team_id,
                        "target_id": svc_id,
                        "type": "OWNS",
                        "properties": {}
                    })

    # Team membership (assign people to teams)
    people_per_team = len(people) // len(teams)
    for i, person in enumerate(people):
        team_idx = i // people_per_team
        if team_idx < len(teams):
            relationships.append({
                "id": str(uuid.uuid4()),
                "source_id": person["id"],
                "target_id": teams[team_idx]["id"],
                "type": "MEMBER_OF",
                "properties": {}
            })

    # Deployment groups (services that deploy together)
    deployment_groups = [
        ["payment-api", "payment-processor", "refund-service"],
        ["notification-service", "email-worker", "sms-worker", "push-worker"],
        ["analytics-ingestion", "analytics-processor"],
    ]

    for group in deployment_groups:
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                src_id = find_entity(group[i])
                tgt_id = find_entity(group[j])
                if src_id and tgt_id:
                    relationships.append({
                        "id": str(uuid.uuid4()),
                        "source_id": src_id,
                        "target_id": tgt_id,
                        "type": "DEPLOYS_WITH",
                        "properties": {}
                    })

    print(f"Generated {len(relationships)} relationships")

    # ============================================
    # DOCUMENTS (Incidents + Runbooks)
    # ============================================

    # Generate incident chain
    incidents = [
        {
            "id": str(uuid.uuid4()),
            "external_id": "INC-2024-001",
            "title": "Payment API Database Connection Pool Exhausted",
            "severity": "high",
            "affected": ["payment-api", "payments-db"],
            "responder": people[0]["name"],
            "caused_by": None,
            "summary": "Database connection pool exhaustion causing payment processing delays"
        },
        {
            "id": str(uuid.uuid4()),
            "external_id": "INC-2024-002",
            "title": "Session Cache Eviction Cascade",
            "severity": "critical",
            "affected": ["session-cache", "user-service", "auth-service"],
            "responder": people[1]["name"],
            "caused_by": None,
            "summary": "Redis cache eviction causing authentication service degradation"
        },
        {
            "id": str(uuid.uuid4()),
            "external_id": "INC-2024-003",
            "title": "API Gateway High Latency",
            "severity": "critical",
            "affected": ["api-gateway", "web-frontend", "mobile-api"],
            "responder": people[2]["name"],
            "caused_by": "INC-2024-002",  # Caused by session cache issue
            "summary": "API gateway experiencing high latency due to upstream cache failures"
        },
        {
            "id": str(uuid.uuid4()),
            "external_id": "INC-2024-004",
            "title": "Notification Queue Backlog",
            "severity": "medium",
            "affected": ["notification-queue", "email-worker"],
            "responder": people[3]["name"],
            "caused_by": None,
            "summary": "Email worker unable to keep up with notification queue"
        },
        {
            "id": str(uuid.uuid4()),
            "external_id": "INC-2024-005",
            "title": "Payment Processing Delays",
            "severity": "high",
            "affected": ["payment-api", "billing-service"],
            "responder": people[0]["name"],
            "caused_by": "INC-2024-004",  # Caused by notification backlog
            "summary": "Payment confirmations delayed due to notification service issues"
        },
    ]

    for inc in incidents:
        content = f"""
Incident Summary:
{inc['summary']}

External ID: {inc['external_id']}
Severity: {inc['severity']}
Affected Services: {', '.join(inc['affected'])}
Responder: {inc['responder']}

Status: Resolved
"""
        if inc['caused_by']:
            content += f"\nCaused By: {inc['caused_by']}\n"

        documents.append({
            "id": inc["id"],
            "type": "incident",
            "title": f"{inc['external_id']}: {inc['title']}",
            "content": content,
            "metadata": {
                "external_id": inc["external_id"],
                "severity": inc["severity"],
                "services_affected": inc["affected"],
                "responder": inc["responder"]
            }
        })

    # Add CAUSED_BY relationships for incident chains
    for inc in incidents:
        if inc['caused_by']:
            caused_by_inc = next((i for i in incidents if i['external_id'] == inc['caused_by']), None)
            if caused_by_inc:
                relationships.append({
                    "id": str(uuid.uuid4()),
                    "source_id": inc["id"],
                    "target_id": caused_by_inc["id"],
                    "type": "CAUSED_BY",
                    "properties": {}
                })

    # Generate runbooks (but NOT for all services - coverage gaps!)
    runbooks = [
        {
            "title": "RUNBOOK: Database Connection Troubleshooting",
            "category": "database",
            "services": ["payment-api", "user-service", "auth-service"],
            "content": "Diagnostic steps for database connection issues..."
        },
        {
            "title": "RUNBOOK: Redis Cache Operations",
            "category": "cache",
            "services": ["session-cache", "api-cache"],
            "content": "How to manage and troubleshoot Redis cache..."
        },
        {
            "title": "RUNBOOK: API Gateway Troubleshooting",
            "category": "api",
            "services": ["api-gateway"],
            "content": "Diagnosing API gateway performance issues..."
        },
        # Note: No runbook for notification-service or payment-processor (coverage gaps!)
    ]

    for rb in runbooks:
        documents.append({
            "id": str(uuid.uuid4()),
            "type": "runbook",
            "title": rb["title"],
            "content": rb["content"],
            "metadata": {
                "category": rb["category"],
                "services_covered": rb["services"]
            }
        })

    print(f"Generated {len(documents)} documents ({len(incidents)} incidents, {len(runbooks)} runbooks)")
    print(f"Note: Runbook coverage gaps exist for some services (intentional)")

    # ============================================
    # SYMBOLIC RULES
    # ============================================

    rules = [
        {
            "id": str(uuid.uuid4()),
            "name": "service_must_have_owner",
            "type": "invariant",
            "expression": {"condition": "ALL services MUST have at least one OWNS relationship from a team"},
            "description": "Every service must be owned by at least one team",
            "priority": 10,
            "applies_to": ["Service"]
        },
        {
            "id": str(uuid.uuid4()),
            "name": "critical_service_requires_runbook",
            "type": "safety",
            "expression": {"condition": "Services with criticality=critical MUST have at least one runbook"},
            "description": "Critical services require operational runbooks",
            "priority": 9,
            "applies_to": ["Service"]
        },
        {
            "id": str(uuid.uuid4()),
            "name": "database_single_primary",
            "type": "invariant",
            "expression": {"condition": "Each service can DEPENDS_ON at most one Database with role=primary"},
            "description": "Services should have a single primary database",
            "priority": 8,
            "applies_to": ["Service", "Database"]
        },
        {
            "id": str(uuid.uuid4()),
            "name": "incident_must_have_responder",
            "type": "invariant",
            "expression": {"condition": "All incidents MUST have at least one assigned responder"},
            "description": "Every incident must be assigned to someone",
            "priority": 10,
            "applies_to": ["Incident"]
        },
        {
            "id": str(uuid.uuid4()),
            "name": "critical_incident_escalation",
            "type": "escalation",
            "expression": {"condition": "Critical incidents unresolved for >30min require manager escalation"},
            "description": "Critical incidents have time-based escalation policy",
            "priority": 9,
            "applies_to": ["Incident"]
        },
    ]

    return {
        "entities": entities,
        "relationships": relationships,
        "documents": documents,
        "rules": rules,
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "dataset_type": "scaled_mvp2",
            "entity_count": len(entities),
            "relationship_count": len(relationships),
            "document_count": len(documents),
            "rule_count": len(rules),
            "breakdown": {
                "services": len(services),
                "components": len(components),
                "teams": len(teams),
                "people": len(people)
            }
        }
    }


def save_scaled_data(output_dir: str = "data/scaled"):
    """Generate and save scaled data to JSON files"""

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    data = generate_scaled_data()

    # Save each component separately
    with open(f"{output_dir}/entities.json", "w") as f:
        json.dump(data["entities"], f, indent=2)

    with open(f"{output_dir}/relationships.json", "w") as f:
        json.dump(data["relationships"], f, indent=2)

    with open(f"{output_dir}/documents.json", "w") as f:
        json.dump(data["documents"], f, indent=2)

    with open(f"{output_dir}/rules.json", "w") as f:
        json.dump(data["rules"], f, indent=2)

    # Save combined dataset
    with open(f"{output_dir}/scaled_data.json", "w") as f:
        json.dump(data, f, indent=2)

    print("\n" + "="*60)
    print("SCALED DATA GENERATED (MVP 2)")
    print("="*60)
    print(f"Total Entities: {data['metadata']['entity_count']}")
    print(f"  - Services: {data['metadata']['breakdown']['services']}")
    print(f"  - Infrastructure: {data['metadata']['breakdown']['components']}")
    print(f"  - Teams: {data['metadata']['breakdown']['teams']}")
    print(f"  - People: {data['metadata']['breakdown']['people']}")
    print(f"\nRelationships: {data['metadata']['relationship_count']}")
    print(f"Documents: {data['metadata']['document_count']}")
    print(f"Rules: {data['metadata']['rule_count']}")
    print(f"\nFiles saved to: {output_dir}/")
    print("="*60 + "\n")

    return data


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "scaled":
        save_scaled_data()
    else:
        save_walking_skeleton_data()
