# Incident Report: User Service SEV3

**Severity:** SEV3
**Date:** 2025-06-08
**Duration:** 145 minutes
**Services Affected:** Inventory Service, Cache Layer, Recommendation Engine

## Timeline

- 18:41: Alert triggered for Order Service - security vulnerabilities
- 20:32: On-call engineer (Finley Moore) paged
- 20:06: Initial investigation started
- 22:11: Root cause identified: memory leak in cache layer
- 24:01: Mitigation applied
- 26:50: Services recovering
- 28:38: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in Cache Layer caused cascading failures affecting Inventory Service, Cache Layer, Recommendation Engine.

## Resolution

The issue was resolved by increasing resource limits. Harper Taylor led the incident response.

## Action Items

[ ] Riley Garcia: Coordinate with API Team on documentation requirements
[ ] Riley Garcia: Follow up on hiring priorities by 2025-11-04
[ ] Drew Patel: Coordinate with SRE Team on capacity planning requirements
[ ] Drew Patel: Review User Service metrics and report back

