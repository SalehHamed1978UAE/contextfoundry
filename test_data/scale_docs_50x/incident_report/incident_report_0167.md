# Incident Report: Cache Layer SEV1

**Severity:** SEV1
**Date:** 2025-06-12
**Duration:** 71 minutes
**Services Affected:** SMS Gateway, Cache Layer, Inventory Service, Notification Service

## Timeline

- 04:33: Alert triggered for Checkout Service - scaling bottlenecks
- 05:34: On-call engineer (Harper Taylor) paged
- 06:25: Initial investigation started
- 07:27: Root cause identified: database connection pool exhaustion
- 07:26: Mitigation applied
- 08:45: Services recovering
- 08:40: Incident resolved, monitoring

## Root Cause

Memory leaks in Search Service caused cascading failures affecting SMS Gateway, Cache Layer, Inventory Service, Notification Service.

## Resolution

The issue was resolved by applying a hotfix. Casey Martinez led the incident response.

## Action Items

[ ] Mia White: Create proposal for hiring priorities improvements
[ ] Harper Taylor: Create proposal for cloud migration improvements
[ ] Blake Walker: Review API Gateway metrics and report back
[ ] Blake Walker: Schedule meeting with Frontend Team to discuss next steps

