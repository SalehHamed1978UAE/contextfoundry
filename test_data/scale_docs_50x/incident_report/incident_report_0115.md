# Incident Report: Order Service SEV3

**Severity:** SEV3
**Date:** 2025-06-29
**Duration:** 136 minutes
**Services Affected:** Checkout Service, Analytics Service, Shipping Service, Inventory Service

## Timeline

- 14:04: Alert triggered for SMS Gateway - memory leaks
- 14:17: On-call engineer (Finley Moore) paged
- 16:42: Initial investigation started
- 17:00: Root cause identified: failed deployment rollback
- 17:27: Mitigation applied
- 18:22: Services recovering
- 19:21: Incident resolved, monitoring

## Root Cause

Data inconsistency in Fraud Detection caused cascading failures affecting Checkout Service, Analytics Service, Shipping Service, Inventory Service.

## Resolution

The issue was resolved by rolling back the deployment. Taylor Kim led the incident response.

## Action Items

[ ] Kendall Thomas: Follow up on cloud migration by 2025-11-25
[ ] Blake Walker: Review SMS Gateway metrics and report back
[ ] Blake Walker: Follow up on hiring priorities by 2025-11-30
[ ] Kendall Thomas: Review Search Service metrics and report back

