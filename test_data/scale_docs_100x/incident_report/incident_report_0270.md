# Incident Report: Order Service SEV2

**Severity:** SEV2
**Date:** 2025-10-18
**Duration:** 110 minutes
**Services Affected:** Order Service, API Gateway

## Timeline

- 02:12: Alert triggered for Cache Layer - configuration drift
- 03:40: On-call engineer (Riley Garcia) paged
- 05:58: Initial investigation started
- 07:31: Root cause identified: memory leak in cache layer
- 08:47: Mitigation applied
- 09:18: Services recovering
- 09:27: Incident resolved, monitoring

## Root Cause

Resource exhaustion in Notification Service caused cascading failures affecting Order Service, API Gateway.

## Resolution

The issue was resolved by restarting affected services. Emerson Wilson led the incident response.

## Action Items

[ ] Riley Garcia: Schedule meeting with Growth Team to discuss next steps
[ ] Tatum Lewis: Follow up on capacity planning by 2025-11-20
[ ] Tatum Lewis: Schedule meeting with Mobile Team to discuss next steps

