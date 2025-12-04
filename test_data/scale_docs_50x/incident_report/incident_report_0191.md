# Incident Report: Auth Service SEV2

**Severity:** SEV2
**Date:** 2025-07-06
**Duration:** 107 minutes
**Services Affected:** User Service, Email Service

## Timeline

- 08:55: Alert triggered for SMS Gateway - missing documentation
- 08:34: On-call engineer (Parker Harris) paged
- 08:45: Initial investigation started
- 10:44: Root cause identified: database connection pool exhaustion
- 12:52: Mitigation applied
- 14:25: Services recovering
- 16:46: Incident resolved, monitoring

## Root Cause

Missing documentation in Checkout Service caused cascading failures affecting User Service, Email Service.

## Resolution

The issue was resolved by rolling back the deployment. Dakota Miller led the incident response.

## Action Items

[ ] Emerson Wilson: Follow up on documentation by 2025-11-07
[ ] Taylor Kim: Follow up on monitoring improvements by 2025-11-27
[ ] Quinn Thompson: Review User Service metrics and report back

