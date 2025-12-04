# Incident Report: API Gateway SEV1

**Severity:** SEV1
**Date:** 2025-09-06
**Duration:** 116 minutes
**Services Affected:** User Service, SMS Gateway, Checkout Service, Cache Layer

## Timeline

- 09:01: Alert triggered for Checkout Service - security vulnerabilities
- 10:00: On-call engineer (Morgan Chen) paged
- 11:26: Initial investigation started
- 13:58: Root cause identified: database connection pool exhaustion
- 13:21: Mitigation applied
- 15:42: Services recovering
- 16:22: Incident resolved, monitoring

## Root Cause

Data inconsistency in API Gateway caused cascading failures affecting User Service, SMS Gateway, Checkout Service, Cache Layer.

## Resolution

The issue was resolved by applying a hotfix. Blake Walker led the incident response.

## Action Items

[ ] Jamie Anderson: Follow up on compliance requirements by 2025-11-25
[ ] Logan Jackson: Coordinate with Growth Team on database sharding requirements

