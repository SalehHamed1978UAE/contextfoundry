# Design Doc: Hiring Priorities Implementation

**Author:** Taylor Kim
**Reviewers:** Sydney Clark, Blake Adams, Parker Harris
**Status:** In Review
**Created:** 2025-06-20

## Overview

This design document proposes changes to Shipping Service to support hiring priorities. The goal is to address current missing documentation and improve system reliability.

## Requirements

1. Support hiring priorities with minimal downtime
2. Maintain backward compatibility
3. Improve observability
4. Meet Security Team SLA requirements

## Technical Design

- Avery Brown noted that User Service is currently experiencing scaling bottlenecks.
- Kendall Thomas suggested involving DevOps Team in the hiring priorities initiative.
- Kendall Thomas raised concerns about deployment failures in the context of hiring priorities.
- Avery Brown raised concerns about timeout errors in the context of hiring priorities.
- Sydney Clark presented data showing improvements in Checkout Service after implementing hiring priorities.
- There was significant debate about hiring priorities. Sage Robinson advocated for a phased approach.
- There was significant debate about hiring priorities. Harper Taylor advocated for a phased approach.
- Avery Brown presented data showing improvements in User Service after implementing hiring priorities.

## Alternatives Considered

1. Use existing Payment Service infrastructure (rejected: doesn't scale)
2. Third-party solution (rejected: cost prohibitive)
3. Proposed approach (selected)

## Implementation Plan

- Week 1: Development environment setup
- Week 2-3: Core implementation
- Week 4: Integration testing with Analytics Service
- Week 5: Staged rollout

