# Incident Report: Cache Layer SEV1

**Severity:** SEV1
**Date:** 2025-07-01
**Duration:** 125 minutes
**Services Affected:** Analytics Service

## Timeline

- 09:54: Alert triggered for Inventory Service - resource exhaustion
- 10:50: On-call engineer (Taylor Kim) paged
- 10:48: Initial investigation started
- 10:37: Root cause identified: memory leak in cache layer
- 11:39: Mitigation applied
- 12:14: Services recovering
- 14:18: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Notification Service caused cascading failures affecting Analytics Service.

## Resolution

The issue was resolved by increasing resource limits. Emerson Wilson led the incident response.

## Action Items

[ ] Morgan Chen: Schedule meeting with API Team to discuss next steps
[ ] Morgan Chen: Schedule meeting with Mobile Team to discuss next steps
[ ] Morgan Chen: Follow up on CI/CD pipeline by 2025-11-06

