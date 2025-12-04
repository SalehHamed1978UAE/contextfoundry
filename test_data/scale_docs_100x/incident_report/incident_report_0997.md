# Incident Report: Cache Layer SEV3

**Severity:** SEV3
**Date:** 2025-10-17
**Duration:** 113 minutes
**Services Affected:** Email Service, Payment Service, Search Service, Recommendation Engine

## Timeline

- 21:37: Alert triggered for Email Service - missing documentation
- 23:10: On-call engineer (Tatum Lewis) paged
- 25:46: Initial investigation started
- 26:53: Root cause identified: database connection pool exhaustion
- 28:27: Mitigation applied
- 29:57: Services recovering
- 31:57: Incident resolved, monitoring

## Root Cause

Technical debt in User Service caused cascading failures affecting Email Service, Payment Service, Search Service, Recommendation Engine.

## Resolution

The issue was resolved by rolling back the deployment. Blake Walker led the incident response.

## Action Items

[ ] Sage Robinson: Follow up on compliance requirements by 2025-11-06
[ ] Drew Patel: Coordinate with Security Team on scalability planning requirements

