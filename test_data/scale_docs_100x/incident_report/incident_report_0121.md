# Incident Report: API Gateway SEV2

**Severity:** SEV2
**Date:** 2025-08-25
**Duration:** 164 minutes
**Services Affected:** API Gateway, Fraud Detection, Inventory Service

## Timeline

- 17:12: Alert triggered for Recommendation Engine - deployment failures
- 19:31: On-call engineer (Kendall Thomas) paged
- 19:09: Initial investigation started
- 20:37: Root cause identified: network partition in Recommendation Engine
- 22:01: Mitigation applied
- 24:26: Services recovering
- 24:23: Incident resolved, monitoring

## Root Cause

Memory leaks in Analytics Service caused cascading failures affecting API Gateway, Fraud Detection, Inventory Service.

## Resolution

The issue was resolved by rolling back the deployment. Jordan Lee led the incident response.

## Action Items

[ ] Sage Robinson: Coordinate with Platform Team on disaster recovery requirements
[ ] Kendall Thomas: Review Order Service metrics and report back
[ ] Sage Robinson: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Parker Harris: Create proposal for cost reduction improvements

