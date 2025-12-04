# Incident Report: SMS Gateway SEV3

**Severity:** SEV3
**Date:** 2025-07-29
**Duration:** 107 minutes
**Services Affected:** Payment Service

## Timeline

- 21:27: Alert triggered for Order Service - memory leaks
- 21:14: On-call engineer (Quinn Thompson) paged
- 21:46: Initial investigation started
- 22:12: Root cause identified: resource limit reached
- 23:55: Mitigation applied
- 25:06: Services recovering
- 25:51: Incident resolved, monitoring

## Root Cause

Error rates increasing in Notification Service caused cascading failures affecting Payment Service.

## Resolution

The issue was resolved by increasing resource limits. Reese Martin led the incident response.

## Action Items

[ ] Alex Rivera: Create proposal for observability stack improvements
[ ] Drew Patel: Review API Gateway metrics and report back

