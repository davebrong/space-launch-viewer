# Space Launch Visibility by ZIP Code

Historical browsing amendment: retain location-based Viewable as default, All as the upcoming catalog, and add Past launches for the separate Cape/Kennedy previous-launch archive. Past launches is independent of ZIP eligibility and the 30-day horizon, sorted newest first, with explicit provider total, page retrieval time, original outcome, record-update time and API links. Load older pages on demand through the shared worker/cache and provider budget; never label a partial page as the complete archive.

Implementation specification and feasibility review

Version 1.2 • October 13 2026

### Product amendment — practical planning simulations (2026-10-13)

Location-first correction: Viewable covers today through 30 calendar days ahead at the confirmed observer point, including today's completed launches. Remove the redundant Upcoming filter. Nearby Cape/Kennedy early-ascent planning applies across mission families: calculate pad-relative direction and distance, use a documented conservative coverage policy (within 100 km and a WGS84 sightline to a reference point 2 km above the known pad), and label “Nearby launch estimate.” These parameters are model assumptions, not measured sighting boundaries. Watch guidance spans T−2 to T+5 minutes, or the published launch window with those buffers; it is not a predicted visible duration. Date-only nearby opportunities remain visible with time TBA and no numerical viewing interval. Do not invent a trajectory. Distant unsupported missions still require additional models or admitted mission evidence.


Subsequent simplification: default the launch list to **Viewable**, computed for the confirmed location, including supported estimates and nominal simulations with a viewing interval. Retain **All** for the full schedule and mark unavailable entries distinctly. Today's completed opportunities remain reviewable; older launches remain in All. Unsupported families, absent timing/geometry, paused launches and uniformly poor known viewing conditions do not enter Viewable. Hide Observations and Privacy links from ordinary navigation, detail actions and the footer; retain their direct pages and APIs without deleting data. Preserve an explicitly chosen filter, but migrate the old default-All preference to the new default.

The user's subsequent instruction authorizes a nominal prelaunch simulation when mission-specific route/profile evidence is absent. For explicitly supported launch families, lead with a simple direction and broad observer-local watch interval, labeled “Simulated estimate.” Use documented, versioned assumptions and observer geometry; detailed paths are optional. Keep assumptions and stricter source-admission diagnostics collapsed. This supersedes the prohibition on showing any numerical planning result without an admitted route/profile below, for this separate simulation feature only. Assumptions must not be represented as published or measured trajectories. Never hardcode an example direction/time as a launch prediction.

The scenario uses the scheduled launch time, not actual liftoff or sightings. A completed launch retains the same planning scenario. Exclude forecasts issued or retrieved after scheduled liftoff from the prelaunch weather summary; if no forecast was saved, say so briefly. The result is a newly calculated scenario, not a claim that this app saved a forecast before launch. Existing evidence-based classifications, alerts, empirical validation and release gates retain their original meaning.

Build a web application that combines a mission’s modeled ascent, the observer’s location, local sunlight, and cloud forecasts to answer when and where a launch may be visible. The core use case remains Cape Canaveral or Kennedy launches viewed from Maryland. This free-data revision supersedes v1.0 and its paid-access instructions. The original Word document is an older version; use this Markdown specification for implementation.

## Simple MVP flow

1. Read the launch time and mission from the free Launch Library API.
2. Use mission-specific SpaceX route information when published; otherwise use FAA/Space Force launch advisories to identify a coarse outbound corridor. Preserve whether this is a published path or an inferred corridor.
3. Combine the route with a documented representative ascent profile to estimate a broad viewing window and direction from the ZIP. If only a corridor is available, show route-based potential and omit unsupported timing/elevation details.
4. Overlay NWS cloud cover, local time, sunrise and twilight.
5. Show a clearly labeled approximate opportunity with the source, or explain the missing route information. Improve precision after real observations.

No full rocket flight simulator or paid trajectory feed is required. The basic question is whether conditions make a sighting plausible, not the rocket's exact position each second. A hazard corridor can support coarse screening; it does not establish a precise centerline, height or visibility boundary.

## Decisions made

**Hard constraint: $0 in mandatory API or data subscriptions. Flight Club is removed. No purchases, paid trials, automatic upgrades, or vendor negotiations are prerequisites.** Use an existing computer/server for the pilot; a new host or domain is not assumed free.

