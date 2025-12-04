# Incident Report: User Service SEV1

**Severity:** SEV1
**Date:** 2025-07-01
**Duration:** 86 minutes
**Services Affected:** Auth Service, SMS Gateway, Checkout Service, Shipping Service

## Timeline

- 06:38: Alert triggered for Recommendation Engine - scaling bottlenecks
- 06:21: On-call engineer (Quinn Thompson) paged
- 06:25: Initial investigation started
- 08:00: Root cause identified: database connection pool exhaustion
- 09:03: Mitigation applied
- 09:38: Services recovering
- 11:34: Incident resolved, monitoring

## Root Cause

Data inconsistency in User Service caused cascading failures affecting Auth Service, SMS Gateway, Checkout Service, Shipping Service.

## Resolution

The issue was resolved by rolling back the deployment. Kendall Thomas led the incident response.

## Action Items

[ ] Blake Adams: Follow up on Q4 planning by 2025-11-28
[ ] Drew Patel: Schedule meeting with Backend Team to discuss next steps

