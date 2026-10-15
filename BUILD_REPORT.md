# Build report — 2026-10-13

Historical browsing: Past launches reads the separate previous-launch archive, with no observer-visibility restriction. The current Cape/Kennedy query reports 1,414 records, from Vanguard (1957-12-06) through Dragon CRS-35 (2026-10-13). The UI loads 100 at a time and shows source/update timestamps; older pages are shared, worker-fetched and subject to the API budget. The upcoming catalog remains separate. [Verification](evidence/build/history.json).


2026-10-13 location QA: nearby Cape/Kennedy planning now uses the confirmed point and pad across mission families, including date-only opportunities with time TBA. Viewable is today through 30 days; Upcoming was removed. Live results for a near-Cape ZIP and a Maryland ZIP differ. This does not complete distant mission coverage. [Verification](evidence/build/nearby.json).

## Coverage audit: core visibility integration is incomplete

The live public schedule and NWS adapters are real. However, the application has zero admitted production routes and zero ascent profiles; it does not yet assemble public mission-specific sources into viewing estimates across launches. The Dragon-only fallback is an authored simulation, not a substitute for that integration. Earlier wording that the application was implemented overstated completion. The core product is **incomplete**, independently of the empirical pilot and off-host backup gates.

The audit also found and fixed a first-page-only schedule bug. A live budgeted refresh now ingests all **205 Cape/Kennedy records across three pages**. HTTP failures preserve partial data and retry delays; pagination stays on the approved provider and reserves capacity for imminent refreshes. **All** means all records in the PRD’s Cape/Kennedy scope, not worldwide coverage. [Source audit and remaining work](evidence/build/source-audit.json), [live catalogue proof](evidence/build/source-audit/catalog.json).

## Current list: Viewable by ZIP, simpler navigation

The list now defaults to **Viewable**, using location-specific viewing intervals from admitted evidence or the nominal simulation. Unsupported entries are excluded; **All** retains the full schedule and clearly marks entries without estimates. Bandwagon 5 has neither an applicable model nor admitted mission route/profile and appears as **No viewing estimate** in All. No Dragon scenario is silently reused for the rideshare. Today's completed plans remain reviewable. Location changes discard prior eligibility; loading and failures do not fall back to an unfiltered schedule.

Observations and Privacy links are hidden from navigation, launch details and the footer. Their direct pages and APIs remain intact. [Viewable QA](evidence/build/viewable.json) records the final checks and scope. Screenshots were removed from the public repository because they showed test locations.

## Current result: practical simulated viewing plan

The user's follow-up changed the product requirement: a useful prelaunch scenario may use explicit simulation assumptions instead of waiting for a verified mission trajectory. The SpX-35 result for the Maryland QA ZIP now leads with **Look south → southeast → east, around 6:34–6:45 AM EDT**, labeled **Simulated estimate**. Simulation geometry and assumptions are expandable; missing verified-route diagnostics are in collapsed technical details. The page remains available after launch.

The first nominal family covers Cape Falcon 9 / Dragon station missions. It evaluates nine heading/height combinations over an authored nine-minute ascent using WGS84 observer geometry, then adds a two-minute watch buffer. It does not use actual liftoff, sightings or postlaunch cloud forecasts to calculate the plan. The model is an assumption-based scenario, not claimed to be a mission-specific trajectory or validated sighting forecast. Unknown times, stopped launches and unsupported families are excluded. The existing stricter classification/alert and empirical gates remain separate.

Verification and the exact model manifest are in [planning QA](evidence/build/planning.json). Screenshots were removed from the public repository because they showed test locations. The earlier QA results below describe the previous, more restrictive presentation; original full-suite and load results remain a baseline, not a rerun of the new simulation.

## Same-day launch QA follow-up — Maryland QA ZIP

The reported Dragon CRS-2 SpX-35 page remains available after completion. Completed launches now have a review presentation, retain supported sky geometry when available, explain missing path/profile evidence without implying the launch was invisible, and label weather as forecasts with valid and issue times. Unknown provider time placeholders no longer create exact date groups. Assessment errors exit loading and show a useful error; navigation cannot display an older request's assessment.

Observation reports now require the actual viewing time and distinguish retrospective reports from prospective validation. A regression also found and fixed deletion of shared weather caches when a different session at the same ZIP was deleted. Cache cleanup now waits until the final location reference is removed.

QA verification and exact command records are in [qa-md-zip.json](evidence/build/qa-md-zip.json), including application, desktop/mobile browser/accessibility, contract, pilot, privacy, type, lint, specification and Linux build checks. Screenshots were removed from the public repository because they showed test locations. Earlier failed runs are retained; the new browser selectors were corrected to distinguish date headings from card headings and application alerts from Next.js's route announcer. Original acceptance fixtures were preserved.

**Evidence limitation:** this mission still lacks an admitted path and compatible ascent profile for a verified forecast. The simulation follow-up above supplies a separate assumed scenario. The user's reported sighting was not silently entered into the observation archive or counted toward an empirical gate. The full acceptance/load/recovery results below are the earlier implementation baseline; QA reran the affected scenarios, not the entire suite. Release remains blocked.

