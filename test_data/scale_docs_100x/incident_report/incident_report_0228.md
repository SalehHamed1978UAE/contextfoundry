# Incident Report: User Service SEV2

**Severity:** SEV2
**Date:** 2025-07-15
**Duration:** 34 minutes
**Services Affected:** Email Service, Notification Service

## Timeline

- 19:40: Alert triggered for Shipping Service - missing documentation
- 21:18: On-call engineer (Jordan Lee) paged
- 23:42: Initial investigation started
- 25:23: Root cause identified: resource limit reached
- 27:51: Mitigation applied
- 28:24: Services recovering
- 30:54: Incident resolved, monitoring

## Root Cause

Deployment failures in Email Service caused cascading failures affecting Email Service, Notification Service.

## Resolution

The issue was resolved by restarting affected services. Riley Garcia led the incident response.

## Action Items

[ ] Parker Harris: Follow up on compliance requirements by 2025-11-16
[ ] Avery Brown: Coordinate with Frontend Team on cloud migration requirements
[ ] Parker Harris: Coordinate with Infrastructure Team on CI/CD pipeline requirements
[ ] Quinn Thompson: Coordinate with Growth Team on testing strategy requirements
[ ] Parker Harris: Coordinate with Data Team on team restructuring requirements

