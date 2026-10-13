# Deterministic rules: visibility_rules_v1_1
All boundaries below are normative beta heuristics, not detection probabilities. Clock is injected UTC. Spec choice clarifies unspecified boundaries without changing PRD thresholds.

## R-TIME: precision, clock and freshness
- Store UTC; observer IANA timezone controls display date/grouping, abbreviations and numeric offsets. UTC->local is unambiguous; local input with a repeated hour requires offset/fold, nonexistent local input rejects422. Schedule jobs in UTC only. Date-only retains source calendar basis; do not convert an arbitrary midnight into another date.
- Exact time supports countdown only before scheduled T0 and while scheduled status is fresh. At now>=net without confirmed liftoff show Awaiting launch confirmation; no moving rocket. Hold/scrub/cancel/completed/disabled override.
- Event dates are each observer-local date touched by [view_start,view_end). Sunrise/set at solar center -0.833 degrees; civil/nautical/astronomical boundaries -6/-12/-18. Numeric geometric Sun angle drives rules. Labels: Sun>=-0.833 daylight, [-6,-0.833) civil, [-12,-6) nautical, [-18,-12) astronomical, below-18 night. At equal threshold use brighter label. Rising/set events include direction. No crossing means null with no-rise/no-set state, not00:00. DE421 coverage read from pinned kernel; reject outside actual range rather than assuming date support.
- Schedule fetch fresh iff age<=15m when earliest possible T0-now<=6h, otherwise<=60m. Future fetched_at or issue time >now+5m is clock error; ignore for freshness and block positives. Source last_updated may be old if successfully revalidated unchanged; retain both timestamps.
- Weather fresh iff fetch age<=60m AND issue age<=12h AND entire evaluated interval covered. Exactly limits fresh; >limit stale. Unknown issue time blocks positive reminders/combined positive advice. Weather beyond validity -> unavailable, never nearest-bin extrapolation.
- Route is current only when approved parser/match, validity covers evaluated launch alternative, and last permitted successful check age<=2h near T0 (<=6h away), otherwise<=12h. Source-specific stricter terms prevail. Historical immutable profiles do not expire with age; current compatibility revision must remain valid. A source says unchanged via304 counts successful check but does not change issue time/hash.

## R-GEO: sampling, emission and uncertainty
Geodetic degrees, ellipsoidal meters -> WGS84 ECEF meters -> observer ENU. Azimuth atan2(E,N) modulo360, elevation atan2(U,hypot(E,N)), Euclidean slant range meters. Zenith bearing undefined, represented by absence of sector in internal calculation; never arbitrary zero. Check segment/Earth ellipsoid intersection excluding observer endpoint; occulted targets cannot qualify. No terrain/refraction correction.

Resample each admitted stage at t=0,5,... through covered first ascent burn, plus interval boundaries. Linear interpolation altitude/downrange only between same-stage valid samples separated <=15s; >15s splits coverage. Ground position comes from registry's independently supported geodesic route, not direct conversion of downrange to longitude. Never bridge stage switches or infer ignition/cutoff from smooth curves. Ascending first burn only; return/orbit/reentry/passive plume excluded.

Luminous segment = unocculted geometric elevation>0 AND source-backed active_engine or active_plume. At exactly0 not above horizon. Qualifies when continuous elapsed duration>=20s; 5 samples 0..20 represent20s, not25s. Count time differences, not sample count. Interpolate threshold crossing on a valid segment; never bridge missing data. Engine eligibility survives target shadow. Plume lighting descriptor requires active plume AND sunlit; sunlit/no emission fails. Conservative target shadow: use consistent Earth-fixed Sun vector transformed from ephemeris, test target-to-Sun ray against Earth ellipsoid (cylindrical point-Sun approximation); tangency treated shadow/uncertain. Record approximation, no brightness claim.

