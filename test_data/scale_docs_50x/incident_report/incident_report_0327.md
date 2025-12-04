# Incident Report: Order Service SEV2

**Severity:** SEV2
**Date:** 2025-08-13
**Duration:** 101 minutes
**Services Affected:** Checkout Service, API Gateway, Cache Layer, Fraud Detection

## Timeline

- 05:45: Alert triggered for Search Service - scaling bottlenecks
- 05:26: On-call engineer (Blake Adams) paged
- 07:01: Initial investigation started
- 09:17: Root cause identified: database connection pool exhaustion
- 10:13: Mitigation applied
- 10:05: Services recovering
- 11:37: Incident resolved, monitoring

## Root Cause

Resource exhaustion in Payment Service caused cascading failures affecting Checkout Service, API Gateway, Cache Layer, Fraud Detection.

## Resolution

The issue was resolved by applying a hotfix. Dakota Miller led the incident response.

## Action Items

[ ] Mia White: Review Recommendation Engine metrics and report back
[ ] Mia White: Follow up on scalability planning by 2025-11-13

