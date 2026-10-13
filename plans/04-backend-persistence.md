# Backend and persistence

Run in dependency order. A blocked external input blocks its evidence gate, not unrelated software tasks. Record pass/fail/blocked separately; no task passes on an empty test suite.

## T10 — Database and API ownership contracts

- Requirements: R014, R016, R018.
- Affected files/components: `services/api/db/`, `services/api/routes/`, `migrations/`.
- Prerequisites: T01, T04, T06.
- Acceptance criteria: Schema migrations/constraints, immutable snapshots/revisions, read/private DTO split; implement every OpenAPI endpoint and error, pagination/cursors/ETag/If-Match/idempotency. Session capability+CSRF, authorization, quota and malformed inputs tested.
- Verification commands:

```sh
python -m implementation.checks api-contract
python -m implementation.checks migrations
python tests/acceptance/run.py --suite R014
```

- Completion evidence: `evidence/OpenAPI-response-validation`, `evidence/migration-upgrade-restore-report`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T11 — Durable jobs, cache and computation orchestration

- Requirements: R011, R015, R016.
- Affected files/components: `services/worker/jobs.py`, `services/api/cache.py`, `services/worker/scheduler.py`.
- Prerequisites: T09, T10.
- Acceptance criteria: Leader/budget locks, jobs unique/leased/restart-safe, cache includes all hashes and runtime freshness; no per-user polling; crash/retry/disk-full paths preserve old snapshots, clock injection. Schedule changes invalidate before notice claim.
- Verification commands:

```sh
python -m implementation.checks worker-recovery
python tests/acceptance/run.py --suite revision_race
```

- Completion evidence: `evidence/worker-crash-report`, `evidence/cache-invalidation-report`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T12 — Security, admin and privacy lifecycle

- Requirements: R014, R016, R018.
- Affected files/components: `services/api/security/`, `services/api/admin/`, `services/worker/privacy.py`.
- Prerequisites: T10, T11.
- Acceptance criteria: Protected authenticated admin disable/retry/audit; no direct production row edits. SSRF/input/CSRF/ownership tests; secrets/log redaction. Immediate unsubscribe and <=24h erasure with backup tombstones,30d logs.
- Verification commands:

```sh
python -m implementation.checks security
python tests/acceptance/run.py --suite privacy_delete
python tests/acceptance/run.py --suite admin_disable
```

- Completion evidence: `evidence/security-test-report`, `evidence/erasure-audit`. Include timestamp, command/exit code, software/input hashes and raw logs.
