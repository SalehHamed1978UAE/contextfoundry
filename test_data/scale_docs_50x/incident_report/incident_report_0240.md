# Incident Report: Inventory Service SEV1

**Severity:** SEV1
**Date:** 2025-06-16
**Duration:** 179 minutes
**Services Affected:** Analytics Service, Inventory Service, Order Service

## Timeline

- 02:56: Alert triggered for API Gateway - error rates increasing
- 03:15: On-call engineer (Casey Martinez) paged
- 05:04: Initial investigation started
- 07:21: Root cause identified: network partition in Inventory Service
- 08:06: Mitigation applied
- 10:07: Services recovering
- 10:57: Incident resolved, monitoring

## Root Cause

Deployment failures in Payment Service caused cascading failures affecting Analytics Service, Inventory Service, Order Service.

## Resolution

The issue was resolved by restarting affected services. Logan Jackson led the incident response.

## Action Items

[ ] Finley Moore: Schedule meeting with Frontend Team to discuss next steps
[ ] Cameron Davis: Coordinate with SRE Team on documentation requirements
[ ] Cameron Davis: Create proposal for cost reduction improvements
[ ] Finley Moore: Follow up on compliance requirements by 2025-12-03
[ ] Dakota Miller: Coordinate with QA Team on compliance requirements requirements

