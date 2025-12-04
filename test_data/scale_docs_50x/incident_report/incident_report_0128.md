# Incident Report: Shipping Service SEV2

**Severity:** SEV2
**Date:** 2025-09-13
**Duration:** 61 minutes
**Services Affected:** Shipping Service, Notification Service

## Timeline

- 04:02: Alert triggered for Auth Service - technical debt
- 06:56: On-call engineer (Riley Garcia) paged
- 08:10: Initial investigation started
- 08:09: Root cause identified: memory leak in cache layer
- 08:00: Mitigation applied
- 10:13: Services recovering
- 11:08: Incident resolved, monitoring

## Root Cause

Data inconsistency in Email Service caused cascading failures affecting Shipping Service, Notification Service.

## Resolution

The issue was resolved by rolling back the deployment. Avery Brown led the incident response.

## Action Items

[ ] Kendall Thomas: Coordinate with API Team on microservices refactoring requirements
[ ] Parker Harris: Follow up on capacity planning by 2025-11-05
[ ] Cameron Davis: Coordinate with SRE Team on hiring priorities requirements
[ ] Kendall Thomas: Coordinate with Data Team on Q4 planning requirements
[ ] Kendall Thomas: Follow up on technical debt by 2025-11-22

