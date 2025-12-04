# Incident Report: Auth Service SEV2

**Severity:** SEV2
**Date:** 2025-07-23
**Duration:** 56 minutes
**Services Affected:** Analytics Service, Recommendation Engine, Payment Service, Search Service

## Timeline

- 15:03: Alert triggered for Payment Service - memory leaks
- 17:55: On-call engineer (Quinn Thompson) paged
- 17:55: Initial investigation started
- 17:53: Root cause identified: memory leak in cache layer
- 17:02: Mitigation applied
- 18:45: Services recovering
- 20:19: Incident resolved, monitoring

## Root Cause

Resource exhaustion in Recommendation Engine caused cascading failures affecting Analytics Service, Recommendation Engine, Payment Service, Search Service.

## Resolution

The issue was resolved by restarting affected services. Blake Walker led the incident response.

## Action Items

[ ] Jordan Lee: Review API Gateway metrics and report back
[ ] Jordan Lee: Create proposal for observability stack improvements
[ ] Blake Walker: Follow up on testing strategy by 2025-11-13
[ ] Casey Martinez: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Casey Martinez: Schedule meeting with SRE Team to discuss next steps

