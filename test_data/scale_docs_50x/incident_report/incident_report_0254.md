# Incident Report: User Service SEV2

**Severity:** SEV2
**Date:** 2025-08-17
**Duration:** 176 minutes
**Services Affected:** User Service, API Gateway

## Timeline

- 00:37: Alert triggered for Recommendation Engine - missing documentation
- 02:20: On-call engineer (Emerson Wilson) paged
- 03:48: Initial investigation started
- 05:31: Root cause identified: failed deployment rollback
- 06:34: Mitigation applied
- 08:50: Services recovering
- 10:48: Incident resolved, monitoring

## Root Cause

Error rates increasing in Shipping Service caused cascading failures affecting User Service, API Gateway.

## Resolution

The issue was resolved by restarting affected services. Sydney Clark led the incident response.

## Action Items

[ ] Sydney Clark: Coordinate with Frontend Team on Q4 planning requirements
[ ] Avery Brown: Create proposal for database sharding improvements

