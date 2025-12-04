# Incident Report: Payment Service SEV1

**Severity:** SEV1
**Date:** 2025-07-16
**Duration:** 36 minutes
**Services Affected:** Auth Service, Order Service, Shipping Service

## Timeline

- 14:04: Alert triggered for Cache Layer - configuration drift
- 16:15: On-call engineer (Sydney Clark) paged
- 17:09: Initial investigation started
- 18:48: Root cause identified: certificate expiration
- 18:35: Mitigation applied
- 18:24: Services recovering
- 20:55: Incident resolved, monitoring

## Root Cause

Missing documentation in Fraud Detection caused cascading failures affecting Auth Service, Order Service, Shipping Service.

## Resolution

The issue was resolved by increasing resource limits. Cameron Davis led the incident response.

## Action Items

[ ] Jordan Lee: Review Checkout Service metrics and report back
[ ] Sydney Clark: Create proposal for testing strategy improvements
[ ] Taylor Kim: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Sydney Clark: Coordinate with Growth Team on incident response requirements
[ ] Taylor Kim: Schedule meeting with SRE Team to discuss next steps

