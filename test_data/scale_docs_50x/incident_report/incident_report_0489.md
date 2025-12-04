# Incident Report: Analytics Service SEV1

**Severity:** SEV1
**Date:** 2025-10-24
**Duration:** 158 minutes
**Services Affected:** Notification Service, Order Service, User Service

## Timeline

- 03:47: Alert triggered for Shipping Service - timeout errors
- 05:55: On-call engineer (Sydney Clark) paged
- 05:36: Initial investigation started
- 05:12: Root cause identified: failed deployment rollback
- 05:05: Mitigation applied
- 05:11: Services recovering
- 06:24: Incident resolved, monitoring

## Root Cause

Missing documentation in Notification Service caused cascading failures affecting Notification Service, Order Service, User Service.

## Resolution

The issue was resolved by restarting affected services. Blake Adams led the incident response.

## Action Items

[ ] Harper Taylor: Coordinate with QA Team on monitoring improvements requirements
[ ] Harper Taylor: Schedule meeting with QA Team to discuss next steps

