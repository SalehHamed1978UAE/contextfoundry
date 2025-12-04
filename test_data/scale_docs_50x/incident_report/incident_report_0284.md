# Incident Report: Cache Layer SEV3

**Severity:** SEV3
**Date:** 2025-11-03
**Duration:** 171 minutes
**Services Affected:** SMS Gateway, Email Service

## Timeline

- 00:08: Alert triggered for Payment Service - missing documentation
- 00:07: On-call engineer (Harper Taylor) paged
- 00:34: Initial investigation started
- 01:31: Root cause identified: database connection pool exhaustion
- 01:20: Mitigation applied
- 03:19: Services recovering
- 03:52: Incident resolved, monitoring

## Root Cause

Latency issues in Payment Service caused cascading failures affecting SMS Gateway, Email Service.

## Resolution

The issue was resolved by increasing resource limits. Tatum Lewis led the incident response.

## Action Items

[ ] Logan Jackson: Review Checkout Service metrics and report back
[ ] Emerson Wilson: Create proposal for testing strategy improvements
[ ] Logan Jackson: Follow up on caching strategy by 2025-12-03
[ ] Logan Jackson: Follow up on Q4 planning by 2025-11-21
[ ] Emerson Wilson: Create proposal for cloud migration improvements

