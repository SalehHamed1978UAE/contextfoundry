# Incident Report: Checkout Service SEV1

**Severity:** SEV1
**Date:** 2025-07-26
**Duration:** 172 minutes
**Services Affected:** Inventory Service

## Timeline

- 05:37: Alert triggered for Search Service - deployment failures
- 07:07: On-call engineer (Blake Adams) paged
- 08:57: Initial investigation started
- 08:29: Root cause identified: resource limit reached
- 08:36: Mitigation applied
- 10:19: Services recovering
- 11:32: Incident resolved, monitoring

## Root Cause

Memory leaks in Inventory Service caused cascading failures affecting Inventory Service.

## Resolution

The issue was resolved by restarting affected services. Jamie Anderson led the incident response.

## Action Items

[ ] Finley Moore: Follow up on capacity planning by 2025-12-03
[ ] Mia White: Create proposal for API versioning improvements
[ ] Cameron Davis: Coordinate with Frontend Team on disaster recovery requirements
[ ] Mia White: Review API Gateway metrics and report back
[ ] Finley Moore: Schedule meeting with Platform Team to discuss next steps

