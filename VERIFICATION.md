# Specification delivery and verification

Created2026-10-13. Original `Launch_Visibility_PRD.md` preserved. This workspace contains specification/contracts/fixtures/scaffolding/plans; no full application has been implemented.

## Passed

- 9 offline specification checks: JSON Schemas, OpenAPI3.1, positive/negative examples, fixture/oracle integrity, raw provenance hashes, real provider payload contracts, requirements/stories/task DAG traceability, document links and harness self-tests.
- 10 harness self-tests, including missing implementation nonzero, unavailable provider exit2, provider schema drift exit1, geometry/time tolerance and wrong-output rejection.
- Live LL2, NWS point and returned NWS grid HTTP/schema smoke checks passed; exact report in `evidence/live-latest.json`. This is not an end-to-end forecast pass.
- 44 recorded source retrievals:43HTTP200, one404 for unneeded SpaceXtract setup.py candidate path. Actual pinned licenses, source files, telemetry index/series/events, LL2/OpenAPI, NWS, Census, USNO and hazard PDF archived and hashed.
- 15 JSON Schemas including external/fixture/candidate-track contracts;24 API operations;20 schema examples;112 scalar behavioral fixtures and12 component scenarios. All16 stories mapped,24 stable requirement groups,21 implementation tasks in7 plans.

## Failed as expected because implementation is excluded

`python tests/acceptance/run.py --suite all` exits1 with MISSING_IMPLEMENTATION. Application behavior is NOT passed. `python tools/release_gate.py --stage software` exits1 because G-SOFTWARE lacks implementation, while listing external evidence blockers separately. Pilot release likewise fails software and blocks observations. These failures are intentional safeguards, not waived tests.

## Blocked / not yet evidenced

- G-REAL: independently supported historical Cape route, fully qualified profile family, held-out mission and real Maryland envelope must be demonstrated in T02. Orbcomm archive is genuine but is not that demonstration.
- G-UPCOMING: actual upcoming Cape mission route/attempt matching and compatibility investigation remains T03; a missing route must be documented honestly.
- G-GUIDANCE: mission-specific official guidance exists, but exact observer region/timing classification fixture is not yet verified.
- G-PILOT: future5-launch/30-attempt observations; separate from software release/correctness.
- GNU make is absent on this Windows host; every implemented target's Python equivalent was run. Makefile recipes use real tabs. Future application commands intentionally await T01 implementation.

## Decisions and actual dependencies

Use Next.js/FastAPI/Python worker/PostgreSQL/Skyfield and local assets, existing hardware Compose, in-app notices and ICS. Mandatory data/API subscriptions$0, no paid fallback. Hazard corridor does not authorize timed geometry. Reconstructed advice capped at Possible. NOTAM-Mapper parser copying excluded due MIT-root/GPL-file conflict. Census21201 is39.294961,-76.622341; no assumed home. All source issue/fetch/valid times remain distinct.

Public route/profile metadata and future observations are actual evidence dependencies; payment is not. T01/T08 must provision pinned free runtime packages, timezone and DE421 assets; T18 needs an existing host and off-host backup destination for operational readiness. No new host/domain/email service is required; optional email stays disabled. Source availability may change and no arbitrary map parser is promised.

Start with `python tools/start_implementation.py` or `make start`, then execute T01 in `plans/01-vertical-slice.md`. Ordered implementation continues through T21. First build milestone: historical Cape-to-Maryland case, then upcoming mission attempt; it is not the stopping point.

Machine records: `evidence/verification.json`, raw command logs under `evidence/logs/`, `evidence/spec-check.json`, `evidence/live-latest.json`, `evidence/gates.json`. Complete generated file inventory: `GENERATED_FILES.md`.
