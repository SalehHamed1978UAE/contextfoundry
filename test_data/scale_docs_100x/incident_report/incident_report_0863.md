# Incident Report: Order Service SEV3

**Severity:** SEV3
**Date:** 2025-11-12
**Duration:** 138 minutes
**Services Affected:** Fraud Detection, Recommendation Engine, Inventory Service

## Timeline

- 13:20: Alert triggered for Cache Layer - error rates increasing
- 13:33: On-call engineer (Sydney Clark) paged
- 14:57: Initial investigation started
- 16:26: Root cause identified: network partition in Fraud Detection
- 16:12: Mitigation applied
- 16:25: Services recovering
- 16:46: Incident resolved, monitoring

## Root Cause

Technical debt in Analytics Service caused cascading failures affecting Fraud Detection, Recommendation Engine, Inventory Service.

## Resolution

The issue was resolved by restarting affected services. Reese Martin led the incident response.

## Action Items

[ ] Casey Martinez: Create proposal for budget allocation improvements
[ ] Avery Brown: Follow up on budget allocation by 2025-11-04

