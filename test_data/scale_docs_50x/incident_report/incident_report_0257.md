# Incident Report: Cache Layer SEV2

**Severity:** SEV2
**Date:** 2025-06-26
**Duration:** 116 minutes
**Services Affected:** Fraud Detection, Inventory Service, Cache Layer

## Timeline

- 19:19: Alert triggered for Inventory Service - scaling bottlenecks
- 20:51: On-call engineer (Parker Harris) paged
- 21:17: Initial investigation started
- 22:17: Root cause identified: database connection pool exhaustion
- 23:51: Mitigation applied
- 23:32: Services recovering
- 25:37: Incident resolved, monitoring

## Root Cause

Technical debt in Notification Service caused cascading failures affecting Fraud Detection, Inventory Service, Cache Layer.

## Resolution

The issue was resolved by restarting affected services. Drew Patel led the incident response.

## Action Items

[ ] Kendall Thomas: Coordinate with SRE Team on security audit requirements
[ ] Blake Adams: Coordinate with Growth Team on security audit requirements
[ ] Finley Moore: Coordinate with SRE Team on observability stack requirements

