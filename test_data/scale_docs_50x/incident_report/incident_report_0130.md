# Incident Report: Email Service SEV1

**Severity:** SEV1
**Date:** 2025-08-15
**Duration:** 161 minutes
**Services Affected:** Fraud Detection

## Timeline

- 06:45: Alert triggered for Recommendation Engine - memory leaks
- 08:05: On-call engineer (Riley Garcia) paged
- 10:22: Initial investigation started
- 10:32: Root cause identified: certificate expiration
- 10:44: Mitigation applied
- 11:19: Services recovering
- 13:22: Incident resolved, monitoring

## Root Cause

Missing documentation in API Gateway caused cascading failures affecting Fraud Detection.

## Resolution

The issue was resolved by rolling back the deployment. Casey Martinez led the incident response.

## Action Items

[ ] Jordan Lee: Create proposal for monitoring improvements improvements
[ ] Sydney Clark: Review Analytics Service metrics and report back
[ ] Logan Jackson: Follow up on capacity planning by 2025-11-11
[ ] Avery Brown: Coordinate with Platform Team on Q4 planning requirements

