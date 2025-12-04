# Incident Report: User Service SEV2

**Severity:** SEV2
**Date:** 2025-06-23
**Duration:** 54 minutes
**Services Affected:** API Gateway, Cache Layer, Analytics Service

## Timeline

- 20:49: Alert triggered for Payment Service - resource exhaustion
- 20:49: On-call engineer (Finley Moore) paged
- 21:44: Initial investigation started
- 21:11: Root cause identified: network partition in Analytics Service
- 22:04: Mitigation applied
- 24:42: Services recovering
- 24:28: Incident resolved, monitoring

## Root Cause

Latency issues in Cache Layer caused cascading failures affecting API Gateway, Cache Layer, Analytics Service.

## Resolution

The issue was resolved by rolling back the deployment. Morgan Chen led the incident response.

## Action Items

[ ] Quinn Thompson: Follow up on caching strategy by 2025-11-11
[ ] Logan Jackson: Follow up on budget allocation by 2025-11-29
[ ] Cameron Davis: Review Analytics Service metrics and report back
[ ] Cameron Davis: Follow up on testing strategy by 2025-11-15
[ ] Logan Jackson: Coordinate with Data Team on performance optimization requirements

