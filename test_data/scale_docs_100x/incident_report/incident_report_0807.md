# Incident Report: Inventory Service SEV2

**Severity:** SEV2
**Date:** 2025-07-21
**Duration:** 53 minutes
**Services Affected:** Email Service, Cache Layer, Analytics Service

## Timeline

- 09:19: Alert triggered for Fraud Detection - memory leaks
- 10:25: On-call engineer (Logan Jackson) paged
- 12:32: Initial investigation started
- 12:05: Root cause identified: database connection pool exhaustion
- 14:44: Mitigation applied
- 16:55: Services recovering
- 17:29: Incident resolved, monitoring

## Root Cause

Resource exhaustion in Fraud Detection caused cascading failures affecting Email Service, Cache Layer, Analytics Service.

## Resolution

The issue was resolved by increasing resource limits. Emerson Wilson led the incident response.

## Action Items

[ ] Tatum Lewis: Follow up on documentation by 2025-11-27
[ ] Riley Garcia: Coordinate with Security Team on team restructuring requirements
[ ] Emerson Wilson: Review Checkout Service metrics and report back
[ ] Tatum Lewis: Schedule meeting with DevOps Team to discuss next steps
[ ] Emerson Wilson: Review API Gateway metrics and report back

