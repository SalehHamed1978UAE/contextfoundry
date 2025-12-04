# Incident Report: API Gateway SEV3

**Severity:** SEV3
**Date:** 2025-07-05
**Duration:** 168 minutes
**Services Affected:** Recommendation Engine, Email Service

## Timeline

- 13:04: Alert triggered for Search Service - error rates increasing
- 15:16: On-call engineer (Sage Robinson) paged
- 16:08: Initial investigation started
- 18:13: Root cause identified: failed deployment rollback
- 18:06: Mitigation applied
- 19:39: Services recovering
- 20:32: Incident resolved, monitoring

## Root Cause

Latency issues in Auth Service caused cascading failures affecting Recommendation Engine, Email Service.

## Resolution

The issue was resolved by applying a hotfix. Reese Martin led the incident response.

## Action Items

[ ] Jamie Anderson: Create proposal for Q4 planning improvements
[ ] Cameron Davis: Follow up on Q4 planning by 2025-11-23
[ ] Cameron Davis: Coordinate with Growth Team on hiring priorities requirements

