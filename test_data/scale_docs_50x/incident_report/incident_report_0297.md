# Incident Report: Auth Service SEV2

**Severity:** SEV2
**Date:** 2025-11-23
**Duration:** 61 minutes
**Services Affected:** Order Service, Cache Layer

## Timeline

- 13:03: Alert triggered for Order Service - technical debt
- 14:12: On-call engineer (Casey Martinez) paged
- 16:09: Initial investigation started
- 16:23: Root cause identified: network partition in Email Service
- 16:00: Mitigation applied
- 16:40: Services recovering
- 18:53: Incident resolved, monitoring

## Root Cause

Missing documentation in Inventory Service caused cascading failures affecting Order Service, Cache Layer.

## Resolution

The issue was resolved by restarting affected services. Blake Adams led the incident response.

## Action Items

[ ] Dakota Miller: Coordinate with Backend Team on security audit requirements
[ ] Drew Patel: Review Payment Service metrics and report back
[ ] Drew Patel: Coordinate with Growth Team on scalability planning requirements
[ ] Drew Patel: Schedule meeting with API Team to discuss next steps

