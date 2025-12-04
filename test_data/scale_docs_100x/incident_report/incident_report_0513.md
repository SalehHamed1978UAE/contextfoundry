# Incident Report: Analytics Service SEV2

**Severity:** SEV2
**Date:** 2025-11-20
**Duration:** 46 minutes
**Services Affected:** SMS Gateway

## Timeline

- 21:25: Alert triggered for SMS Gateway - memory leaks
- 23:59: On-call engineer (Taylor Kim) paged
- 24:01: Initial investigation started
- 25:04: Root cause identified: certificate expiration
- 25:51: Mitigation applied
- 26:32: Services recovering
- 27:00: Incident resolved, monitoring

## Root Cause

Deployment failures in User Service caused cascading failures affecting SMS Gateway.

## Resolution

The issue was resolved by applying a hotfix. Blake Adams led the incident response.

## Action Items

[ ] Mia White: Create proposal for security audit improvements
[ ] Mia White: Coordinate with Infrastructure Team on caching strategy requirements
[ ] Casey Martinez: Coordinate with Data Team on cloud migration requirements
[ ] Blake Adams: Schedule meeting with Backend Team to discuss next steps

