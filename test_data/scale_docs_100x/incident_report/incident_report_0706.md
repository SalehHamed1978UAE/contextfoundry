# Incident Report: API Gateway SEV1

**Severity:** SEV1
**Date:** 2025-09-25
**Duration:** 79 minutes
**Services Affected:** Shipping Service

## Timeline

- 11:55: Alert triggered for Search Service - timeout errors
- 13:14: On-call engineer (Reese Martin) paged
- 13:12: Initial investigation started
- 15:07: Root cause identified: database connection pool exhaustion
- 17:39: Mitigation applied
- 18:05: Services recovering
- 18:11: Incident resolved, monitoring

## Root Cause

Missing documentation in Search Service caused cascading failures affecting Shipping Service.

## Resolution

The issue was resolved by restarting affected services. Kendall Thomas led the incident response.

## Action Items

[ ] Sage Robinson: Coordinate with Security Team on disaster recovery requirements
[ ] Alex Rivera: Follow up on vendor evaluation by 2025-11-13

