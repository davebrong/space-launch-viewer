# Requirements baseline 1.0
Authority: ../Launch_Visibility_PRD.md v1.2. All IDs are stable; never renumber. Requirement groups below include the detailed normative clauses in rules.md, contracts/README.md and the preserved acceptance criteria. “Required” covers the complete application; optional capabilities cannot block the baseline. Excluded scope must not be used to bypass missing data.

| ID | Scope | Requirement |
|---|---|---|
| R001 | required | **Cost and scope.** Mandatory API/data spend is $0; preserve Cape/Kennedy-to-Maryland use case, existing hardware and free local deployment; no purchases, paid fallback or automatic upgrade. |
| R002 | required | **Location.** US ZIP representative point confirmation; optional GPS/manual fallback, coordinates, local IANA timezone; preserve leading zero; up to 100 active locations; fixture-zip is a fixture only. |
| R003 | required | **Schedule.** LL2 production v2.3.0; normalize identifiers, pad, variant, precision, window, status and timestamps; exact/window/date/unknown remain distinct; no fabricated liftoff. |
| R004 | required | **Evidence.** Exact mission/pad/attempt association; typed evidence and versioned route registry; deterministic approved parsers; hazard-only screening has no timed/elevation forecast; unknown branches/doglegs fail closed. |
| R005 | required | **Profiles and reuse.** Inspect and reuse suitable open source; pin historical snapshots, licenses, hashes and metadata including variant/class/recovery/stage/datum/downrange/time origin and powered intervals. Incompatible/unknown metadata cannot enter production. |
| R006 | required | **Geometry.** WGS84 ECEF/ENU, true azimuth, geometric elevation/range/occultation; 5 s samples, gaps <=15 s, >=20 s luminous visibility; only first ascent burns; no booster return, passive drift, refraction or full simulator. |
| R007 | required | **Ensemble.** Preserve correlated candidate tracks, union of windows, maximum elevation range, circular sectors and movement; round times outward to minute and bearings outward to 15 degrees; disclose disagreement and uncertainty. |
| R008 | required | **Astronomy/time.** Observer-local date and offset across DST; numeric solar elevation, Earth shadow, active emission; DE421 pinned/range checked; sunrise -0.833 degrees, twilight -6/-12/-18; no-rise/no-set null; daylight is explanatory. |
| R009 | required | **Weather.** NWS observer point/grid skyCover with intervals and issue/fetch times; percent/meters; worst overlapping bin or qualifying continuous subinterval; exact clear/mixed/poor/fresh thresholds; missing clouds unavailable, missing visibility disclosed. |
| R010 | required | **Advice.** Deterministic visibility_rules_v1_1 order, four advice labels, reconstruction <=Possible; official observer-region/time evidence required for Worth a look; no percentage probability, model-dependent negatives. |
| R011 | required | **Uncertainty/revisions.** Evaluate window alternatives and refine changing outcomes; invalidate on time/liftoff/location/route/weather/rules changes; stale essential data blocks combined positive advice and new positive notices. |
| R012 | required | **Free notices.** In-app history and downloadable ICS snapshots; precise-target T-24h/T-30m, conditional window planning; default Worth a look, Possible opt-in; quiet 22:00-07:00 with explicit override; no past milestones. |
| R013 | required | **Notice transitions.** Revision cancel/recompute; >=300 s shift, local-date change, scrub or persistent downgrade correct prior notices; 10 min coalesce except inside T-30 or scrub; transactional uniqueness and consent/status recheck, retries and expiry. |
| R014 | required | **Privacy/security.** Selected subscription location only; optional exact GPS; immediate unsubscribe, deletion <=24h; 30-day redacted logs, protected admin, audit actions, server secrets, HTTPS. |
| R015 | required | **Ingestion budgets.** Shared LL2 30m/5m polls with 12 requests rolling hour including pages/retries; route 6h/1h where permitted; NWS daily points and hourly/15m distinct-cell grids with backoff; no per-user schedule polling. |
| R016 | required | **Backend and operations.** Next.js/FastAPI/worker/PostgreSQL Compose, versioned evidence/templates locally; jobs/outbox/cache, health, daily off-host backup/recovery; no mandatory Redis/Kubernetes. |
| R017 | required | **UI.** Responsive accessible location/list/detail/sky-band/conditions/sources/subscriptions/notices/admin journeys; state distinctions, local dates, sunrise changes and source-supported precision. |
| R018 | required | **Reproducibility.** Record source URLs/hashes/licenses, coordinates, UTC, parser/astronomy/rules versions and reasons; independent geometry <=0.1 degree and sunrise/sunset <=120 s; every story has regression evidence. |
| R019 | required | **Engineering gate.** Initial three-day investigation: historical Cape/Maryland case FIRST, held-out profile, independent route, near-pad comparison, then upcoming mission attempt; failure report is not a passed real-data gate; continue whole build. |
| R020 | required | **Release and performance.** Real Cape fixture, compatible profile family, independent mission route, separate official-guidance fixture; all stories and failure modes; 100 locations x two-stage 15m full candidate set; cached p95 <2 s and no budget overrun. |
| R021 | required | **Empirical pilot.** Archive prospective forecasts and forecast-time weather before launch; collect >=5 launches and >=30 labeled attempts, clouds and unsuccessful/inconclusive outcomes; publish denominators/false positives/missed sightings; absence of sighting !=negative. |
| R022 | optional | **Email.** Only already available verified no-additional-cost email, explicit consent/verified address and provider-specific idempotency/reconciliation tests; disabled by default. |
| R023 | optional | **Research improvements.** Multiple representative profiles beyond initial one, modern video OCR and licensed ISSC exports; optional layers can downgrade, never improve worse baseline; not required dependencies. |
| R024 | excluded | **Non-goals.** No Flight Club, paid feeds, full flight simulator, orbital passes/reentry, terrain/building obstruction, 3D cloud transfer, live dot, SMS/required push, guaranteed email, calibrated probabilities or arbitrary map interpretation. |

