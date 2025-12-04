# Incident Report: SMS Gateway SEV2

**Severity:** SEV2
**Date:** 2025-07-14
**Duration:** 82 minutes
**Services Affected:** Recommendation Engine, Inventory Service, SMS Gateway, Search Service

## Timeline

- 05:13: Alert triggered for User Service - technical debt
- 05:39: On-call engineer (Finley Moore) paged
- 07:35: Initial investigation started
- 09:25: Root cause identified: resource limit reached
- 10:15: Mitigation applied
- 12:58: Services recovering
- 14:27: Incident resolved, monitoring

## Root Cause

Resource exhaustion in Order Service caused cascading failures affecting Recommendation Engine, Inventory Service, SMS Gateway, Search Service.

## Resolution

The issue was resolved by increasing resource limits. Jordan Lee led the incident response.

## Action Items

[ ] Blake Walker: Create proposal for security audit improvements
[ ] Kendall Thomas: Review Fraud Detection metrics and report back

