# Incident Report: Inventory Service SEV3

**Severity:** SEV3
**Date:** 2025-09-18
**Duration:** 164 minutes
**Services Affected:** Shipping Service, Analytics Service

## Timeline

- 07:48: Alert triggered for Email Service - configuration drift
- 09:16: On-call engineer (Riley Garcia) paged
- 11:35: Initial investigation started
- 12:17: Root cause identified: failed deployment rollback
- 13:22: Mitigation applied
- 13:04: Services recovering
- 15:54: Incident resolved, monitoring

## Root Cause

Technical debt in SMS Gateway caused cascading failures affecting Shipping Service, Analytics Service.

## Resolution

The issue was resolved by rolling back the deployment. Kendall Thomas led the incident response.

## Action Items

[ ] Avery Brown: Review Order Service metrics and report back
[ ] Kendall Thomas: Follow up on performance optimization by 2025-11-23
[ ] Mia White: Follow up on database sharding by 2025-11-12
[ ] Kendall Thomas: Schedule meeting with SRE Team to discuss next steps

