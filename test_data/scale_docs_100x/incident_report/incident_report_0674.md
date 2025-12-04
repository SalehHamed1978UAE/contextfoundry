# Incident Report: Analytics Service SEV3

**Severity:** SEV3
**Date:** 2025-11-24
**Duration:** 55 minutes
**Services Affected:** Search Service, Checkout Service, Order Service

## Timeline

- 12:26: Alert triggered for Auth Service - missing documentation
- 12:33: On-call engineer (Reese Martin) paged
- 12:02: Initial investigation started
- 12:08: Root cause identified: network partition in Cache Layer
- 13:15: Mitigation applied
- 13:39: Services recovering
- 13:50: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Checkout Service caused cascading failures affecting Search Service, Checkout Service, Order Service.

## Resolution

The issue was resolved by rolling back the deployment. Morgan Chen led the incident response.

## Action Items

[ ] Riley Garcia: Follow up on API versioning by 2025-11-14
[ ] Alex Rivera: Create proposal for CI/CD pipeline improvements

