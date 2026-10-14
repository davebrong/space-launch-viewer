# Issue #1 — mission-specific flight plans: status (2026-10-14)

This supersedes `WIP.txt` (the 2026-10-13 checkpoint). **The core problem is only partly solved.** The unsupported assumption is gone and discovery is real, but free sources supply only coarse route information for a small fraction of missions. No free source of timed, altitude-bearing upcoming trajectories was found.

## What changed

- **Removed** `dragon-iss-nominal-v1`, the fixed 40/45/50° northeast Dragon/ISS model. No vehicle family, payload, destination or orbit implies a direction. A regression test (`test_no_family_based_fallback_can_produce_viewing_advice`) covers this.
- **Discovery** runs for every catalog mission regardless of vehicle or date precision, against two sources. Each mission gets a per-source state: found, stale, not_found, ambiguous, unavailable, blocked, queued or pending. A failed check never leaves a mission pending.
  - **Next Spaceflight** public mission pages report a general departure heading.
    - Matching is exact after explicit name normalization, plus pad validation. The numeric heading embedded in the page must agree with the word.
    - The heading is treated as a 90° quadrant, because the numeric field showed only 45 or 135 across 7 Florida missions of 5 vehicle families.
  - **US Coast Guard NAVCEN SOLAR** launch hazard notices are stored as hazard corridors only.
    - Matching is exact after explicit name normalization, and the notice windows must cover the scheduled date.
    - Near-pad closures are ignored. A message ID reused across missions makes the match ambiguous.
  - A heading that points away from every published hazard area is withheld ("Route sources disagree"). When they agree, only the overlapping bearings are swept; hazard areas never become a single centerline.
- **WIP defects fixed:**
  - A cached robots body followed by a 404 no longer crashes.
  - Robots or index failures now record explicit states.
  - Budget exhaustion queues the remaining missions without making requests.
  - Retry-After and the 6-hour source period are respected.
  - A transient failure keeps the last heading, labeled stale. A changed or invalid page or a 404 withdraws it.
  - Source provenance and licence text are per source, no longer LL2's.
  - Discovery errors cannot stop schedule or weather refreshes.
- **Viewing model** `published-heading-envelope-v1`:
  - Inputs are the admitted heading quadrant (5 headings), a generic, explicitly assumed ascent height/distance envelope (3 scales) and the confirmed observer point.
  - The viewing direction from the observer is reported separately from the departure heading from the pad.
  - An absolute watch time is given only for exact or window launches; otherwise the window is stated as minutes after liftoff.
  - Paths below 3° are reported as horizon-grazing.
  - Clear skies are assumed; cloud cover is a secondary note.
- **API/contracts:**
  - New endpoints `GET /api/v1/launches/{id}/flight-plan` and `GET /api/v1/flight-plan-coverage`.
  - New schema `spec/contracts/flight-plan.schema.json`.
  - Extended `planning_scenario` and `ViewingOpportunity` contracts; TypeScript types regenerated.
- **UI:**
  - Clear-sky lead ("Look … in clear skies"), with the departure heading shown separately as "from the pad".
  - A Mission route information panel (evidence type, source, retrieval time, hash, per-source checks, source changes).
  - Distinct missing-coverage labels and a route-coverage table on the launch list.

## Live coverage (deployed stack, 2026-10-14 ~12:20 UTC)

`GET /api/v1/flight-plan-coverage`: **4 of 205** cached Cape/Kennedy missions have route information. All 4 have a reported departure heading; one also has a hazard corridor. None has a timed path. 201 are `not_found`.

- **By family:** Falcon 9 3/82; Vulcan 1/60; Falcon Heavy 0/12; New Glenn 0/30; Atlas V 0/6; Space Launch System 0/5; Starship 0/3; Terran R 0/4; Nova 0/1; unknown vehicle 0/2.
- **By date precision:** 200 missions have unknown dates (1 with route information). Next Spaceflight's upcoming index lists only about 18 launches worldwide. SOLAR notices appear only days before launch.

## Real examples (`offline-validation-2026-10-14.json`, `live-validation-2026-10-14.json`)

| Mission | Sources | ZIP md-zip (Maryland, MD area) | ZIP fl-zip (Florida) |
|---|---|---|---|
| Dragon CRS-35 (2026-10-13 10:33Z, SLC-40) | Next Spaceflight "Launching Northeast"; SOLAR CGD-SE BNM 9079-26 hazard areas 15°–60° from the pad, 35–552 km. Sources agree, so headings are swept only across the 15°–60° overlap. | Look south → southeast → east → northeast in clear skies, 6:33–6:45 AM EDT; 15 of 15 modeled paths visible; peak 6°–86° depending on heading | Look southeast → east → northeast, 6:33–6:45 AM EDT; 15 of 15; peak 24°–46° |
| Bandwagon-5 (2026-10-19 10:30Z, SLC-40) | Next Spaceflight "Launching Southeast" only. No SOLAR notice yet; no primary source states its direction. | Grazes your horizon (modeled): no path rises 3° | Look southeast in clear skies, 6:30–6:41 AM EDT; 15 of 15; peak 18°–26° |

