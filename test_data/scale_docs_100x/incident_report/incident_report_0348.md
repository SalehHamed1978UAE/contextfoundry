# Incident Report: User Service SEV3

**Severity:** SEV3
**Date:** 2025-06-21
**Duration:** 23 minutes
**Services Affected:** Shipping Service, User Service

## Timeline

- 13:19: Alert triggered for Checkout Service - security vulnerabilities
- 15:37: On-call engineer (Taylor Kim) paged
- 17:00: Initial investigation started
- 17:06: Root cause identified: network partition in Fraud Detection
- 18:45: Mitigation applied
- 20:43: Services recovering
- 22:22: Incident resolved, monitoring

## Root Cause

Deployment failures in Auth Service caused cascading failures affecting Shipping Service, User Service.

## Resolution

The issue was resolved by increasing resource limits. Emerson Wilson led the incident response.

## Action Items

[ ] Blake Walker: Create proposal for performance optimization improvements
[ ] Jordan Lee: Follow up on monitoring improvements by 2025-11-14

