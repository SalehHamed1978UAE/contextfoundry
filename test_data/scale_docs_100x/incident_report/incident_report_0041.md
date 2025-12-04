# Incident Report: Search Service SEV3

**Severity:** SEV3
**Date:** 2025-07-01
**Duration:** 177 minutes
**Services Affected:** Recommendation Engine, Analytics Service, Fraud Detection, Order Service

## Timeline

- 18:38: Alert triggered for Order Service - missing documentation
- 19:48: On-call engineer (Alex Rivera) paged
- 21:40: Initial investigation started
- 21:46: Root cause identified: failed deployment rollback
- 21:11: Mitigation applied
- 21:05: Services recovering
- 22:52: Incident resolved, monitoring

## Root Cause

Latency issues in Notification Service caused cascading failures affecting Recommendation Engine, Analytics Service, Fraud Detection, Order Service.

## Resolution

The issue was resolved by applying a hotfix. Sydney Clark led the incident response.

## Action Items

[ ] Sage Robinson: Follow up on vendor evaluation by 2025-11-14
[ ] Jordan Lee: Create proposal for cloud migration improvements
[ ] Sage Robinson: Follow up on documentation by 2025-11-09
[ ] Sage Robinson: Review Inventory Service metrics and report back

