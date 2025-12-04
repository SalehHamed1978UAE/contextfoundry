# Incident Report: Inventory Service SEV3

**Severity:** SEV3
**Date:** 2025-06-24
**Duration:** 170 minutes
**Services Affected:** Search Service

## Timeline

- 05:08: Alert triggered for Order Service - security vulnerabilities
- 07:44: On-call engineer (Reese Martin) paged
- 09:20: Initial investigation started
- 10:33: Root cause identified: memory leak in cache layer
- 10:51: Mitigation applied
- 12:48: Services recovering
- 14:03: Incident resolved, monitoring

## Root Cause

Error rates increasing in SMS Gateway caused cascading failures affecting Search Service.

## Resolution

The issue was resolved by rolling back the deployment. Taylor Kim led the incident response.

## Action Items

[ ] Logan Jackson: Create proposal for API versioning improvements
[ ] Avery Brown: Schedule meeting with Security Team to discuss next steps
[ ] Emerson Wilson: Review Email Service metrics and report back
[ ] Cameron Davis: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Cameron Davis: Create proposal for cost reduction improvements

