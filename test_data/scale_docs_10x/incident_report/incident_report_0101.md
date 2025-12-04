# Incident Report: Fraud Detection SEV3

**Severity:** SEV3
**Date:** 2025-10-31
**Duration:** 153 minutes
**Services Affected:** Cache Layer, Checkout Service, SMS Gateway, Fraud Detection

## Timeline

- 01:43: Alert triggered for Order Service - data inconsistency
- 02:28: On-call engineer (Dakota Miller) paged
- 04:50: Initial investigation started
- 04:24: Root cause identified: database connection pool exhaustion
- 04:30: Mitigation applied
- 05:19: Services recovering
- 05:25: Incident resolved, monitoring

## Root Cause

Memory leaks in Search Service caused cascading failures affecting Cache Layer, Checkout Service, SMS Gateway, Fraud Detection.

## Resolution

The issue was resolved by rolling back the deployment. Finley Moore led the incident response.

## Action Items

[ ] Mia White: Review Order Service metrics and report back
[ ] Mia White: Create proposal for caching strategy improvements
[ ] Blake Adams: Schedule meeting with DevOps Team to discuss next steps
[ ] Jamie Anderson: Review Payment Service metrics and report back
[ ] Blake Adams: Follow up on documentation by 2025-12-04

