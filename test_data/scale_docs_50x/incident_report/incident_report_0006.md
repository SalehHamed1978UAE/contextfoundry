# Incident Report: Checkout Service SEV1

**Severity:** SEV1
**Date:** 2025-06-29
**Duration:** 139 minutes
**Services Affected:** User Service

## Timeline

- 13:08: Alert triggered for Order Service - deployment failures
- 14:39: On-call engineer (Jordan Lee) paged
- 14:06: Initial investigation started
- 14:00: Root cause identified: network partition in Cache Layer
- 14:19: Mitigation applied
- 15:16: Services recovering
- 17:32: Incident resolved, monitoring

## Root Cause

Memory leaks in Search Service caused cascading failures affecting User Service.

## Resolution

The issue was resolved by rolling back the deployment. Blake Adams led the incident response.

## Action Items

[ ] Blake Adams: Coordinate with Growth Team on database sharding requirements
[ ] Blake Adams: Coordinate with SRE Team on security audit requirements
[ ] Blake Adams: Follow up on budget allocation by 2025-11-25
[ ] Finley Moore: Create proposal for monitoring improvements improvements
[ ] Logan Jackson: Schedule meeting with Security Team to discuss next steps

