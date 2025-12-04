# Incident Report: Order Service SEV1

**Severity:** SEV1
**Date:** 2025-12-04
**Duration:** 98 minutes
**Services Affected:** Shipping Service

## Timeline

- 01:24: Alert triggered for Shipping Service - configuration drift
- 01:58: On-call engineer (Riley Garcia) paged
- 02:05: Initial investigation started
- 03:29: Root cause identified: network partition in Recommendation Engine
- 04:47: Mitigation applied
- 06:38: Services recovering
- 06:33: Incident resolved, monitoring

## Root Cause

Configuration drift in Payment Service caused cascading failures affecting Shipping Service.

## Resolution

The issue was resolved by rolling back the deployment. Blake Adams led the incident response.

## Action Items

[ ] Taylor Kim: Coordinate with QA Team on capacity planning requirements
[ ] Blake Walker: Review Search Service metrics and report back
[ ] Blake Walker: Review User Service metrics and report back
[ ] Taylor Kim: Coordinate with SRE Team on vendor evaluation requirements

