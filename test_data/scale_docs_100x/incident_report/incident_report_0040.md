# Incident Report: Order Service SEV3

**Severity:** SEV3
**Date:** 2025-11-20
**Duration:** 28 minutes
**Services Affected:** Fraud Detection, Analytics Service, SMS Gateway, Email Service

## Timeline

- 12:38: Alert triggered for Analytics Service - deployment failures
- 12:48: On-call engineer (Blake Adams) paged
- 12:11: Initial investigation started
- 13:07: Root cause identified: database connection pool exhaustion
- 14:11: Mitigation applied
- 15:21: Services recovering
- 16:45: Incident resolved, monitoring

## Root Cause

Error rates increasing in API Gateway caused cascading failures affecting Fraud Detection, Analytics Service, SMS Gateway, Email Service.

## Resolution

The issue was resolved by increasing resource limits. Avery Brown led the incident response.

## Action Items

[ ] Sage Robinson: Follow up on microservices refactoring by 2025-11-05
[ ] Logan Jackson: Create proposal for documentation improvements
[ ] Morgan Chen: Review Order Service metrics and report back
[ ] Quinn Thompson: Coordinate with QA Team on team restructuring requirements

