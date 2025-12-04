# Incident Report: Checkout Service SEV3

**Severity:** SEV3
**Date:** 2025-10-19
**Duration:** 127 minutes
**Services Affected:** Shipping Service, SMS Gateway, Recommendation Engine, User Service

## Timeline

- 15:48: Alert triggered for Checkout Service - resource exhaustion
- 17:23: On-call engineer (Jordan Lee) paged
- 17:54: Initial investigation started
- 18:58: Root cause identified: certificate expiration
- 18:46: Mitigation applied
- 18:21: Services recovering
- 18:46: Incident resolved, monitoring

## Root Cause

Missing documentation in Email Service caused cascading failures affecting Shipping Service, SMS Gateway, Recommendation Engine, User Service.

## Resolution

The issue was resolved by applying a hotfix. Taylor Kim led the incident response.

## Action Items

[ ] Kendall Thomas: Follow up on capacity planning by 2025-11-28
[ ] Kendall Thomas: Schedule meeting with SRE Team to discuss next steps
[ ] Tatum Lewis: Coordinate with Data Team on vendor evaluation requirements

