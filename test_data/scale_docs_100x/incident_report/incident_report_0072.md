# Incident Report: Email Service SEV3

**Severity:** SEV3
**Date:** 2025-08-21
**Duration:** 38 minutes
**Services Affected:** Auth Service, Search Service, Shipping Service, Checkout Service

## Timeline

- 14:32: Alert triggered for Email Service - deployment failures
- 16:31: On-call engineer (Finley Moore) paged
- 17:55: Initial investigation started
- 17:37: Root cause identified: network partition in Payment Service
- 19:38: Mitigation applied
- 19:25: Services recovering
- 19:14: Incident resolved, monitoring

## Root Cause

Timeout errors in Recommendation Engine caused cascading failures affecting Auth Service, Search Service, Shipping Service, Checkout Service.

## Resolution

The issue was resolved by restarting affected services. Logan Jackson led the incident response.

## Action Items

[ ] Jamie Anderson: Schedule meeting with Security Team to discuss next steps
[ ] Avery Brown: Review User Service metrics and report back

