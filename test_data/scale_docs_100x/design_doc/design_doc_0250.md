# Design Doc: Vendor Evaluation Implementation

**Author:** Finley Moore
**Reviewers:** Mia White, Kendall Thomas, Jamie Anderson
**Status:** Approved
**Created:** 2025-09-27

## Overview

This design document proposes changes to Order Service to support vendor evaluation. The goal is to address current timeout errors and improve system reliability.

## Requirements

1. Support vendor evaluation with minimal downtime
2. Maintain backward compatibility
3. Improve observability
4. Meet API Team SLA requirements

## Technical Design

- Morgan Chen suggested involving DevOps Team in the vendor evaluation initiative.
- Tatum Lewis suggested involving Frontend Team in the vendor evaluation initiative.
- Reese Martin presented data showing improvements in Notification Service after implementing vendor evaluation.
- Riley Garcia raised concerns about error rates increasing in the context of vendor evaluation.
- Tatum Lewis recommended a proof-of-concept for vendor evaluation using Payment Service.
- Morgan Chen recommended a proof-of-concept for vendor evaluation using Fraud Detection.
- The discussion around vendor evaluation highlighted tensions between speed and stability.
- Riley Garcia noted that SMS Gateway is currently experiencing technical debt.

## Alternatives Considered

1. Use existing Notification Service infrastructure (rejected: doesn't scale)
2. Third-party solution (rejected: cost prohibitive)
3. Proposed approach (selected)

## Implementation Plan

- Week 1: Development environment setup
- Week 2-3: Core implementation
- Week 4: Integration testing with Fraud Detection
- Week 5: Staged rollout

