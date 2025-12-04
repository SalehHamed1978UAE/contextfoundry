# Incident Report: Email Service SEV3

**Severity:** SEV3
**Date:** 2025-10-30
**Duration:** 46 minutes
**Services Affected:** Order Service, API Gateway, Shipping Service

## Timeline

- 19:21: Alert triggered for Cache Layer - deployment failures
- 21:12: On-call engineer (Quinn Thompson) paged
- 21:56: Initial investigation started
- 23:48: Root cause identified: memory leak in cache layer
- 23:47: Mitigation applied
- 23:29: Services recovering
- 24:26: Incident resolved, monitoring

## Root Cause

Timeout errors in API Gateway caused cascading failures affecting Order Service, API Gateway, Shipping Service.

## Resolution

The issue was resolved by rolling back the deployment. Avery Brown led the incident response.

## Action Items

[ ] Alex Rivera: Review Payment Service metrics and report back
[ ] Harper Taylor: Follow up on observability stack by 2025-11-30
[ ] Alex Rivera: Create proposal for cost reduction improvements
[ ] Mia White: Schedule meeting with DevOps Team to discuss next steps
[ ] Casey Martinez: Schedule meeting with API Team to discuss next steps

