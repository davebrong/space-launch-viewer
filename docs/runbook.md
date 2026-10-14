# Local operation

From the repository root, run `python tools/dev.py`, then open
`http://127.0.0.1:3007`. The command installs locked dependencies when missing,
creates a private `.env` with a random local database password if none exists,
starts the dedicated PostgreSQL container, migrates it, and starts the API,
worker and Next.js. Python 3.12, Node 24 LTS, uv, npm and Docker are required.
The implementation machine also has Node 26; the Linux image pins Node 24.
Keep the terminal open. Ctrl+C stops the application children. Database volumes
persist. Do not use `docker compose down -v` unless intentionally erasing data.

The normal application obtains real LL2/NWS data. Synthetic fixtures are confined
to tests. No paid credentials or email account are needed. Unsupported route,
profile or guidance evidence produces “Not enough data”.

## Linux Compose

Copy `.env.example` to `.env` and supply a random `POSTGRES_PASSWORD`. Compose serves
`http://127.0.0.1:3080` and sets the API origin from `COMPOSE_APP_ORIGIN` (default
`http://127.0.0.1:3080`), not from `APP_ORIGIN`, so the local `tools/dev.py` origin (3007)
in the same `.env` cannot break a redeploy. Run `docker compose up --build -d --wait`.
Open `http://127.0.0.1:3080`. The database has no published port in this deployment.
The proxy binds loopback only. The Dockerfiles use resolved immutable base digests;
application containers run without root and with read-only filesystems.

External deployment requires an existing Linux machine, existing reachable name,
and a working TLS configuration. Replace the local Caddy listener with the existing
HTTPS listener/certificate configuration, set the exact HTTPS `COMPOSE_APP_ORIGIN`, and set
`COOKIE_SECURE=true`. Do not expose the local HTTP listener publicly. No host,
domain, certificate service subscription or cloud storage is provisioned here.

## Verification commands

Use `uv run --frozen` to select the locked Python environment.

- `uv run --frozen pytest` — application numerical tests.
- `uv run --frozen ruff check packages services implementation ops tests/application tools/dev.py` and `npm run lint`.
- `npm run build` — optimized Next.js build.
- `uv run --frozen python -m implementation.checks full-release` — original acceptance harness with the real adapter, including browser/database/operations scenarios.
- `python tools/check_spec.py` — original offline specification and harness checks (install `requirements-spec.txt` if needed).
- `python tests/acceptance/live.py` — original read-only provider smoke. This is not route validation.
- `uv run --frozen python -m implementation.gates historical-cape`, `upcoming-cape`, `official-guidance`, or `pilot` — evidence gates; blocked gates exit nonzero.
- `uv run --frozen python -m implementation.checks load-100` — 100 confirmed points, two-stage 15-minute full synthetic ensemble and 1000 requests/20 clients.
- `python tools/release_gate.py` — release audit, which must remain blocked/failed until required evidence exists.

For the original acceptance command directly, set `LV_ACCEPTANCE_COMMAND` to the
JSON array `[".venv/Scripts/python","-m","implementation.acceptance_adapter"]`
on Windows, or `[".venv/bin/python","-m","implementation.acceptance_adapter"]`
on Linux. Missing configuration deliberately remains a harness failure.

Browser verification uses the running local app at port 3007 and the built Compose
web/proxy at port 3080. Start `docker compose up -d postgres api web proxy` first.
Playwright starts an isolated PostgreSQL-backed test API/proxy on port 3091; its
synthetic state endpoints are never included in the production image. Keep the
separate Compose worker stopped while the local development worker is active so
independent databases do not duplicate free-provider polling.

## Admin

Run `uv run --frozen python -m implementation.manage admin-secret` locally.
Store the printed recovery secret privately; place only its hash in
`ADMIN_SECRET_HASH` in `.env` and restart API. There are no default credentials.
The admin screen exchanges the secret for a 15-minute token kept in browser memory.
Login attempts have a shared database rate limit. Mission changes and retries
are append-only audited. A 403/429 source backoff cannot be bypassed by Retry.

## Backup and recovery

Set `BACKUP_DESTINATION` to an accessible **existing off-host directory** and
`BACKUP_KEY` to a privately stored Fernet key. Verify that this directory is really
off-host before setting `BACKUP_DESTINATION_OFFHOST=true`. No default destination
is assumed. `uv run --frozen python -m ops.backup backup` writes a consistent
encrypted database/immutable-asset snapshot and encrypted deletion ledger.
When those settings are configured, the worker schedules a daily encrypted backup
and synchronizes the deletion ledger every 30 seconds. For Linux Compose add
`-f compose.yaml -f compose.backup.yaml` to the Compose command; the override
requires an existing directory and never creates a storage destination. Keep the key outside backups
and source control. Without the existing destination, off-host recovery is blocked.

Retention preserves daily/weekly recovery points; review capacity and keep seven
daily and four weekly snapshots. Recovery objective: RPO <=24 hours, RTO <=4 hours.
An isolated local encrypted restore test is implemented and measured separately;
it does not establish off-host RPO or disaster survivability.

Before restore: stop workers/delivery, create a fresh isolated migrated database,
decrypt and verify the backup and all asset hashes, and supply the **latest**
deletion ledger independently of the older backup. `ops.backup.restore()` refuses
a populated target, reapplies tombstones, cancels ambiguous/pending outbox work,
and does not send external messages. Verify private deleted records are absent,
migrations are current, and counts/hashes match; then allow budgeted fresh ingestion
and resume workers. Never start service against restored private data before tombstones.

## Failures and maintenance

Health: `/api/v1/health/live` and `/api/v1/health/ready`; protected
`/api/v1/admin/metrics`, `/api/v1/admin/ingestion`, `/api/v1/admin/audit`.
Inspect `docker compose ps` and `docker compose logs --tail 100 api worker`.
Worker error logs contain error classes, not URLs with coordinates, session keys,
request bodies or secrets. File rotation retains 30 daily logs.

LL2 is shared, centrally cached, and capped at 12 requests/rolling hour, including
failures. NWS points and grid cache are shared; cells are staggered deterministically.
Provider outages retain previous immutable snapshots; successful retrieval does not
rewrite issue time. Snapshot writes use temporary files, fsync and atomic replace.
Recoverable jobs have 120-second leases and bounded retries. A crashed worker releases
its leader lock; another worker can reclaim expired work. Avoid running multiple
independent deployments against the same source without sharing the request ledger.

Apply a dependency update only with new resolved locks, license inventory, fixtures,
API/browser checks and a restore drill. Registry data updates are immutable versioned
releases; untested document formats, arbitrary map interpretation and model-generated
routes are never admitted. See `docs/coverage.md` for the current evidence support.

## Reviewed registry packages

The admin import accepts `{ "kind": "route-evidence" | "ascent-profile", "document": <contract JSON>, "raw_base64": <original source bytes>, "review_notes": <permission/identity/compatibility review> }`. The document follows the corresponding file under `spec/contracts/`. Its source SHA256 must match the original bytes. Only the three reviewed-v1 formats in `docs/coverage.md` are supported. The import records an immutable version and audit entry. Synthetic inputs are refused in normal operation. Expired route validity or unknown recovery/vehicle metadata prevents admission even if a package is stored. New versions must use new IDs.

The highest revision for each route/profile family supersedes earlier revisions,
including when the replacement is rejected. Keep family identity fields stable when
withdrawing prior evidence. Imports invalidate affected pending notices; delivery
rechecks the current assessment before committing an in-app notice.
