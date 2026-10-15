# Launch visibility agent instructions
Read Launch_Visibility_PRD.md (v1.2, authoritative), IMPLEMENTATION_PLAN.md and spec/ before implementation. Preserve existing files and user changes. This repository currently supplies a specification and test scaffold, not an application.

Purpose: answer whether a Cape Canaveral/Kennedy launch may be visible from a confirmed Maryland ZIP representative point. Cover all 16 stories and all milestones. Continue through EVERY implementation milestone; the historical vertical slice is an approach gate, never the stopping point. If a data-dependent task blocks, record the evidence, continue all independent software tasks, and leave the affected release gate blocked. Never claim a schedule-only app is complete.

Architecture: Next.js/TypeScript UI; FastAPI/Python service and one Python worker; PostgreSQL with transactional outbox; Skyfield, WGS84, pinned local ephemeris/timezone data; Docker Compose on existing Linux hardware. SVG sky bands, no map service. See spec/architecture.md for ownership and storage.

Conventions: Python 3.11+ with type hints, UTC-aware datetimes and explicit unit suffixes; strict TypeScript, generated API types; snake_case JSON; immutable versioned inputs and pure deterministic rule functions with injected clocks. No NaN/Infinity, no silent unit conversions, no network in calculation functions. UTC jobs, observer IANA display zone. Decimal ZIP strings preserve zeroes. Use migrations, parameterized SQL, request IDs, structured redacted logs, semantic revisions. The repository is public: committed evidence, logs and docs must not contain absolute local paths, usernames, hostnames, emails, IP addresses or cloud project/billing IDs; write `<repo>`/`<home>` placeholders and keep operator settings in gitignored `.runtime/`. Pin actual supported package/image versions and hashes during T01; do not invent lockfiles. No application code is required for this specification task.

Commands (Python equivalents work on Windows without make):
- python -m pip install -r requirements-spec.txt
- make spec-check / python tools/check_spec.py
- make acceptance / python tests/acceptance/run.py --suite all
- make integration / python tests/acceptance/live.py
- make release / python tools/release_gate.py
- make start / python tools/start_implementation.py
Future build: make dev, make test-app, make lint, make migrate, make backup, make restore-drill, make load. T01 must implement these real commands, not no-op stubs.

Constraints: mandatory API/data spend $0. No paid APIs, trials requiring payment, automatic upgrades, Flight Club, paid maps, inference APIs or new hosting/domain purchases. Inspect existing open source before replacement. No full rocket simulator, TLE back-propagation, fabricated route, hazard-centerline inference, guaranteed detection or measured probability. Missing data stays unavailable. Preserve distinctions among published path, hazard corridor, historical telemetry, reconstructed estimate, official guidance and observed sighting.

External dependency reports are required only for actual failed/unavailable inputs: specific URL/status/time; missing route/compatibility/emission metadata; source permission/license conflict; inaccessible existing host/backup destination; optional mail adapter's unverified free entitlement; prospective human observations. Record attempted retrieval and affected gate in evidence/gates.json. Missing paid credentials are never a dependency. Do not repeatedly ask routine decisions; document assumptions. Respect 403, robots/source terms and 429 without bypasses. New document formats remain unsupported until parser fixtures pass.

Definition of done: all required requirements and stories trace to passing behavior/integration/UI/load/security/recovery checks; real historical Cape/Maryland gate and upcoming attempt documented; supported source matrix published; in-app alerts and ICS, admin, privacy deletion and existing-hardware deployment work; no mandatory recurring service bill; evidence archived. Software completeness and empirical validation are separate. Pilot five launches/30 labeled attempts is required before considering stronger reconstruction advice; keep Possible cap. Do not mark empirical gates passed without observations. Keep verification reports and exact command outputs, including failures and blocked gates.
