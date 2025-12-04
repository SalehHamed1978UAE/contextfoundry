# Design Doc: Caching Strategy Implementation

**Author:** Dakota Miller
**Reviewers:** Taylor Kim, Cameron Davis, Mia White
**Status:** Draft
**Created:** 2025-10-21

## Overview

This design document proposes changes to Shipping Service to support caching strategy. The goal is to address current resource exhaustion and improve system reliability.

## Requirements

1. Support caching strategy with minimal downtime
2. Maintain backward compatibility
3. Improve observability
4. Meet SRE Team SLA requirements

## Technical Design

- Mia White presented data showing improvements in Fraud Detection after implementing caching strategy.
- Mia White presented data showing improvements in Checkout Service after implementing caching strategy.
- The discussion around caching strategy highlighted tensions between speed and stability.
- The discussion around caching strategy highlighted tensions between speed and stability.
- There was significant debate about caching strategy. Mia White advocated for a phased approach.
- Mia White raised concerns about security vulnerabilities in the context of caching strategy.
- Alex Rivera noted that Notification Service is currently experiencing missing documentation.

## Alternatives Considered

1. Use existing Email Service infrastructure (rejected: doesn't scale)
2. Third-party solution (rejected: cost prohibitive)
3. Proposed approach (selected)

## Implementation Plan

- Week 1: Development environment setup
- Week 2-3: Core implementation
- Week 4: Integration testing with Payment Service
- Week 5: Staged rollout

