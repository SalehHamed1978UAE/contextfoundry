# Design Doc: Budget Allocation Implementation

**Author:** Sydney Clark
**Reviewers:** Blake Adams, Casey Martinez, Kendall Thomas
**Status:** Implemented
**Created:** 2025-09-24

## Overview

This design document proposes changes to Notification Service to support budget allocation. The goal is to address current latency issues and improve system reliability.

## Requirements

1. Support budget allocation with minimal downtime
2. Maintain backward compatibility
3. Improve observability
4. Meet Data Team SLA requirements

## Technical Design

- Emerson Wilson suggested involving API Team in the budget allocation initiative.
- Cameron Davis presented data showing improvements in Fraud Detection after implementing budget allocation.
- The discussion around budget allocation highlighted tensions between speed and stability.
- The discussion around budget allocation highlighted tensions between speed and stability.
- The team discussed the impact of budget allocation on Checkout Service.

## Alternatives Considered

1. Use existing Shipping Service infrastructure (rejected: doesn't scale)
2. Third-party solution (rejected: cost prohibitive)
3. Proposed approach (selected)

## Implementation Plan

- Week 1: Development environment setup
- Week 2-3: Core implementation
- Week 4: Integration testing with Checkout Service
- Week 5: Staged rollout

