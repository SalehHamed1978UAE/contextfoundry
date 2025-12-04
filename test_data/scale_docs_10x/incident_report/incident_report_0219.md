# Incident Report: Email Service SEV3

**Severity:** SEV3
**Date:** 2025-08-03
**Duration:** 108 minutes
**Services Affected:** Order Service, Recommendation Engine, Search Service

## Timeline

- 19:04: Alert triggered for Payment Service - security vulnerabilities
- 20:45: On-call engineer (Mia White) paged
- 22:38: Initial investigation started
- 23:54: Root cause identified: failed deployment rollback
- 25:48: Mitigation applied
- 25:14: Services recovering
- 27:09: Incident resolved, monitoring

## Root Cause

Memory leaks in Notification Service caused cascading failures affecting Order Service, Recommendation Engine, Search Service.

## Resolution

The issue was resolved by restarting affected services. Finley Moore led the incident response.

## Action Items

[ ] Avery Brown: Create proposal for team restructuring improvements
[ ] Harper Taylor: Review Inventory Service metrics and report back
[ ] Blake Adams: Coordinate with QA Team on vendor evaluation requirements

