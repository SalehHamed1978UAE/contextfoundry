# Incident Report: Email Service SEV1

**Severity:** SEV1
**Date:** 2025-07-28
**Duration:** 122 minutes
**Services Affected:** API Gateway, Recommendation Engine, Search Service, Checkout Service

## Timeline

- 05:36: Alert triggered for API Gateway - scaling bottlenecks
- 06:42: On-call engineer (Dakota Miller) paged
- 07:28: Initial investigation started
- 09:40: Root cause identified: memory leak in cache layer
- 10:03: Mitigation applied
- 12:58: Services recovering
- 13:18: Incident resolved, monitoring

## Root Cause

Missing documentation in Cache Layer caused cascading failures affecting API Gateway, Recommendation Engine, Search Service, Checkout Service.

## Resolution

The issue was resolved by rolling back the deployment. Harper Taylor led the incident response.

## Action Items

[ ] Dakota Miller: Review Cache Layer metrics and report back
[ ] Sydney Clark: Review Payment Service metrics and report back
[ ] Alex Rivera: Schedule meeting with Growth Team to discuss next steps

