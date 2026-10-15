# Traceability

Machine-readable authoritative mapping: [traceability.json](traceability.json); IDs validated offline. Every task has explicit commands and required evidence in [plans/tasks.json](../plans/tasks.json). Fixtures are executable vectors; they are not proof that application behavior passes. Requirements without scalar fixtures use named application/browser/operations scenarios below.

| Requirement/story | Tasks | Fixture IDs | Release gates |
|---|---|---|---|
| R001 | T01, T18, T19 | provider-403, provider-429, provider-503, provider-timeout | G-SPEC, G-SOFTWARE |
| R002 | T02, T06, T13 | zip-21201, zip-00601, zip-missing, zip-numeric, location-change | G-SPEC, G-SOFTWARE |
| R003 | T03, T04, T13 | date-only, window-only, awaiting-confirmation | G-SPEC, G-SOFTWARE |
| R004 | T02, T03, T05, T14 | reconstruction-cap, missing-route, hazard-only, dogleg, ambiguous-mission, variant-mismatch, missing-emission, incomplete-negative, complete-negative, poor-clouds, stale-feed, missing-weather, official-clear, official-mixed, outside-map, scrub, hold, completed, cancelled | G-SPEC, G-SOFTWARE, G-REAL |
| R005 | T01, T02, T05 | stage-switch, reconstruction-cap, missing-route, hazard-only, dogleg, ambiguous-mission, variant-mismatch, missing-emission, incomplete-negative, complete-negative, poor-clouds, stale-feed, missing-weather, official-clear, official-mixed, outside-map, scrub, hold, completed, cancelled, orbcomm-archive | G-SPEC, G-SOFTWARE, G-REAL |
| R006 | T02, T07 | cape-md-pad, cape-md-high, near-pad, equator-east, shadow-night, shadow-day, shadow-offset, engine-in-shadow, sunlit-inactive, active-sunlit-plume, duration-19.999, duration-20, duration-20.001, zero-horizon, gap-15, gap-15.001, stage-switch | G-SPEC, G-SOFTWARE, G-REAL |
| R007 | T07, T14 | north-wrap, round-outward | G-SPEC, G-SOFTWARE |
| R008 | T08, T13 | rollover, dst-fold-edt, dst-fold-est, dst-spring-before, dst-spring-after, dst-nonexistent, dst-ambiguous, sunrise-baltimore, polar-no-rise, twilight--18, twilight--12, twilight--6, twilight--0.833, twilight--18.001, sunrise-slip, shadow-night, shadow-day, shadow-offset, engine-in-shadow, sunlit-inactive, active-sunlit-plume, lighting-39, lighting-40, lighting-41, lighting-42 | G-SPEC, G-SOFTWARE |
| R009 | T03, T06, T09, T14 | cloud25, cloud25plus, cloud75, vis5000, vis4999, vis9999, vis10000, visibility-missing, layers-clear, layers-low60, layers-mid41, fog, total-missing, bin-boundary, bin-poor-overlap, better-subinterval, fresh-boundary, fetch-stale, issue-stale, issue-unknown, coverage-gap | G-SPEC, G-SOFTWARE |
| R010 | T09, T14 | lighting-39, lighting-40, lighting-41, lighting-42, reconstruction-cap, missing-route, hazard-only, dogleg, ambiguous-mission, variant-mismatch, missing-emission, incomplete-negative, complete-negative, poor-clouds, stale-feed, missing-weather, official-clear, official-mixed, outside-map, scrub, hold, completed, cancelled | G-SPEC, G-SOFTWARE, G-GUIDANCE |
| R011 | T03, T04, T08, T09, T11 | location-change, sunrise-slip, fresh-boundary, fetch-stale, issue-stale, issue-unknown, coverage-gap, reconstruction-cap, missing-route, hazard-only, dogleg, ambiguous-mission, variant-mismatch, missing-emission, incomplete-negative, complete-negative, poor-clouds, stale-feed, missing-weather, official-clear, official-mixed, outside-map, scrub, hold, completed, cancelled, date-only, window-only, awaiting-confirmation, provider-403, provider-429, provider-503, provider-timeout | G-SPEC, G-SOFTWARE |
| R012 | T15, T16, T17 | quiet-215959, quiet-220000, quiet-065959, quiet-070000, overnight-opt-in, no-past-milestone | G-SPEC, G-SOFTWARE |
| R013 | T15, T16 | correction-299, correction-300, date-correction, debounce-94, debounce-95, debounce-96, debounce-97, expired-notice, notification-race, unsubscribe-race, revision-race | G-SPEC, G-SOFTWARE |
| R014 | T10, T12, T15, T18 | unsubscribe-race, delete-24h, mission-disable | G-SPEC, G-SOFTWARE |
| R015 | T04, T06, T11, T20 | provider-403, provider-429, provider-503, provider-timeout, ll2-budget | G-SPEC, G-SOFTWARE |
| R016 | T01, T10, T11, T12, T17, T18, T20 | Task-specific integration/operational evidence (see commands in JSON) | G-SPEC, G-SOFTWARE |
| R017 | T13, T14, T15 | Task-specific integration/operational evidence (see commands in JSON) | G-SPEC, G-SOFTWARE |
| R018 | T01, T02, T05, T07, T08, T09, T10, T12, T19 | cape-md-pad, cape-md-high, near-pad, equator-east, sunrise-baltimore, reproducibility, mission-disable, orbcomm-archive | G-SPEC, G-SOFTWARE |
| R019 | T02, T03, T19 | cape-md-pad, cape-md-high, near-pad, equator-east, orbcomm-archive | G-SPEC, G-SOFTWARE, G-REAL |
| R020 | T19, T20 | Task-specific integration/operational evidence (see commands in JSON) | G-SPEC, G-SOFTWARE, G-REAL |
| R021 | T15, T21 | Task-specific integration/operational evidence (see commands in JSON) | G-SPEC, G-PILOT |
| R022 | T17 | Task-specific integration/operational evidence (see commands in JSON) | G-SPEC, G-SOFTWARE |
| R023 | T21 | Task-specific integration/operational evidence (see commands in JSON) | G-SPEC, G-SOFTWARE |
| R024 | T21 | Task-specific integration/operational evidence (see commands in JSON) | G-SPEC, G-SOFTWARE |
| US-01 | T02, T06, T13 | zip-21201, zip-00601, zip-missing, zip-numeric, location-change | G-SPEC, G-SOFTWARE |
| US-02 | T08, T13 | rollover, dst-fold-edt, dst-fold-est, dst-spring-before, dst-spring-after | G-SPEC, G-SOFTWARE |
| US-03 | T08, T13, T15, T16, T17 | rollover, dst-fold-edt, dst-fold-est, dst-spring-before, dst-spring-after, dst-nonexistent, dst-ambiguous | G-SPEC, G-SOFTWARE |
| US-04 | T08, T13 | sunrise-baltimore, polar-no-rise, twilight--18, twilight--12, twilight--6, twilight--0.833, twilight--18.001 | G-SPEC, G-SOFTWARE |
| US-05 | T03, T04, T08, T09, T11, T13 | sunrise-slip | G-SPEC, G-SOFTWARE |
| US-06 | T02, T07, T08, T13 | shadow-night, shadow-day, shadow-offset, engine-in-shadow, sunlit-inactive, active-sunlit-plume, lighting-39, lighting-40, lighting-41, lighting-42 | G-SPEC, G-SOFTWARE |
| US-07 | T02, T07, T14 | cape-md-pad, cape-md-high, near-pad, equator-east, duration-19.999, duration-20, duration-20.001, zero-horizon, gap-15, gap-15.001, north-wrap, round-outward | G-SPEC, G-SOFTWARE |
| US-08 | T01, T02, T03, T05, T14 | stage-switch, reconstruction-cap, missing-route, hazard-only, dogleg, ambiguous-mission, variant-mismatch, missing-emission, incomplete-negative, complete-negative, poor-clouds, stale-feed, missing-weather, official-clear, official-mixed, outside-map, scrub, hold, completed, cancelled, orbcomm-archive | G-SPEC, G-SOFTWARE |
| US-09 | T03, T06, T09, T14 | cloud25, cloud25plus, cloud75, vis5000, vis4999, vis9999, vis10000, visibility-missing, layers-clear, layers-low60, layers-mid41, fog, total-missing, bin-boundary, bin-poor-overlap, better-subinterval | G-SPEC, G-SOFTWARE |
| US-10 | T09, T14 | lighting-39, lighting-40, lighting-41, lighting-42, reconstruction-cap, missing-route, hazard-only, dogleg, ambiguous-mission, variant-mismatch, missing-emission, incomplete-negative, complete-negative, poor-clouds, stale-feed, missing-weather, official-clear, official-mixed, outside-map, scrub, hold, completed, cancelled | G-SPEC, G-SOFTWARE |
| US-11 | T03, T04, T06, T08, T09, T11, T20 | fresh-boundary, fetch-stale, issue-stale, issue-unknown, coverage-gap, reconstruction-cap, missing-route, hazard-only, dogleg, ambiguous-mission, variant-mismatch, missing-emission, incomplete-negative, complete-negative, poor-clouds, stale-feed, missing-weather, official-clear, official-mixed, outside-map, scrub, hold, completed, cancelled, provider-403, provider-429, provider-503, provider-timeout, ll2-budget | G-SPEC, G-SOFTWARE |
| US-12 | T03, T04, T08, T09, T11, T13 | date-only, window-only, awaiting-confirmation | G-SPEC, G-SOFTWARE |
| US-13 | T15, T16, T17 | quiet-215959, quiet-220000, quiet-065959, quiet-070000, overnight-opt-in, no-past-milestone | G-SPEC, G-SOFTWARE |
| US-14 | T15, T16 | correction-299, correction-300, date-correction, debounce-94, debounce-95, debounce-96, debounce-97, expired-notice, notification-race, revision-race | G-SPEC, G-SOFTWARE |
| US-15 | T10, T12, T15, T18 | unsubscribe-race, delete-24h | G-SPEC, G-SOFTWARE |
| US-16 | T01, T02, T05, T07, T08, T09, T10, T12, T19 | reproducibility, mission-disable | G-SPEC, G-SOFTWARE |

