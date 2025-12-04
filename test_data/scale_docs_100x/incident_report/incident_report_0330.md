# Incident Report: Checkout Service SEV1

**Severity:** SEV1
**Date:** 2025-12-01
**Duration:** 67 minutes
**Services Affected:** Checkout Service, Recommendation Engine

## Timeline

- 08:27: Alert triggered for API Gateway - latency issues
- 08:58: On-call engineer (Emerson Wilson) paged
- 10:41: Initial investigation started
- 12:56: Root cause identified: memory leak in cache layer
- 13:04: Mitigation applied
- 15:31: Services recovering
- 17:17: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Cache Layer caused cascading failures affecting Checkout Service, Recommendation Engine.

## Resolution

The issue was resolved by increasing resource limits. Jordan Lee led the incident response.

## Action Items

[ ] Riley Garcia: Create proposal for technical debt improvements
[ ] Drew Patel: Follow up on monitoring improvements by 2025-12-04
[ ] Mia White: Schedule meeting with Security Team to discuss next steps

