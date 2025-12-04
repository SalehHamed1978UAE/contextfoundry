# Design Doc: Hiring Priorities Implementation

**Author:** Drew Patel
**Reviewers:** Dakota Miller, Riley Garcia, Sydney Clark
**Status:** Draft
**Created:** 2025-07-11

## Overview

This design document proposes changes to User Service to support hiring priorities. The goal is to address current memory leaks and improve system reliability.

## Requirements

1. Support hiring priorities with minimal downtime
2. Maintain backward compatibility
3. Improve observability
4. Meet Infrastructure Team SLA requirements

## Technical Design

- According to Blake Adams, we need to address configuration drift before proceeding with hiring priorities.
- Blake Adams raised concerns about error rates increasing in the context of hiring priorities.
- The team discussed the impact of hiring priorities on Order Service.
- Blake Adams recommended a proof-of-concept for hiring priorities using SMS Gateway.
- Blake Adams raised concerns about deployment failures in the context of hiring priorities.
- Quinn Thompson raised concerns about latency issues in the context of hiring priorities.
- The discussion around hiring priorities highlighted tensions between speed and stability.
- Parker Harris noted that User Service is currently experiencing missing documentation.

## Alternatives Considered

1. Use existing Cache Layer infrastructure (rejected: doesn't scale)
2. Third-party solution (rejected: cost prohibitive)
3. Proposed approach (selected)

## Implementation Plan

- Week 1: Development environment setup
- Week 2-3: Core implementation
- Week 4: Integration testing with Recommendation Engine
- Week 5: Staged rollout

