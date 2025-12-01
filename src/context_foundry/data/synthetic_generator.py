"""
Synthetic IT Operations Data Generator.
Creates a realistic fictional IT environment for testing multi-hop queries.
"""
import uuid
from datetime import datetime, timedelta
import random
from typing import List, Dict, Tuple


def generate_synthetic_data() -> Dict:
    """
    Generate synthetic IT operations data.
    
    Target: 10 services, 5 teams, 20 people, 20 incidents, 5 runbooks
    With realistic dependencies and relationships for multi-hop queries.
    """
    
    teams = [
        {
            "id": str(uuid.uuid4()),
            "name": "Platform Team",
            "entity_type": "TEAM",
            "properties": {"slack_channel": "#platform-team", "on_call_rotation": "weekly"},
            "description": "Responsible for core platform infrastructure and databases"
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Payments Team",
            "entity_type": "TEAM",
            "properties": {"slack_channel": "#payments-team", "on_call_rotation": "daily"},
            "description": "Handles all payment processing and financial transactions"
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Authentication Team",
            "entity_type": "TEAM",
            "properties": {"slack_channel": "#auth-team", "on_call_rotation": "weekly"},
            "description": "Manages user authentication, authorization, and identity"
        },
        {
            "id": str(uuid.uuid4()),
            "name": "API Team",
            "entity_type": "TEAM",
            "properties": {"slack_channel": "#api-team", "on_call_rotation": "weekly"},
            "description": "Develops and maintains public and internal APIs"
        },
        {
            "id": str(uuid.uuid4()),
            "name": "SRE Team",
            "entity_type": "TEAM",
            "properties": {"slack_channel": "#sre-team", "on_call_rotation": "daily", "pagerduty": "sre-escalation"},
            "description": "Site Reliability Engineering - handles incidents and system health"
        }
    ]
    
    people = [
        {"id": str(uuid.uuid4()), "name": "Sarah Chen", "entity_type": "PERSON", "properties": {"role": "Tech Lead", "team": "Platform Team", "phone": "+1-555-0101", "expertise": ["PostgreSQL", "Redis", "Kubernetes"]}, "description": "Platform Team tech lead, database expert"},
        {"id": str(uuid.uuid4()), "name": "Mike Johnson", "entity_type": "PERSON", "properties": {"role": "Senior Engineer", "team": "Platform Team", "phone": "+1-555-0102", "expertise": ["PostgreSQL", "AWS"]}, "description": "Senior platform engineer, AWS specialist"},
        {"id": str(uuid.uuid4()), "name": "Emily Rodriguez", "entity_type": "PERSON", "properties": {"role": "Manager", "team": "Payments Team", "phone": "+1-555-0201", "expertise": ["Stripe", "PCI Compliance"]}, "description": "Payments team manager, PCI compliance expert"},
        {"id": str(uuid.uuid4()), "name": "James Wilson", "entity_type": "PERSON", "properties": {"role": "Tech Lead", "team": "Payments Team", "phone": "+1-555-0202", "expertise": ["Payment Processing", "Stripe", "Fraud Detection"]}, "description": "Payments tech lead, Stripe integration owner"},
        {"id": str(uuid.uuid4()), "name": "Lisa Park", "entity_type": "PERSON", "properties": {"role": "Engineer", "team": "Payments Team", "phone": "+1-555-0203", "expertise": ["Python", "Payments"]}, "description": "Payments engineer"},
        {"id": str(uuid.uuid4()), "name": "David Kim", "entity_type": "PERSON", "properties": {"role": "Tech Lead", "team": "Authentication Team", "phone": "+1-555-0301", "expertise": ["OAuth", "JWT", "Security"]}, "description": "Auth team tech lead, security expert"},
        {"id": str(uuid.uuid4()), "name": "Rachel Green", "entity_type": "PERSON", "properties": {"role": "Senior Engineer", "team": "Authentication Team", "phone": "+1-555-0302", "expertise": ["Identity", "SSO"]}, "description": "Senior auth engineer, SSO specialist"},
        {"id": str(uuid.uuid4()), "name": "Tom Martinez", "entity_type": "PERSON", "properties": {"role": "Tech Lead", "team": "API Team", "phone": "+1-555-0401", "expertise": ["REST", "GraphQL", "API Design"]}, "description": "API team tech lead"},
        {"id": str(uuid.uuid4()), "name": "Amy Liu", "entity_type": "PERSON", "properties": {"role": "Engineer", "team": "API Team", "phone": "+1-555-0402", "expertise": ["Python", "FastAPI"]}, "description": "API engineer"},
        {"id": str(uuid.uuid4()), "name": "Chris Taylor", "entity_type": "PERSON", "properties": {"role": "SRE Lead", "team": "SRE Team", "phone": "+1-555-0501", "pagerduty": True, "expertise": ["Incident Response", "Monitoring", "Kubernetes"]}, "description": "SRE team lead, incident commander"},
        {"id": str(uuid.uuid4()), "name": "Nina Patel", "entity_type": "PERSON", "properties": {"role": "Senior SRE", "team": "SRE Team", "phone": "+1-555-0502", "pagerduty": True, "expertise": ["Monitoring", "Alerting"]}, "description": "Senior SRE, monitoring expert"},
        {"id": str(uuid.uuid4()), "name": "Alex Thompson", "entity_type": "PERSON", "properties": {"role": "SRE", "team": "SRE Team", "phone": "+1-555-0503", "pagerduty": True, "expertise": ["On-call", "Triage"]}, "description": "SRE engineer, on-call specialist"},
        {"id": str(uuid.uuid4()), "name": "Jordan Lee", "entity_type": "PERSON", "properties": {"role": "Engineer", "team": "Platform Team", "phone": "+1-555-0103", "expertise": ["Redis", "Caching"]}, "description": "Platform engineer, caching expert"},
        {"id": str(uuid.uuid4()), "name": "Sam Brown", "entity_type": "PERSON", "properties": {"role": "Engineer", "team": "Authentication Team", "phone": "+1-555-0303", "expertise": ["MFA", "Security"]}, "description": "Auth engineer, MFA specialist"},
        {"id": str(uuid.uuid4()), "name": "Mia White", "entity_type": "PERSON", "properties": {"role": "VP Engineering", "team": "SRE Team", "phone": "+1-555-0001", "pagerduty": True, "expertise": ["Leadership", "Incident Management"]}, "description": "VP of Engineering, escalation point for SEV1"},
        {"id": str(uuid.uuid4()), "name": "Kevin Zhang", "entity_type": "PERSON", "properties": {"role": "Engineer", "team": "API Team", "phone": "+1-555-0403", "expertise": ["Rate Limiting", "Security"]}, "description": "API engineer, rate limiting owner"},
        {"id": str(uuid.uuid4()), "name": "Olivia Scott", "entity_type": "PERSON", "properties": {"role": "Engineer", "team": "Payments Team", "phone": "+1-555-0204", "expertise": ["Refunds", "Disputes"]}, "description": "Payments engineer, refunds and disputes"},
        {"id": str(uuid.uuid4()), "name": "Ryan Adams", "entity_type": "PERSON", "properties": {"role": "DBA", "team": "Platform Team", "phone": "+1-555-0104", "expertise": ["PostgreSQL", "Backup", "Recovery"]}, "description": "Database administrator"},
        {"id": str(uuid.uuid4()), "name": "Diana Cruz", "entity_type": "PERSON", "properties": {"role": "Security Engineer", "team": "Authentication Team", "phone": "+1-555-0304", "expertise": ["Penetration Testing", "Security Audits"]}, "description": "Security engineer"},
        {"id": str(uuid.uuid4()), "name": "Brian Hall", "entity_type": "PERSON", "properties": {"role": "Engineer", "team": "SRE Team", "phone": "+1-555-0504", "expertise": ["Automation", "Runbooks"]}, "description": "SRE automation specialist"},
    ]
    
    services = [
        {
            "id": str(uuid.uuid4()),
            "name": "Payments Database",
            "entity_type": "DATABASE",
            "properties": {"type": "PostgreSQL", "version": "14.2", "primary": True, "sla": "99.99%"},
            "description": "Primary PostgreSQL database for payment transactions. Critical for all payment processing."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Payment Service",
            "entity_type": "SERVICE",
            "properties": {"language": "Python", "framework": "FastAPI", "tier": "critical"},
            "description": "Core payment processing service. Handles all financial transactions."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Auth Service",
            "entity_type": "SERVICE",
            "properties": {"language": "Go", "tier": "critical"},
            "description": "Authentication and authorization service. Required for all authenticated requests."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "User Database",
            "entity_type": "DATABASE",
            "properties": {"type": "PostgreSQL", "version": "14.2", "primary": True},
            "description": "User identity and profile database."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "API Gateway",
            "entity_type": "SERVICE",
            "properties": {"language": "Go", "tier": "critical"},
            "description": "Main API gateway. Routes all external traffic."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Session Cache",
            "entity_type": "COMPONENT",
            "properties": {"type": "Redis", "version": "7.0", "cluster": True},
            "description": "Redis cluster for session management and caching."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Notification Service",
            "entity_type": "SERVICE",
            "properties": {"language": "Python", "tier": "standard"},
            "description": "Handles email, SMS, and push notifications."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Checkout Service",
            "entity_type": "SERVICE",
            "properties": {"language": "TypeScript", "tier": "critical"},
            "description": "Customer checkout flow. Orchestrates payment and order creation."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Order Database",
            "entity_type": "DATABASE",
            "properties": {"type": "PostgreSQL", "version": "14.2"},
            "description": "Order and transaction history database."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Fraud Detection Service",
            "entity_type": "SERVICE",
            "properties": {"language": "Python", "tier": "critical"},
            "description": "Real-time fraud detection for payment transactions."
        }
    ]
    
    relationships = []
    
    for team in teams:
        team_members = [p for p in people if p["properties"].get("team") == team["name"]]
        for person in team_members:
            relationships.append({
                "id": str(uuid.uuid4()),
                "source_name": person["name"],
                "target_name": team["name"],
                "relationship_type": "MEMBER_OF",
                "confidence": 0.95,
                "source_sentence": f"{person['name']} is a member of {team['name']}."
            })
            if person["properties"].get("role") in ["Tech Lead", "Manager", "SRE Lead", "VP Engineering"]:
                relationships.append({
                    "id": str(uuid.uuid4()),
                    "source_name": person["name"],
                    "target_name": team["name"],
                    "relationship_type": "MANAGES",
                    "confidence": 0.95,
                    "source_sentence": f"{person['name']} leads/manages {team['name']}."
                })
    
    relationships.extend([
        {"id": str(uuid.uuid4()), "source_name": "Platform Team", "target_name": "Payments Database", "relationship_type": "OWNS", "confidence": 0.95, "source_sentence": "Platform Team owns and maintains the Payments Database."},
        {"id": str(uuid.uuid4()), "source_name": "Platform Team", "target_name": "User Database", "relationship_type": "OWNS", "confidence": 0.95, "source_sentence": "Platform Team owns the User Database."},
        {"id": str(uuid.uuid4()), "source_name": "Platform Team", "target_name": "Session Cache", "relationship_type": "OWNS", "confidence": 0.95, "source_sentence": "Platform Team manages the Redis Session Cache."},
        {"id": str(uuid.uuid4()), "source_name": "Payments Team", "target_name": "Payment Service", "relationship_type": "OWNS", "confidence": 0.95, "source_sentence": "Payments Team owns the Payment Service."},
        {"id": str(uuid.uuid4()), "source_name": "Payments Team", "target_name": "Fraud Detection Service", "relationship_type": "OWNS", "confidence": 0.95, "source_sentence": "Payments Team owns the Fraud Detection Service."},
        {"id": str(uuid.uuid4()), "source_name": "Authentication Team", "target_name": "Auth Service", "relationship_type": "OWNS", "confidence": 0.95, "source_sentence": "Authentication Team owns the Auth Service."},
        {"id": str(uuid.uuid4()), "source_name": "API Team", "target_name": "API Gateway", "relationship_type": "OWNS", "confidence": 0.95, "source_sentence": "API Team owns the API Gateway."},
    ])
    
    relationships.extend([
        {"id": str(uuid.uuid4()), "source_name": "Payment Service", "target_name": "Payments Database", "relationship_type": "DEPENDS_ON", "confidence": 0.98, "source_sentence": "Payment Service requires Payments Database for all transaction storage."},
        {"id": str(uuid.uuid4()), "source_name": "Payment Service", "target_name": "Auth Service", "relationship_type": "DEPENDS_ON", "confidence": 0.95, "source_sentence": "Payment Service validates tokens through Auth Service."},
        {"id": str(uuid.uuid4()), "source_name": "Payment Service", "target_name": "Fraud Detection Service", "relationship_type": "DEPENDS_ON", "confidence": 0.90, "source_sentence": "Payment Service calls Fraud Detection for transaction validation."},
        {"id": str(uuid.uuid4()), "source_name": "Auth Service", "target_name": "User Database", "relationship_type": "DEPENDS_ON", "confidence": 0.98, "source_sentence": "Auth Service stores user credentials in User Database."},
        {"id": str(uuid.uuid4()), "source_name": "Auth Service", "target_name": "Session Cache", "relationship_type": "DEPENDS_ON", "confidence": 0.95, "source_sentence": "Auth Service uses Session Cache for active sessions."},
        {"id": str(uuid.uuid4()), "source_name": "API Gateway", "target_name": "Auth Service", "relationship_type": "DEPENDS_ON", "confidence": 0.98, "source_sentence": "API Gateway validates all requests through Auth Service."},
        {"id": str(uuid.uuid4()), "source_name": "API Gateway", "target_name": "Payment Service", "relationship_type": "DEPENDS_ON", "confidence": 0.90, "source_sentence": "API Gateway routes payment requests to Payment Service."},
        {"id": str(uuid.uuid4()), "source_name": "Checkout Service", "target_name": "Payment Service", "relationship_type": "DEPENDS_ON", "confidence": 0.98, "source_sentence": "Checkout Service processes payments through Payment Service."},
        {"id": str(uuid.uuid4()), "source_name": "Checkout Service", "target_name": "Order Database", "relationship_type": "DEPENDS_ON", "confidence": 0.95, "source_sentence": "Checkout Service stores orders in Order Database."},
        {"id": str(uuid.uuid4()), "source_name": "Checkout Service", "target_name": "Auth Service", "relationship_type": "DEPENDS_ON", "confidence": 0.90, "source_sentence": "Checkout Service verifies user identity through Auth Service."},
        {"id": str(uuid.uuid4()), "source_name": "Notification Service", "target_name": "User Database", "relationship_type": "DEPENDS_ON", "confidence": 0.85, "source_sentence": "Notification Service fetches user contact info from User Database."},
        {"id": str(uuid.uuid4()), "source_name": "Fraud Detection Service", "target_name": "Payments Database", "relationship_type": "DEPENDS_ON", "confidence": 0.90, "source_sentence": "Fraud Detection queries historical transactions from Payments Database."},
    ])
    
    relationships.extend([
        {"id": str(uuid.uuid4()), "source_name": "Emily Rodriguez", "target_name": "Mia White", "relationship_type": "ESCALATES_TO", "confidence": 0.95, "source_sentence": "For SEV1 payment issues, Emily Rodriguez escalates to VP Mia White."},
        {"id": str(uuid.uuid4()), "source_name": "David Kim", "target_name": "Mia White", "relationship_type": "ESCALATES_TO", "confidence": 0.95, "source_sentence": "For SEV1 auth issues, David Kim escalates to VP Mia White."},
        {"id": str(uuid.uuid4()), "source_name": "Chris Taylor", "target_name": "Mia White", "relationship_type": "ESCALATES_TO", "confidence": 0.95, "source_sentence": "SRE Lead Chris Taylor escalates SEV1 to VP Mia White."},
        {"id": str(uuid.uuid4()), "source_name": "Sarah Chen", "target_name": "Chris Taylor", "relationship_type": "ESCALATES_TO", "confidence": 0.90, "source_sentence": "Platform issues escalate from Sarah Chen to SRE Lead Chris Taylor."},
    ])
    
    incidents = [
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-001: Payments Database Failover",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV1", "status": "resolved", "duration_minutes": 45, "date": "2024-01-15"},
            "description": "Primary payments database failed over to replica. 45 minute payment processing delay."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-002: Auth Service Latency Spike",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV2", "status": "resolved", "duration_minutes": 30, "date": "2024-01-22"},
            "description": "Auth service response times exceeded 2 seconds due to session cache issues."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-003: Checkout Service OOM",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV2", "status": "resolved", "duration_minutes": 20, "date": "2024-02-01"},
            "description": "Checkout service pods crashed due to memory leak during flash sale."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-004: Fraud Detection False Positives",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV3", "status": "resolved", "duration_minutes": 120, "date": "2024-02-10"},
            "description": "Fraud detection blocked 15% of legitimate transactions due to model drift."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-005: API Gateway Rate Limiting Bug",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV2", "status": "resolved", "duration_minutes": 60, "date": "2024-02-15"},
            "description": "Rate limiting incorrectly applied to internal services causing cascading failures."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-006: User Database Connection Exhaustion",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV1", "status": "resolved", "duration_minutes": 35, "date": "2024-02-20"},
            "description": "Auth service exhausted database connection pool during traffic spike."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-007: Session Cache Cluster Partition",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV1", "status": "resolved", "duration_minutes": 25, "date": "2024-02-25"},
            "description": "Redis cluster network partition caused session validation failures."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-008: Payment Service Stripe Timeout",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV2", "status": "resolved", "duration_minutes": 40, "date": "2024-03-01"},
            "description": "Stripe API timeouts caused payment processing delays."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-009: Notification Service Queue Backlog",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV3", "status": "resolved", "duration_minutes": 180, "date": "2024-03-05"},
            "description": "Email notification queue backed up, 3 hour delay in confirmations."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-010: Auth Token Validation Bug",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV1", "status": "resolved", "duration_minutes": 15, "date": "2024-03-10"},
            "description": "JWT validation bypass discovered and patched. Security incident."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-011: Order Database Replication Lag",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV3", "status": "resolved", "duration_minutes": 90, "date": "2024-03-12"},
            "description": "Order database read replica 5 minutes behind primary."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-012: Checkout Service Deploy Rollback",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV2", "status": "resolved", "duration_minutes": 10, "date": "2024-03-15"},
            "description": "Bad deploy to checkout service caused cart calculation errors."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-013: Payments Database Disk Full",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV1", "status": "resolved", "duration_minutes": 20, "date": "2024-03-18"},
            "description": "Payments database disk reached 100%, writes blocked until cleanup."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-014: API Gateway Certificate Expiry",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV1", "status": "resolved", "duration_minutes": 5, "date": "2024-03-20"},
            "description": "TLS certificate expired on API gateway, all external traffic blocked."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-015: Fraud Detection Model Latency",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV3", "status": "resolved", "duration_minutes": 60, "date": "2024-03-22"},
            "description": "ML model inference time increased 10x after model update."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-016: Auth Service Memory Leak",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV2", "status": "resolved", "duration_minutes": 45, "date": "2024-03-25"},
            "description": "Memory leak in auth service caused gradual degradation."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-017: Payment Refund Processing Failure",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV2", "status": "resolved", "duration_minutes": 120, "date": "2024-03-28"},
            "description": "Refund processing queue stuck, customer refunds delayed 2 hours."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-018: Session Cache Eviction Storm",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV2", "status": "resolved", "duration_minutes": 30, "date": "2024-04-01"},
            "description": "Mass session eviction caused wave of re-authentications."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-019: Checkout Service Dependency Update",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV3", "status": "resolved", "duration_minutes": 15, "date": "2024-04-05"},
            "description": "Breaking change in payment SDK required emergency rollback."
        },
        {
            "id": str(uuid.uuid4()),
            "name": "INC-2024-020: Network Partition - US-East",
            "entity_type": "INCIDENT",
            "properties": {"severity": "SEV1", "status": "resolved", "duration_minutes": 8, "date": "2024-04-08"},
            "description": "AWS network partition isolated US-East region for 8 minutes."
        },
    ]
    
    incident_relationships = [
        ("INC-2024-001: Payments Database Failover", "Payments Database", "CAUSED_BY"),
        ("INC-2024-001: Payments Database Failover", "Payment Service", "AFFECTS"),
        ("INC-2024-001: Payments Database Failover", "Checkout Service", "AFFECTS"),
        ("INC-2024-001: Payments Database Failover", "Sarah Chen", "RESOLVED_BY"),
        ("INC-2024-002: Auth Service Latency Spike", "Session Cache", "CAUSED_BY"),
        ("INC-2024-002: Auth Service Latency Spike", "Auth Service", "AFFECTS"),
        ("INC-2024-002: Auth Service Latency Spike", "David Kim", "RESOLVED_BY"),
        ("INC-2024-006: User Database Connection Exhaustion", "User Database", "CAUSED_BY"),
        ("INC-2024-006: User Database Connection Exhaustion", "Auth Service", "AFFECTS"),
        ("INC-2024-006: User Database Connection Exhaustion", "API Gateway", "AFFECTS"),
        ("INC-2024-006: User Database Connection Exhaustion", "Sarah Chen", "RESOLVED_BY"),
        ("INC-2024-007: Session Cache Cluster Partition", "Session Cache", "CAUSED_BY"),
        ("INC-2024-007: Session Cache Cluster Partition", "Auth Service", "AFFECTS"),
        ("INC-2024-007: Session Cache Cluster Partition", "Jordan Lee", "RESOLVED_BY"),
        ("INC-2024-010: Auth Token Validation Bug", "Auth Service", "CAUSED_BY"),
        ("INC-2024-010: Auth Token Validation Bug", "API Gateway", "AFFECTS"),
        ("INC-2024-010: Auth Token Validation Bug", "Diana Cruz", "RESOLVED_BY"),
        ("INC-2024-013: Payments Database Disk Full", "Payments Database", "CAUSED_BY"),
        ("INC-2024-013: Payments Database Disk Full", "Payment Service", "AFFECTS"),
        ("INC-2024-013: Payments Database Disk Full", "Ryan Adams", "RESOLVED_BY"),
        ("INC-2024-014: API Gateway Certificate Expiry", "API Gateway", "CAUSED_BY"),
        ("INC-2024-014: API Gateway Certificate Expiry", "Tom Martinez", "RESOLVED_BY"),
        ("INC-2024-020: Network Partition - US-East", "API Gateway", "AFFECTS"),
        ("INC-2024-020: Network Partition - US-East", "Chris Taylor", "RESOLVED_BY"),
    ]
    
    for source, target, rel_type in incident_relationships:
        relationships.append({
            "id": str(uuid.uuid4()),
            "source_name": source,
            "target_name": target,
            "relationship_type": rel_type,
            "confidence": 0.95,
            "source_sentence": f"Incident {source} has relationship {rel_type} with {target}."
        })
    
    runbooks = [
        {
            "id": str(uuid.uuid4()),
            "title": "Payments Database Failover Procedure",
            "doc_type": "RUNBOOK",
            "content": """# Payments Database Failover Procedure

## Overview
This runbook covers the procedure for handling Payments Database failovers, whether planned or unplanned.

## Prerequisites
- Access to AWS console with RDS permissions
- PagerDuty access for escalation
- Database connection credentials

## Steps

### 1. Identify the Issue
- Check CloudWatch for RDS metrics
- Verify primary database status in AWS RDS console
- Check application logs for connection errors

### 2. Assess Impact
- Payment Service will be unable to process transactions
- Checkout Service will fail payment steps
- Fraud Detection historical queries will fail

### 3. Failover Procedure
1. Confirm replica is in sync (lag < 1 second)
2. Initiate RDS failover via AWS console
3. Wait for DNS propagation (typically 30-60 seconds)
4. Verify application connections are restored
5. Monitor for any stuck transactions

### 4. Post-Failover
- Notify Payments Team (Emily Rodriguez)
- Document incident in INC ticket
- Schedule post-mortem if unplanned

## Escalation
- SEV1: Notify VP Engineering (Mia White) immediately
- Contact: Platform Team (Sarah Chen) for database issues

## Recovery Time Objective: 15 minutes""",
            "metadata": {"services": ["Payment Service", "Payments Database"], "severity": "SEV1", "owner": "Platform Team"}
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Auth Service Incident Response",
            "doc_type": "RUNBOOK",
            "content": """# Auth Service Incident Response

## Overview
Response procedures for Auth Service incidents affecting user authentication.

## Impact Assessment
Auth Service outage affects:
- ALL authenticated API requests
- User login/logout
- Session validation
- API Gateway request authorization

## Severity Guidelines
- SEV1: Complete auth failure, no users can log in
- SEV2: Degraded performance, >2s response times
- SEV3: Partial functionality, specific features affected

## Immediate Actions

### For SEV1
1. Page SRE Team (Chris Taylor)
2. Notify Authentication Team (David Kim)
3. Check Session Cache (Redis) cluster health
4. Check User Database connection pool

### For SEV2
1. Check Session Cache latency
2. Review recent deploys
3. Check User Database query performance

## Common Causes
1. Session Cache cluster issues
2. User Database connection exhaustion
3. JWT validation bugs
4. Memory leaks in auth pods

## Escalation Path
1. On-call SRE → Chris Taylor (SRE Lead)
2. Chris Taylor → David Kim (Auth Tech Lead)
3. David Kim → Mia White (VP Engineering) for SEV1

## Recovery Time Objective: 10 minutes for SEV1""",
            "metadata": {"services": ["Auth Service", "Session Cache", "User Database"], "severity": "SEV1", "owner": "Authentication Team"}
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Checkout Service Troubleshooting",
            "doc_type": "RUNBOOK",
            "content": """# Checkout Service Troubleshooting

## Overview
Guide for diagnosing and resolving Checkout Service issues.

## Dependencies
Checkout Service depends on:
- Payment Service (critical)
- Auth Service (critical)
- Order Database
- Notification Service (non-critical)

## Common Issues

### Cart Calculation Errors
- Check recent deploys for pricing logic changes
- Verify discount service responses
- Review cart state in Order Database

### Payment Processing Failures
- Check Payment Service health
- Verify Stripe API status
- Check Fraud Detection service

### Memory Issues (OOM)
- Check pod memory usage
- Review for memory leaks
- Consider horizontal scaling for high traffic

## Escalation
- Checkout issues → API Team (Tom Martinez)
- Payment failures → Payments Team (James Wilson)
- Database issues → Platform Team (Sarah Chen)

## Rollback Procedure
1. Identify bad commit
2. Revert via CI/CD pipeline
3. Verify cart functionality
4. Monitor error rates""",
            "metadata": {"services": ["Checkout Service", "Payment Service", "Order Database"], "severity": "SEV2", "owner": "API Team"}
        },
        {
            "id": str(uuid.uuid4()),
            "title": "SEV1 Incident Commander Playbook",
            "doc_type": "RUNBOOK",
            "content": """# SEV1 Incident Commander Playbook

## Overview
This playbook is for the Incident Commander role during SEV1 incidents.

## Incident Commander Responsibilities
1. Coordinate response across teams
2. Manage communication
3. Make escalation decisions
4. Document timeline

## Initial Response (First 5 Minutes)
1. Acknowledge page in PagerDuty
2. Open incident Slack channel #inc-YYYYMMDD-XXX
3. Identify affected services
4. Page relevant service owners

## Escalation Matrix

### By Service
- Payments Database/Payment Service → Emily Rodriguez (Payments) → Mia White
- Auth Service/Session Cache → David Kim (Auth) → Mia White
- API Gateway → Tom Martinez (API) → Mia White
- Infrastructure → Sarah Chen (Platform) → Chris Taylor → Mia White

### By Severity
- SEV1: VP Engineering (Mia White) notified within 5 minutes
- SEV1 > 30 minutes: CTO notification required

## Communication Templates

### Initial Notification
"SEV1 Incident: [Service] is experiencing [issue]. Impact: [description]. 
Current status: Investigating. Next update in 15 minutes."

### Resolution
"SEV1 Resolved: [Service] issue resolved at [time]. 
Duration: [X] minutes. Root cause: [brief description].
Post-mortem scheduled for [date]."

## Post-Incident
1. Document full timeline
2. Schedule post-mortem within 48 hours
3. Update runbooks if needed
4. File action items""",
            "metadata": {"services": [], "severity": "SEV1", "owner": "SRE Team"}
        },
        {
            "id": str(uuid.uuid4()),
            "title": "Database Connection Pool Exhaustion",
            "doc_type": "RUNBOOK",
            "content": """# Database Connection Pool Exhaustion

## Overview
Procedures for handling database connection pool exhaustion.

## Symptoms
- Application errors: "connection pool exhausted"
- Slow queries or timeouts
- Increasing connection count in database metrics

## Affected Services
- Auth Service → User Database
- Payment Service → Payments Database
- Checkout Service → Order Database

## Immediate Actions

### 1. Identify Source
```sql
SELECT client_addr, count(*) 
FROM pg_stat_activity 
WHERE datname = 'your_db'
GROUP BY client_addr 
ORDER BY count DESC;
```

### 2. Kill Idle Connections
```sql
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'idle' 
AND query_start < now() - interval '5 minutes';
```

### 3. Temporary Relief
- Scale up application pods to distribute load
- Increase pool size (temporary)
- Enable connection queuing

## Root Cause Investigation
- Check for connection leaks in application code
- Review recent deploys
- Check for long-running queries
- Verify connection timeout settings

## Prevention
- Set appropriate pool sizes (recommended: 20-50 per pod)
- Implement connection timeouts
- Add connection pool monitoring alerts

## Contacts
- Platform Team (Sarah Chen, Ryan Adams) for database issues
- Service owners for application-level fixes""",
            "metadata": {"services": ["User Database", "Payments Database", "Order Database"], "severity": "SEV1", "owner": "Platform Team"}
        }
    ]
    
    rules = [
        {
            "id": str(uuid.uuid4()),
            "name": "SEV1 Escalation Rule",
            "rule_type": "ESCALATION_POLICY",
            "description": "All SEV1 incidents must be escalated to VP Engineering within 5 minutes",
            "condition": "incident.severity == 'SEV1' AND incident.duration > 5_minutes",
            "action": "escalate_to('Mia White', 'VP Engineering')",
            "priority": 100,
            "entity_types": ["INCIDENT"],
            "metadata": {"contact": "Mia White", "sla_minutes": 5}
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Database Owner Notification",
            "rule_type": "ESCALATION_POLICY",
            "description": "Database incidents must notify Platform Team",
            "condition": "incident.affected_service.entity_type == 'DATABASE'",
            "action": "notify_team('Platform Team')",
            "priority": 90,
            "entity_types": ["INCIDENT", "DATABASE"],
            "metadata": {"team": "Platform Team", "contact": "Sarah Chen"}
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Payment Service Dependency Check",
            "rule_type": "INVARIANT",
            "description": "Payment Service must always have Payments Database available",
            "condition": "service.name == 'Payment Service' AND NOT depends_on('Payments Database').is_healthy",
            "action": "flag_critical('Payment Service cannot operate without Payments Database')",
            "priority": 100,
            "entity_types": ["SERVICE", "DATABASE"],
            "relationship_types": ["DEPENDS_ON"],
            "metadata": {"critical": True}
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Auth Service Required for API",
            "rule_type": "INVARIANT",
            "description": "API Gateway requires Auth Service for all authenticated requests",
            "condition": "service.name == 'API Gateway' AND NOT depends_on('Auth Service').is_healthy",
            "action": "flag_critical('API Gateway cannot validate requests without Auth Service')",
            "priority": 100,
            "entity_types": ["SERVICE"],
            "relationship_types": ["DEPENDS_ON"],
            "metadata": {"critical": True}
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Single Primary Database",
            "rule_type": "INVARIANT",
            "description": "Each database cluster must have exactly one primary",
            "condition": "database.properties.primary == True",
            "action": "validate_unique_primary(database.cluster)",
            "priority": 95,
            "entity_types": ["DATABASE"],
            "metadata": {"validation": "uniqueness"}
        },
        {
            "id": str(uuid.uuid4()),
            "name": "On-Call Requirement",
            "rule_type": "SAFETY_CHECK",
            "description": "All critical services must have on-call coverage",
            "condition": "service.properties.tier == 'critical'",
            "action": "verify_oncall_exists(service.owner_team)",
            "priority": 80,
            "entity_types": ["SERVICE", "TEAM"],
            "relationship_types": ["OWNS"],
            "metadata": {"check_type": "coverage"}
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Cascade Impact Assessment",
            "rule_type": "VALIDATION",
            "description": "When assessing service impact, include all downstream dependencies",
            "condition": "query.type == 'impact_assessment'",
            "action": "traverse_dependencies(service, direction='downstream', depth=3)",
            "priority": 70,
            "entity_types": ["SERVICE", "DATABASE", "COMPONENT"],
            "relationship_types": ["DEPENDS_ON", "USES"],
            "metadata": {"traversal_depth": 3}
        },
        {
            "id": str(uuid.uuid4()),
            "name": "Escalation Chain Validation",
            "rule_type": "VALIDATION",
            "description": "Verify escalation paths exist for incident response",
            "condition": "query.type == 'escalation' OR query.type == 'incident_response'",
            "action": "validate_escalation_path(team, severity)",
            "priority": 85,
            "entity_types": ["TEAM", "PERSON"],
            "relationship_types": ["ESCALATES_TO", "MANAGES"],
            "metadata": {"requires_path": True}
        }
    ]
    
    all_entities = teams + people + services + incidents
    
    return {
        "entities": all_entities,
        "relationships": relationships,
        "documents": runbooks,
        "rules": rules,
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "entity_count": len(all_entities),
            "relationship_count": len(relationships),
            "document_count": len(runbooks),
            "rule_count": len(rules)
        }
    }


if __name__ == "__main__":
    import json
    data = generate_synthetic_data()
    print(f"Generated synthetic data:")
    print(f"  Entities: {data['metadata']['entity_count']}")
    print(f"  Relationships: {data['metadata']['relationship_count']}")
    print(f"  Documents: {data['metadata']['document_count']}")
    print(f"  Rules: {data['metadata']['rule_count']}")
