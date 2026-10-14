# Supported evidence and evaluation

Historical browsing: Past launches reads the separate previous-launch archive, with no observer-visibility restriction. The current Cape/Kennedy query reports 1,414 records, from Vanguard (1957-12-06) through Dragon CRS-35 (2026-10-13). The UI loads 100 at a time and shows source/update timestamps; older pages are shared, worker-fetched and subject to the API budget. The upcoming catalog remains separate. [Verification](../evidence/build/history.json).


**Mission route coverage remains partial (issue #1).** The Dragon/ISS northeast simulation (`dragon-iss-nominal-v1`) has been removed. No vehicle family, payload, destination or orbit implies a direction any more. Every catalog mission, whatever its vehicle or date precision, enters automatic route discovery against two free public sources:

- **Next Spaceflight public mission pages** report a general departure direction ("Launching Southeast"). The page's embedded numeric heading was only ever 45 or 135 across seven Florida missions of five vehicle families, so the direction is treated as a 90° quadrant. It is a reported heading from the pad, not trajectory coordinates or an operator-filed plan, and the site publishes no terms or API permission (see limitations below). Its upcoming index lists only about 18 launches worldwide.
- **US Coast Guard NAVCEN SOLAR** publishes mission-named launch hazard areas (Broadcast Notices to Mariners) as GeoJSON. These are safety zones, never a centerline, altitude or timing. They are shown as hazard corridors and are used only to reject a reported heading that points away from every published hazard area, or to narrow the swept headings to the overlap.

With an admitted heading, `published-heading-envelope-v1` (`packages/visibility/planning.py`) sweeps five headings across the quadrant with a generic, explicitly labeled ascent height/distance envelope and computes where to look *from the observer*: direction, a watch interval relative to liftoff (absolute only when the launch time is exact or a window) and peak elevation. It assumes clear skies; cloud forecasts are a secondary note. Paths below 3° are reported as horizon-grazing. Missing coverage (pending, not found, unavailable, blocked, ambiguous, hazard-only, sources disagree) is shown separately from modeled results and never counts as a negative. `GET /api/v1/flight-plan-coverage` reports denominators by state, evidence type, vehicle family and time precision, plus a notice-window denominator: missions dated within the next 7 days or already flown. Both sources publish only days before launch, so that window is the meaningful coverage measure; undated or later missions are labeled “Route not published yet” rather than “No published route found”. No free source of timed, altitude-bearing upcoming trajectories was found; the full audit is in [evidence/build/flight-plan-audit/](../evidence/build/flight-plan-audit/STATUS.md).

The nearby early-ascent fallback (`packages/visibility/nearby.py`) applies across mission families. It requires a known Cape/Kennedy pad, a confirmed point within 100 km, and an unobstructed WGS84 line of sight to a reference point 2 km above the pad. These are explicit model coverage parameters, not source-derived visibility boundaries. Direction is toward the pad; T−2 to T+5 minutes is practical watch guidance, not a calculated visible interval. No flight path is generated. Published windows retain their full uncertainty; date-only opportunities retain time TBA. Trees, buildings, weather and actual flight behavior can prevent a sighting. This fixes nearby eligibility but does not complete distant trajectory coverage. [Nearby QA](../evidence/build/nearby.json).

| Input | Normal operation | Limits |
|---|---|---|
| Launch Library 2 2.3.0 | Real HTTPS schedule adapter; Cape/Kennedy location and coordinate post-filter | Source precision and status retained; scheduled T0 is not liftoff; central 12/hour budget |
| Census 2025 Gazetteer | Bundled pipe-delimited ZIP representative points, hashes and attribution | ZCTA is not every postal ZIP; manual/device confirmation fallback |
| NWS | Real points → returned grid; ISO intervals, total cloud, visibility and fog when supplied | No layer invention, extrapolation or paid fallback; fetch and issue ages separate |
| Skyfield / DE421 / timezonefinder / tzdata | Locked local astronomy and zone assets | Geometric horizon, no buildings/terrain; unsupported ephemeris dates unavailable |
| Historical Orbcomm OG2 archive | Real pinned parser fixture; explicit km-to-m conversion | Research only: stage/altitude datum/modern compatibility unresolved |
| Reviewed path manifest v1 | Exact mission/pad/attempt, tested schema, published geodesic vertices | No production path family currently admitted; no hazard centerline inference |
| Reviewed official guidance v1 | Separate regional membership and source timing path | TOMEX+ page exists but its image is not classified into an observer boundary; real fixture gate remains blocked |
| Reviewed hazard manifest v1 | Coarse source evidence only | No timed track, inferred altitude, or Worth a look |
| Next Spaceflight mission pages | Automatic per-mission discovery; exact name + pad validation; numeric/word heading consistency check | Quadrant-level reported heading only; partial index; no published terms or API permission |
| NAVCEN SOLAR hazard notices | Automatic per-mission discovery; exact normalized names; notice windows must cover the launch date | Hazard corridor only; unstable `tmp/test.js` path; banner says not all missions are shown |
| Other PDFs, images, new formats | Unsupported | Require parser fixtures and reviewed applicability before admission |
| In-app / ICS | Free baseline | Calendar is a snapshot; updates require downloading again |
| Email | Disabled | No entitlement or paid account is assumed; not a release dependency |

The route/profile gate does not mean software tests prove a sighting. Synthetic
geometry/load/browser fixtures never enter the production registry or pilot counts.

Prospective assessments retain source hashes and original forecast-time weather.
Observations support seen, not_seen, inconclusive and not_attempted with explicit
consent. Coverage reports include all ingested Cape missions, including unsupported
ones, and separate positive/missed attempts from inconclusive and missing feedback.
No response is never counted as a negative. Five launches and 30 properly archived
human viewing attempts are still required; no observations were fabricated.
Reconstructed advice remains capped at Possible even after numerical checks pass.

Completed launches remain available for retrospective viewing review. A review can
show supported model geometry, solar events and overlapping forecast bins; it does
not recreate a prelaunch forecast or measure realized clouds. The observation form
collects the viewing timestamp separately from submission time. Retrospective
reports and assessments first saved after liftoff do not count toward prospective
forecast-validation denominators, even if a real sighting is reported.

Automatic raw-source revalidation currently permits the reviewed NASA blog and
SpaceX launch paths in the adapter allowlist, subject to robots, source backoff and
shared budgets. A changed hash or unsuccessful refresh suppresses admission until
review. Other hosts need a tested adapter before automatic retrieval is supported.
Within each route/profile family, only the highest immutable revision participates;
a later rejection supersedes an older approval. Same-revision alternatives remain
separate candidates. LL2 ingestion now follows all Cape/Kennedy result pages, retains partial results on failure, and records catalogue completeness in `ll2:catalog-status`. Every page/retry shares the rolling budget; broad pages reserve one slot for imminent refreshes. The live audit retrieved 205 entries over three pages. Coverage denominators describe ingested Cape/Kennedy records, not a global census.

Historical archive entries now open local ZIP-specific viewing pages with the same planning models as upcoming launches. Display potential, direction and supported watch times; unknown precision stays untimed, current weather is excluded, and failed launches retain their outcome. Verified with 32 application tests and desktop/mobile detail, reload, navigation and pagination checks. [Historical detail QA](../evidence/build/history-detail.json). Existing model-coverage and empirical release limitations remain.
