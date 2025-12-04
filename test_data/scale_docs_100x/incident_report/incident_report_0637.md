# Incident Report: Search Service SEV1

**Severity:** SEV1
**Date:** 2025-10-29
**Duration:** 43 minutes
**Services Affected:** User Service, Auth Service, Payment Service

## Timeline

- 12:47: Alert triggered for Auth Service - latency issues
- 12:51: On-call engineer (Blake Adams) paged
- 13:28: Initial investigation started
- 13:28: Root cause identified: database connection pool exhaustion
- 15:06: Mitigation applied
- 16:44: Services recovering
- 17:37: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in Inventory Service caused cascading failures affecting User Service, Auth Service, Payment Service.

## Resolution

The issue was resolved by increasing resource limits. Taylor Kim led the incident response.

## Action Items

[ ] Avery Brown: Create proposal for database sharding improvements
[ ] Mia White: Schedule meeting with QA Team to discuss next steps
[ ] Mia White: Follow up on caching strategy by 2025-11-15
[ ] Mia White: Create proposal for capacity planning improvements

