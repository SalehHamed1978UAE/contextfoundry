# Incident Report: Cache Layer SEV1

**Severity:** SEV1
**Date:** 2025-09-07
**Duration:** 41 minutes
**Services Affected:** Auth Service, Shipping Service, Order Service, Analytics Service

## Timeline

- 09:35: Alert triggered for Cache Layer - error rates increasing
- 10:07: On-call engineer (Dakota Miller) paged
- 10:33: Initial investigation started
- 12:31: Root cause identified: failed deployment rollback
- 13:28: Mitigation applied
- 14:57: Services recovering
- 15:33: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in Payment Service caused cascading failures affecting Auth Service, Shipping Service, Order Service, Analytics Service.

## Resolution

The issue was resolved by rolling back the deployment. Jamie Anderson led the incident response.

## Action Items

[ ] Dakota Miller: Coordinate with Data Team on microservices refactoring requirements
[ ] Mia White: Review Notification Service metrics and report back

