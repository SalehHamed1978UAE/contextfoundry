# Incident Report: Auth Service SEV2

**Severity:** SEV2
**Date:** 2025-08-30
**Duration:** 121 minutes
**Services Affected:** Cache Layer

## Timeline

- 01:39: Alert triggered for API Gateway - technical debt
- 01:36: On-call engineer (Jamie Anderson) paged
- 03:10: Initial investigation started
- 04:50: Root cause identified: certificate expiration
- 06:14: Mitigation applied
- 08:54: Services recovering
- 09:30: Incident resolved, monitoring

## Root Cause

Error rates increasing in Recommendation Engine caused cascading failures affecting Cache Layer.

## Resolution

The issue was resolved by rolling back the deployment. Blake Adams led the incident response.

## Action Items

[ ] Jordan Lee: Schedule meeting with Infrastructure Team to discuss next steps
[ ] Tatum Lewis: Create proposal for database sharding improvements
[ ] Mia White: Create proposal for performance optimization improvements
[ ] Jamie Anderson: Schedule meeting with Frontend Team to discuss next steps

