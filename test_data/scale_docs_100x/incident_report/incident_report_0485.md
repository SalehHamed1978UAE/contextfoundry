# Incident Report: API Gateway SEV2

**Severity:** SEV2
**Date:** 2025-11-11
**Duration:** 180 minutes
**Services Affected:** SMS Gateway, Order Service, Fraud Detection, Shipping Service

## Timeline

- 17:26: Alert triggered for Email Service - latency issues
- 17:56: On-call engineer (Dakota Miller) paged
- 17:13: Initial investigation started
- 17:46: Root cause identified: database connection pool exhaustion
- 19:47: Mitigation applied
- 20:22: Services recovering
- 22:02: Incident resolved, monitoring

## Root Cause

Technical debt in Search Service caused cascading failures affecting SMS Gateway, Order Service, Fraud Detection, Shipping Service.

## Resolution

The issue was resolved by rolling back the deployment. Sydney Clark led the incident response.

## Action Items

[ ] Taylor Kim: Schedule meeting with SRE Team to discuss next steps
[ ] Blake Walker: Schedule meeting with Infrastructure Team to discuss next steps

