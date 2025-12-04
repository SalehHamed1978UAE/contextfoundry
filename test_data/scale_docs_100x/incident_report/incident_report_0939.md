# Incident Report: Email Service SEV1

**Severity:** SEV1
**Date:** 2025-09-19
**Duration:** 67 minutes
**Services Affected:** Recommendation Engine, Search Service

## Timeline

- 12:20: Alert triggered for Checkout Service - error rates increasing
- 13:24: On-call engineer (Morgan Chen) paged
- 14:29: Initial investigation started
- 14:48: Root cause identified: failed deployment rollback
- 14:47: Mitigation applied
- 15:18: Services recovering
- 17:56: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in Auth Service caused cascading failures affecting Recommendation Engine, Search Service.

## Resolution

The issue was resolved by rolling back the deployment. Casey Martinez led the incident response.

## Action Items

[ ] Sydney Clark: Follow up on microservices refactoring by 2025-11-20
[ ] Casey Martinez: Review User Service metrics and report back
[ ] Parker Harris: Create proposal for documentation improvements
[ ] Sydney Clark: Create proposal for API versioning improvements
[ ] Drew Patel: Schedule meeting with QA Team to discuss next steps

