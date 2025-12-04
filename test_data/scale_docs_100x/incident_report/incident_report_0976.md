# Incident Report: Notification Service SEV1

**Severity:** SEV1
**Date:** 2025-08-04
**Duration:** 171 minutes
**Services Affected:** Notification Service, Analytics Service, Inventory Service, Fraud Detection

## Timeline

- 01:03: Alert triggered for Cache Layer - deployment failures
- 01:07: On-call engineer (Emerson Wilson) paged
- 02:59: Initial investigation started
- 02:57: Root cause identified: certificate expiration
- 03:12: Mitigation applied
- 03:35: Services recovering
- 04:39: Incident resolved, monitoring

## Root Cause

Missing documentation in Auth Service caused cascading failures affecting Notification Service, Analytics Service, Inventory Service, Fraud Detection.

## Resolution

The issue was resolved by rolling back the deployment. Harper Taylor led the incident response.

## Action Items

[ ] Dakota Miller: Review Analytics Service metrics and report back
[ ] Riley Garcia: Follow up on CI/CD pipeline by 2025-11-12
[ ] Taylor Kim: Schedule meeting with Infrastructure Team to discuss next steps

