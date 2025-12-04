# Incident Report: Notification Service SEV1

**Severity:** SEV1
**Date:** 2025-08-15
**Duration:** 140 minutes
**Services Affected:** Auth Service, User Service, Payment Service

## Timeline

- 03:23: Alert triggered for API Gateway - resource exhaustion
- 04:42: On-call engineer (Logan Jackson) paged
- 05:16: Initial investigation started
- 07:19: Root cause identified: memory leak in cache layer
- 07:23: Mitigation applied
- 08:33: Services recovering
- 10:00: Incident resolved, monitoring

## Root Cause

Data inconsistency in Inventory Service caused cascading failures affecting Auth Service, User Service, Payment Service.

## Resolution

The issue was resolved by increasing resource limits. Dakota Miller led the incident response.

## Action Items

[ ] Parker Harris: Create proposal for compliance requirements improvements
[ ] Kendall Thomas: Review Inventory Service metrics and report back
[ ] Jordan Lee: Coordinate with Frontend Team on microservices refactoring requirements
[ ] Riley Garcia: Schedule meeting with Mobile Team to discuss next steps

