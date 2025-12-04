# Incident Report: Shipping Service SEV2

**Severity:** SEV2
**Date:** 2025-06-08
**Duration:** 178 minutes
**Services Affected:** Search Service

## Timeline

- 10:14: Alert triggered for Cache Layer - latency issues
- 11:05: On-call engineer (Emerson Wilson) paged
- 11:17: Initial investigation started
- 11:46: Root cause identified: certificate expiration
- 12:10: Mitigation applied
- 13:28: Services recovering
- 14:54: Incident resolved, monitoring

## Root Cause

Configuration drift in Email Service caused cascading failures affecting Search Service.

## Resolution

The issue was resolved by rolling back the deployment. Drew Patel led the incident response.

## Action Items

[ ] Reese Martin: Follow up on hiring priorities by 2025-12-03
[ ] Casey Martinez: Create proposal for compliance requirements improvements
[ ] Reese Martin: Create proposal for performance optimization improvements
[ ] Casey Martinez: Coordinate with Backend Team on incident response requirements
[ ] Alex Rivera: Create proposal for budget allocation improvements

