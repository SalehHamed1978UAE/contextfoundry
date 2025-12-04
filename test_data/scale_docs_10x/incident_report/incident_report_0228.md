# Incident Report: Notification Service SEV3

**Severity:** SEV3
**Date:** 2025-07-07
**Duration:** 78 minutes
**Services Affected:** Email Service, User Service, Inventory Service, Checkout Service

## Timeline

- 18:15: Alert triggered for SMS Gateway - configuration drift
- 18:09: On-call engineer (Riley Garcia) paged
- 20:50: Initial investigation started
- 20:02: Root cause identified: failed deployment rollback
- 20:54: Mitigation applied
- 20:22: Services recovering
- 20:19: Incident resolved, monitoring

## Root Cause

Configuration drift in Email Service caused cascading failures affecting Email Service, User Service, Inventory Service, Checkout Service.

## Resolution

The issue was resolved by increasing resource limits. Cameron Davis led the incident response.

## Action Items

[ ] Cameron Davis: Schedule meeting with Backend Team to discuss next steps
[ ] Drew Patel: Coordinate with Infrastructure Team on database sharding requirements

