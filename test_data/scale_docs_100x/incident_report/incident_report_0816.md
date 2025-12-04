# Incident Report: Order Service SEV3

**Severity:** SEV3
**Date:** 2025-12-01
**Duration:** 88 minutes
**Services Affected:** Order Service, Cache Layer

## Timeline

- 11:12: Alert triggered for Notification Service - missing documentation
- 12:57: On-call engineer (Blake Walker) paged
- 14:28: Initial investigation started
- 14:09: Root cause identified: resource limit reached
- 16:04: Mitigation applied
- 17:09: Services recovering
- 18:54: Incident resolved, monitoring

## Root Cause

Memory leaks in Shipping Service caused cascading failures affecting Order Service, Cache Layer.

## Resolution

The issue was resolved by restarting affected services. Alex Rivera led the incident response.

## Action Items

[ ] Sydney Clark: Follow up on vendor evaluation by 2025-11-17
[ ] Sage Robinson: Create proposal for vendor evaluation improvements

