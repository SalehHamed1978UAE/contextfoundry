# Incident Report: Checkout Service SEV2

**Severity:** SEV2
**Date:** 2025-07-01
**Duration:** 30 minutes
**Services Affected:** Inventory Service, API Gateway, Analytics Service

## Timeline

- 15:45: Alert triggered for Cache Layer - timeout errors
- 16:27: On-call engineer (Reese Martin) paged
- 18:13: Initial investigation started
- 19:45: Root cause identified: network partition in Checkout Service
- 20:23: Mitigation applied
- 22:00: Services recovering
- 23:47: Incident resolved, monitoring

## Root Cause

Configuration drift in Payment Service caused cascading failures affecting Inventory Service, API Gateway, Analytics Service.

## Resolution

The issue was resolved by restarting affected services. Avery Brown led the incident response.

## Action Items

[ ] Kendall Thomas: Follow up on API versioning by 2025-11-06
[ ] Kendall Thomas: Schedule meeting with Security Team to discuss next steps
[ ] Sage Robinson: Review Fraud Detection metrics and report back
[ ] Sage Robinson: Create proposal for incident response improvements

