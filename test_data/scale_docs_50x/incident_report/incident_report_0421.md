# Incident Report: Fraud Detection SEV2

**Severity:** SEV2
**Date:** 2025-11-24
**Duration:** 40 minutes
**Services Affected:** SMS Gateway, Shipping Service, Notification Service, API Gateway

## Timeline

- 16:34: Alert triggered for Shipping Service - configuration drift
- 16:13: On-call engineer (Harper Taylor) paged
- 17:46: Initial investigation started
- 19:48: Root cause identified: database connection pool exhaustion
- 21:48: Mitigation applied
- 21:32: Services recovering
- 21:56: Incident resolved, monitoring

## Root Cause

Timeout errors in Email Service caused cascading failures affecting SMS Gateway, Shipping Service, Notification Service, API Gateway.

## Resolution

The issue was resolved by rolling back the deployment. Morgan Chen led the incident response.

## Action Items

[ ] Blake Adams: Follow up on cost reduction by 2025-11-18
[ ] Blake Adams: Coordinate with Growth Team on Q4 planning requirements
[ ] Alex Rivera: Create proposal for microservices refactoring improvements
[ ] Jordan Lee: Review Fraud Detection metrics and report back

