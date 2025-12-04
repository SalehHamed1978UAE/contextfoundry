# Security Audit Strategy

**Author:** Morgan Chen
**Last Updated:** 2025-08-07
**Status:** Draft

## Executive Summary

This document outlines the strategic approach to security audit for the upcoming quarter. Key stakeholders include QA Team and DevOps Team.

## Background

The need for security audit has become increasingly apparent as Inventory Service faces latency issues. Dakota Miller initially raised this concern in Q2.

## Proposed Approach

- Finley Moore noted that Checkout Service is currently experiencing memory leaks.
- Finley Moore noted that API Gateway is currently experiencing timeout errors.
- There was significant debate about security audit. Jamie Anderson advocated for a phased approach.
- According to Finley Moore, we need to address configuration drift before proceeding with security audit.
- Cameron Davis raised concerns about timeout errors in the context of security audit.
- Jamie Anderson recommended a proof-of-concept for security audit using Checkout Service.

## Timeline

- Phase 1 (Week 1-2): Planning and requirements
- Phase 2 (Week 3-6): Implementation
- Phase 3 (Week 7-8): Testing and rollout

## Risks and Mitigations

- technical debt may impact timeline
- Resource constraints in SRE Team
- Dependencies on Search Service

