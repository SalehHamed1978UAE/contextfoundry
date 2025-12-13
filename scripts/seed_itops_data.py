#!/usr/bin/env python3
"""
Seed IT Ops Service Dependency Graph

Creates 80 SERVICE entities with realistic DEPENDS_ON, CALLS, HOSTS relationships
to enable blast radius queries and demonstrate relationship traversal value.

Usage:
    python scripts/seed_itops_data.py [--tenant-id UUID]
"""

import os
import sys
import uuid
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import psycopg2
from psycopg2.extras import execute_values

DATABASE_URL = os.environ.get("DATABASE_URL")

SERVICES = {
    "gateway": [
        ("API Gateway", "Primary ingress point for all client requests"),
        ("GraphQL Gateway", "GraphQL API aggregation layer"),
        ("WebSocket Gateway", "Real-time connection management"),
        ("Mobile Gateway", "Mobile-specific API optimizations"),
        ("Partner Gateway", "Third-party API integrations"),
    ],
    "auth": [
        ("Auth Service", "Authentication and token management"),
        ("Identity Provider", "User identity federation"),
        ("Session Manager", "Session state management"),
        ("OAuth Service", "OAuth2 provider implementation"),
        ("MFA Service", "Multi-factor authentication"),
        ("API Key Service", "API key generation and validation"),
    ],
    "core_business": [
        ("Order Service", "Order lifecycle management"),
        ("Payment Service", "Payment processing and reconciliation"),
        ("Inventory Service", "Stock management and reservations"),
        ("Pricing Service", "Dynamic pricing engine"),
        ("Cart Service", "Shopping cart management"),
        ("Checkout Service", "Checkout flow orchestration"),
        ("Fulfillment Service", "Order fulfillment coordination"),
        ("Shipping Service", "Shipping rate calculation and tracking"),
        ("Returns Service", "Return and refund processing"),
        ("Subscription Service", "Recurring billing management"),
    ],
    "user": [
        ("User Service", "User profile management"),
        ("Preferences Service", "User preferences storage"),
        ("Notification Service", "Multi-channel notifications"),
        ("Email Service", "Email delivery and templates"),
        ("SMS Service", "SMS gateway integration"),
        ("Push Service", "Mobile push notifications"),
    ],
    "catalog": [
        ("Product Service", "Product catalog management"),
        ("Search Service", "Product search and discovery"),
        ("Recommendation Service", "ML-based recommendations"),
        ("Review Service", "Product reviews and ratings"),
        ("Media Service", "Image and video processing"),
    ],
    "analytics": [
        ("Analytics Service", "Business analytics aggregation"),
        ("Event Collector", "Clickstream event ingestion"),
        ("Reporting Service", "Report generation"),
        ("Dashboard Service", "Real-time dashboards"),
        ("A/B Test Service", "Experiment management"),
    ],
    "infrastructure": [
        ("Config Service", "Centralized configuration"),
        ("Feature Flag Service", "Feature toggle management"),
        ("Rate Limiter", "API rate limiting"),
        ("Circuit Breaker", "Fault tolerance coordination"),
        ("Service Mesh", "Service-to-service networking"),
        ("Load Balancer", "Traffic distribution"),
        ("CDN Edge", "Content delivery edge nodes"),
    ],
    "data": [
        ("PostgreSQL Primary", "Primary relational database"),
        ("PostgreSQL Replica", "Read replica database"),
        ("Redis Cache", "Distributed caching layer"),
        ("Redis Session", "Session storage cluster"),
        ("Elasticsearch", "Search and log indexing"),
        ("Kafka", "Event streaming platform"),
        ("Kafka Connect", "Data integration pipelines"),
        ("S3 Storage", "Object storage"),
        ("MongoDB", "Document database for unstructured data"),
    ],
    "monitoring": [
        ("Prometheus", "Metrics collection and storage"),
        ("Grafana", "Metrics visualization"),
        ("AlertManager", "Alert routing and deduplication"),
        ("PagerDuty Gateway", "Incident management integration"),
        ("Jaeger", "Distributed tracing"),
        ("Log Aggregator", "Centralized logging"),
        ("Synthetic Monitor", "Uptime and synthetic testing"),
    ],
    "security": [
        ("WAF", "Web application firewall"),
        ("Secrets Manager", "Secrets and credential storage"),
        ("Certificate Manager", "TLS certificate management"),
        ("Audit Service", "Security audit logging"),
        ("Vulnerability Scanner", "Security scanning"),
    ],
    "ml": [
        ("ML Platform", "Machine learning infrastructure"),
        ("Model Registry", "ML model versioning"),
        ("Feature Store", "ML feature management"),
        ("Inference Service", "Real-time model inference"),
    ],
}