R021 depends on future real-world observations. R019/R020 depend on available public evidence and independent references, not a guarantee of sightings. R022 is optional, excluded when disabled; it cannot become a required paid service. R023 optional improvements cannot block baseline. R024 is a negative scope invariant checked in dependency/configuration and product review, not a request to implement excluded features.

## Executable component scenarios

- `api-contract`: R014, R016, R018; run `python tests/acceptance/run.py --suite api-contract`.
- `route-registry`: R004, R005; run `python tests/acceptance/run.py --suite route-registry`.
- `launch-windows`: R008, R011; run `python tests/acceptance/run.py --suite launch-windows`.
- `browser-journeys`: R002, R007, R008, R017; run `python tests/acceptance/run.py --suite browser-journeys`.
- `postgres-races`: R012, R013, R014; run `python tests/acceptance/run.py --suite postgres-races`.
- `calendar`: R012, R013; run `python tests/acceptance/run.py --suite calendar`.
- `worker-recovery`: R011, R015, R016; run `python tests/acceptance/run.py --suite worker-recovery`.
- `privacy-security`: R014, R016; run `python tests/acceptance/run.py --suite privacy-security`.
- `backup-restore`: R014, R016; run `python tests/acceptance/run.py --suite backup-restore`.
- `load-100`: R015, R020; run `python tests/acceptance/run.py --suite load-100`.
- `pilot-archive`: R021; run `python tests/acceptance/run.py --suite pilot-archive`.
- `scope-cost`: R001, R022, R023, R024; run `python tests/acceptance/run.py --suite scope-cost`.

## Application verification (2026-10-13)

The implemented task and evidence mapping is in [task-status.json](../evidence/build/task-status.json) and [BUILD_REPORT.md](../BUILD_REPORT.md). The original vectors and expected results are unchanged. The complete acceptance run passed 123 checks; required off-host recovery is the one failing check. Numerical, API, UI, concurrency and load evidence does not pass the real historical/upcoming/guidance or prospective pilot gates. Each machine-readable row now includes its actual passing/nonpassing cases and separate external gates.
