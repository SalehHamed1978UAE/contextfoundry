# Incident Report: Notification Service SEV2

**Severity:** SEV2
**Date:** 2025-11-12
**Duration:** 46 minutes
**Services Affected:** Auth Service, Email Service, Payment Service, Analytics Service

## Timeline

- 02:18: Alert triggered for Analytics Service - resource exhaustion
- 03:19: On-call engineer (Alex Rivera) paged
- 04:31: Initial investigation started
- 04:39: Root cause identified: network partition in Notification Service
- 05:38: Mitigation applied
- 07:32: Services recovering
- 07:39: Incident resolved, monitoring

## Root Cause

Latency issues in Inventory Service caused cascading failures affecting Auth Service, Email Service, Payment Service, Analytics Service.

## Resolution

The issue was resolved by rolling back the deployment. Tatum Lewis led the incident response.

## Action Items

[ ] Parker Harris: Coordinate with Mobile Team on vendor evaluation requirements
[ ] Finley Moore: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Finley Moore: Follow up on CI/CD pipeline by 2025-11-07

