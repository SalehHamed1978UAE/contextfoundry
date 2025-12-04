# Incident Report: Payment Service SEV3

**Severity:** SEV3
**Date:** 2025-09-19
**Duration:** 155 minutes
**Services Affected:** Search Service, Auth Service

## Timeline

- 08:19: Alert triggered for Email Service - latency issues
- 09:38: On-call engineer (Reese Martin) paged
- 11:07: Initial investigation started
- 11:03: Root cause identified: network partition in Order Service
- 12:52: Mitigation applied
- 12:55: Services recovering
- 12:13: Incident resolved, monitoring

## Root Cause

Timeout errors in Payment Service caused cascading failures affecting Search Service, Auth Service.

## Resolution

The issue was resolved by restarting affected services. Emerson Wilson led the incident response.

## Action Items

[ ] Reese Martin: Create proposal for Q4 planning improvements
[ ] Finley Moore: Create proposal for observability stack improvements
[ ] Sydney Clark: Schedule meeting with SRE Team to discuss next steps
[ ] Finley Moore: Follow up on monitoring improvements by 2025-11-28

