# Incident Report: API Gateway SEV1

**Severity:** SEV1
**Date:** 2025-11-12
**Duration:** 150 minutes
**Services Affected:** Order Service, SMS Gateway

## Timeline

- 14:32: Alert triggered for Fraud Detection - error rates increasing
- 14:24: On-call engineer (Alex Rivera) paged
- 16:48: Initial investigation started
- 18:45: Root cause identified: database connection pool exhaustion
- 20:14: Mitigation applied
- 20:48: Services recovering
- 22:12: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in Shipping Service caused cascading failures affecting Order Service, SMS Gateway.

## Resolution

The issue was resolved by rolling back the deployment. Alex Rivera led the incident response.

## Action Items

[ ] Sage Robinson: Follow up on observability stack by 2025-11-04
[ ] Reese Martin: Schedule meeting with Backend Team to discuss next steps
[ ] Morgan Chen: Coordinate with Growth Team on capacity planning requirements
[ ] Reese Martin: Schedule meeting with Growth Team to discuss next steps
[ ] Reese Martin: Review Order Service metrics and report back

