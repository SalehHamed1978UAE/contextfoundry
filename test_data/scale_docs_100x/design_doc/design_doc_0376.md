# Design Doc: Hiring Priorities Implementation

**Author:** Jordan Lee
**Reviewers:** Mia White, Dakota Miller, Blake Adams
**Status:** Implemented
**Created:** 2025-10-02

## Overview

This design document proposes changes to Notification Service to support hiring priorities. The goal is to address current technical debt and improve system reliability.

## Requirements

1. Support hiring priorities with minimal downtime
2. Maintain backward compatibility
3. Improve observability
4. Meet API Team SLA requirements

## Technical Design

- Emerson Wilson noted that Auth Service is currently experiencing configuration drift.
- The discussion around hiring priorities highlighted tensions between speed and stability.
- There was significant debate about hiring priorities. Taylor Kim advocated for a phased approach.
- Taylor Kim raised concerns about technical debt in the context of hiring priorities.
- Morgan Chen noted that Search Service is currently experiencing timeout errors.
- Morgan Chen recommended a proof-of-concept for hiring priorities using User Service.
- Morgan Chen suggested involving Frontend Team in the hiring priorities initiative.

## Alternatives Considered

1. Use existing Notification Service infrastructure (rejected: doesn't scale)
2. Third-party solution (rejected: cost prohibitive)
3. Proposed approach (selected)

## Implementation Plan

- Week 1: Development environment setup
- Week 2-3: Core implementation
- Week 4: Integration testing with Search Service
- Week 5: Staged rollout