## Earlier implementation baseline

The application components are running locally; the coverage audit above corrects the earlier completion claim. **Release remains blocked** by real route/profile/guidance evidence, required off-host recovery, and the prospective observation pilot. A schedule entry is not presented as a visibility estimate. No real Maryland sighting accuracy is claimed.

## Run and open

From this repository: `python tools/dev.py`, then open **http://127.0.0.1:3007**. The command was exercised successfully with the existing hardware and dedicated PostgreSQL container. It installs locked dependencies when missing, migrates, and starts Next.js, FastAPI and one worker. It rejects occupied ports without stopping unrelated services. Ports 3000–3006 belonged to existing user services and were preserved.

Prerequisites, Linux Compose, operator-secret setup, backup/restore and failure handling are in [docs/runbook.md](docs/runbook.md). [.env.example](.env.example), [uv.lock](uv.lock), [hashed Python requirements](requirements-app.lock.txt), [package-lock.json](package-lock.json) and [compose.yaml](compose.yaml) are supplied. `.env` is private and ignored. No default admin password, paid account, new hosting, domain or external message service was created. The deployment worker is stopped while the local development worker runs, avoiding duplicate independent provider polling.

## Implemented behavior

- Confirmed Census ZIP representative points, preserved leading zeroes, optional GPS/manual fallback, saved-point selection and observer IANA clocks. Device timezone does not set the viewing timezone.
- Real LL2 2.3 schedules and status/precision normalization, delays, exact/window/date/unknown presentations, completed/in-flight handling, audited reviewed corrections and immutable revisions. Live configuration responses caught and corrected the provider's status-9 and day-precision mappings.
- Separate reviewed published-path, hazard and official-guidance registries, raw-source hash checking, exact mission/pad/attempt admission, historical compatibility, first-burn interpolation, gaps and immutable version supersession. Source revalidation honors allowed paths, robots and backoff; changed raw content suppresses advice pending review.
- WGS84 ECEF/ENU/occultation, five-second candidate sampling, horizon crossing estimates, circular sectors, coarse intervals/elevations, candidate envelopes, local DE421 solar/twilight/shadow calculations and conditional launch alternatives. Reconstructions stay capped at Possible.
- Real NWS point/grid integration, unit and interval normalization, qualifying subintervals, issue/fetch freshness, gaps and unavailable layers/haze. Failed essential refreshes suppress actionable advice while cached source data remain inspectable.
- Responsive launch and guidance UI with loading, empty, error, stale and unavailable states, SVG plus table, source timestamps/hashes, sunrise/twilight and weather. Official guidance does not acquire invented elevations or trajectories.
- In-app subscriptions with local preview, default-off Possible/overnight choices, edits, transactional notices, quiet-hour suppression, expiry, corrections/debounce, unsubscribe, history and RFC5545 snapshot calendars.
- Protected admin, evidence import, audit, health and coverage/queue metrics; private session/recovery key; observations linked to immutable forecasts; deletion cascades and raw GPS-point snapshot removal; backup deletion records.
- PostgreSQL migrations, source budgets, leased jobs, leader locks, atomic snapshots, immutable archives, structured redacted logs, pinned nonroot Linux containers and encrypted backup/restore tooling. Configured existing backup storage enables daily worker backups and frequent deletion-ledger sync. Email remains disabled.

The complete per-task ledger is [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md). All 16 stories and requirement rows retain their original mapping and now have implementation evidence in [spec/traceability.json](spec/traceability.json).

## Verification results

| Check | Result and evidence |
|---|---|
| Original specification and harness checks | 9/9 pass; [command record](evidence/build/logs/spec-final.json) |
| Original full acceptance suite | **123 passed, 1 failed**, unchanged 112 vectors plus 12 scenarios. The failure is required off-host backup recovery; the harness itself reports failed, not blocked. [Full results](evidence/build/acceptance-final.json), [exact command/output](evidence/build/logs/full-release-all.json) |
| Additional application tests | 13 pass, including independent PROJ geometry, source enum regression, gaps/first burns, complete-negative limits, immutable registry and raw-point privacy deletion. [Record](evidence/build/logs/application-unit-final.json) |
| Browser and accessibility | 6 desktop/mobile journeys passed in Chromium; real API/PostgreSQL, live schedule and isolated synthetic evidence states, including observation submission and admin authentication/audit/disable/import rejection. No critical/serious axe violations. [Report](evidence/build/playwright-pre-qa.json), [command](evidence/build/logs/browser-admin-observation-final.json) |
| Strict TypeScript and Python lint | Pass; [TypeScript](evidence/build/logs/typescript-final.json), [Python](evidence/build/logs/python-lint-final.json) |
| Live provider smoke | LL2, NWS point and NWS grid passed; [record](evidence/build/logs/provider-live-final.json). This validates transport/schema, not visibility. |
| Build and deployment | Optimized Next.js/Linux build and Compose startup passed, with final Python images rebuilt after review. [Compose](evidence/build/logs/linux-compose-final.json), [final images](evidence/build/logs/linux-final-python-images.json) |
| Running services | Local API/database/astronomy/worker healthy. Final Linux API image starts; database/astronomy healthy, its worker deliberately stopped to avoid duplicate polling. [Start](evidence/build/logs/linux-final-api-start.json), [readiness responses](evidence/build/logs/final-running-health.json) |
| Local encrypted restore on Linux artifact | Hashes match; deletion record replayed; zero external sends; 0.650 seconds in this small isolated drill. [Record](evidence/build/logs/deployment-artifact-restore.json). This does not prove off-host RPO or disaster recovery. |
| Full ensemble load | 100 confirmed points, 2 candidates, 2 stages ×181 samples (15 minutes), then 1000 cached API requests/20 clients. Cached p95 **0.356 s** (<2 s), zero budget overruns, peak process memory 135.6 MiB, maximum queue claim lag 1.262 s. [Raw measurements](evidence/build/ensemble-load.json) |
| Release audit | Nonzero exit 2, explicitly blocked; specification passes and external recovery/data/pilot gates stay open. [Software](evidence/build/logs/release-software-final.json), [including pilot](evidence/build/logs/release-pilot-final.json) |

