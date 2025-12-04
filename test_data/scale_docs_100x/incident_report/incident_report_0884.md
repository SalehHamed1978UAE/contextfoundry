# Incident Report: Checkout Service SEV1

**Severity:** SEV1
**Date:** 2025-11-06
**Duration:** 60 minutes
**Services Affected:** Cache Layer, Checkout Service, Shipping Service, Inventory Service

## Timeline

- 17:46: Alert triggered for Notification Service - missing documentation
- 17:06: On-call engineer (Parker Harris) paged
- 18:47: Initial investigation started
- 19:08: Root cause identified: database connection pool exhaustion
- 19:11: Mitigation applied
- 19:31: Services recovering
- 20:27: Incident resolved, monitoring

## Root Cause

Missing documentation in User Service caused cascading failures affecting Cache Layer, Checkout Service, Shipping Service, Inventory Service.

## Resolution

The issue was resolved by increasing resource limits. Sydney Clark led the incident response.

## Action Items

[ ] Harper Taylor: Review API Gateway metrics and report back
[ ] Morgan Chen: Schedule meeting with Frontend Team to discuss next steps
[ ] Morgan Chen: Follow up on caching strategy by 2025-11-11
[ ] Morgan Chen: Create proposal for disaster recovery improvements
[ ] Harper Taylor: Review Order Service metrics and report back

