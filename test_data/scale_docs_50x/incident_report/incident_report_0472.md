# Incident Report: Shipping Service SEV1

**Severity:** SEV1
**Date:** 2025-11-14
**Duration:** 55 minutes
**Services Affected:** Order Service, Inventory Service

## Timeline

- 07:26: Alert triggered for Fraud Detection - missing documentation
- 07:29: On-call engineer (Sage Robinson) paged
- 07:08: Initial investigation started
- 07:15: Root cause identified: certificate expiration
- 07:33: Mitigation applied
- 07:32: Services recovering
- 07:37: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in Inventory Service caused cascading failures affecting Order Service, Inventory Service.

## Resolution

The issue was resolved by restarting affected services. Blake Walker led the incident response.

## Action Items

[ ] Cameron Davis: Coordinate with Frontend Team on budget allocation requirements
[ ] Quinn Thompson: Review Fraud Detection metrics and report back
[ ] Riley Garcia: Schedule meeting with API Team to discuss next steps
[ ] Blake Walker: Create proposal for testing strategy improvements