| Area | Implementation decision |
| --- | --- |
| Product | A forecast of possible launch-viewing opportunities by ZIP, with explicit evidence quality. Cape/Kennedy to Maryland remains the main test case. |
| Initial coverage | List Cape/Kennedy launches. Produce viewing estimates only when the public evidence supports them. Include mission-specific official viewing guidance from Wallops when available. Do not replace the Cape use case with Wallops-only coverage. |
| Location | US ZIP representative point confirmed by the user, optional GPS/manual coordinates. Maryland fixture-zip is a test fixture, not an assumed home. Up to 100 active locations. |
| Route and ascent | Combine free historical ascent profiles with current mission-specific public route evidence. Evaluate several plausible tracks; label all reconstructed tracks approximate. Official viewing guidance has its own evidence path. |
| Weather | NWS public API only for the required baseline. No Open-Meteo entitlement or paid cloud-layer service is required. |
| Advice | Worth a look, Possible, Unlikely, Not enough data. Historical-profile reconstructions are capped at Possible in the initial beta. No percentage probability. |
| Alerts | In-app notices and a downloadable calendar file are the free baseline. Email is optional only through an already available no-additional-cost mail service. No paid email dependency. |
| Build | Next.js, FastAPI, Python worker, PostgreSQL, Skyfield, local timezone data; Docker Compose on existing hardware. Store versioned evidence and templates locally. |
| First milestone | Demonstrate one free Cape-to-Maryland estimate and document its uncertainty before expanding the application. Missing paid credentials can never block this milestone. Missing usable public route evidence can. |

## What feasibility means here

Free schedule and weather APIs exist. Free historical rocket telemetry and official viewing maps also exist. These are useful ingredients, but no complete, reliable, free API of upcoming mission-specific 3D ascent trajectories was verified in this review.

The feasible free design therefore changes the product's precision: it offers conditional, approximate opportunities on supported routes, plus local clouds and sunlight. It cannot promise precise viewing times or reliable coverage for every Cape launch. Downloadable JSON datasets and public documents supplement the APIs; this is not an API-only trajectory solution.

Building deterministic geometry and weather integration is feasible. The ability to forecast useful Maryland sightings from reconstructed tracks remains a validation task. Historical altitude and speed do not uniquely determine latitude/longitude; a target orbit does not uniquely determine the flown ascent. An attractive simulated flight is not validation.

## Data contracts and dependency resolution

| Component | Free source and contract | Failure behavior |
| --- | --- | --- |
| Schedule [1] | Launch Library 2 production v2.3.0; cache centrally within the documented 15 unauthenticated requests/hour. Normalize ID, pad, vehicle, time precision, window, status and source time. | Cached schedule with age; suppress new positive notices when stale. |
| Historical profiles [2] | Download JSON from shahar603/Telemetry-Data. Preserve source URL, commit/hash, mission, stage, units, event labels and repository license. Analysed downrange is derived, not a surveyed 3D track. | Bundle verified snapshots. Never depend on the old hosted Launch Dashboard API being online. |
| Mission route evidence [3] | Prefer mission-specific SpaceX/operator pages with explicit direction or track. FAA NOTAMs and Space Launch Delta 45 airspace/marine advisories can supply additional coarse corridor evidence. Match mission, pad and launch attempt; retain document hash and publication time. | No route evidence, ambiguous mission association or unexplained dogleg means no reconstructed location forecast. Hazard zones are not centerline trajectories. |
| Official visibility guidance [4] | Match a NASA/operator visibility map or written viewing region to the exact mission. Preserve the source's timing and scope. | Show the original source link. No pixel-to-ZIP classification unless coordinates and boundary uncertainty have been verified. |
| Weather [5] | NWS /points/{lat},{lon}, then its returned forecastGridData URL. Read skyCover, valid intervals, updateTime, and visibility/weather fields when present. | Weather unavailable; retain independently valid schedule and geometry. No paid fallback. |
| Location and astronomy [6–9] | Census ZCTA coordinates; local timezonefinder/zoneinfo; Skyfield with bundled ephemeris. | Offer GPS/manual coordinates for ZIPs without a ZCTA. Unresolved zones or unsupported dates are explicit unavailable states. |
| Optional research source [10] | ISSC documents free reconstructed-flight exports containing telemetry and ground tracks. | Candidate only: programmatic access, reuse scope, accuracy and mission matching have not been validated. No dependency on it in the initial build. |

### Free trajectory replacement

Implement two primary evidence paths, with a coarse route-screening fallback:

1. **Official guidance:** a mission-specific published viewing region and timing, if provided. Combine its stated opportunity with local weather and sunlight. Do not invent an azimuth/elevation curve from a visibility map. Maps of safety zones do not qualify as visibility maps.
2. **Reconstructed ascent:** reusable historical profiles plus independently sourced current route evidence. For each candidate profile, build a WGS84 ground path and altitude/time series, then calculate what the observer would see. Display an interval and directional sector across the candidate set, not a single precise track.

Each profile needs vehicle variant, mission/orbit class, pad or compatible launch latitude, recovery configuration when relevant, stage identification, time origin, altitude datum, downrange definition and powered intervals. Missing metadata disqualifies production use. Older Falcon 9 variants can test the mathematics but cannot silently stand in for current Block 5 missions. Do not infer route solely from a Starlink name, orbital inclination or booster landing point.

Use documented simple ascent routes only in v1. Reject known/possible doglegs that the model cannot represent. Coarse direction or a hazard polygon alone is insufficient for timed location predictions. A future mission's route must be supported independently of the historical profile; the profile supplies ascent shape, not evidence of that mission's heading.

