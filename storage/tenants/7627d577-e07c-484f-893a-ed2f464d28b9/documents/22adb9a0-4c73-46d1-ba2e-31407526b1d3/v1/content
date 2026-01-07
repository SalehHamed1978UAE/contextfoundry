# Nexus Platform - On-Call Procedures

**Document Owner**: Engineering Leadership  
**Last Updated**: December 2025

---

## On-Call Expectations

On-call engineers are expected to:
1. Acknowledge pages within 5 minutes
2. Begin investigation within 15 minutes
3. Escalate if unable to resolve within 30 minutes
4. Document all incidents in incident management system

---

## Incident Severity Definitions

### SEV-1: Critical
- Complete service outage affecting all customers
- Data loss or security breach
- Revenue impact > $10,000/hour

**Examples:**
- Auth Service down (blocks all services)
- Orders Database corruption
- Payment processing completely failed

**Response:**
- All hands on deck
- Executive notification required
- Bridge call initiated immediately

### SEV-2: Major
- Partial service degradation
- Significant customer impact
- Revenue impact > $1,000/hour

**Examples:**
- Payment Service intermittent failures
- High latency on order submission
- Notification delivery delays > 1 hour

**Response:**
- Primary on-call investigates
- Team lead notified
- Status page updated

### SEV-3: Minor
- Limited customer impact
- Workaround available
- No revenue impact

**Examples:**
- Single customer reporting issues
- Non-critical feature degraded
- Elevated error rate < 1%

**Response:**
- Primary on-call investigates
- Fix during business hours acceptable

---

## Service Dependency Quick Reference

When investigating issues, understand the dependency chain:

### If Auth Service is down:
**Everything fails.** Auth Service is a dependency for:
- API Gateway (token validation)
- Order Service (customer authentication)
- Payment Service (merchant authentication)
- Inventory Service (service-to-service auth)

**Escalate to**: Security Team (security-oncall)

### If Payment Service is down:
**Orders fail at checkout.** Payment Service affects:
- Order Service (cannot complete payments)

Does NOT affect:
- Auth Service (independent)
- Inventory Service (can still check stock)
- API Gateway (can still route)

**Escalate to**: Commerce Team (commerce-primary)

### If Orders Database is down:
**Order Service fails completely.** Affects:
- Order Service (cannot persist orders)

Does NOT affect other databases or services directly.

**Escalate to**: Data Engineering Team (data-oncall)

### If Inventory Service is down:
**Orders fail at stock check.** Affects:
- Order Service (cannot verify stock)

Does NOT affect:
- Payment Service (can still process payments)
- Auth Service (independent)

**Escalate to**: Commerce Team (commerce-primary)

---

## Blast Radius Reference

| Service Failure | Direct Impact | Indirect Impact |
|-----------------|---------------|-----------------|
| Auth Service | All authenticated services | All customers |
| Payment Service | Order Service | Checkout flow |
| Inventory Service | Order Service | Stock-dependent orders |
| Orders Database | Order Service | All orders |
| Users Database | Auth Service | All authenticated services |
| Payments Database | Payment Service | Order Service |
| Session Cache | API Gateway, Auth Service | All requests |

---

## Communication Templates

### Status Page Update
```
[INVESTIGATING] We are investigating issues with [SERVICE].
Customers may experience [SYMPTOM]. We will provide updates every 30 minutes.
```

### Incident Resolved
```
[RESOLVED] The issue with [SERVICE] has been resolved.
Root cause: [BRIEF DESCRIPTION]. 
Duration: [TIME]. 
Detailed postmortem to follow.
```

---

## Post-Incident Requirements

All SEV-1 and SEV-2 incidents require:
1. Incident timeline document within 24 hours
2. Root cause analysis within 3 business days
3. Action items with owners and due dates
4. Team retrospective meeting
5. Postmortem published to engineering wiki
