# Architecture Document: Order Processing System

## Overview

The order processing system handles the complete lifecycle of customer orders, from placement through fulfillment. This document describes the architecture, service dependencies, and operational considerations.

## System Components

### Core Services

**order-service**
The order-service is the central orchestrator for order processing. It is owned by the commerce-team and deployed on Kubernetes. The order-service receives orders from the api-gateway and coordinates with downstream services for payment, inventory, and fulfillment.

- Runtime: Java 17 (Spring Boot)
- Port: 8090
- Health endpoint: /actuator/health
- Repository: github.com/internal/order-service

**inventory-service**
The inventory-service tracks product availability and manages stock reservations. It is owned by the commerce-team. The inventory-service depends on inventory-db (PostgreSQL) for persistent storage and inventory-cache (Redis) for fast lookups.

- Runtime: Go 1.21
- Port: 8091
- Health endpoint: /health

**fulfillment-service**
The fulfillment-service manages shipping and delivery tracking. It is owned by the logistics-team and integrates with external shipping providers via the shipping-gateway.

- Runtime: Python 3.11 (FastAPI)
- Port: 8092
- Health endpoint: /health

### Infrastructure Components

**orders-db** (PostgreSQL 15)
Primary database for order data. Handles ~50,000 writes per day. Owned by the database-team.
- Host: db-prod-orders.internal
- Replication: Streaming replication to read replica
- Backup: Daily snapshots to S3

**inventory-db** (PostgreSQL 15)
Product inventory and stock levels. Owned by the database-team.
- Host: db-prod-inventory.internal
- Replication: Streaming replication to read replica

**inventory-cache** (Redis 7.2)
Fast cache for product availability checks. TTL: 60 seconds.
- Host: redis-prod-inventory.internal

**order-events** (Apache Kafka)
Event streaming for order state changes. Used by billing-service, notification-service, and analytics-pipeline for event-driven processing.
- Cluster: kafka-prod-01.internal
- Topics: order.created, order.paid, order.shipped, order.completed

## Service Dependencies

```
api-gateway → order-service → payment-api (payment processing)
                            → inventory-service (stock check/reserve)
                            → fulfillment-service (shipping)
                            → notification-service (order confirmations)

order-service → orders-db (persistence)
order-service → order-events (event publishing)

inventory-service → inventory-db (persistence)
inventory-service → inventory-cache (fast reads)

fulfillment-service → shipping-gateway (external)
```

## Team Ownership

| Component | Team | Primary Contact |
|-----------|------|----------------|
| order-service | commerce-team | Sarah Park |
| inventory-service | commerce-team | Sarah Park |
| fulfillment-service | logistics-team | James Wilson |
| orders-db | database-team | Bob Martinez |
| inventory-db | database-team | Bob Martinez |
| order-events | platform-team | David Kim |
| api-gateway | platform-team | David Kim |

## Failure Modes

### Order Service Failure
If order-service goes down, all new orders are blocked. The api-gateway returns 503 to clients. Existing orders in-flight may be in inconsistent state.

**Recovery:** Restart order-service. Check orders-db for partially committed orders. Replay events from order-events Kafka topic if needed.

### Payment Integration Failure
If payment-api is unreachable, order-service queues payment requests in order-events for retry. Orders enter "payment_pending" state. The payment-api team (payments-team) should be contacted via PagerDuty.

### Inventory Service Failure
If inventory-service is down, order-service uses stale cache data from inventory-cache (best-effort). Stock reservations may fail, requiring manual reconciliation by commerce-team.

## Monitoring

- Grafana dashboards: "Order Pipeline", "Inventory Levels", "Fulfillment SLA"
- PagerDuty routing: commerce-team for order/inventory, logistics-team for fulfillment
- SLA: 99.9% for order placement, 99.5% for fulfillment initiation

## Document Metadata

- **Author**: Sarah Park (commerce-team)
- **Last Updated**: 2024-12-01
- **Version**: 1.0
- **Review Cycle**: Quarterly
