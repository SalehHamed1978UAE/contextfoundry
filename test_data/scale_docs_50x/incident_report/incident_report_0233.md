# Incident Report: API Gateway SEV2

**Severity:** SEV2
**Date:** 2025-08-28
**Duration:** 178 minutes
**Services Affected:** Fraud Detection, User Service, Checkout Service, Search Service

## Timeline

- 15:51: Alert triggered for Shipping Service - technical debt
- 15:55: On-call engineer (Alex Rivera) paged
- 16:37: Initial investigation started
- 16:26: Root cause identified: resource limit reached
- 17:28: Mitigation applied
- 18:24: Services recovering
- 18:45: Incident resolved, monitoring

## Root Cause

Error rates increasing in Inventory Service caused cascading failures affecting Fraud Detection, User Service, Checkout Service, Search Service.

## Resolution

The issue was resolved by restarting affected services. Jamie Anderson led the incident response.

## Action Items

[ ] Sage Robinson: Follow up on technical debt by 2025-11-09
[ ] Reese Martin: Follow up on caching strategy by 2025-11-22
[ ] Sage Robinson: Review Fraud Detection metrics and report back

