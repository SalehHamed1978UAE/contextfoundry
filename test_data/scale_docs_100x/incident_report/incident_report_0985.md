# Incident Report: Cache Layer SEV3

**Severity:** SEV3
**Date:** 2025-09-18
**Duration:** 69 minutes
**Services Affected:** SMS Gateway, Fraud Detection, Payment Service, Email Service

## Timeline

- 08:10: Alert triggered for API Gateway - latency issues
- 10:52: On-call engineer (Quinn Thompson) paged
- 12:20: Initial investigation started
- 12:52: Root cause identified: failed deployment rollback
- 12:49: Mitigation applied
- 14:25: Services recovering
- 15:32: Incident resolved, monitoring

## Root Cause

Deployment failures in Auth Service caused cascading failures affecting SMS Gateway, Fraud Detection, Payment Service, Email Service.

## Resolution

The issue was resolved by applying a hotfix. Logan Jackson led the incident response.

## Action Items

[ ] Emerson Wilson: Create proposal for technical debt improvements
[ ] Reese Martin: Schedule meeting with Mobile Team to discuss next steps

