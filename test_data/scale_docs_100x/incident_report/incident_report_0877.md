# Incident Report: Inventory Service SEV2

**Severity:** SEV2
**Date:** 2025-11-20
**Duration:** 123 minutes
**Services Affected:** Payment Service, Inventory Service, Cache Layer

## Timeline

- 02:07: Alert triggered for Shipping Service - technical debt
- 03:28: On-call engineer (Emerson Wilson) paged
- 05:11: Initial investigation started
- 06:35: Root cause identified: network partition in Auth Service
- 06:01: Mitigation applied
- 07:59: Services recovering
- 09:34: Incident resolved, monitoring

## Root Cause

Technical debt in User Service caused cascading failures affecting Payment Service, Inventory Service, Cache Layer.

## Resolution

The issue was resolved by applying a hotfix. Harper Taylor led the incident response.

## Action Items

[ ] Riley Garcia: Follow up on technical debt by 2025-11-18
[ ] Logan Jackson: Schedule meeting with Platform Team to discuss next steps

