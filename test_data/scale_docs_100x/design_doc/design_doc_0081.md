# Design Doc: Hiring Priorities Implementation

**Author:** Blake Adams
**Reviewers:** Avery Brown, Tatum Lewis, Jordan Lee
**Status:** Approved
**Created:** 2025-08-25

## Overview

This design document proposes changes to Checkout Service to support hiring priorities. The goal is to address current memory leaks and improve system reliability.

## Requirements

1. Support hiring priorities with minimal downtime
2. Maintain backward compatibility
3. Improve observability
4. Meet QA Team SLA requirements

## Technical Design

- The discussion around hiring priorities highlighted tensions between speed and stability.
- Emerson Wilson recommended a proof-of-concept for hiring priorities using SMS Gateway.
- Mia White presented data showing improvements in API Gateway after implementing hiring priorities.
- The discussion around hiring priorities highlighted tensions between speed and stability.
- Blake Adams proposed that we should prioritize hiring priorities before Q4.
- Quinn Thompson suggested involving Mobile Team in the hiring priorities initiative.
- Blake Adams suggested involving SRE Team in the hiring priorities initiative.
- The team discussed the impact of hiring priorities on Fraud Detection.

## Alternatives Considered

1. Use existing Auth Service infrastructure (rejected: doesn't scale)
2. Third-party solution (rejected: cost prohibitive)
3. Proposed approach (selected)

## Implementation Plan

- Week 1: Development environment setup
- Week 2-3: Core implementation
- Week 4: Integration testing with API Gateway
- Week 5: Staged rollout