DEPENDENCIES = [
    ("API Gateway", "DEPENDS_ON", "Auth Service"),
    ("API Gateway", "DEPENDS_ON", "Rate Limiter"),
    ("API Gateway", "DEPENDS_ON", "Load Balancer"),
    ("API Gateway", "CALLS", "Order Service"),
    ("API Gateway", "CALLS", "User Service"),
    ("API Gateway", "CALLS", "Product Service"),
    ("API Gateway", "CALLS", "Cart Service"),
    ("API Gateway", "CALLS", "Search Service"),
    
    ("GraphQL Gateway", "DEPENDS_ON", "API Gateway"),
    ("GraphQL Gateway", "CALLS", "Order Service"),
    ("GraphQL Gateway", "CALLS", "User Service"),
    ("GraphQL Gateway", "CALLS", "Product Service"),
    
    ("Mobile Gateway", "DEPENDS_ON", "API Gateway"),
    ("WebSocket Gateway", "DEPENDS_ON", "Redis Session"),
    ("Partner Gateway", "DEPENDS_ON", "API Gateway"),
    ("Partner Gateway", "DEPENDS_ON", "API Key Service"),
    
    ("Auth Service", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Auth Service", "DEPENDS_ON", "Redis Session"),
    ("Auth Service", "CALLS", "Identity Provider"),
    ("Auth Service", "CALLS", "MFA Service"),
    
    ("Identity Provider", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Session Manager", "DEPENDS_ON", "Redis Session"),
    ("OAuth Service", "DEPENDS_ON", "Auth Service"),
    ("MFA Service", "DEPENDS_ON", "SMS Service"),
    ("API Key Service", "DEPENDS_ON", "Redis Cache"),
    
    ("Order Service", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Order Service", "DEPENDS_ON", "Kafka"),
    ("Order Service", "CALLS", "Payment Service"),
    ("Order Service", "CALLS", "Inventory Service"),
    ("Order Service", "CALLS", "Pricing Service"),
    ("Order Service", "CALLS", "Fulfillment Service"),
    ("Order Service", "CALLS", "Notification Service"),
    
    ("Payment Service", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Payment Service", "DEPENDS_ON", "Secrets Manager"),
    ("Payment Service", "CALLS", "Audit Service"),
    
    ("Inventory Service", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Inventory Service", "DEPENDS_ON", "Redis Cache"),
    ("Inventory Service", "CALLS", "Kafka"),
    
    ("Pricing Service", "DEPENDS_ON", "Redis Cache"),
    ("Pricing Service", "DEPENDS_ON", "Feature Flag Service"),
    
    ("Cart Service", "DEPENDS_ON", "Redis Cache"),
    ("Cart Service", "CALLS", "Pricing Service"),
    ("Cart Service", "CALLS", "Inventory Service"),
    
    ("Checkout Service", "DEPENDS_ON", "Order Service"),
    ("Checkout Service", "CALLS", "Cart Service"),
    ("Checkout Service", "CALLS", "Payment Service"),
    ("Checkout Service", "CALLS", "Shipping Service"),
    
    ("Fulfillment Service", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Fulfillment Service", "CALLS", "Shipping Service"),
    ("Fulfillment Service", "CALLS", "Notification Service"),
    
    ("Shipping Service", "DEPENDS_ON", "Redis Cache"),
    ("Returns Service", "DEPENDS_ON", "Order Service"),
    ("Returns Service", "CALLS", "Payment Service"),
    ("Returns Service", "CALLS", "Inventory Service"),
    
    ("Subscription Service", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Subscription Service", "CALLS", "Payment Service"),
    ("Subscription Service", "CALLS", "Notification Service"),
    
    ("User Service", "DEPENDS_ON", "PostgreSQL Primary"),
    ("User Service", "DEPENDS_ON", "Redis Cache"),
    ("User Service", "CALLS", "Preferences Service"),
    
    ("Preferences Service", "DEPENDS_ON", "Redis Cache"),
    
    ("Notification Service", "DEPENDS_ON", "Kafka"),
    ("Notification Service", "CALLS", "Email Service"),
    ("Notification Service", "CALLS", "SMS Service"),
    ("Notification Service", "CALLS", "Push Service"),
    
    ("Email Service", "DEPENDS_ON", "S3 Storage"),
    ("SMS Service", "DEPENDS_ON", "Secrets Manager"),
    ("Push Service", "DEPENDS_ON", "Redis Cache"),
    
    ("Product Service", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Product Service", "DEPENDS_ON", "Redis Cache"),
    ("Product Service", "CALLS", "Media Service"),
    
    ("Search Service", "DEPENDS_ON", "Elasticsearch"),
    ("Search Service", "CALLS", "Product Service"),
    
    ("Recommendation Service", "DEPENDS_ON", "Feature Store"),
    ("Recommendation Service", "CALLS", "Inference Service"),
    ("Recommendation Service", "CALLS", "User Service"),
    
    ("Review Service", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Media Service", "DEPENDS_ON", "S3 Storage"),
    ("Media Service", "DEPENDS_ON", "CDN Edge"),
    
    ("Analytics Service", "DEPENDS_ON", "Kafka"),
    ("Analytics Service", "DEPENDS_ON", "Elasticsearch"),
    ("Event Collector", "CALLS", "Kafka"),
    ("Reporting Service", "DEPENDS_ON", "PostgreSQL Replica"),
    ("Dashboard Service", "DEPENDS_ON", "Prometheus"),
    ("A/B Test Service", "DEPENDS_ON", "Feature Flag Service"),
    
    ("Config Service", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Config Service", "DEPENDS_ON", "Redis Cache"),
    ("Feature Flag Service", "DEPENDS_ON", "Config Service"),
    ("Rate Limiter", "DEPENDS_ON", "Redis Cache"),
    ("Circuit Breaker", "DEPENDS_ON", "Redis Cache"),
    ("Service Mesh", "DEPENDS_ON", "Config Service"),
    ("Load Balancer", "DEPENDS_ON", "Service Mesh"),
    ("CDN Edge", "DEPENDS_ON", "S3 Storage"),
    
    ("PostgreSQL Replica", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Kafka Connect", "DEPENDS_ON", "Kafka"),
    ("Kafka Connect", "CALLS", "PostgreSQL Primary"),
    ("Kafka Connect", "CALLS", "Elasticsearch"),
    
    ("Prometheus", "CALLS", "API Gateway"),
    ("Prometheus", "CALLS", "Order Service"),
    ("Prometheus", "CALLS", "Payment Service"),
    ("Grafana", "DEPENDS_ON", "Prometheus"),
    ("AlertManager", "DEPENDS_ON", "Prometheus"),
    ("AlertManager", "CALLS", "PagerDuty Gateway"),
    ("AlertManager", "CALLS", "Notification Service"),
    ("Jaeger", "DEPENDS_ON", "Elasticsearch"),
    ("Log Aggregator", "DEPENDS_ON", "Elasticsearch"),
    ("Log Aggregator", "DEPENDS_ON", "Kafka"),
    ("Synthetic Monitor", "CALLS", "API Gateway"),
    
    ("WAF", "DEPENDS_ON", "Load Balancer"),
    ("Secrets Manager", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Certificate Manager", "DEPENDS_ON", "Secrets Manager"),
    ("Audit Service", "DEPENDS_ON", "Kafka"),
    ("Audit Service", "DEPENDS_ON", "Elasticsearch"),
    ("Vulnerability Scanner", "CALLS", "Audit Service"),
    
    ("ML Platform", "DEPENDS_ON", "Kafka"),
    ("ML Platform", "DEPENDS_ON", "S3 Storage"),
    ("Model Registry", "DEPENDS_ON", "S3 Storage"),
    ("Model Registry", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Feature Store", "DEPENDS_ON", "Redis Cache"),
    ("Feature Store", "DEPENDS_ON", "PostgreSQL Primary"),
    ("Inference Service", "DEPENDS_ON", "Model Registry"),
    ("Inference Service", "DEPENDS_ON", "Feature Store"),
]

HOSTS_RELATIONSHIPS = [
    ("Service Mesh", "HOSTS", "API Gateway"),
    ("Service Mesh", "HOSTS", "Order Service"),
    ("Service Mesh", "HOSTS", "Payment Service"),
    ("Service Mesh", "HOSTS", "User Service"),
    ("Service Mesh", "HOSTS", "Product Service"),
    ("Service Mesh", "HOSTS", "Auth Service"),
    ("Service Mesh", "HOSTS", "Notification Service"),
    ("Service Mesh", "HOSTS", "Search Service"),
    ("Load Balancer", "HOSTS", "API Gateway"),
    ("Load Balancer", "HOSTS", "GraphQL Gateway"),
]


def get_or_create_tenant(conn, tenant_id=None):
    """Get existing tenant or create new one for IT Ops demo."""
    with conn.cursor() as cur:
        if tenant_id:
            cur.execute("SELECT id FROM platform.tenants WHERE id = %s", (tenant_id,))
            row = cur.fetchone()
            if row:
                return row[0]
        
        cur.execute("SELECT id FROM platform.tenants WHERE name = 'IT Ops Demo' LIMIT 1")
        row = cur.fetchone()
        if row:
            return row[0]
        
        new_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO platform.tenants (id, name, slug, created_at)
            VALUES (%s, 'IT Ops Demo', 'it-ops-demo', NOW())
            RETURNING id
        """, (new_id,))
        conn.commit()
        return cur.fetchone()[0]


def create_services(conn, tenant_id):
    """Create all SERVICE entities."""
    entities = []
    for category, services in SERVICES.items():
        for name, description in services:
            entities.append({
                "id": str(uuid.uuid4()),
                "name": name,
                "entity_type": "SERVICE",
                "description": description,
                "category": category,
                "tenant_id": tenant_id,
            })
    
    with conn.cursor() as cur:
        for e in entities:
            cur.execute("""
                SELECT id FROM entities WHERE tenant_id = %s AND name = %s AND entity_type = %s
            """, (e["tenant_id"], e["name"], e["entity_type"]))
            existing = cur.fetchone()
            
            if existing:
                cur.execute("""
                    UPDATE entities SET description = %s, lifecycle_state = 'TRUSTED', confidence = 0.95, updated_at = NOW()
                    WHERE id = %s
                """, (e["description"], existing[0]))
            else:
                cur.execute("""
                    INSERT INTO entities (id, name, entity_type, description, lifecycle_state, confidence, tenant_id, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, 'TRUSTED', 0.95, %s, NOW(), NOW())
                """, (e["id"], e["name"], e["entity_type"], e["description"], e["tenant_id"]))
        conn.commit()
    
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, name FROM entities 
            WHERE tenant_id = %s AND entity_type = 'SERVICE'
        """, (tenant_id,))
        return {row[1]: row[0] for row in cur.fetchall()}


def create_relationships(conn, tenant_id, entity_map):
    """Create all relationships between services."""
    all_rels = DEPENDENCIES + HOSTS_RELATIONSHIPS
    
    inserted = 0
    skipped = 0
    
    with conn.cursor() as cur:
        for source_name, rel_type, target_name in all_rels:
            source_id = entity_map.get(source_name)
            target_id = entity_map.get(target_name)
            
            if not source_id or not target_id:
                skipped += 1
                continue
            
            cur.execute("""
                INSERT INTO relationships (id, source_id, target_id, relationship_type, lifecycle_state, confidence, tenant_id, created_at, updated_at)
                VALUES (%s, %s, %s, %s, 'TRUSTED', 0.95, %s, NOW(), NOW())
                ON CONFLICT DO NOTHING
            """, (str(uuid.uuid4()), source_id, target_id, rel_type, tenant_id))
            inserted += 1
        
        conn.commit()
    
    return inserted, skipped


def verify_data(conn, tenant_id):
    """Verify the seeded data."""
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) FROM entities 
            WHERE tenant_id = %s AND entity_type = 'SERVICE' AND lifecycle_state = 'TRUSTED'
        """, (tenant_id,))
        service_count = cur.fetchone()[0]
        
        cur.execute("""
            SELECT relationship_type, COUNT(*) 
            FROM relationships 
            WHERE tenant_id = %s AND lifecycle_state = 'TRUSTED'
            GROUP BY relationship_type
        """, (tenant_id,))
        rel_counts = dict(cur.fetchall())
        
        cur.execute("""
            SELECT se.name, r.relationship_type, te.name
            FROM relationships r
            JOIN entities se ON r.source_id = se.id
            JOIN entities te ON r.target_id = te.id
            WHERE r.tenant_id = %s 
              AND (se.name = 'API Gateway' OR te.name = 'API Gateway')
              AND r.lifecycle_state = 'TRUSTED'
        """, (tenant_id,))
        api_gateway_rels = cur.fetchall()
        
    return {
        "services": service_count,
        "relationships": rel_counts,
        "api_gateway_connections": api_gateway_rels,
    }


def main():
    parser = argparse.ArgumentParser(description="Seed IT Ops service dependency data")
    parser.add_argument("--tenant-id", type=str, help="Tenant UUID to use")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be created without inserting")
    args = parser.parse_args()
    
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL environment variable required")
        sys.exit(1)
    
    total_services = sum(len(s) for s in SERVICES.values())
    total_rels = len(DEPENDENCIES) + len(HOSTS_RELATIONSHIPS)
    
    print(f"IT Ops Seed Data:")
    print(f"  Services: {total_services}")
    print(f"  Relationships: {total_rels}")
    print(f"    DEPENDS_ON: {sum(1 for r in DEPENDENCIES if r[1] == 'DEPENDS_ON')}")
    print(f"    CALLS: {sum(1 for r in DEPENDENCIES if r[1] == 'CALLS')}")
    print(f"    HOSTS: {len(HOSTS_RELATIONSHIPS)}")
    print()
    
    if args.dry_run:
        print("Dry run - no data inserted")
        return
    
    conn = psycopg2.connect(DATABASE_URL)
    
    try:
        tenant_id = get_or_create_tenant(conn, args.tenant_id)
        print(f"Using tenant: {tenant_id}")
        
        print("Creating services...")
        entity_map = create_services(conn, tenant_id)
        print(f"  Created/updated {len(entity_map)} services")
        
        print("Creating relationships...")
        inserted, skipped = create_relationships(conn, tenant_id, entity_map)
        print(f"  Inserted {inserted} relationships, skipped {skipped}")
        
        print("\nVerifying data...")
        stats = verify_data(conn, tenant_id)
        print(f"  Total services: {stats['services']}")
        print(f"  Relationships by type: {stats['relationships']}")
        print(f"  API Gateway connections: {len(stats['api_gateway_connections'])}")
        
        print("\nAPI Gateway dependency graph:")
        for src, rel, tgt in stats['api_gateway_connections'][:10]:
            print(f"    {src} --[{rel}]--> {tgt}")
        
        print("\n✓ IT Ops seed data loaded successfully")
        print(f"  Tenant ID: {tenant_id}")
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
