# Incident Report: Email Service SEV2

**Severity:** SEV2
**Date:** 2025-11-18
**Duration:** 145 minutes
**Services Affected:** Search Service, Shipping Service, Inventory Service, SMS Gateway

## Timeline

- 14:47: Alert triggered for Auth Service - missing documentation
- 15:26: On-call engineer (Tatum Lewis) paged
- 15:23: Initial investigation started
- 15:53: Root cause identified: failed deployment rollback
- 15:39: Mitigation applied
- 17:41: Services recovering
- 18:20: Incident resolved, monitoring

## Root Cause

Timeout errors in Auth Service caused cascading failures affecting Search Service, Shipping Service, Inventory Service, SMS Gateway.

## Resolution

The issue was resolved by rolling back the deployment. Tatum Lewis led the incident response.

## Action Items

[ ] Taylor Kim: Create proposal for technical debt improvements
[ ] Drew Patel: Follow up on technical debt by 2025-11-21
[ ] Blake Walker: Schedule meeting with Backend Team to discuss next steps

