# Incident Report: Analytics Service SEV3

**Severity:** SEV3
**Date:** 2025-06-17
**Duration:** 134 minutes
**Services Affected:** Search Service, Order Service, Shipping Service, API Gateway

## Timeline

- 01:00: Alert triggered for Analytics Service - scaling bottlenecks
- 01:02: On-call engineer (Harper Taylor) paged
- 02:20: Initial investigation started
- 03:47: Root cause identified: network partition in Order Service
- 05:51: Mitigation applied
- 06:48: Services recovering
- 08:23: Incident resolved, monitoring

## Root Cause

Latency issues in Shipping Service caused cascading failures affecting Search Service, Order Service, Shipping Service, API Gateway.

## Resolution

The issue was resolved by increasing resource limits. Jamie Anderson led the incident response.

## Action Items

[ ] Mia White: Follow up on hiring priorities by 2025-11-16
[ ] Logan Jackson: Schedule meeting with DevOps Team to discuss next steps

