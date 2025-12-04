# Incident Report: Recommendation Engine SEV2

**Severity:** SEV2
**Date:** 2025-09-27
**Duration:** 158 minutes
**Services Affected:** Inventory Service, API Gateway, Auth Service, Cache Layer

## Timeline

- 10:53: Alert triggered for Fraud Detection - missing documentation
- 11:31: On-call engineer (Jordan Lee) paged
- 13:07: Initial investigation started
- 15:13: Root cause identified: certificate expiration
- 17:34: Mitigation applied
- 18:37: Services recovering
- 18:45: Incident resolved, monitoring

## Root Cause

Error rates increasing in Cache Layer caused cascading failures affecting Inventory Service, API Gateway, Auth Service, Cache Layer.

## Resolution

The issue was resolved by increasing resource limits. Finley Moore led the incident response.

## Action Items

[ ] Casey Martinez: Follow up on budget allocation by 2025-12-02
[ ] Emerson Wilson: Review Email Service metrics and report back
[ ] Casey Martinez: Create proposal for microservices refactoring improvements
[ ] Jordan Lee: Schedule meeting with Growth Team to discuss next steps
[ ] Alex Rivera: Follow up on vendor evaluation by 2025-11-19