Create a versioned route registry with explicit approved source formats and deterministic parsers. New or changed source formats remain unsupported until tested. An agent may propose extracted parameters, but model-generated text is not route evidence. Structural ambiguity must yield Not enough data rather than an invented branch.

Start with one documented representative profile for a supported family and label it a low-confidence estimate; multiple profiles are an improvement, not a prerequisite to a prototype. When several profiles exist, display their spread without calling it a statistical confidence interval. Preserve the correlations within each track. If compatibility cannot be established, omit the numerical estimate and retain coarse route screening. A route-screening result must say that altitude and timed visibility are unresolved; it is not a confirmed sighting forecast.

**Coarse route screening:** when only an identifiable launch corridor is available, display its public source and whether the launch is a candidate for further viewing analysis. Do not assign Worth a look or an exact viewing window from the corridor alone. Weather and solar conditions remain useful as separately labeled information. This fallback does not require historical reconstruction.

### First engineering gate

Within an initial three-day technical investigation:

- Download and parse the free telemetry index, representative analysed series, event data and licenses.
- Identify compatible profiles and independent current route evidence for one Cape mission. Record which values are observed, derived or assumed.
- Run the observer geometry for Maryland and a location near the pad. Compare with an independent geometry implementation.
- Hold back a historical mission's profile to test generalization; do not validate a template against the same data used to construct it. Separate profile agreement from real sighting validation.
- Produce a supported approximate result or a concrete failure report. Do not purchase access or declare a schedule-only app to be the completed launch-visibility product.

This replaces the paid provisioning gate. A three-day investigation is a time box, not a promise that useful free route coverage will be proven in three days.

## Executable visibility rules

Use a versioned deterministic rule set, initially visibility_rules_v1_1. The thresholds below are product heuristics selected to make the beta executable; they are not measured detection probabilities. Remove the previous requirement to develop a calibrated Favorable classifier before shipping.

### Normalize and evaluate the track

Represent each reconstructed candidate as time since liftoff plus geodetic latitude, longitude and altitude, then convert to WGS84 Earth-fixed positions. Document all datum and unit conversions; do not treat downrange distance as longitude or a slant range. Align stage data to liftoff without mixing returning-booster telemetry with second-stage ascent.

Evaluate ascending stages through the first ascent burn; omit return burns, orbital passes, reentry and passive post-cutoff plume drift. Require source-backed powered intervals. Historical burn timings are approximate when applied to another mission and contribute to the displayed uncertainty.

Use five-second samples without bridging gaps longer than 15 seconds. Calculate observer-to-target east/north/up, true-north azimuth, geometric elevation, range and Earth occultation. A luminous candidate requires at least 20 seconds above the geometric horizon. Independently validate the coordinate mathematics; no rocket refraction correction in v1.

Compute observer solar elevation and target Earth shadow at each sample in consistent frames. Active engine emission can remain eligible in shadow. Sunlit-plume opportunity requires an active plume source; a sunlit point alone is insufficient.

For reconstructed tracks show the union of candidate windows, the range of maximum elevations, and the smallest valid directional sectors, with circular wrap handled at north. Report disagreement between tracks. Round time bounds outward to whole minutes and bearings outward to 15-degree sectors; actual source uncertainty may require wider ranges. Do not display a precise moving dot as live telemetry.

After a schedule slip recompute weather and illumination for every candidate. A route, vehicle or mission-profile change invalidates the selection. Official-guidance-only results display only the spatial/timing information the source actually provides.

### Decision order

| Step | Beta behavior |
| --- | --- |
| 1 Status | Hold, scrub, cancelled and completed override immediate advice. Reaching scheduled T0 does not prove liftoff. |
| 2 Evidence | No matching official guidance or admissible reconstructed family: Not enough data. Weather and pad distance alone never create visibility eligibility. |
| 3 Timing and completeness | Missing applicable viewing interval, source-backed emission interval for tracks, route support, weather coverage or fresh essential data: Not enough data for combined advice. Preserve independently valid information. |
| 4 Negative geometry | All complete admitted tracks below the horizon: Unlikely within the modeled envelope. Label that limitation. Incomplete tracks cannot establish a negative; being outside a published map is not automatically proof of invisibility. |
| 5 Weather | Poor weather during all supported viewing opportunities: Unlikely, with a cloud/haze reason. Evaluate a better continuous subinterval if present. |
| 6 Official guidance | Worth a look is allowed only when an applicable official source explicitly includes the observer's region and supplies a usable viewing interval, weather is clear and fresh, and the guidance remains applicable after timing changes. Otherwise Possible or Not enough data. Do not reinterpret a generic regional statement as an exact ZIP boundary. |
| 7 Reconstructed opportunity | At least one admissible luminous track segment with non-poor weather: Possible — approximate flight profile. State whether all modeled tracks agree. Initial beta never promotes a reconstruction to Worth a look. |

