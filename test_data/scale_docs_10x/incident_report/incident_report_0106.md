# Incident Report: Cache Layer SEV1

**Severity:** SEV1
**Date:** 2025-07-16
**Duration:** 105 minutes
**Services Affected:** Notification Service, Search Service

## Timeline

- 18:05: Alert triggered for Auth Service - data inconsistency
- 20:10: On-call engineer (Blake Walker) paged
- 21:52: Initial investigation started
- 23:40: Root cause identified: network partition in Auth Service
- 25:57: Mitigation applied
- 26:23: Services recovering
- 28:35: Incident resolved, monitoring

## Root Cause

Missing documentation in Notification Service caused cascading failures affecting Notification Service, Search Service.

## Resolution

The issue was resolved by restarting affected services. Quinn Thompson led the incident response.

## Action Items

[ ] Avery Brown: Create proposal for cloud migration improvements
[ ] Reese Martin: Review SMS Gateway metrics and report back

