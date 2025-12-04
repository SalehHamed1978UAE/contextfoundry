# Incident Report: User Service SEV2

**Severity:** SEV2
**Date:** 2025-07-22
**Duration:** 103 minutes
**Services Affected:** Cache Layer

## Timeline

- 11:37: Alert triggered for Email Service - memory leaks
- 13:04: On-call engineer (Harper Taylor) paged
- 13:12: Initial investigation started
- 13:50: Root cause identified: failed deployment rollback
- 14:02: Mitigation applied
- 14:27: Services recovering
- 16:51: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in Fraud Detection caused cascading failures affecting Cache Layer.

## Resolution

The issue was resolved by rolling back the deployment. Riley Garcia led the incident response.

## Action Items

[ ] Reese Martin: Create proposal for API versioning improvements
[ ] Sage Robinson: Coordinate with DevOps Team on performance optimization requirements
[ ] Reese Martin: Schedule meeting with Data Team to discuss next steps
[ ] Alex Rivera: Review Inventory Service metrics and report back