The load host was Windows 11/Python 3.12.9 with 12 logical CPUs and Linux PostgreSQL. This is a synthetic full-ensemble software benchmark, not a guarantee for different hardware or a real mission. Python dependency deprecation warnings remain recorded; they did not fail checks.

Resolved failures are retained in timestamped logs: Windows process/temp/cache sandbox restrictions; a horizon-occultation defect; location-navigation and deletion-message races; an isolated browser proxy configuration; a TypeScript pagination inference error; and a browser run overlapping the startup restart. The startup manager now returns failure on occupied ports or failed children and cleans up its own process trees. No assertion was relaxed to hide a failure. Later check records identify the passing reruns.

## Precisely scoped external blockers

| Gate | Evidence and missing input |
|---|---|
| G-REAL | [Historical report](evidence/build/G-REAL.json): real Orbcomm OG2 archive parses 578 samples. Independently verified geodetic route, altitude datum/stage identity, appropriate vehicle/recovery compatibility and a separate held-out qualified mission remain unavailable. Downloaded archive metadata alone is not an admitted trajectory. |
| G-UPCOMING | [Upcoming report](evidence/build/G-UPCOMING.json): real Cape schedule and Maryland NWS retrievals succeeded; the upcoming Bandwagon 5 attempt has no admitted independent mission path plus compatible profile. Hazard areas cannot provide the missing track. |
| G-GUIDANCE | [Official report](evidence/build/G-GUIDANCE.json): NASA TOMEX+ page returned HTTP 200. It is a Wallops example, not a Cape validation, and no reviewed observer boundary plus usable observer viewing interval is admitted. A launch window or image alone does not pass. |
| G-BACKUP / G-SOFTWARE recovery | No existing off-host destination/key is configured. [Storage inspection](evidence/build/logs/existing-storage-inspection.json) confirms N: is a local fixed disk. [Untruncated failing command](evidence/build/logs/offhost-backup-failure-detail.json) records the missing destination. Local encrypted restore works; off-host RPO ≤24 h and disaster survivability remain unverified. |
| G-PILOT | [Pilot report](evidence/build/G-PILOT.json): five real launches and 30 labeled human viewing attempts have not been collected. Synthetic tests, missing feedback and unattempted observations cannot satisfy this gate. |

Exact attempted URLs, HTTP statuses, UTC times and hashes are retained in [evidence/gates.json](evidence/gates.json) and the linked gate reports. No paid credentials are requested as a dependency. The [supported source matrix](docs/coverage.md) describes admitted formats and limitations.

## Release boundaries

No live mission-specific reconstruction is currently admitted. Normal operation correctly returns Not enough data where evidence is missing; synthetic positive cases are isolated from production. The schedule inventory is the centrally cached provider page (up to 100 returned Cape records per fetch), so coverage denominators describe ingested missions, not an independently exhaustive global launch census. API/UI pagination handles accumulated cached records.

Local HTTP binds loopback. Public HTTPS on a separately named existing host has not been established; the runbook documents the configuration without provisioning anything. Terrain/buildings, measured detection probabilities, full rocket dynamics, return burns and TLE back-propagation are outside scope. The release command remains nonzero until the required external gates are fulfilled. Software verification and empirical validation are separate.

Reviewed release inputs and hashes: [manifest](evidence/build/release-input-manifest.json). Release-gate proof: [software audit](evidence/releases/G-SOFTWARE.json).

Historical archive entries now open local ZIP-specific viewing pages with the same planning models as upcoming launches. Display potential, direction and supported watch times; unknown precision stays untimed, current weather is excluded, and failed launches retain their outcome. Verified with 32 application tests and desktop/mobile detail, reload, navigation and pagination checks. [Historical detail QA](evidence/build/history-detail.json). Existing model-coverage and empirical release limitations remain.
