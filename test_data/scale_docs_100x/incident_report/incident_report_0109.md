# Incident Report: Auth Service SEV2

**Severity:** SEV2
**Date:** 2025-11-23
**Duration:** 173 minutes
**Services Affected:** Checkout Service, SMS Gateway, Cache Layer

## Timeline

- 06:25: Alert triggered for SMS Gateway - technical debt
- 06:46: On-call engineer (Casey Martinez) paged
- 08:07: Initial investigation started
- 10:45: Root cause identified: resource limit reached
- 12:35: Mitigation applied
- 13:00: Services recovering
- 13:25: Incident resolved, monitoring

## Root Cause

Latency issues in Order Service caused cascading failures affecting Checkout Service, SMS Gateway, Cache Layer.

## Resolution

The issue was resolved by applying a hotfix. Jamie Anderson led the incident response.

## Action Items

[ ] Parker Harris: Schedule meeting with Mobile Team to discuss next steps
[ ] Emerson Wilson: Follow up on documentation by 2025-11-25
[ ] Emerson Wilson: Follow up on team restructuring by 2025-11-04
[ ] Parker Harris: Review Recommendation Engine metrics and report back
[ ] Parker Harris: Create proposal for scalability planning improvements

