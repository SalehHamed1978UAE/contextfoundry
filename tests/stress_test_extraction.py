"""
Stress Test: Constrained Extraction Pipeline

Tests 10 realistic incident reports through the extraction pipeline.

Success Criteria:
- 0 garbage entities (low confidence staging entities)
- 0 invalid type assignments (only SERVICE, DATABASE, INCIDENT, TEAM, PERSON, COMPONENT)
- All orphan patterns captured properly
- < 5 seconds average extraction time per document
"""

import sys
import time
import logging
from typing import Dict, List, Any
from dataclasses import dataclass

sys.path.insert(0, '/home/runner/workspace')

from src.context_foundry.models.schema import get_session, Entity, Relationship
from src.context_foundry.agents.graph_builder import GraphBuilderAgent

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

TEST_DOCUMENTS = [
    {
        "title": "Network Outage - Load Balancer Failure",
        "content": """INCIDENT REPORT - INC-2025-001

Date: December 6, 2025 08:15 UTC

The primary load balancer experienced a hardware failure causing 100% packet loss to the API Gateway.
All downstream services including the Auth Service, User Service, and Payment Service became unreachable.

Root cause: Power supply failure on load balancer LB-PROD-01.

Impact:
- 15,000 users affected
- Revenue loss estimated at $45,000

Resolution: Failover to secondary load balancer LB-PROD-02 completed by Network Team.
Incident Commander: Sarah Chen (Platform Team)
"""
    },
    {
        "title": "Database Corruption - Primary DB",
        "content": """INCIDENT REPORT - INC-2025-002

Date: December 5, 2025 14:30 UTC

The Customers Database experienced table corruption in the orders table.
SELECT queries returned inconsistent results, causing Order Service to return 500 errors.

Root cause: Disk failure on database server causing incomplete writes.

Affected services:
- Order Service (100% error rate)
- Inventory Service (partial failures)
- Reporting Service (stale data)

Resolution: Restored from point-in-time backup by DBA Team.
Post-mortem scheduled for Friday.
"""
    },
    {
        "title": "API Rate Limiting - Third Party Throttle",
        "content": """INCIDENT REPORT - INC-2025-003

Date: December 4, 2025 11:00 UTC

Stripe Payment Gateway throttled our API requests due to exceeding rate limits.
Payment Processing Service started returning 429 errors to customers.

Root cause: Marketing campaign caused 10x normal checkout volume.

Impact:
- Checkout Service degraded for 45 minutes
- 2,300 failed payment attempts
- Customer complaints: 156

Resolution: Upgraded Stripe plan and implemented request queuing.
Owner: Payments Team
"""
    },
    {
        "title": "Memory Leak - User Service OOM",
        "content": """INCIDENT REPORT - INC-2025-004

Date: December 3, 2025 03:45 UTC

User Service pods started crashing due to memory exhaustion (OOM killed).
Memory usage grew from 2GB to 8GB limit over 4 hours.

Root cause: Memory leak in session handling code after last deployment.

Affected systems:
- User Service (recurring restarts)
- Auth Service (authentication delays)
- Frontend App (slow login)

Resolution: Rolled back to previous deployment. Memory leak fix deployed next day.
On-call engineer: Marcus Lee (Backend Team)
"""
    },
    {
        "title": "Certificate Expiry - SSL Outage",
        "content": """INCIDENT REPORT - INC-2025-005

Date: December 2, 2025 00:00 UTC

SSL certificate for payments.example.com expired at midnight.
All HTTPS traffic to Payment Gateway returned SSL_ERROR_EXPIRED_CERTIFICATE.

Root cause: Certificate renewal automation failed silently 30 days ago.

Impact:
- Payment Gateway unreachable for 2 hours
- Mobile App payment flow broken
- Revenue loss: $125,000

Resolution: Emergency certificate renewal by Security Team.
Follow-up: Added certificate expiry monitoring alerts.
"""
    },
    {
        "title": "DDoS Attack - Login Endpoint",
        "content": """INCIDENT REPORT - INC-2025-006

Date: December 1, 2025 16:30 UTC

Detected distributed denial-of-service attack targeting /api/v1/login endpoint.
Traffic peaked at 50,000 requests per second from 12,000 unique IPs.

Root cause: Botnet attack, likely credential stuffing attempt.

Affected services:
- Auth Service (overloaded)
- API Gateway (rate limiting triggered)
- Monitoring Service (metrics delayed)

Resolution: Enabled Cloudflare DDoS protection, IP blocklist updated.
Security Team investigating potential data breach.
"""
    },
    {
        "title": "Config Drift - Production Mismatch",
        "content": """INCIDENT REPORT - INC-2025-007

Date: November 30, 2025 09:00 UTC

Production configuration for Notification Service diverged from staging.
Email templates in production contained outdated branding from 2023.

Root cause: Manual config change bypassed deployment pipeline.

Impact:
- 50,000 emails sent with wrong branding
- Customer confusion reported
- Brand compliance violation

Resolution: Synced config from staging. Added config drift detection.
Owner: DevOps Team
"""
    },
    {
        "title": "Dependency Vulnerability - NPM Package",
        "content": """INCIDENT REPORT - INC-2025-008

Date: November 29, 2025 10:15 UTC

Critical vulnerability CVE-2025-1234 discovered in lodash@4.17.20.
All Node.js services potentially affected by prototype pollution attack.

Affected services:
- API Gateway (Node.js)
- Webhook Service (Node.js)
- Admin Portal (Node.js)

Risk assessment: HIGH - Remote code execution possible.

Resolution: Emergency patch deployed within 4 hours.
Security Team performed threat hunting, no exploitation detected.
"""
    },
    {
        "title": "Data Sync Lag - Replica Behind",
        "content": """INCIDENT REPORT - INC-2025-009

Date: November 28, 2025 07:30 UTC

Read replica of Users Database fell 15 minutes behind primary.
Analytics Service and Reporting Service showed stale user data.

Root cause: Network congestion between primary and replica data centers.

Impact:
- Analytics Dashboard showing old data
- Real-time reports delayed
- No customer-facing impact

Resolution: Network Team increased bandwidth allocation.
DBA Team monitoring replication lag closely.
"""
    },
    {
        "title": "Capacity Breach - Order Volume Spike",
        "content": """INCIDENT REPORT - INC-2025-010

Date: November 27, 2025 12:00 UTC (Black Friday)

Order volume exceeded provisioned capacity by 300%.
Order Service queue depth reached 50,000, causing 30-second delays.

Root cause: Underestimated Black Friday traffic despite forecasts.

Affected services:
- Order Service (overwhelmed)
- Inventory Service (queue backup)
- Notification Service (delayed confirmations)
- Warehouse Integration (sync lag)

Resolution: Emergency scaling to 10x pods. Database connections increased.
Platform Team worked 16-hour shift to stabilize.
"""
    }
]

