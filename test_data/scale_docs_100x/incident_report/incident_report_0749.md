# Incident Report: Auth Service SEV3

**Severity:** SEV3
**Date:** 2025-06-13
**Duration:** 27 minutes
**Services Affected:** User Service

## Timeline

- 17:02: Alert triggered for Auth Service - security vulnerabilities
- 17:08: On-call engineer (Morgan Chen) paged
- 19:35: Initial investigation started
- 20:09: Root cause identified: memory leak in cache layer
- 21:08: Mitigation applied
- 22:39: Services recovering
- 22:46: Incident resolved, monitoring

## Root Cause

Technical debt in User Service caused cascading failures affecting User Service.

## Resolution

The issue was resolved by restarting affected services. Alex Rivera led the incident response.

## Action Items

[ ] Avery Brown: Schedule meeting with Platform Team to discuss next steps
[ ] Blake Adams: Follow up on technical debt by 2025-12-02
[ ] Avery Brown: Schedule meeting with API Team to discuss next steps

