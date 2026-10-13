# Application implementation checklist

2026-10-13 location QA: nearby Cape/Kennedy planning now uses the confirmed point and pad across mission families, including date-only opportunities with time TBA. Viewable is today through 30 days; Upcoming was removed. Live ZIP fl-zip and md-zip results differ. This does not complete distant mission coverage. [Verification](evidence/build/nearby.json).

Coverage audit: the core ZIP visibility integration is incomplete. T05 supplies a registry, not automatic mission-source discovery or qualified production profiles. T04’s first-page bug is fixed and all 205 currently returned Cape/Kennedy records are ingested. See [source audit](evidence/build/source-audit.json).

Viewable-list follow-up: T10/T13/T14 now provide paginated, owner-checked viewing summaries, a default ZIP-based Viewable filter, explicit unsupported cards in All, location-change invalidation, and hidden Observations/Privacy entry points. Direct pages and privacy deletion remain functional. [Verification](evidence/build/viewable.json).

Practical-planning follow-up: the user's later requirement permits a nominal simulation fallback. T12/T13 now deliver a direction/time-first page, optional simulated geometry and collapsed source details for supported Dragon station launches. T09/T14 retain separate admitted-evidence classifications and alert rules. [Planning evidence](evidence/build/planning.json) records the model, checks and scope; no empirical gate was promoted.

All T01–T21 milestones were pursued. The PRD v1.2 remains authoritative. The explicit implementation request supersedes the old specification-only sentence. No original acceptance expectation or fixture was relaxed.

The full acceptance command executes all named suites in the plans; aliases share those suite results. Exact executed commands, stdout/stderr, exit codes and hashes are under `evidence/build/logs/`. External failures are not passes.

QA follow-up for ZIP md-zip and the same-day SpX-35 launch: completed-launch reviews, supported geometry retention, unknown-date grouping, loading/error/navigation states, forecast timestamps, retrospective observation classification and shared weather-cache ownership were corrected. [QA evidence](evidence/build/qa-md-zip.json) supplements the T12/T13/T14/T15/T21 baseline below; data, off-host recovery and prospective pilot gates remain blocked.

| Task | Status | Delivered work | Verification |
|---|---|---|---|
| T01 | Implemented / verified | Pinned locks, real dev/lint/test/migrate commands, generated DTOs, immutable base images | spec-final; python-lint-final; typescript-final; linux-compose-final |
| T02 | Externally blocked | Parsed 578 real Orbcomm samples and archived permissions; route/datum/stage/held-out admission missing | G-REAL.json; gate-historical-cape |
| T03 | Attempt complete; visibility externally blocked | Live Cape schedule and Maryland NWS attempt recorded; no qualified path/profile for upcoming mission | G-UPCOMING.json; provider-live-final |
| T04 | Implemented / verified | Real LL2 enums, Cape filter, material revisions, shared budgets and failure behavior | full acceptance R003/R015; worker-recovery; ll2-launch_statuses.json |
| T05 | Partial: registry implemented; automatic source integration missing | Audited versioned registry, raw hashes, tested formats, compatibility and source-change suppression | route-registry; application-unit-final; G-REAL/G-GUIDANCE |
| T06 | Implemented / verified | Census ZIP/GPS/manual confirmation, IANA zone, NWS units/intervals/cache and quota | full acceptance R002/R009; live provider check; browser |
| T07 | Implemented / verified | WGS84 geometry, first ascent burns, horizon crossings, gaps, circular envelopes and complete-negative rules | geometry/R006/R007; independent PROJ unit check |
| T08 | Implemented / verified | Local DE421, solar references, DST/folds/gaps, launch-window alternatives | R008/R011; launch-windows; browser |
| T09 | Implemented / verified | Ordered advice, weather subintervals/freshness, source-failure suppression, immutable input archives | R009/R010; reproducibility; application-unit-final |
| T10 | Implemented / verified | PostgreSQL migrations, original OpenAPI operations, ownership, revisions, cursor pages, idempotency | api-contract; encrypted restore; application-unit-final |
| T11 | Implemented / verified | Leased durable jobs, leader/request locks, atomic snapshots, recovery and cache invalidation | worker-recovery; revision_race; load-100 |
| T12 | Implemented / verified | Admin auth/audit, CSRF/SSRF, private deletion including raw point blobs, recovery tombstones, redacted logs | privacy-security; admin_disable; privacy_delete; unit/browser |
| T13 | Implemented / verified | Responsive confirmation, fallback, local date grouping, precision/status/error/empty states | six desktop/mobile browser journeys; accessibility artifacts |
| T14 | Software implemented; real guidance gate blocked | SVG/table, source provenance, uncertainty, solar/weather and conditional alternatives | browser-guidance; G-GUIDANCE.json |
| T15 | Implemented / verified | Reminder previews/editing/opt-ins, history, privacy/recovery, observations and admin controls | browser journeys; API/security/notification suites |
| T16 | Implemented / verified | Transactional outbox, timing, quiet hours, corrections, downgrade debounce, unsubscribe and races | R012/R013; postgres-races; revision_race |
| T17 | Implemented / verified | RFC5545 snapshot export, health/coverage/queue metrics; optional email disabled | calendar; health; scope-cost |
| T18 | Software/local deployment verified; off-host gate blocked | Nonroot Linux Compose, encrypted backup scheduler and isolated restore; no off-host destination | linux-compose-final; deployment-artifact-restore; G-BACKUP |
| T19 | Regression complete; release gates blocked | Original 112 vectors plus 12 scenarios: 123 pass, off-host restore fails; real gates remain blocked | acceptance-final.json; releases/; spec-final |
| T20 | Load/local recovery verified; off-host verification blocked | 100 points, full two-candidate/two-stage ensemble, cached target met, memory and queue metrics, Linux restore | ensemble-load.json; deployment-artifact-restore; G-BACKUP |
| T21 | Archive software verified; human pilot externally blocked | Prelaunch immutable forecasts, outcomes and denominators; no fabricated observations or stronger advice | pilot-archive; G-PILOT.json |

See [BUILD_REPORT.md](BUILD_REPORT.md), [runbook](docs/runbook.md), and [release inputs](evidence/build/release-input-manifest.json).