Especially favorable modeled lighting flag only if same continuous >=60s segment has elevation>=5, observer Sun<=-6 and active emission. Sunlight alone insufficient. Flag cannot promote beyond Possible. Shadow is explanatory for active engine; daylight never automatically rejects engine eligibility.

For ensemble: union qualifying intervals; retain per-candidate windows and disagreement. Do not fill gaps between union components. Max-elevation bounds are min/max of candidate maxima (complete candidates only, coverage limitations explicit). Circular bearings remove largest empty gap, tie choose lowest normalized start; separate disjoint temporal sectors if one span misrepresents movement. Round start down/end up minute, bearings floor/ceil15; preserve raw internal values. 359..1 -> sector345..15 wrapping north. State direction/movement from track, never pad bearing. If source uncertainty wider, use outward larger source bounds. Approximate sky band, no precise moving dot.

## R-WEATHER: interval algebra
All weather/view bins [start,end); equality at end/start gives no overlap. Reject zero/negative durations. Partition candidate opportunity at every source bin boundary; combine simultaneous bins using worst tier. Null total cloud -> unavailable even if layers exist. Do not interpolate hourly cloud into minute forecasts. Keep missing layer/visibility flags.

| Condition (in priority order) | Tier |
|---|---|
| Missing total/coverage, malformed units, unknown essential issue time | unavailable (or stale if age test fails) |
| total>=75 OR available low>=60 OR available visibility<5000m OR explicit fog true | poor |
| total<=25 AND each available layer low<=20, mid<=40, high<=60 AND (visibility missing OR visibility>=10000) | clear |
| Otherwise fully covered | mixed |

Exactly5000m is mixed unless another poor reason; exactly10000 may be clear. total25 clear,25.0001 mixed,75 poor. Missing visibility does not mean infinity; clear tier explicitly says haze unknown. Fog unknown disclosed, not asserted false. Layers missing means total-only mode; available layers may downgrade a clear total but never improve poor total. Mixed/present lower quality source cannot override poor fresh baseline. Observer grid only; no pad weather substitution and no maximum rocket range from surface visibility.

Retain all maximal continuous non-poor subintervals >=20s for reconstructed opportunities (official guidance likewise requires>=20s usable portion for combined positive advice). At least one clear qualifying subinterval can support official Worth a look even if excluded portions are poor; display only shorter interval plus full source interval and weather limitation. If all supported opportunities poor =>Unlikely; if better segments exist but all <20s =>Unlikely/weather_no_usable_segment. If any required part missing, full combined advice Not enough data unless a separately fully covered >=20s subset is explicitly selected as the narrowed supported opportunity; UI must disclose omitted unknown portion. Never infer all-poor from incomplete coverage.

## R-ADVICE: ordered table
| Order | Predicate | Result |
|---|---|---|
|1|disabled, hold, scrubbed, cancelled, completed; or scheduled T0 passed without confirmation|Not enough data plus distinct non-actionable display status; cancel positives|
|2|no exact approved official guidance or admissible reconstruction|Not enough data; hazard-only route_screening has no timed windows|
|3|missing applicable interval/emission/route/required coverage/fresh inputs; unknown launch status; unsupported time|Not enough data; independently valid geometry/weather/source facts retained|
|4|all admitted complete tracks remain at/below horizon over eligible modeled first burns|Unlikely, reason below_horizon_within_model; incomplete tracks cannot prove this|
|5|all supported opportunities poor or no>=20s non-poor opportunity|Unlikely with cloud/haze reason|
|6|official guidance explicitly includes observer region, applicable timing and >=20s clear fresh portion|Worth a look; if mixed covered portion Possible; uncertain membership Not enough data|
|7|>=20s admissible reconstructed luminous portion with non-poor covered weather|Possible; mandatory approximate-profile/low-elevation/cloud-sightline limitations|
|8|otherwise (e.g. no emission-supported horizon interval)|Not enough data with reason; do not create negative invisibility claim|

