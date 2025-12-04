# Incident Report: Notification Service SEV2

**Severity:** SEV2
**Date:** 2025-09-29
**Duration:** 81 minutes
**Services Affected:** Recommendation Engine, Checkout Service, User Service

## Timeline

- 17:54: Alert triggered for Payment Service - data inconsistency
- 17:39: On-call engineer (Drew Patel) paged
- 18:28: Initial investigation started
- 20:24: Root cause identified: database connection pool exhaustion
- 22:34: Mitigation applied
- 23:20: Services recovering
- 25:45: Incident resolved, monitoring

## Root Cause

Technical debt in Shipping Service caused cascading failures affecting Recommendation Engine, Checkout Service, User Service.

## Resolution

The issue was resolved by increasing resource limits. Alex Rivera led the incident response.

## Action Items

[ ] Dakota Miller: Review SMS Gateway metrics and report back
[ ] Blake Walker: Create proposal for cloud migration improvements
[ ] Emerson Wilson: Create proposal for hiring priorities improvements
[ ] Emerson Wilson: Coordinate with API Team on team restructuring requirements

