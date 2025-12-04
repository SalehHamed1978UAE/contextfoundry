# Design Doc: Hiring Priorities Implementation

**Author:** Mia White
**Reviewers:** Logan Jackson, Cameron Davis, Dakota Miller
**Status:** Draft
**Created:** 2025-11-17

## Overview

This design document proposes changes to SMS Gateway to support hiring priorities. The goal is to address current configuration drift and improve system reliability.

## Requirements

1. Support hiring priorities with minimal downtime
2. Maintain backward compatibility
3. Improve observability
4. Meet API Team SLA requirements

## Technical Design

- According to Blake Adams, we need to address resource exhaustion before proceeding with hiring priorities.
- The discussion around hiring priorities highlighted tensions between speed and stability.
- Blake Adams recommended a proof-of-concept for hiring priorities using Cache Layer.
- Cameron Davis suggested involving Security Team in the hiring priorities initiative.
- Sage Robinson presented data showing improvements in User Service after implementing hiring priorities.
- Parker Harris presented data showing improvements in Notification Service after implementing hiring priorities.
- Cameron Davis proposed that we should prioritize hiring priorities before Q4.

## Alternatives Considered

1. Use existing SMS Gateway infrastructure (rejected: doesn't scale)
2. Third-party solution (rejected: cost prohibitive)
3. Proposed approach (selected)

## Implementation Plan

- Week 1: Development environment setup
- Week 2-3: Core implementation
- Week 4: Integration testing with Payment Service
- Week 5: Staged rollout

