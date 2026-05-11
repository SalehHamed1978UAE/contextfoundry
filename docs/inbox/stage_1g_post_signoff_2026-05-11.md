SEND TO REPLIT — START

Stage 1G result accepted.

The operating-instruction reframe was interpreted correctly:
- reversible cleanup was allowed;
- scoped Gardener diagnostic fixes were allowed;
- v2 remained parked;
- Stage 2 was not started;
- global ontology, prompts, scheduler, and schema were not changed.

The successful promotion run is accepted as meaningful evidence:
- runtime 57s;
- 658 entities promoted;
- 21 relationships promoted;
- zero errors;
- ontology unchanged;
- block reasons captured.

Before running Cycle 2, run architect/code review on the gardener.py changes and targeted tests for:
1. tenant-scoped duplicate filtering;
2. batched relationship endpoint lookup equivalence;
3. no cross-tenant leakage;
4. relationship promotion still requires trusted endpoints.

If architect review and targeted tests pass, run one additional tenant-scoped promotion cycle on S to test convergence.

Do not start Stage 2.
Do not start scheduler.
Do not run Nexus 100 scoring.
Do not touch v2.
Do not edit replit.md.