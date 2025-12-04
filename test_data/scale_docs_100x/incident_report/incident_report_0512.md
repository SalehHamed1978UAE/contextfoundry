# Incident Report: Recommendation Engine SEV1

**Severity:** SEV1
**Date:** 2025-08-05
**Duration:** 18 minutes
**Services Affected:** Order Service, API Gateway, Analytics Service, Fraud Detection

## Timeline

- 17:53: Alert triggered for Inventory Service - error rates increasing
- 18:29: On-call engineer (Tatum Lewis) paged
- 20:47: Initial investigation started
- 21:57: Root cause identified: certificate expiration
- 22:07: Mitigation applied
- 23:31: Services recovering
- 24:26: Incident resolved, monitoring

## Root Cause

Latency issues in API Gateway caused cascading failures affecting Order Service, API Gateway, Analytics Service, Fraud Detection.

## Resolution

The issue was resolved by rolling back the deployment. Alex Rivera led the incident response.

## Action Items

[ ] Casey Martinez: Review Cache Layer metrics and report back
[ ] Casey Martinez: Review Order Service metrics and report back
[ ] Quinn Thompson: Create proposal for scalability planning improvements
[ ] Blake Adams: Create proposal for testing strategy improvements
[ ] Casey Martinez: Review Search Service metrics and report back

