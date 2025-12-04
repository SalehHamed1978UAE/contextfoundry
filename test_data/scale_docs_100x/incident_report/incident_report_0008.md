# Incident Report: Email Service SEV2

**Severity:** SEV2
**Date:** 2025-08-25
**Duration:** 95 minutes
**Services Affected:** Shipping Service

## Timeline

- 12:08: Alert triggered for Search Service - technical debt
- 13:16: On-call engineer (Taylor Kim) paged
- 14:14: Initial investigation started
- 16:53: Root cause identified: resource limit reached
- 17:23: Mitigation applied
- 18:49: Services recovering
- 20:27: Incident resolved, monitoring

## Root Cause

Missing documentation in Order Service caused cascading failures affecting Shipping Service.

## Resolution

The issue was resolved by restarting affected services. Logan Jackson led the incident response.

## Action Items

[ ] Emerson Wilson: Create proposal for cloud migration improvements
[ ] Logan Jackson: Follow up on disaster recovery by 2025-11-12
[ ] Emerson Wilson: Coordinate with Backend Team on Q4 planning requirements

