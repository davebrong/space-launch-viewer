# Supported evidence and evaluation

Historical browsing: Past launches reads the separate previous-launch archive, with no observer-visibility restriction. The current Cape/Kennedy query reports 1,414 records, from Vanguard (1957-12-06) through Dragon CRS-35 (2026-10-13). The UI loads 100 at a time and shows source/update timestamps; older pages are shared, worker-fetched and subject to the API budget. The upcoming catalog remains separate. [Verification](../evidence/build/history.json).


**The core product is incomplete.** Schedule/weather integrations work, but no production route/profile is admitted and automatic mission-by-mission source discovery is not implemented. The simulation below is a limited authored scenario, not the requested broad source integration. [Audit](../evidence/build/source-audit.json).

The practical-planning amendment adds a separate simulation fallback for Cape Falcon 9 / Dragon station missions with a precise scheduled time. It uses authored altitude/downrange assumptions and northeast heading variants, not an admitted published trajectory. The UI labels the result “Simulated estimate,” leads with direction and a broad watch interval, and keeps the assumptions expandable. This requires no postlaunch observations. Only forecast values issued and fetched before the scheduled launch enter its prelaunch weather summary. Outside the nearby coverage below, unsupported families and imprecise schedules do not receive a nominal trajectory plan. Stopped launches are excluded. The versioned model and its assumptions are in `packages/visibility/planning.py`; [planning QA](../evidence/build/planning.json) records verification. This feature does not change evidence-admission, alert classifications or empirical validation status below.

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
