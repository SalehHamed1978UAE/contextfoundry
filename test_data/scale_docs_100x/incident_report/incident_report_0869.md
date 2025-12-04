# Incident Report: Checkout Service SEV2

**Severity:** SEV2
**Date:** 2025-11-02
**Duration:** 115 minutes
**Services Affected:** Auth Service, Payment Service, Recommendation Engine, Cache Layer

## Timeline

- 17:24: Alert triggered for Search Service - data inconsistency
- 19:11: On-call engineer (Tatum Lewis) paged
- 21:19: Initial investigation started
- 22:39: Root cause identified: memory leak in cache layer
- 24:26: Mitigation applied
- 24:02: Services recovering
- 26:58: Incident resolved, monitoring

## Root Cause

Latency issues in Search Service caused cascading failures affecting Auth Service, Payment Service, Recommendation Engine, Cache Layer.

## Resolution

The issue was resolved by restarting affected services. Avery Brown led the incident response.

## Action Items

[ ] Kendall Thomas: Follow up on scalability planning by 2025-11-10
[ ] Jordan Lee: Review Inventory Service metrics and report back

