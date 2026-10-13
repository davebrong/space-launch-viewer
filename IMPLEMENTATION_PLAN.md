# Complete implementation plan
Start with `python tools/start_implementation.py` (or `make start`); it prints T01's exact instructions. This command starts the handoff by exposing the first task; it does not claim to launch an autonomous agent or implement the app.

Read AGENTS.md and spec/requirements.md first. v1.2 PRD is authoritative. Continue through EVERY required milestone. Initial three-day engineering investigation validates approach and records honest failure if public evidence is inadequate; it is not a stopping point. No paid credentials/procurement gates. Re-estimate effort after T03, not an invented 20–25 day promise.

## Ordered checklist
- [ ] T01 bootstrap, then T02 historical Cape-to-Maryland case FIRST, then T03 upcoming Cape attempt: [vertical slice](plans/01-vertical-slice.md).
- [ ] T04–T06 shared free source ingestion, registry/profiles, location/NWS: [ingestion](plans/02-ingestion.md).
- [ ] T07–T09 geometry, astronomy/time/windows and combined rules: [visibility](plans/03-visibility-astronomy.md).
- [ ] T10–T12 persistence/APIs, durable work/cache and security/privacy/admin: [backend](plans/04-backend-persistence.md).
- [ ] T13–T14 location/list/details; T15 follows notifications T16–T17: [frontend](plans/05-frontend.md).
- [ ] T16–T18 notices/ICS/metrics and deployment/recovery; return to complete T15: [notifications and operations](plans/06-notifications-operations.md).
- [ ] T19–T20 whole-application regression and ensemble performance/deployment: [integration](plans/07-integration-deployment.md).
- [ ] T21 archive prospective forecasts and conduct pilot; preserve cap: [pilot](plans/07-integration-deployment.md#t21--prospective-pilot-and-coverage-evaluation).

Explicit topological execution order: T01,T02,T03,T04,T05,T06,T07,T08,T09,T10,T11,T12,T13,T14,T16,T17,T15,T18,T19,T20,T21. Data blockers may permit dependency work against labeled fixtures, but never pass real-data gates. Each task's prerequisites in plans/tasks.json distinguish required integration from independent scaffolding work.

## Completion and gates
Specification phase completes when schemas/examples/reference integrity, OpenAPI, traceability and task graph pass. Missing application acceptance must fail clearly; live unavailable gates return exit2. An unavailable required source is not a test pass or a substitute result.

Entire application software is complete only when all required scope works across APIs/UI/ingestion/calculation/alerts/privacy/admin/ops, all16 stories pass, real historical Cape/Maryland evidence and separate official guidance fixture pass, upcoming attempt is documented,100-location full-ensemble cached p95<2s within provider budgets, existing hardware deployment and off-host restore verified, and evidence manifest/release gate passes. Optional email disabled is complete baseline; optional enabled email adds actual provider gates. Public host absent means local deployment; off-host backups still need an existing destination for production-readiness.

Software correctness does not establish empirical visibility reliability. G-PILOT requires >=5 launches and>=30 labeled viewing attempts with forecast-time archives and denominators; stronger advice requires a separate documented ruleset change. The first historical demo and a schedule-only UI never satisfy application completion. Preserve all blocked gates with concrete source/status/attempt and next actionable task, while completing independent work.