The Bandwagon-5 heading is a single secondary source. Earlier Bandwagon flights went in different directions, so the series does not stand in for this mission. SOLAR should be rechecked before launch; the worker does this automatically every 6 hours, hourly within 6 hours of launch.

## Source verdicts (`source-verdicts-2026-10-14.json`, `retrievals-2026-10-14.json`)

| Source | Verdict |
|---|---|
| USCG NAVCEN SOLAR | Hazard corridors, US Government work. The `tmp/test.js` path is unstable, and the chart says not all missions are shown. **Integrated.** |
| Next Spaceflight | Quadrant-level reported heading. robots.txt and terms both return 404, and API access has no ETA, so reuse permission is unverified. Only the compass word, URL, hash and time are kept; 12 requests/hour. **Integrated with that risk.** |
| NGA MSI broadcast warnings | Stale (newest message 2024-05-10); no mission names. Not integrated. |
| FAA TFR / NOTAM API | TFR list had no space-operations entries to validate. The NOTAM API needs a registered key, which was not registered. |
| SpaceX site JSON, NASA pages, LL2, RocketLaunch.live | Schedule and mission metadata; no direction or path. |
| Space Launch Delta 45 PDFs | Near-shore hazard coordinates; unpredictable URLs, PDF parsing needed. Not integrated. |
| Blue Origin | HTTP 429 bot checkpoint; not retried. |
| ISSC | HTTP 403 (2026-10-13); not retried. |
| ULA | Terms §1.6 prohibit automated collection. Not fetched. |

Raw bodies stay in the git-ignored `.runtime/flight-plan-audit/` and are not redistributed.

## Remaining gaps (not claimed as fixed)

- 201/205 missions have no route information. Most have unknown dates, and the sources publish only near launch.
- No timed trajectory. All estimates use an assumed generic ascent envelope across a 90° heading quadrant, so viewing sectors can be broad.
- Next Spaceflight reuse permission is unverified. SOLAR's file path may change. Either source can disappear; the app then shows explicit unavailable states.
- No empirical validation. G-PILOT still requires real observations; nothing here is a measured detection probability.
- Release gates: G-SOFTWARE remains blocked (partial coverage; off-host recovery). G-REAL, G-UPCOMING, G-GUIDANCE and G-PILOT are unchanged.

## Verification

See `verification-2026-10-14.json` and `../logs/flight-plan-*-2026-10-14.txt` for exact commands and outputs, including failures.

- **Application tests:** 60 passed. 28 are new in `test_flight_plans.py`: parsers on fixtures, worker discovery with 403/404/429/robots/budget/changed-plan/stale cases, planning semantics, API contracts.
- **Other checks:** Ruff passed; TypeScript passed; spec check 9/9.
- **Docker builds:** production `docker compose build api worker web` passed (includes `next build`).
- **Browser:** Playwright 14/14 (desktop + mobile) against the redeployed stack on port 3080 (`../logs/flight-plan-browser-2026-10-14.txt`).
- **Acceptance (`implementation.checks full-release`):** 123 passed, 1 failed.
  - The failure is `backup-restore`: no verified off-host destination, the same as the 2026-10-13 baseline.
  - The API contract check now covers the flight-plan, coverage and launch-history endpoints. It surfaced three undocumented history error codes, which were added to `error.schema.json`.
- **Software release gate:** exit 2. G-SOFTWARE, G-REAL, G-UPCOMING, G-GUIDANCE and G-BACKUP are blocked; G-PILOT is empirical and separate.
- **Parser on real pages:** `parser-real-pages-2026-10-14.json` covers 7 retrieved Next Spaceflight pages (Falcon 9, Falcon Heavy, Vulcan, New Glenn). All parsed. Wrong-mission, wrong-pad and inconsistent-heading negatives were rejected.
- **Chrome QA:** a manual pass of the live UI found a misleading blended sky band, contradictory "different direction" copy, a raw-data NAVCEN link, exposed hashes and "45–45%" cloud ranges. These were fixed and redeployed.
  - Not addressed: loading-state heading flicker, Title Case badges, and mobile layout, which was not checked in Chrome. Playwright's 360px project did pass.
- **Code review (independent subagent):** fixed and regression-tested:
  - Per-source staleness. A fresh second source no longer hides stale retained evidence, and evidence now ages by its own retrieval time.
  - Undated historical estimates were labelled "not visible".
  - Archived launches whose check failed or was budget-queued are rechecked when due.
  - A changed SOLAR format now withdraws hazard evidence instead of reusing the old copy.
  - The budget stop only queues missions that actually need a request.
  - Digit-group name collisions ("11-1" vs "1-11") are fixed.
  - Assessment cache keys ignore refetch hashes.
- **Final live check:** after the last redeploy: `live-validation-final-2026-10-14.json`.
