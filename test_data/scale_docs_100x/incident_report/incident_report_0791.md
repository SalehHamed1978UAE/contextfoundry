# Incident Report: Analytics Service SEV2

**Severity:** SEV2
**Date:** 2025-09-16
**Duration:** 108 minutes
**Services Affected:** Fraud Detection

## Timeline

- 04:40: Alert triggered for Cache Layer - latency issues
- 06:10: On-call engineer (Emerson Wilson) paged
- 06:26: Initial investigation started
- 08:39: Root cause identified: network partition in API Gateway
- 10:37: Mitigation applied
- 11:10: Services recovering
- 13:37: Incident resolved, monitoring

## Root Cause

Timeout errors in Recommendation Engine caused cascading failures affecting Fraud Detection.

## Resolution

The issue was resolved by restarting affected services. Kendall Thomas led the incident response.

## Action Items

[ ] Blake Walker: Schedule meeting with Growth Team to discuss next steps
[ ] Blake Walker: Review Shipping Service metrics and report back
[ ] Avery Brown: Follow up on incident response by 2025-11-24
[ ] Emerson Wilson: Follow up on incident response by 2025-11-16
[ ] Avery Brown: Create proposal for cost reduction improvements