Official outside map !=invisible. Observations do not automatically alter forecast. No label implies calibrated probability. Clear weather cannot supply missing route evidence. Reconstructed result cannot use official label simply because source is an official hazard notice.

## R-WINDOW: alternatives and invalidation
For window-only launch evaluate closed T0 endpoints,5min offsets from start, solar transition instants translated through each candidate's viewing offsets, and weather boundary instants translated similarly. Bisect adjacent alternatives with different outcomes until separation<=60s; retain both boundary outcomes and mark remaining boundary uncertainty. Display conditional envelope and per-alternative reasons, never guaranteed exact interval. Cap operational window enumeration at48h; wider/date-only =>time_insufficient and no numerical reminder, preserve schedule. Do not merge incompatible profile alternatives as if one track.

A revision to launch time (any amount), actual liftoff, location, route/profile, weather hash, rules/astronomy/timezone data invalidates affected assessment/cache/jobs. Recompute solar and weather at new UTC, not just shift labels. Source-absolute official guidance invalidates on ANY time revision unless revalidated; explicit liftoff-relative source may remain valid if its stated profile/validity conditions still apply. Vehicle/route/profile changes invalidate selection, not just cache. Recompute posterior actual-liftoff view only on confirming source; archive prelaunch forecast unchanged.

## R-NOTIFY: deterministic state transitions
At creation only milestones with due_at>created_at may enqueue; exactly equal is not future. T-24h/T-30m relative to first UNROUNDED supported viewing start. Window-only conditional planning uses earliest possible viewing start, no precise30m notice; date/unknown none. Default threshold Worth a look; Possible requires explicit opt-in and reconstructed label. No positives if stale/incomplete/nonactionable. Expiry is min(view_end, next material invalidation); due_at<=now<expiry required.

| Event | Transaction/action |
|---|---|
| New eligible milestone | Insert outbox with unique subscription/attempt/type/material revision; content snapshots assessment hash |
| Any time revision | Cancel old pending/claimed unsent jobs; recompute future milestones; preserve delivered history |
| >=300s shift from LAST DELIVERED target, changed observer local date, scrub, or advice downgrade | For previously alerted subscriber create material correction; <300s with same local date has no correction unless another material change |
| Ordinary downgrade persists >=600s | Deliver one correction; a recovery before600s cancels debounce |
| now>=view_start-1800s OR scrub | Downgrade updates immediately; scrub bypasses coalescing even outside horizon |
| Quiet local time >=22:00 OR <07:00, no overnight opt-in | Mark in-app history suppressed_quiet; active delivery suppressed, no late catch-up |
| Unsubscribe/delete/disabled mission | Lock subscriber/launch then cancel pending; sender rechecks under same lock; committed disable before claim prevents send |
| now>=expires_at | expired; no retries or late positives |
| Transient local worker failure | rollback; retry1m,2m,4m,...cap15m, at most5 claims while unexpired |
| External provider timeout after possible acceptance | delivery_unknown; reconcile by actual provider key/status contract; never blind resend to claim exactly once |

Attempt changes only explicit new attempt after scrub; UUID reused by upstream does not conflate attempts. At-most-one logical in-app row guaranteed via unique constraint plus row locks; two concurrent workers lose conflict without second notice. Lock order subscription then launch then outbox; leases120s, restart reclaims expired claim only after rechecking expiry/revisions. Unique key survives retries; source weather fetches with unchanged semantic outcome do not create material revisions. Ordinary upgrades don't create correction unless subscriber opted-in at a future milestone; no notification oscillation. Corrections use quiet hours too; scrub bypasses coalescing, not user consent/quiet policy.

ICS download is snapshot: display limitation, UID stable per attempt/location, SEQUENCE revision; new file needed after change. No guaranteed automatic delivery. Optional email disabled until free existing entitlement, verified address and actual idempotency/reconciliation tests pass.
