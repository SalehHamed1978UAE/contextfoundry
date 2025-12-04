# Incident Report: Order Service SEV2

**Severity:** SEV2
**Date:** 2025-07-24
**Duration:** 125 minutes
**Services Affected:** User Service, Notification Service, Fraud Detection

## Timeline

- 17:26: Alert triggered for Shipping Service - data inconsistency
- 18:37: On-call engineer (Casey Martinez) paged
- 19:40: Initial investigation started
- 21:46: Root cause identified: certificate expiration
- 23:02: Mitigation applied
- 25:36: Services recovering
- 27:24: Incident resolved, monitoring

## Root Cause

Deployment failures in Analytics Service caused cascading failures affecting User Service, Notification Service, Fraud Detection.

## Resolution

The issue was resolved by rolling back the deployment. Reese Martin led the incident response.

## Action Items

[ ] Jamie Anderson: Schedule meeting with Mobile Team to discuss next steps
[ ] Sage Robinson: Coordinate with API Team on CI/CD pipeline requirements
[ ] Logan Jackson: Coordinate with Infrastructure Team on microservices refactoring requirements

