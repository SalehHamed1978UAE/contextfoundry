# Incident Report: Auth Service SEV2

**Severity:** SEV2
**Date:** 2025-07-21
**Duration:** 68 minutes
**Services Affected:** Auth Service

## Timeline

- 06:31: Alert triggered for Analytics Service - resource exhaustion
- 06:37: On-call engineer (Blake Adams) paged
- 08:11: Initial investigation started
- 08:25: Root cause identified: database connection pool exhaustion
- 08:11: Mitigation applied
- 10:08: Services recovering
- 12:00: Incident resolved, monitoring

## Root Cause

Latency issues in Analytics Service caused cascading failures affecting Auth Service.

## Resolution

The issue was resolved by increasing resource limits. Cameron Davis led the incident response.

## Action Items

[ ] Blake Adams: Create proposal for capacity planning improvements
[ ] Cameron Davis: Follow up on cloud migration by 2025-11-20
[ ] Drew Patel: Coordinate with Infrastructure Team on security audit requirements
[ ] Drew Patel: Follow up on scalability planning by 2025-11-08
[ ] Jamie Anderson: Schedule meeting with Security Team to discuss next steps

