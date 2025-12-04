# Incident Report: Analytics Service SEV2

**Severity:** SEV2
**Date:** 2025-06-28
**Duration:** 45 minutes
**Services Affected:** Cache Layer, Inventory Service, SMS Gateway

## Timeline

- 18:00: Alert triggered for Email Service - resource exhaustion
- 19:20: On-call engineer (Sage Robinson) paged
- 20:33: Initial investigation started
- 21:47: Root cause identified: network partition in Shipping Service
- 23:38: Mitigation applied
- 25:06: Services recovering
- 27:55: Incident resolved, monitoring

## Root Cause

Latency issues in Email Service caused cascading failures affecting Cache Layer, Inventory Service, SMS Gateway.

## Resolution

The issue was resolved by increasing resource limits. Sydney Clark led the incident response.

## Action Items

[ ] Sydney Clark: Follow up on disaster recovery by 2025-11-20
[ ] Mia White: Coordinate with SRE Team on compliance requirements requirements
[ ] Sydney Clark: Review Payment Service metrics and report back

