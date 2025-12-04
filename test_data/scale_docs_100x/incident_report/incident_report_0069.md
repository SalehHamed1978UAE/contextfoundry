# Incident Report: API Gateway SEV2

**Severity:** SEV2
**Date:** 2025-09-25
**Duration:** 69 minutes
**Services Affected:** Search Service, Notification Service, Inventory Service, SMS Gateway

## Timeline

- 07:55: Alert triggered for Email Service - latency issues
- 08:13: On-call engineer (Jamie Anderson) paged
- 10:06: Initial investigation started
- 11:17: Root cause identified: failed deployment rollback
- 11:37: Mitigation applied
- 11:31: Services recovering
- 11:40: Incident resolved, monitoring

## Root Cause

Deployment failures in Inventory Service caused cascading failures affecting Search Service, Notification Service, Inventory Service, SMS Gateway.

## Resolution

The issue was resolved by restarting affected services. Blake Adams led the incident response.

## Action Items

[ ] Taylor Kim: Follow up on caching strategy by 2025-11-24
[ ] Avery Brown: Create proposal for monitoring improvements improvements
[ ] Taylor Kim: Create proposal for budget allocation improvements
[ ] Avery Brown: Schedule meeting with DevOps Team to discuss next steps
[ ] Blake Adams: Follow up on caching strategy by 2025-11-30

