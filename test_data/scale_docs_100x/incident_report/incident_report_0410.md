# Incident Report: User Service SEV3

**Severity:** SEV3
**Date:** 2025-07-19
**Duration:** 109 minutes
**Services Affected:** Search Service, Order Service

## Timeline

- 08:57: Alert triggered for Order Service - data inconsistency
- 08:43: On-call engineer (Emerson Wilson) paged
- 08:58: Initial investigation started
- 10:15: Root cause identified: database connection pool exhaustion
- 12:08: Mitigation applied
- 12:18: Services recovering
- 14:20: Incident resolved, monitoring

## Root Cause

Resource exhaustion in API Gateway caused cascading failures affecting Search Service, Order Service.

## Resolution

The issue was resolved by applying a hotfix. Parker Harris led the incident response.

## Action Items

[ ] Logan Jackson: Coordinate with Security Team on vendor evaluation requirements
[ ] Logan Jackson: Coordinate with Security Team on performance optimization requirements
[ ] Tatum Lewis: Review Notification Service metrics and report back
[ ] Alex Rivera: Schedule meeting with Growth Team to discuss next steps
[ ] Alex Rivera: Coordinate with Infrastructure Team on team restructuring requirements

