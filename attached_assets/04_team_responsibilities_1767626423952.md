# Nexus Platform - Team Responsibilities

**Document Owner**: Engineering Leadership  
**Last Updated**: December 2025  
**Purpose**: Define ownership and escalation paths for all platform components

---

## Team Overview

### Platform Engineering Team

**Team Lead**: Alex Thompson  
**Headcount**: 8 engineers  
**Focus**: Infrastructure, developer experience, cross-cutting concerns

**Services Owned:**
- API Gateway
- Notification Service
- Session Cache
- CI/CD Pipeline
- Monitoring Infrastructure

**On-call rotation**: platform-primary (PagerDuty)  
**Escalation contact**: Alex Thompson (alex.t@nexus.example)

**Responsibilities:**
- API Gateway routing and rate limiting configuration
- Notification delivery reliability
- Session management and caching strategy
- Platform-wide observability
- Developer tooling and deployment pipelines

---

### Commerce Team

**Team Lead**: David Kim  
**Headcount**: 12 engineers  
**Focus**: Customer-facing commerce functionality

**Services Owned:**
- Order Service
- Payment Service
- Inventory Service
- Shopping Cart Service (deprecated, migrating to Order Service)

**On-call rotation**: commerce-primary (PagerDuty)  
**Escalation contact**: David Kim (david.k@nexus.example)

**Responsibilities:**
- Order processing and fulfillment
- Payment processing and PCI compliance
- Inventory management and stock allocation
- Cart and checkout experience
- Commerce business logic

---

### Security Team

**Team Lead**: Sarah Chen  
**Headcount**: 5 engineers  
**Focus**: Authentication, authorization, security

**Services Owned:**
- Auth Service
- Identity Provider integration
- Secret management infrastructure

**On-call rotation**: security-oncall (PagerDuty)  
**Escalation contact**: Sarah Chen (sarah.c@nexus.example)

**Responsibilities:**
- User authentication and session management
- API authorization and token validation
- Security incident response
- Penetration testing coordination
- Compliance certifications (SOC2, PCI-DSS)

---

### Data Engineering Team

**Team Lead**: Maria Santos  
**Headcount**: 6 engineers  
**Focus**: Data infrastructure, databases, analytics

**Services Owned:**
- Orders Database
- Payments Database
- Users Database
- Products Database
- Data Warehouse
- ETL Pipelines

**On-call rotation**: data-oncall (PagerDuty)  
**Escalation contact**: Maria Santos (maria.s@nexus.example)

**Responsibilities:**
- Database administration and optimization
- Backup and disaster recovery
- Data replication and consistency
- Analytics and reporting infrastructure
- Data governance and retention policies

---

## Cross-Team Dependencies

### Platform Engineering depends on:
- Security Team for Auth Service integration
- Data Engineering Team for monitoring data storage

### Commerce Team depends on:
- Security Team for Auth Service (payment validation)
- Platform Engineering for API Gateway configuration
- Platform Engineering for Notification Service
- Data Engineering for database support

### Security Team depends on:
- Data Engineering for Users Database
- Platform Engineering for Session Cache

### Data Engineering depends on:
- Security Team for database credential management
- Platform Engineering for backup infrastructure

---

## Escalation Matrix

| Severity | First Response | Escalation (15 min) | Executive (30 min) |
|----------|----------------|---------------------|-------------------|
| SEV-1 | On-call engineer | Team Lead | VP Engineering |
| SEV-2 | On-call engineer | Team Lead | - |
| SEV-3 | On-call engineer | - | - |

---

## Service Ownership Quick Reference

| Service | Team | Lead | On-call |
|---------|------|------|---------|
| API Gateway | Platform Engineering | Alex Thompson | platform-primary |
| Order Service | Commerce | David Kim | commerce-primary |
| Payment Service | Commerce | David Kim | commerce-primary |
| Inventory Service | Commerce | David Kim | commerce-primary |
| Auth Service | Security | Sarah Chen | security-oncall |
| Notification Service | Platform Engineering | Alex Thompson | platform-primary |
| Orders Database | Data Engineering | Maria Santos | data-oncall |
| Payments Database | Data Engineering | Maria Santos | data-oncall |
| Users Database | Data Engineering | Maria Santos | data-oncall |
| Products Database | Data Engineering | Maria Santos | data-oncall |
| Session Cache | Platform Engineering | Alex Thompson | platform-primary |

---

## Contact Information

For urgent issues outside business hours:
1. Page the appropriate on-call rotation via PagerDuty
2. If no response in 15 minutes, escalate to team lead
3. For SEV-1 incidents, create bridge call and page all affected team leads
