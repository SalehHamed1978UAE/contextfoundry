# Incident Report: User Service SEV3

**Severity:** SEV3
**Date:** 2025-06-11
**Duration:** 149 minutes
**Services Affected:** API Gateway, Cache Layer, SMS Gateway

## Timeline

- 15:32: Alert triggered for Recommendation Engine - security vulnerabilities
- 16:55: On-call engineer (Blake Walker) paged
- 16:46: Initial investigation started
- 17:41: Root cause identified: resource limit reached
- 18:19: Mitigation applied
- 20:58: Services recovering
- 22:08: Incident resolved, monitoring

## Root Cause

Scaling bottlenecks in API Gateway caused cascading failures affecting API Gateway, Cache Layer, SMS Gateway.

## Resolution

The issue was resolved by increasing resource limits. Sage Robinson led the incident response.

## Action Items

[ ] Jamie Anderson: Follow up on Q4 planning by 2025-11-09
[ ] Avery Brown: Review Notification Service metrics and report back
[ ] Drew Patel: Review Cache Layer metrics and report back
[ ] Jamie Anderson: Create proposal for compliance requirements improvements
[ ] Jamie Anderson: Review SMS Gateway metrics and report back

