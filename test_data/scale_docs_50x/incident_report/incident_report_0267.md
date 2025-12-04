# Incident Report: Auth Service SEV3

**Severity:** SEV3
**Date:** 2025-06-23
**Duration:** 172 minutes
**Services Affected:** Notification Service, Shipping Service

## Timeline

- 16:58: Alert triggered for Shipping Service - deployment failures
- 18:56: On-call engineer (Emerson Wilson) paged
- 18:22: Initial investigation started
- 19:21: Root cause identified: network partition in Checkout Service
- 21:33: Mitigation applied
- 21:20: Services recovering
- 23:48: Incident resolved, monitoring

## Root Cause

Timeout errors in User Service caused cascading failures affecting Notification Service, Shipping Service.

## Resolution

The issue was resolved by restarting affected services. Sage Robinson led the incident response.

## Action Items

[ ] Alex Rivera: Coordinate with DevOps Team on performance optimization requirements
[ ] Alex Rivera: Follow up on API versioning by 2025-11-27
[ ] Casey Martinez: Create proposal for budget allocation improvements
[ ] Cameron Davis: Follow up on documentation by 2025-11-27

