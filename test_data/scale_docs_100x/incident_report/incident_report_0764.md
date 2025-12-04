# Incident Report: Auth Service SEV3

**Severity:** SEV3
**Date:** 2025-07-08
**Duration:** 156 minutes
**Services Affected:** Email Service, Analytics Service

## Timeline

- 05:12: Alert triggered for User Service - configuration drift
- 07:39: On-call engineer (Quinn Thompson) paged
- 07:17: Initial investigation started
- 09:03: Root cause identified: network partition in Email Service
- 11:35: Mitigation applied
- 11:43: Services recovering
- 11:42: Incident resolved, monitoring

## Root Cause

Resource exhaustion in User Service caused cascading failures affecting Email Service, Analytics Service.

## Resolution

The issue was resolved by increasing resource limits. Blake Walker led the incident response.

## Action Items

[ ] Alex Rivera: Coordinate with Backend Team on technical debt requirements
[ ] Parker Harris: Coordinate with Infrastructure Team on team restructuring requirements
[ ] Quinn Thompson: Schedule meeting with SRE Team to discuss next steps
[ ] Cameron Davis: Follow up on budget allocation by 2025-11-18

