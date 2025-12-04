# Incident Report: SMS Gateway SEV3

**Severity:** SEV3
**Date:** 2025-08-04
**Duration:** 108 minutes
**Services Affected:** Search Service, SMS Gateway, User Service

## Timeline

- 06:32: Alert triggered for Shipping Service - configuration drift
- 06:54: On-call engineer (Reese Martin) paged
- 06:49: Initial investigation started
- 08:31: Root cause identified: memory leak in cache layer
- 08:45: Mitigation applied
- 08:03: Services recovering
- 08:22: Incident resolved, monitoring

## Root Cause

Missing documentation in Checkout Service caused cascading failures affecting Search Service, SMS Gateway, User Service.

## Resolution

The issue was resolved by increasing resource limits. Parker Harris led the incident response.

## Action Items

[ ] Harper Taylor: Follow up on team restructuring by 2025-11-07
[ ] Harper Taylor: Follow up on capacity planning by 2025-11-04
[ ] Sage Robinson: Follow up on testing strategy by 2025-11-15

