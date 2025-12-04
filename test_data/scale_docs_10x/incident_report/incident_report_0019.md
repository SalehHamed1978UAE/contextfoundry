# Incident Report: Cache Layer SEV1

**Severity:** SEV1
**Date:** 2025-06-20
**Duration:** 49 minutes
**Services Affected:** Auth Service, Payment Service, Email Service, Search Service

## Timeline

- 04:42: Alert triggered for Auth Service - deployment failures
- 04:22: On-call engineer (Reese Martin) paged
- 05:53: Initial investigation started
- 05:40: Root cause identified: database connection pool exhaustion
- 07:23: Mitigation applied
- 07:18: Services recovering
- 08:58: Incident resolved, monitoring

## Root Cause

Configuration drift in Notification Service caused cascading failures affecting Auth Service, Payment Service, Email Service, Search Service.

## Resolution

The issue was resolved by applying a hotfix. Kendall Thomas led the incident response.

## Action Items

[ ] Jordan Lee: Schedule meeting with DevOps Team to discuss next steps
[ ] Avery Brown: Review Payment Service metrics and report back
[ ] Riley Garcia: Review API Gateway metrics and report back

