# Incident Report: Notification Service SEV3

**Severity:** SEV3
**Date:** 2025-11-17
**Duration:** 33 minutes
**Services Affected:** User Service, Order Service, SMS Gateway

## Timeline

- 02:09: Alert triggered for SMS Gateway - error rates increasing
- 03:17: On-call engineer (Casey Martinez) paged
- 04:13: Initial investigation started
- 04:22: Root cause identified: certificate expiration
- 06:41: Mitigation applied
- 08:14: Services recovering
- 09:25: Incident resolved, monitoring

## Root Cause

Deployment failures in Recommendation Engine caused cascading failures affecting User Service, Order Service, SMS Gateway.

## Resolution

The issue was resolved by increasing resource limits. Drew Patel led the incident response.

## Action Items

[ ] Riley Garcia: Coordinate with Infrastructure Team on scalability planning requirements
[ ] Riley Garcia: Coordinate with Growth Team on testing strategy requirements
[ ] Cameron Davis: Follow up on CI/CD pipeline by 2025-11-28