VALID_ENTITY_TYPES = {'SERVICE', 'DATABASE', 'INCIDENT', 'TEAM', 'PERSON', 'COMPONENT'}


@dataclass
class StressTestResult:
    """Results from a single document extraction"""
    doc_title: str
    extraction_time_ms: float
    entities_extracted: int
    relationships_extracted: int
    entity_types: List[str]
    invalid_types: List[str]
    success: bool


def run_stress_test() -> Dict[str, Any]:
    """
    Run the stress test on all 10 incident documents.
    
    Returns summary statistics and detailed results.
    """
    session = get_session()
    agent = GraphBuilderAgent(session)
    
    before_entities = session.query(Entity).count()
    before_rels = session.query(Relationship).count()
    
    results: List[StressTestResult] = []
    total_entities = 0
    total_relationships = 0
    invalid_type_count = 0
    extraction_times = []
    
    print("=" * 70)
    print("STRESS TEST: Constrained Extraction Pipeline")
    print("=" * 70)
    print(f"\nProcessing {len(TEST_DOCUMENTS)} incident reports...\n")
    
    for i, doc in enumerate(TEST_DOCUMENTS, 1):
        print(f"[{i}/10] Processing: {doc['title'][:50]}...")
        
        start_time = time.time()
        try:
            extraction_result = agent.ingest_document(
                text=doc['content'],
                title=doc['title']
            )
            success = True
        except Exception as e:
            print(f"       ERROR: {e}")
            extraction_result = None
            success = False
        
        elapsed_ms = (time.time() - start_time) * 1000
        extraction_times.append(elapsed_ms)
        
        if extraction_result:
            result = StressTestResult(
                doc_title=doc['title'],
                extraction_time_ms=elapsed_ms,
                entities_extracted=extraction_result.entities_extracted,
                relationships_extracted=extraction_result.relationships_extracted,
                entity_types=[],
                invalid_types=[],
                success=success
            )
            
            total_entities += result.entities_extracted
            total_relationships += result.relationships_extracted
            
            print(f"       -> {result.entities_extracted} entities, {result.relationships_extracted} rels, {elapsed_ms:.0f}ms")
        else:
            result = StressTestResult(
                doc_title=doc['title'],
                extraction_time_ms=elapsed_ms,
                entities_extracted=0,
                relationships_extracted=0,
                entity_types=[],
                invalid_types=[],
                success=False
            )
        
        results.append(result)
    
    after_entities = session.query(Entity).count()
    after_rels = session.query(Relationship).count()
    
    garbage_entities = session.query(Entity).filter(
        Entity.lifecycle_state == 'STAGING',
        Entity.confidence < 0.5
    ).count()
    
    invalid_entities = session.query(Entity).filter(
        ~Entity.entity_type.in_(VALID_ENTITY_TYPES)
    ).all()
    invalid_type_count = len(invalid_entities)
    if invalid_entities:
        print(f"\n   WARNING: Invalid entity types found:")
        for e in invalid_entities[:5]:
            print(f"      - {e.name} ({e.entity_type})")
    
    avg_time = sum(extraction_times) / len(extraction_times) if extraction_times else 0
    max_time = max(extraction_times) if extraction_times else 0
    min_time = min(extraction_times) if extraction_times else 0
    
    print("\n" + "=" * 70)
    print("STRESS TEST RESULTS")
    print("=" * 70)
    
    print(f"\n1. EXTRACTION SUMMARY:")
    print(f"   Documents processed: {len(TEST_DOCUMENTS)}")
    print(f"   Successful extractions: {sum(1 for r in results if r.success)}")
    print(f"   Total entities extracted: {total_entities}")
    print(f"   Total relationships extracted: {total_relationships}")
    
    print(f"\n2. PERFORMANCE:")
    print(f"   Average extraction time: {avg_time:.0f}ms")
    print(f"   Min extraction time: {min_time:.0f}ms")
    print(f"   Max extraction time: {max_time:.0f}ms")
    print(f"   Under 5s threshold: {'PASS' if avg_time < 5000 else 'FAIL'}")
    
    print(f"\n3. DATA INTEGRITY:")
    print(f"   Garbage entities (low confidence): {garbage_entities}")
    print(f"   Invalid type assignments: {invalid_type_count}")
    print(f"   Zero garbage check: {'PASS' if garbage_entities == 0 else 'FAIL'}")
    print(f"   Zero invalid types check: {'PASS' if invalid_type_count == 0 else 'FAIL'}")
    
    print(f"\n4. DATABASE CHANGES:")
    print(f"   Entities: {before_entities} -> {after_entities} (+{after_entities - before_entities})")
    print(f"   Relationships: {before_rels} -> {after_rels} (+{after_rels - before_rels})")
    
    all_entity_types = set()
    for r in results:
        all_entity_types.update(r.entity_types)
    print(f"\n5. ENTITY TYPES EXTRACTED:")
    print(f"   {sorted(all_entity_types)}")
    
    success_criteria = {
        "zero_garbage_entities": garbage_entities == 0,
        "zero_invalid_types": invalid_type_count == 0,
        "under_5s_average": avg_time < 5000,
        "all_docs_processed": sum(1 for r in results if r.success) == len(TEST_DOCUMENTS)
    }
    
    all_passed = all(success_criteria.values())
    
    print(f"\n6. SUCCESS CRITERIA:")
    for criterion, passed in success_criteria.items():
        status = "PASS" if passed else "FAIL"
        print(f"   {criterion}: {status}")
    
    print(f"\n{'=' * 70}")
    print(f"OVERALL RESULT: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
    print(f"{'=' * 70}\n")
    
    session.close()
    
    return {
        "results": results,
        "summary": {
            "total_documents": len(TEST_DOCUMENTS),
            "successful_extractions": sum(1 for r in results if r.success),
            "total_entities": total_entities,
            "total_relationships": total_relationships,
            "avg_extraction_time_ms": avg_time,
            "garbage_entities": garbage_entities,
            "invalid_type_assignments": invalid_type_count,
            "all_passed": all_passed
        },
        "success_criteria": success_criteria
    }


if __name__ == "__main__":
    run_stress_test()