Sunrise, daylight and observer twilight are explanatory inputs, not universal visibility cutoffs. For reconstructed opportunities flag especially favorable modeled lighting when the same 60-second segment has elevation >=5 degrees, observer Sun <=-6 degrees and active engine/plume emission. This flag does not remove the Possible cap or establish calibrated brightness.

For a launch window evaluate endpoints, five-minute alternatives, solar transitions and weather-bin changes; refine changing outcomes to one minute. Display a conditional result when alternatives differ. A source's official guidance must be rechecked after substantial timing/profile changes; never transfer an old mission's visibility map to a new launch.

## Local time sunlight and weather

### Time and sunrise behavior

UTC is the storage and job clock. The selected observer point’s IANA zone is the display clock, even if the phone is traveling. Every event includes its local date, zone abbreviation, and UTC offset. Site time is secondary. Exact, window-only, date-only, and unknown launch times remain distinct. Date-only records never get a midnight countdown or an exact viewing reminder.

Use Skyfield with a pinned DE421 ephemeris for v1 and reject dates outside its supported range. Compute sunrise/sunset using the standard solar-center depression of about 0.833 degrees; twilight boundaries are −6, −12, and −18 degrees. Evaluate continuous geometric solar elevation throughout each observation interval; do not substitute the pad’s sunrise or a day/night API boolean. Twilight labels are explanatory, while the rule engine uses numeric elevation [8, 9].

Show sunrise and sunset at the observer, viewing start/end, and lighting changes within that window. Sunrise is not an automatic invisibility threshold. A ten-minute launch slip can move Maryland observation into daylight and change the advice. Polar no-rise/no-set conditions are valid null events. Use an unobstructed horizon; trees, terrain, and buildings are explicitly outside v1 geometry.

### Concrete weather rules

Normalize cloud cover to percent and visibility to meters. For each candidate interval, collect intersecting forecast bins; do not interpolate hourly cloud percentages into minute-precision claims. Evaluate the worst bin within the interval. Favor a qualifying continuous subinterval when one exists, and show its shorter duration. NWS skyCover is the required baseline; v1 operates in total-cloud mode. Optional future layer data may downgrade a result but cannot override a worse baseline.

| **Weather state** | **Rule for visibility_rules_v1_1** |
| --- | --- |
| Clear | Total cover ≤25%. If low/mid/high layers exist: low ≤20%, mid ≤40%, high ≤60%. Available near-surface visibility must be ≥10 km; absence is shown and does not mean infinite visibility. |
| Poor | Total cover ≥75%, or available low cloud ≥60%, or available surface visibility \<5 km, or explicit forecast fog. These are conservative obstruction flags, not a radiative-transfer model. |
| Mixed | All other fully covered forecasts. Conflicting fresh providers use the worse tier. Layers missing means total-only mode; total missing means weather unavailable. |
| Fresh | Near launch: successful fetch ≤60 minutes old; NWS updateTime ≤12 hours old and valid intervals cover the full candidate. Unknown source issue time makes the weather unsuitable for positive reminders. No required fallback provider. |
| Beyond coverage | List the launch and modeled geometry, but show “Weather not available yet.” No weather-based automatic positive reminder. |

Query weather at the observer. Atmospheric sightline cloud sampling and cloud optical depth are deferred; no claim of precise 3D obstruction is made. At low elevations a clear overhead forecast is especially uncertain, and reconstructed forecasts must disclose this limitation even when modeled elevation exceeds 5 degrees. Surface visibility is a haze indicator, never a maximum rocket range.

Invalidate assessments on changed time, actual liftoff, location, trajectory revision, weather snapshot, or ruleset. Store fetch time, source issue time when supplied, valid interval, missing flags, and input hashes separately so a fresh fetch cannot conceal old data.

## Architecture operations and alerts

### Small deployment

Run Next.js, FastAPI, one Python worker, and PostgreSQL in Docker Compose on an existing Linux computer/server; 2 vCPU and 4 GB RAM is an initial sizing assumption, not a hosting purchase. Use HTTPS, daily off-host database backups, health checks, and structured logs. PostgreSQL stores provider snapshots, assessments, subscriptions, and an outbox; Redis and Kubernetes are unnecessary for the pilot. Secrets stay server-side. The UI uses an SVG sky path, so map tiles are not a runtime dependency.

### Refresh and load limits

LL2: one shared poll every 30 minutes normally and every five minutes when a supported launch is within six hours. Cap requests at 12 per rolling hour across pagination and retries; prefer a single filtered supported-launch page near liftoff, postponing broad inventory paging. If more calls are needed, reduce scope or degrade freshness visibly; never upgrade to paid access. Never poll per user. Public unauthenticated documentation specifies 15 calls/hour [1].

Profiles: pin bundled snapshots and refresh only during a validated data update. Route evidence: cache per mission and check supported source pages every six hours, hourly within six hours of launch only when permitted; honor source limits and backoff. Parser failures invalidate unsupported changes. NWS: resolve point-to-grid once and revalidate daily; refresh distinct active cells hourly, then every 15 minutes within six hours of a supported launch. At 100 unique cells this is at most 400 grid requests/hour near launch, spread over the interval and reduced by shared-cell caching. NWS publishes no numeric guaranteed quota; honor backoff.

