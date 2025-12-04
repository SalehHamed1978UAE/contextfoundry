# Incident Report: Auth Service SEV2

**Severity:** SEV2
**Date:** 2025-11-12
**Duration:** 180 minutes
**Services Affected:** API Gateway, Inventory Service, Order Service, Shipping Service

## Timeline

- 22:23: Alert triggered for SMS Gateway - configuration drift
- 23:21: On-call engineer (Jamie Anderson) paged
- 24:17: Initial investigation started
- 25:49: Root cause identified: memory leak in cache layer
- 25:33: Mitigation applied
- 25:54: Services recovering
- 26:17: Incident resolved, monitoring

## Root Cause

Resource exhaustion in Notification Service caused cascading failures affecting API Gateway, Inventory Service, Order Service, Shipping Service.

## Resolution

The issue was resolved by applying a hotfix. Kendall Thomas led the incident response.

## Action Items

[ ] Tatum Lewis: Coordinate with DevOps Team on observability stack requirements
[ ] Casey Martinez: Schedule meeting with Mobile Team to discuss next steps

