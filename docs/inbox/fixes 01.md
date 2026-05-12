# Runtime Extraction Worker Recovery — Queue Consumer Validation

## Alignment

- **Module touched:** runtime extraction worker / Start All process only; read-only queue diagnostics first
- **Product vs implementation:** implementation/runtime validation for the dashboard-to-extraction path
- **Architecture-doc consistency:** supports the existing pipeline: dashboard/API creates extraction_requests; worker drains queue into extraction; extraction/promotion pipeline remains unchanged
- **Drift risk:** mistaking a UI symptom for a pipeline redesign; letting 699 queued jobs drain without understanding scope; running Nexus 100 scoring while debugging extraction queue
- **Out of scope:** UI redesign, Resume Extraction button implementation, Nexus 100 scoring, Stage 2 implementation, ontology mutation, prompt changes, v2 work, `replit.md` edits

## Decision

Investigate and recover the extraction worker.

This is not a UI task.

The dashboard sign-in issue is resolved and not the focus.

The dashboard Resume Extraction button being a stub is recorded as a product/UI bug, but not fixed in this task.

The active blocker is:

```text
extraction_requests queue has work
claim_extraction_request works
brain extraction worker appears silent / not consuming
Required first step — verify current state

Before restarting anything, capture:

Start All status
brain/app.py process PID(s)
process start time
thread count
latest Start All log path
whether any [ExtractionWorker] Starting log exists
whether any [ExtractionWorker] Claimed log exists
extraction_requests count by status
extraction_requests count by tenant_id
top 10 tenant_ids by pending request count
whether vault ecd2f1c2-e1f3-4f5c-8e82-961a84a88eda currently has entities/relationships
whether vault ea177f8d or any dashboard-created vault has entities/relationships/chunks

Important: compare the narrative’s claim that ecd2f1c2 has 0 entities/relationships against the live DB. We have later accepted reports saying that vault had extracted/promoted data. If live DB contradicts the narrative, report the live DB state and do not overwrite it.

Required code read

Read only:

brain/app.py

Find:

start_extraction_worker()
extraction_worker_loop()
claim_batch_requests()
where [ExtractionWorker] logs should be emitted
whether the worker is gated by env var/config
whether exceptions inside the worker thread are caught/logged
whether the worker consumes all tenants globally or can be tenant-scoped

Report whether restarting Start All would:

drain all pending extraction_requests globally
or only a scoped subset
Queue-scope decision

If the worker is global and would drain all 699 pending rows, report that before allowing it to run for a long period.

A short recovery observation is allowed, but do not let it drain the entire queue blindly.

Controlled restart authorization

If diagnostics confirm:

Start All is running
extraction_requests has pending rows
claim_extraction_request works
worker logs are absent
worker thread appears dead or never started

then restart Start All only.

This restart is explicitly authorized for this task because the running process may be missing the extraction worker.

Do not restart Manus.

Do not restart Ontology Vault.

Do not restart test workflows.

Do not touch v2 workflows.

Do not edit replit.md.

Post-restart validation

After Start All restarts, watch for 10 minutes or until 3 documents are claimed, whichever comes first.

Capture:

[ExtractionWorker] Starting line
[ExtractionWorker] Claimed lines
number of requests moved from pending → processing/completed
tenant_ids claimed
entities/chunks/relationships created for claimed tenant(s)
any worker exceptions
whether extraction_level / extraction_status changes

If the worker starts draining unexpected tenants, stop and report.

If the worker emits no startup line after restart, stop and report.

If the worker thread dies, inspect logs and report the exception.

If restart fixes it

Report:

worker recovered by Start All restart
queue claims observed
which tenant_ids were claimed
whether dashboard-created vaults began extracting
whether ecd2f1c2 state matches or conflicts with prior accepted Stage 1J state

Do not run Nexus 100 scoring.

Do not continue into a full dashboard benchmark.

If restart does not fix it

Do not keep restarting.

Run a focused code diagnosis:

why start_extraction_worker did not spawn
whether daemon thread crashed before first log
whether logger is not attached in the thread
whether claim loop raises before logging
whether worker startup is behind a disabled flag

Then report the smallest code fix needed.

Do not edit code unless the fix is local and clearly in the extraction-worker startup/logging path.

If code edit is needed, propose it briefly before applying.

Record UI findings as secondary

Record these as secondary findings only:

Google OAuth client mismatch caused sign-in 403; user fixed externally.
Dashboard Resume Extraction button is a stub that only writes platform.extraction_events.
Nothing currently reads that event, so the button cannot resume extraction.

Do not fix the button in this task.

Stop triggers

Stop and report if:

restart would drain all 699 requests without visibility
worker starts processing wrong tenants uncontrollably
Start All fails to restart
worker crashes immediately
fix requires schema change
fix requires broad UI change
fix requires changing extraction prompts
anything would run Nexus 100 scoring
Final report

Report:

live DB queue state
live state of ecd2f1c2 and dashboard-created vaults
whether worker logs were present before restart
whether Start All restart was performed
post-restart worker behavior
queue movement
entities/chunks/relationships created
whether root cause is stale process, dead thread, missing logger, or code bug
whether follow-up code fix is needed
whether UI Resume button remains a separate later bug
Standing constraints

Do not run Nexus 100 scoring.

Do not start Stage 2 implementation.

Do not mutate ontology.

Do not change prompts.

Do not touch v2.

Do not edit replit.md.

Stop condition

Stop after the Runtime Extraction Worker Recovery report.

Wait for sign-off before UI fixes, Nexus scoring, or broader queue-drain work