Compute assessments on changes and cache by launch, confirmed location, and input versions. A 15-minute track at five-second resolution is 181 samples per stage; 100 locations require about 18,100 evaluations per stage per revision. Benchmark this load before launch. Target p95 cached responses under two seconds. Show source age; do not market a five-minute schedule feed as real-time telemetry.

### Notification state machine

The mandatory free baseline is an in-app notification history plus downloadable ICS planning events. Calendar files are snapshots, not guaranteed automatic scrub/correction delivery; make that explicit. Background push, guaranteed email and SMS are outside the free baseline. An already provisioned no-additional-cost email service may be added behind an adapter, with verified address and consent.

Use quiet hours 10 p.m.–7 a.m. at the observer, with explicit overnight opt-in for active delivery channels. Offer T-24-hour planning and T-30-minute notices when a supported precise target exists. Default positive notices require Worth a look; users must opt into Possible notices and see the approximate-profile label. Window-only launches get conditional planning notices, not an exact viewing reminder.

Every time revision invalidates pending jobs. Correct previously notified users for >=5-minute shifts, changed local date, scrub or downgrade. Ordinary downgrades must persist ten minutes; inside T-30 minutes update immediately. Scrubs bypass coalescing. Do not release an expired notice.

Use PostgreSQL outbox uniqueness keys for subscription, launch attempt, notice type and material revision. Recheck consent/status under lock. In-app inserts are transactionally deduplicated. Optional external delivery must implement the selected provider's actual idempotency/reconciliation contract; never assume exactly-once email from a database lock alone. No automatic paid fallback or upgrade.

### Privacy and operational ownership

Store only the selected location required for a subscription; browsing locations can remain local. Exact GPS is optional. Unsubscribe disables pending notices immediately; delete subscription data within 24 hours. Keep redacted operational logs 30 days. Retain source URLs, dataset licenses and hashes alongside QA snapshots. A protected admin page can disable a mission, inspect freshness, and review failed ingestion without editing production rows manually.

## User stories and acceptance criteria

P0 stories below replace the previous draft’s user-story rules wherever they differ. These are build acceptance criteria, not claims that the application has been implemented.

### US 01 Choose my viewing location

As an observer, I want a ZIP-based location I can verify so the forecast represents my sky.

A leading-zero ZIP remains a string. Show the representative coordinates and a confirmation step. Missing ZCTA entries offer GPS or manual coordinates; changing the point invalidates the forecast.

### US 02 See my local time

As an observer, I want the viewing location’s date and time so travel or UTC cannot confuse me.

For Maryland, 2026-10-14 00:30 UTC displays October 13, 8:30 p.m. EDT, UTC−04:00, even on a phone set to California time. The local date controls list grouping.

### US 03 Handle clock changes

As a subscriber, I want reminders to survive daylight-saving transitions.

On November 1 2026, 05:30 and 06:30 UTC are distinct 1:30 a.m. New York times with different offsets. UTC jobs execute once each; a spring clock skip never creates a nonexistent local job.

### US 04 See sunrise and twilight

As an observer, I want sunrise, sunset, and sky brightness during observation.

Calculate events at the confirmed observer point for each local date in the interval. Show phase changes across sunrise; no-rise/no-set is a valid event state, not midnight.

### US 05 Recompute after a delay

As an observer, I want changed advice when a delay changes lighting.

Synthetic fixture: sunrise 7:10, launch 6:58, viewing T+8 gives 7:06. A ten-minute slip gives 7:16. Recalculate solar, weather, and rule inputs; do not automatically reject daylight.

### US 06 Distinguish engine and plume lighting

As an observer, I want nighttime and twilight opportunities assessed correctly.

At each sample evaluate observer Sun angle, Earth shadow at the target, and powered stage. Engine light can qualify in shadow. A sunlit target alone does not establish a visible plume.

### US 07 Get usable viewing guidance

As an observer, I want when, direction, movement, and elevation.

For reconstructed tracks show the envelope of T+ and local-time intervals, outward-rounded 15-degree bearing sectors, maximum-elevation range and an approximate sky band. Official guidance shows only source-supported information. Never substitute the pad bearing or imply a live measurement.

### US 08 Understand mission coverage

As an observer, I want to know when a mission cannot be modeled.

Require exact mission association for route evidence or official guidance and compatible historical profiles. Unknown route, insufficient profiles or unsupported dogleg returns Not enough data. An old visibility map and an orbital TLE cannot substitute for upcoming ascent evidence.

## User stories for conditions and reliability

### US 09 Check clouds at observation time

As an observer, I want weather matched to the viewing interval.

Use all overlapping forecast bins at the observer. A clear pad cannot override local overcast. Apply the concrete clear/mixed/poor thresholds, expose missing layers, and never multiply layer percentages.

### US 10 Interpret the recommendation

As an observer, I want an actionable but honest result.

