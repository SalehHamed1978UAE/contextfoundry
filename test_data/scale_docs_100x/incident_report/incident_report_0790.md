# Incident Report: Search Service SEV1

**Severity:** SEV1
**Date:** 2025-09-11
**Duration:** 177 minutes
**Services Affected:** Auth Service, Fraud Detection, Payment Service, Recommendation Engine

## Timeline

- 16:20: Alert triggered for Payment Service - timeout errors
- 16:33: On-call engineer (Blake Walker) paged
- 16:56: Initial investigation started
- 16:41: Root cause identified: database connection pool exhaustion
- 16:36: Mitigation applied
- 17:08: Services recovering
- 17:00: Incident resolved, monitoring

## Root Cause

Technical debt in User Service caused cascading failures affecting Auth Service, Fraud Detection, Payment Service, Recommendation Engine.

## Resolution

The issue was resolved by restarting affected services. Tatum Lewis led the incident response.

## Action Items

[ ] Logan Jackson: Review SMS Gateway metrics and report back
[ ] Jamie Anderson: Coordinate with DevOps Team on scalability planning requirements
[ ] Sydney Clark: Create proposal for technical debt improvements