## All user stories and original acceptance criteria

### US-01 Choose my viewing location
As an observer, I want a ZIP-based location I can verify so the forecast represents my sky.

A leading-zero ZIP remains a string. Show the representative coordinates and a confirmation step. Missing ZCTA entries offer GPS or manual coordinates; changing the point invalidates the forecast.

### US-02 See my local time
As an observer, I want the viewing location’s date and time so travel or UTC cannot confuse me.

For Maryland, 2026-10-14 00:30 UTC displays October 13, 8:30 p.m. EDT, UTC−04:00, even on a phone set to California time. The local date controls list grouping.

### US-03 Handle clock changes
As a subscriber, I want reminders to survive daylight-saving transitions.

On November 1 2026, 05:30 and 06:30 UTC are distinct 1:30 a.m. New York times with different offsets. UTC jobs execute once each; a spring clock skip never creates a nonexistent local job.

### US-04 See sunrise and twilight
As an observer, I want sunrise, sunset, and sky brightness during observation.

Calculate events at the confirmed observer point for each local date in the interval. Show phase changes across sunrise; no-rise/no-set is a valid event state, not midnight.

### US-05 Recompute after a delay
As an observer, I want changed advice when a delay changes lighting.

Synthetic fixture: sunrise 7:10, launch 6:58, viewing T+8 gives 7:06. A ten-minute slip gives 7:16. Recalculate solar, weather, and rule inputs; do not automatically reject daylight.

### US-06 Distinguish engine and plume lighting
As an observer, I want nighttime and twilight opportunities assessed correctly.

At each sample evaluate observer Sun angle, Earth shadow at the target, and powered stage. Engine light can qualify in shadow. A sunlit target alone does not establish a visible plume.

### US-07 Get usable viewing guidance
As an observer, I want when, direction, movement, and elevation.

For reconstructed tracks show the envelope of T+ and local-time intervals, outward-rounded 15-degree bearing sectors, maximum-elevation range and an approximate sky band. Official guidance shows only source-supported information. Never substitute the pad bearing or imply a live measurement.

### US-08 Understand mission coverage
As an observer, I want to know when a mission cannot be modeled.

Require exact mission association for route evidence or official guidance and compatible historical profiles. Unknown route, insufficient profiles or unsupported dogleg returns Not enough data. An old visibility map and an orbital TLE cannot substitute for upcoming ascent evidence.

### US-09 Check clouds at observation time
As an observer, I want weather matched to the viewing interval.

Use all overlapping forecast bins at the observer. A clear pad cannot override local overcast. Apply the concrete clear/mixed/poor thresholds, expose missing layers, and never multiply layer percentages.

### US-10 Interpret the recommendation
As an observer, I want an actionable but honest result.

Apply the revised decision order. Reconstructed forecasts never exceed Possible. A negative envelope is labeled model-dependent. Worth a look requires applicable official guidance with usable observer-region/timing evidence plus clear, fresh weather. No output claims a measured detection probability.

### US-11 Avoid stale forecasts
As an observer, I want outdated evidence labeled.

Fresh HTTP retrieval preserves the source issue timestamp. Check valid-time coverage and age. Failed route parsing or a stale essential feed disables new positive notices. Provider outage never triggers a paid service.

### US-12 Handle uncertain launch times
As an observer, I want windows and dates represented without fake precision.

Date-only means no exact countdown. Window-only means conditional alternatives. After scheduled T0 without confirmed liftoff, show Awaiting launch confirmation; never advance a fictional actual trajectory.

### US-13 Control overnight notices
As a subscriber, I want to choose whether dawn reminders interrupt quiet hours.

Setup previews local send times and offers an explicit overnight override. Suppressed notices are labeled and never sent after the viewing interval. Newly subscribed users receive no past milestone notices.

### US-14 Receive changes once
As a subscriber, I want corrections without repeated or obsolete messages.

Time revisions cancel old jobs; changes meeting the policy notify previously alerted subscribers. Concurrent workers preserve one logical in-app notice. Optional delivery adapters must pass provider-specific retry tests; calendar snapshots clearly disclose that later corrections require an updated download.

### US-15 Stop alerts and delete my data
As a subscriber, I want unsubscribe and deletion to work immediately.

A valid unsubscribe token cancels pending outbox work and blocks new sends. Deletion removes the subscription within 24 hours; delivery already accepted by the provider is not represented as recallable.

### US-16 Reproduce every assessment
As the operator, I want traceable calculations and controlled releases.

Each result records source IDs/hashes, UTC basis, coordinates, astronomy and ruleset versions, and reasons. Regression fixtures reproduce it. Admin can disable a bad mission; signed-in admin actions are logged.

## Completeness versus empirical validity
G-SPEC verifies this specification only. G-SOFTWARE requires all baseline software tests and operational evidence. G-REAL requires a supported real historical Cape/Maryland calculation and an independently evidenced route; G-UPCOMING records a real upcoming attempt, including an honest unsupported result. G-GUIDANCE validates the official mode. G-PILOT needs future observation evidence and is distinct from correctness of code. Beta software release requires G-SOFTWARE, G-REAL and G-GUIDANCE; pilot initiation can precede G-PILOT. Stronger reconstructed advice requires a separately reviewed ruleset after G-PILOT, never an automatic promotion after 30 records.
