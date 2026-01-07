# Nexus Platform - Architecture Overview

**Document Owner**: Platform Engineering  
**Last Updated**: December 2025  
**Classification**: Internal

---

## Executive Summary

Nexus Platform is our customer-facing e-commerce system handling approximately 50,000 orders per day. This document describes the service architecture, dependencies, and ownership.

---

## Core Services

### API Gateway
The API Gateway is the entry point for all customer traffic. It handles authentication, rate limiting, and request routing. The API Gateway depends on the Auth Service for token validation and the Session Cache for storing active sessions.

**Owner**: Platform Engineering Team  
**On-call rotation**: PagerDuty schedule "platform-primary"  
**SLA**: 99.95% availability

### Order Service
The Order Service processes customer orders from cart to fulfillment. It depends on the Inventory Service for stock checks, the Payment Service for transaction processing, and the Notification Service for customer communications. Order data is persisted to the Orders Database.

**Owner**: Commerce Team  
**On-call rotation**: PagerDuty schedule "commerce-primary"  
**SLA**: 99.9% availability

### Payment Service
The Payment Service handles all financial transactions including credit card processing, refunds, and payment validation. It depends on the Auth Service for merchant authentication and connects to external payment processors (Stripe, PayPal). Transaction records are stored in the Payments Database.

**Owner**: Commerce Team  
**On-call rotation**: PagerDuty schedule "commerce-primary"  
**SLA**: 99.99% availability (PCI requirement)

### Inventory Service
The Inventory Service manages product availability, warehouse allocation, and stock reservations. It depends on the Products Database for catalog information and publishes events to the Event Bus when stock levels change.

**Owner**: Commerce Team  
**On-call rotation**: PagerDuty schedule "commerce-primary"

### Auth Service
The Auth Service handles user authentication, authorization, and session management. It depends on the Users Database for credential storage and the Session Cache for active session data. All other services depend on Auth Service for token validation.

**Owner**: Security Team  
**On-call rotation**: PagerDuty schedule "security-oncall"  
**SLA**: 99.99% availability (security critical)

### Notification Service
The Notification Service sends emails, SMS, and push notifications to customers. It depends on customer preferences stored in the Users Database and uses external providers (SendGrid, Twilio) for delivery.

**Owner**: Platform Engineering Team  
**On-call rotation**: PagerDuty schedule "platform-primary"

---

## Data Stores

### Orders Database
PostgreSQL database containing order records, line items, and order history. Primary data store for Order Service.

**Owner**: Data Engineering Team  
**Backup frequency**: Continuous replication to standby  
**Recovery point objective**: 1 minute

### Payments Database
PostgreSQL database containing transaction records, payment methods, and audit logs. Primary data store for Payment Service. Subject to PCI-DSS compliance requirements.

**Owner**: Data Engineering Team  
**Backup frequency**: Continuous replication  
**Recovery point objective**: 0 (synchronous replication)

### Users Database
PostgreSQL database containing user accounts, credentials (hashed), and preferences. Primary data store for Auth Service.

**Owner**: Data Engineering Team  
**Backup frequency**: Continuous replication  
**Recovery point objective**: 1 minute

### Products Database
PostgreSQL database containing product catalog, pricing, and inventory levels. Primary data store for Inventory Service.

**Owner**: Data Engineering Team  
**Backup frequency**: Hourly snapshots  
**Recovery point objective**: 1 hour

### Session Cache
Redis cluster storing active user sessions and authentication tokens. Used by API Gateway and Auth Service for fast session validation.

**Owner**: Platform Engineering Team  
**Backup frequency**: None (ephemeral)  
**Recovery**: Rebuild from auth tokens

---

## Dependency Summary

```
Customer Request
       ↓
   API Gateway
       ↓
   ┌─────────────────────────────────────┐
   │                                     │
   ↓                                     ↓
Auth Service                      Order Service
   │                                     │
   ↓                              ┌──────┼──────┐
Users Database                    ↓      ↓      ↓
Session Cache              Inventory  Payment  Notification
                           Service   Service   Service
                              │         │
                              ↓         ↓
                          Products   Payments
                          Database   Database
```

---

## Team Ownership

| Team | Services Owned |
|------|----------------|
| Platform Engineering | API Gateway, Notification Service, Session Cache |
| Commerce Team | Order Service, Payment Service, Inventory Service |
| Security Team | Auth Service |
| Data Engineering | All databases |

---

## Change History

- 2025-12: Added Session Cache dependency to API Gateway
- 2025-11: Migrated Payment Service to new Payments Database
- 2025-10: Added Notification Service dependency to Order Service
