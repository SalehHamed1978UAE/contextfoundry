# Incident Report: Checkout Service SEV3

**Severity:** SEV3
**Date:** 2025-07-08
**Duration:** 94 minutes
**Services Affected:** Recommendation Engine, Order Service, Cache Layer

## Timeline

- 21:55: Alert triggered for Auth Service - security vulnerabilities
- 23:02: On-call engineer (Drew Patel) paged
- 24:27: Initial investigation started
- 26:13: Root cause identified: database connection pool exhaustion
- 27:57: Mitigation applied
- 28:24: Services recovering
- 29:40: Incident resolved, monitoring

## Root Cause

Latency issues in User Service caused cascading failures affecting Recommendation Engine, Order Service, Cache Layer.

## Resolution

The issue was resolved by increasing resource limits. Sage Robinson led the incident response.

## Action Items

[ ] Cameron Davis: Create proposal for hiring priorities improvements
[ ] Tatum Lewis: Review Recommendation Engine metrics and report back