Apply the revised decision order. Reconstructed forecasts never exceed Possible. A negative envelope is labeled model-dependent. Worth a look requires applicable official guidance with usable observer-region/timing evidence plus clear, fresh weather. No output claims a measured detection probability.

### US 11 Avoid stale forecasts

As an observer, I want outdated evidence labeled.

Fresh HTTP retrieval preserves the source issue timestamp. Check valid-time coverage and age. Failed route parsing or a stale essential feed disables new positive notices. Provider outage never triggers a paid service.

### US 12 Handle uncertain launch times

As an observer, I want windows and dates represented without fake precision.

Date-only means no exact countdown. Window-only means conditional alternatives. After scheduled T0 without confirmed liftoff, show Awaiting launch confirmation; never advance a fictional actual trajectory.

### US 13 Control overnight notices

As a subscriber, I want to choose whether dawn reminders interrupt quiet hours.

Setup previews local send times and offers an explicit overnight override. Suppressed notices are labeled and never sent after the viewing interval. Newly subscribed users receive no past milestone notices.

### US 14 Receive changes once

As a subscriber, I want corrections without repeated or obsolete messages.

Time revisions cancel old jobs; changes meeting the policy notify previously alerted subscribers. Concurrent workers preserve one logical in-app notice. Optional delivery adapters must pass provider-specific retry tests; calendar snapshots clearly disclose that later corrections require an updated download.

### US 15 Stop alerts and delete my data

As a subscriber, I want unsubscribe and deletion to work immediately.

A valid unsubscribe token cancels pending outbox work and blocks new sends. Deletion removes the subscription within 24 hours; delivery already accepted by the provider is not represented as recallable.

### US 16 Reproduce every assessment

As the operator, I want traceable calculations and controlled releases.

Each result records source IDs/hashes, UTC basis, coordinates, astronomy and ruleset versions, and reasons. Regression fixtures reproduce it. Admin can disable a bad mission; signed-in admin actions are logged.

## Delivery budget and acceptance gates

| Stage | Deliverable | Pass condition |
| --- | --- | --- |
| Initial three-day investigation | Free data and Cape-to-Maryland vertical slice | Parse real free profiles; identify compatible family and independent mission route evidence; compute a documented approximate envelope. Report a failed data gate honestly. |
| Specification | Schemas, evidence registry and reference fixtures | All 16 stories mapped to machine-readable contracts and tests; no paid credentials required. |
| Core build | Schedule, NWS weather, ZIP/timezone/solar and route adapters | Units, source timestamps, provenance, parser failures and free rate budgets tested. |
| Viewing UI | Official-guidance and reconstructed modes | Source quality visible; reconstruction cap, uncertainty, invalidation and unsupported states enforced. |
| Notices and deployment | In-app notices, ICS, optional existing email, existing host | No new billable dependencies; quiet hours, revisions, unsubscribe, backups and recovery tested. |
| Pilot | Prospective forecast archive and observer feedback | Real viewing attempts recorded with cloud conditions and unsuccessful/inconclusive outcomes. |

The earlier 20–25 engineering-day estimate assumed a ready-made trajectory feed and is withdrawn. Re-estimate implementation after the free-data investigation; neither elapsed agent runtime nor free trajectory coverage is currently proven. The app must not quietly replace missing route evidence with a distance circle to satisfy a deadline.

### Cost constraint

Required API/data subscription spend: **$0**. Use free public LL2/NWS services and bundled open datasets. Do not provision a new host, paid domain, email service, map provider or inference API. Existing hardware, connectivity and development tooling are prerequisites and may have existing costs; this is not a claim of zero electricity or labor cost. If no existing publicly reachable host is available, deliver a local app first.

### Release acceptance

Require a real free-data Cape/Maryland fixture, compatible historical profile set, independent current route evidence, and a separately labeled official-guidance fixture when that feature ships. Synthetic geometry fixtures are also necessary, but cannot satisfy the real-data gate. An independent geometry check must agree within 0.1 degree and Maryland sunrise/sunset within two minutes under the same convention; these tolerances measure code correctness, not trajectory or sighting accuracy.

Test all 16 stories, leading-zero ZIPs, UTC rollover, DST, sunlight changes, ambiguous route branches, variant mismatches, stage switches, missing emission intervals, hazard-polygon misuse, stale evidence, HTTP 403/429/timeouts and local notice concurrency. Distinguish failed, blocked and passed tests.

Run a 100-location load test with a two-stage 15-minute ascent and the full admitted candidate set. Target cached p95 under two seconds and no provider-budget overruns; do not quote single-track performance as an ensemble benchmark. Archive forecasts before launch; realized weather is not a substitute for the forecast that was available then.

Pilot observations should cover at least five launches and 30 labeled viewing attempts before considering stronger reconstructed recommendations. This is an evaluation milestone, not a calibrated statistical guarantee. Publish mission-coverage denominators, false positives, missed sightings and inconclusive cases. Lack of a recorded sighting is not automatically a negative. Preserve the Possible cap until evidence supports a documented rule change.

