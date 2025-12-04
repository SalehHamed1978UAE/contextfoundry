# Incident Report: Fraud Detection SEV1

**Severity:** SEV1
**Date:** 2025-09-14
**Duration:** 151 minutes
**Services Affected:** Search Service, Checkout Service, Recommendation Engine

## Timeline

- 06:34: Alert triggered for Checkout Service - data inconsistency
- 08:12: On-call engineer (Reese Martin) paged
- 08:56: Initial investigation started
- 09:05: Root cause identified: certificate expiration
- 09:56: Mitigation applied
- 09:06: Services recovering
- 11:08: Incident resolved, monitoring

## Root Cause

Security vulnerabilities in Cache Layer caused cascading failures affecting Search Service, Checkout Service, Recommendation Engine.

## Resolution

The issue was resolved by restarting affected services. Morgan Chen led the incident response.

## Action Items

[ ] Taylor Kim: Follow up on Q4 planning by 2025-11-14
[ ] Cameron Davis: Create proposal for Q4 planning improvements

