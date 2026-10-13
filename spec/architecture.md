# Architecture and implementation boundaries
Browser -> same-origin HTTPS reverse proxy -> Next.js pages and `/api/v1` FastAPI. One Python worker uses PostgreSQL for durable jobs, advisory leader lock, row-lock outbox and fetch budgets. Local immutable evidence volume holds validated raw snapshots, profile/route registry, Census, tzdata and DE421. Redis, Kubernetes, cloud storage and paid APIs are unnecessary.

## Components and flow
- `apps/web/`: location confirmation, observer clock, launch list/detail, SVG band plus textual equivalent, source drawer, conditions, subscriptions/history, feedback and protected admin. Generated TypeScript DTOs from OpenAPI; no provider secrets or direct provider polling in browser.
- `services/api/`: Pydantic DTOs, validation/ownership, read models, assessment orchestration, subscriptions and ICS, admin authentication. Calculation can run inline for uncached request within server timeout; duplicate computations coalesce by input hash.
- `services/worker/`: shared schedule/route/weather fetch, normalization, jobs/revisions, recompute, outbox delivery, purge and backups scheduling. Every job has idempotency key, attempts, lease, next_run_utc. Restart-safe, bounded exponential backoff, source budget reserved BEFORE fetch.
- `packages/visibility/`: pure geometry, solar, intervals, deterministic rules and revision logic. Skyfield/geodesic libraries reused; no numerical flight dynamics or network calls. Immutable candidate manifest is separate from provider raw payload.
- `data/registry/` and `data/profiles/`: reviewed versioned source adapters/compatibility manifests. Unsupported source formats stay disabled with visible reason; operator may disable mission but cannot edit geometry live in SQL.
- `tests/`: offline schema/fixtures/pure tests, application adapter, provider smoke integration, DB concurrency, browser accessibility, load and restore. Fixtures/reference generation never imports application code.

## PostgreSQL model
| Table | Keys/relations and invariants |
|---|---|
| owner_sessions | UUID, capability_hash unique, expires_at; no raw capability |
| locations | UUID, owner_id, confirmed point/ZIP/zone, revision; unique owner+canonical point, active quota transaction |
| provider_snapshots | hash unique, source URL, HTTP status, fetched/issued/valid times, blob path, parser version/license; immutable |
| launches / launch_revisions / attempts | provider UUID unique, immutable revision snapshots; attempt UUID stable across delays; pad/status/time metadata |
| route_evidence / profile_versions / associations | source hash and parser revision; exact launch/attempt association; compatibility decision + reasons |
| weather_intervals | snapshot/grid/time interval indexes, percent/meters nullable, no extrapolation |
| assessments | unique(input_digest), launch/attempt/location revisions, JSONB normalized result, computed_at; archived forecasts immutable |
| subscriptions | owner/location FKs, threshold/quiet consent, enabled/deleted; version for If-Match; channel constraints |
| scheduled_jobs / provider_budget | due UTC, lease/expires, unique job key; rolling request ledger per provider under advisory lock |
| outbox / notifications | unique(subscription,attempt,type,material_revision), FK assessment, current state/lease; notifications one logical history item |
| observations | forecast FK, outcome includes inconclusive/not_attempted, viewing/weather notes, explicit archive consent |
| admin_audit | actor, action, target revision, time, reason; append only; no coordinates/tokens in logs |

Use TIMESTAMPTZ; application always serializes Z. SQL constraints for intervals, revision monotonicity and uniqueness; optimistic If-Match for edits; FK cascade privacy deletion without deleting public evidence. Migrations transactional where supported, reversible or documented restore plan. Index due pending jobs, launch net/status, assessment lookup, owner history. Max100 active distinct subscribed points globally in pilot; preserve existing locations when quota reached, return422 LIMIT_REACHED for new.

## Caching and scheduling
Canonical assessment digest includes all source and model hashes, location/zone, launch attempt/revision, rule/astronomy versions. Cached response must still evaluate current freshness/status, not return an expired positive result. ETag supports client revalidation; never let browser cache private data across owners. Snapshots aren't overwritten on new fetch.

LL2 polling30m normally,5m within6h, global hard12/rolling3600s including retries/pages; reserve budget under DB lock. Keep one slot for each imminent refresh; broad paging yields to imminent mission poll. NWS distinct grid cells hourly/15m, spread deterministically by grid hash over period (max400/h at100 unique cells before retries; backoff reduces). Points daily; returned grid URL may change. Routes6h/1h only allowed source patterns; versioned profiles manual validated release refresh. 429 retry no sooner Retry-After, otherwise exponential jitter with injectable RNG.404 route -> missing;403 -> inaccessible no circumvention. Stale schedules remain browsable with age.

## Deployment/security/privacy
Compose services proxy, web, api, worker, postgres with health checks/restart policies/resource limits. Bind DB only internal network; non-root containers, pinned images, read-only app filesystem and writable named data volumes. Local host can use loopback HTTP development; external deployment requires existing hostname/certificate path and HTTPS. No new public host is assumed. Admin bootstrap via local CLI-generated secret/password hash; no default credentials. Short-lived admin tokens, login rate limiting, CSRF/origin checks, CSP, validated upstream HTTPS allowlist, size/time limits and SSRF protection; SQL parameter binding. Secrets only environment files with restricted permissions, never Git/browser/logs.

Anonymous browsing stores location client-side where practical. Transient server points expire24h. Subscription persists only selected point and preferences; exact GPS optional. Unsubscribe bearer token stored hash, immediate cancellation before acknowledging. Data erasure worker <=24h removes subscription/location/owned history and identifiers; public evidence independent. Logs redact tokens/email/precise points and expire30d. Backups encrypted, rotate7 daily+4 weekly using EXISTING off-host destination; restore reapplies deletion ledger before serving and suppresses already delivered outbox. Delete ledger retained only opaque deleted IDs until all backups containing them expire; no original coordinates/email. RPO<=24h and target RTO<=4h on existing hardware are operational objectives verified by drill.

Metrics: fetch success/age/429, source budget, route support denominator, computation duration, queue lag, duplicate conflicts, purge lag, backup age, disk free. Liveness means process alive; readiness fails missing DB/migrations/model assets, may be degraded for providers while cached browsing works. No sensitive metrics labels. Archive prospective forecast and exact then-available weather before T0; distinguish later realized weather.

Recovery: stop delivery, restore DB/evidence manifests, verify hashes and schema migrations, apply tombstones, reconcile delivered/unknown states, invalidate overdue jobs, re-fetch within budgets and then enable worker. Run restore drill in isolated database without sending external mail. Disk-full preserves last complete snapshot and fails readiness; never partially publish a file.

Privacy purge includes private assessment coordinates, owned observations and any raw GPS-bearing payloads, not just location foreign keys. Retain public launch/source snapshots without linking deleted observers. Anonymized aggregates may remain only when individual points and owner IDs cannot be reconstructed.