### Agentic execution

The agent can implement the software, download open snapshots and run offline tests without vendor procurement. It cannot guarantee new public route documents, interpret every arbitrary map correctly, or prove human sighting success without observations. Approved parsers run unattended; unfamiliar evidence fails closed. Keep an explicit support matrix rather than requiring a human to repair each upcoming launch silently.

Replace the previous implementation prompt's “authorized trajectory” prerequisite with “free compatible historical profiles plus independent mission-specific route evidence, or applicable official visibility guidance.” Separate the evidence modes in contracts and fixtures. Prohibit paid provider fallbacks and invented trajectories.

## Feasibility evidence and resolved decisions

### Checks performed on October 13, 2026

| Check | Observed result | Interpretation |
| --- | --- | --- |
| LL2 official documentation and prior endpoint test | Documentation specifies 15 free unauthenticated requests/hour; prior upcoming request returned HTTP 200. | Suitable schedule source within central caching limits. Not a numerical trajectory feed. |
| NWS documentation and prior point/grid tests | Public free API; point and grid requests previously returned HTTP 200 with cloud intervals and issue/valid times. | Suitable required weather source. |
| Telemetry-Data archive | Public index, repository license and Orbcomm OG2 analysed JSON downloaded with HTTP 200. The sample contains time, altitude, speed and derived downrange arrays. This older flight demonstrates accessibility, not compatibility with a current mission. Repository lists Unlicense. | A real free historical dataset, not future mission telemetry. Preserve license and provenance. |
| Hosted Launch Dashboard API | Sample request returned HTTP 502 in this environment. | Do not make this hosted endpoint a runtime dependency; cache downloadable source files. |
| NASA Wallops guidance | Official pages contain mission-specific visibility maps, including 2025 TOMEX+. | Free viewing guidance exists for selected missions. This does not establish Cape coverage. |
| Space Launch Delta 45 advisories | Search retrieved official mission hazard PDFs; direct homepage fetch returned 403. | Public route-related evidence exists, but unattended access and extraction are not validated. Do not bypass access restrictions or equate hazard polygons with flown tracks. |
| ISSC reconstructed exports | Documentation describes free telemetry/JSON/KML exports and says tracks are reconstructed. Direct programmatic page request returned 403. | Worth investigating as an optional free source; not yet a verified API or accuracy reference. |
| End-to-end free visibility model | Not implemented or validated in this review. | No claim that a Maryland sighting, route coverage or automatic extraction has been proven. |

### SpaceX and FAA source findings

SpaceX publishes mission information and a Falcon user guide containing sample mission profiles and timelines. The guide explicitly states that individual flight profiles differ. These samples can inform the approximate ascent model but are not mission-specific 3D telemetry [12].

FAA documentation describes launch NOTAMs as providing hazard-area location, lateral boundaries and active times [13]. Space Launch Delta 45 publishes Falcon 9 airspace PDFs with coordinate lists and mission-specific valid times; the public KF-3 example demonstrates machine-readable coordinates [14]. These are useful free route inputs. A new mission's matching document must still be obtained and parsed; a public PDF is not automatically a stable API.

### Rejected substitutions

- Flight Club is excluded by the user's no-paid-data constraint.
- Ordinary orbital elements describe orbit propagation, not the powered ascent; they cannot fill a missing ascent track by running the orbit backward.
- Hazard polygons are safety areas, not timed altitude/position samples.
- A launch's target inclination can admit different launch directions and does not encode doglegs.
- Static distance-to-pad rings cannot establish a distant Maryland viewing opportunity.
- A free consumer viewing site does not automatically provide an open API or reusable dataset.

The technical approach is now free-source-first and conditional on evidence. The remaining risk is whether supported public routes and compatible profiles provide enough useful Cape coverage, not whether the user will purchase a trajectory subscription.

### Source references

