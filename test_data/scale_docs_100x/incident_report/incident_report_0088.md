# Incident Report: Fraud Detection SEV3

**Severity:** SEV3
**Date:** 2025-11-07
**Duration:** 138 minutes
**Services Affected:** Checkout Service, Email Service, API Gateway

## Timeline

- 13:01: Alert triggered for Payment Service - resource exhaustion
- 13:06: On-call engineer (Jamie Anderson) paged
- 14:38: Initial investigation started
- 14:08: Root cause identified: failed deployment rollback
- 14:07: Mitigation applied
- 16:06: Services recovering
- 18:05: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Inventory Service caused cascading failures affecting Checkout Service, Email Service, API Gateway.

## Resolution

The issue was resolved by restarting affected services. Jordan Lee led the incident response.

## Action Items

[ ] Morgan Chen: Follow up on API versioning by 2025-11-17
[ ] Cameron Davis: Create proposal for documentation improvements

