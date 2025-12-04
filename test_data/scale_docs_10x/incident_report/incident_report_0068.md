# Incident Report: Order Service SEV2

**Severity:** SEV2
**Date:** 2025-09-20
**Duration:** 46 minutes
**Services Affected:** Auth Service, API Gateway, Email Service, Shipping Service

## Timeline

- 07:19: Alert triggered for Email Service - configuration drift
- 09:50: On-call engineer (Parker Harris) paged
- 11:21: Initial investigation started
- 11:29: Root cause identified: resource limit reached
- 12:16: Mitigation applied
- 14:21: Services recovering
- 14:16: Incident resolved, monitoring

## Root Cause

Deployment failures in Order Service caused cascading failures affecting Auth Service, API Gateway, Email Service, Shipping Service.

## Resolution

The issue was resolved by rolling back the deployment. Jamie Anderson led the incident response.

## Action Items

[ ] Alex Rivera: Create proposal for CI/CD pipeline improvements
[ ] Avery Brown: Follow up on database sharding by 2025-11-13
[ ] Mia White: Review SMS Gateway metrics and report back
[ ] Jordan Lee: Create proposal for cost reduction improvements

