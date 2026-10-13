# Notifications and operational features

Run in dependency order. A blocked external input blocks its evidence gate, not unrelated software tasks. Record pass/fail/blocked separately; no task passes on an empty test suite.

## T16 — Notification state machine and race safety

- Requirements: R012, R013.
- Affected files/components: `services/worker/notifications.py`, `services/api/notifications.py`.
- Prerequisites: T09, T11, T12.
- Acceptance criteria: Implement exact milestone/expiry/quiet/threshold/opt-in/revision rules; no past milestones; >=5m accumulated shift/local-date/scrub corrections;10min debounce except immediate window. PostgreSQL two-worker, revision/unsubscribe race and restart tests.
- Verification commands:

```sh
python tests/acceptance/run.py --suite R012
python tests/acceptance/run.py --suite R013
python -m implementation.checks postgres-races
```

- Completion evidence: `evidence/outbox-state-traces`, `evidence/concurrent-transaction-log`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T17 — ICS, operational metrics and optional delivery boundary

- Requirements: R012, R016, R022.
- Affected files/components: `services/api/calendar.py`, `services/worker/metrics.py`, `services/worker/delivery/`.
- Prerequisites: T16.
- Acceptance criteria: RFC5545 snapshot UID/SEQUENCE/time escaping tested; no automatic correction claim. Metrics/health/admin queue. Email remains disabled by default; if enabled require actual free existing provider, verified address/consent, idempotency/reconcile/timeout tests. No paid fallback.
- Verification commands:

```sh
python -m implementation.checks calendar
python -m implementation.checks health
python -m implementation.checks optional-email-policy
```

- Completion evidence: `evidence/ICS-parser-report`, `evidence/health-report`, `evidence/email-disabled-or-tested`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T18 — Existing hardware deployment, backup and recovery

- Requirements: R001, R014, R016.
- Affected files/components: `compose.yaml`, `ops/`, `docs/runbook.md`.
- Prerequisites: T12, T17.
- Acceptance criteria: Pinned nonroot containers, migrations, proxy HTTPS on existing reachable infrastructure or local-only documented. Daily encrypted off-host backup to existing storage; isolation restore <=4h objective and RPO24h, purge tombstones before serves/sends. Disk-full/crash recovery verified.
- Verification commands:

```sh
python -m implementation.checks deployment
python -m implementation.checks backup-restore
```

- Completion evidence: `evidence/host-inventory`, `evidence/restore-drill-log`, `evidence/HTTPS-or-local-only-report`. Include timestamp, command/exit code, software/input hashes and raw logs.
