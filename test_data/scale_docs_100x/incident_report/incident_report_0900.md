# Incident Report: SMS Gateway SEV3

**Severity:** SEV3
**Date:** 2025-07-12
**Duration:** 148 minutes
**Services Affected:** Auth Service

## Timeline

- 16:10: Alert triggered for Notification Service - latency issues
- 18:35: On-call engineer (Dakota Miller) paged
- 18:31: Initial investigation started
- 18:55: Root cause identified: database connection pool exhaustion
- 18:55: Mitigation applied
- 18:07: Services recovering
- 19:52: Incident resolved, monitoring

## Root Cause

Latency issues in Search Service caused cascading failures affecting Auth Service.

## Resolution

The issue was resolved by rolling back the deployment. Sage Robinson led the incident response.

## Action Items

[ ] Alex Rivera: Create proposal for technical debt improvements
[ ] Mia White: Follow up on compliance requirements by 2025-11-20
[ ] Reese Martin: Coordinate with QA Team on observability stack requirements
[ ] Drew Patel: Create proposal for technical debt improvements