1. [Launch Library 2: free access and limits](https://thespacedevs.com/llapi)
2. [Telemetry-Data: historical JSON, methods and license](https://github.com/shahar603/Telemetry-Data); [Launch Dashboard API source](https://github.com/shahar603/Launch-Dashboard-API)
3. [Space Launch Delta 45: public launch advisories](https://www.patrick.spaceforce.mil/)
4. [NASA TOMEX+ mission viewing guidance](https://www.nasa.gov/blogs/wallops/2025/08/26/nasa-sounding-rocket-mission-targeting-aug-26-launch-attempt/)
5. [NWS API documentation](https://www.weather.gov/documentation/services-web-api)
6. [Census national ZCTA Gazetteer](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.2025.html)
7. [IANA timezone database](https://www.iana.org/time-zones)
8. [Skyfield almanac](https://rhodesmill.org/skyfield/almanac.html)
9. [USNO sunrise and twilight conventions](https://aa.usno.navy.mil/faq/RST_defs)
10. [ISSC reconstructed flight exports](https://issc.space/launch-data)
11. [CelesTrak: supplemental orbital elements](https://celestrak.org/NORAD/elements/supplemental/)

12. [SpaceX Falcon Payload User Guide: sample profiles and timelines](https://www.spacex.com/assets/media/falcon-users-guide-2025-05-09.pdf)
13. [FAA: launch/reentry NOTAM information](https://www.faa.gov/air_traffic/publications/atpubs/aip_html/chap7_section_6.html)
14. [Space Launch Delta 45: KF-3 airspace coordinates, October 2025](https://www.patrick.spaceforce.mil/Portals/14/4_%20Eastern%20Range%20Airspace%20%20KF-3%20Consolidated%2010-19%20Oct%202025.pdf)


## GitHub reuse audit — October 13, 2026

The build should reuse existing telemetry data, parsing approaches and astronomy libraries. A generic flight simulator is not required for the first approximate forecast. This audit inspected documentation, selected source files, GitHub metadata and sample data endpoints; it did not execute or certify entire applications.

| Project | Verified capability | Integration decision |
| --- | --- | --- |
| [Launch-Dashboard-API](https://github.com/shahar603/Launch-Dashboard-API) | MIT-licensed Node API. Its v2 schema contains time, altitude, velocity, derived downrange, stage and events; no per-sample latitude/longitude fields. Inspected storage code reads payloads from separately configured S3 storage. GitHub reports last push June 19, 2024. Hosted sample request returned 502 here. | Reuse its data concepts and adapters. Cloning the server does not supply its hosted database. Do not require its service to be online or provision AWS to use public JSON snapshots. |
| [Telemetry-Data](https://github.com/shahar603/Telemetry-Data) | Unlicense repository with archived webcast telemetry. Index, license and Orbcomm OG2 analysed JSON downloaded successfully. Sample has time, altitude, velocity and derived downrange arrays. GitHub reports last push January 24, 2020. | Selected bundled historical data source. Pin a commit and hash; verify stage, variant and profile applicability. Old data is useful reference material, not a current mission track. |
| [SpaceXtract](https://github.com/shahar603/SpaceXtract) | MIT-licensed Python/OpenCV extraction from local video or HLS streams, using configurable templates and regions. | Optional means to add newer profiles. Adapt to current webcast layouts and validate extracted numbers. Keep video OCR out of the required live request path. |
| [NOTAM-Mapper](https://github.com/ravi4ram/NOTAM-Mapper) | MIT-licensed Python parser and map generator; documented examples are ISRO-specific, with hardcoded map boundaries. GitHub reports last push November 26, 2020. | Adapt coordinate parsing for observed FAA/Space Force formats, with fixtures. It maps hazard zones; it does not supply altitude/time trajectories. |
| [R4yGM/SpaceXTelemetry-Api](https://github.com/R4yGM/SpaceXTelemetry-Api) | README directs users away from the defunct .cf domain to GitHub Pages. The Starlink-6 telemetry endpoint returned HTTP 200 and 821 records. GitHub reports last push June 12, 2021 and no detected repository license. | Additional accessible historical candidate, not selected for bundled redistribution until reuse permission is established. Do not mistake a latest.json filename for current mission coverage. |
| [RocketTraker](https://github.com/AstronomyLiveYt/RocketTraker) | Telescope-control project whose documented trajectory source is Flight Club. | Not a replacement for the excluded trajectory dependency. |
| [rocket-launch-visualizer](https://github.com/bradybridges/rocket-launch-visualizer) | Configurable gravity-turn simulator and SVG ascent visualization. | UI/model reference only; no verified mission-specific forecast feed. A generic simulated trajectory is not independent validation. |
| [Apogee](https://github.com/daxrpm/apogee) | Two-stage circular-LEO ascent simulator with FastAPI and a 3D frontend. Documentation describes planar ascent and equatorial propagation. | More simulation machinery than the MVP needs; not a source of actual upcoming mission paths. |
| [Launch Library 2](https://thespacedevs.com/llapi) | Free launch/mission/pad/status data with 15 unauthenticated requests/hour. | Selected schedule and mission-identification API. Pair with trajectory evidence rather than treating metadata as ascent samples. |

### Selected implementation order

1. Import a small, pinned free telemetry dataset directly into the Python backend. No need to deploy the old Node API or recreate its cloud storage.
2. Associate a published mission route or supported advisory with the scheduled launch. Adapt MIT-licensed NOTAM parsing where it helps; preserve hazard-vs-flightpath semantics.
3. Attach a documented representative ascent profile to the route and calculate approximate viewing geometry from the observer point. Show ranges and source quality.
4. Combine with NWS clouds and locally calculated sunlight/timezone. Do not add paid weather, maps or trajectory services.
5. Add SpaceXtract-based profile updates only if old profiles limit coverage. This is data maintenance, not a prerequisite to the first prototype.

A reusable end-to-end ZIP/cloud/launch-visibility application was not verified in this audit. The reusable components above reduce implementation work substantially, but upcoming-route availability and the quality of the approximate visibility estimate still need testing.
