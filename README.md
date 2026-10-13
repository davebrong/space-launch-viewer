# Launchlight — Cape launch visibility

Answers one question: **might a Cape Canaveral / Kennedy launch be visible from my
Maryland ZIP code?** Enter a confirmed Maryland ZIP, and Launchlight combines the
public launch schedule, pad geometry, sky position, twilight and NWS weather to show
when and where in the sky to look, as SVG sky bands. No map service, no paid APIs.

> **Status: work in progress.** The app runs end to end with live public
> launch-schedule and NWS weather integrations, but the core visibility product is
> incomplete: automatic mission-specific source discovery and usable production ascent
> profiles are missing. The Dragon viewing fallback is an authored simulation, not a
> trajectory API. Off-host recovery and the human pilot (observed-sighting) gates are
> still blocked. See the [coverage audit](evidence/build/source-audit.json) and
> [build report](BUILD_REPORT.md) for verified results and remaining work.

Latest QA note (2026-10-13): nearby Cape/Kennedy planning uses the confirmed point and
pad across mission families, including date-only opportunities with time TBA. "Viewable"
covers today through 30 days. Live ZIP fl-zip and md-zip results differ. Distant mission
coverage is not complete. [Verification](evidence/build/nearby.json).

## What it does — and doesn't

- Uses a representative point for a confirmed Maryland ZIP (ZIPs kept as strings).
- Computes geometry with Skyfield on WGS84 using pinned local ephemeris and timezone data.
- Distinguishes published paths, hazard corridors, historical telemetry, reconstructed
  estimates, official guidance and observed sightings — and never blurs them.
- Visibility is capped at **Possible**. No guaranteed detection, no measured probability,
  no fabricated routes, no full rocket simulator. Missing data stays "unavailable".
- In-app alerts and ICS calendar export, an operator admin view and privacy deletion.

## Architecture

| Layer | Tech |
| --- | --- |
| UI | Next.js / strict TypeScript (`apps/web`), API types generated from OpenAPI |
| API | FastAPI / Python 3.12 (`services/api`) |
| Worker | One Python worker for ingestion and jobs (`services/worker`) |
| Domain | Pure, deterministic visibility rules (`packages/visibility`) |
| Storage | PostgreSQL with Alembic migrations and a transactional outbox |
| Deploy | Docker Compose + Caddy on existing Linux hardware (`ops/`) |

Details: [spec/architecture.md](spec/architecture.md).

## Repository layout

```
apps/web/          Next.js UI
services/          FastAPI API and worker
packages/          Visibility/astronomy domain logic
implementation/    Management CLI, checks, acceptance adapter
migrations/        Alembic migrations
ops/               Dockerfiles, Caddyfile, encrypted backup tooling
spec/              Requirements, rules, contracts, traceability (authoritative with the PRD)
plans/             Milestone plans and task list
tests/             Acceptance, application and browser tests plus fixtures
tools/             Spec checks, release gate, dev launcher, research tools
evidence/          Archived verification and gate evidence
docs/              Runbook and coverage notes
```

## Run locally

Requires Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js and Docker.

```sh
python tools/dev.py
```

Open **http://127.0.0.1:3007**. This installs locked dependencies when missing,
generates local credentials into `.env` (see [.env.example](.env.example)), starts a
dedicated PostgreSQL container, migrates, and starts the UI, API and worker. Ctrl+C
stops the processes it owns.

## Tests and checks

GNU make targets are listed; Python equivalents work on Windows without make.

| Command | Purpose |
| --- | --- |
| `make spec-check` / `python tools/check_spec.py` | Validate the specification |
| `make test-app` / `uv run --frozen pytest` | Application unit tests |
| `make lint` | Ruff + Next.js lint |
| `npm run test:browser` | Playwright browser/accessibility tests |
| `make acceptance` | Full acceptance suite via the application adapter |
| `make integration` / `python tests/acceptance/live.py` | Live source integration |
| `make release` / `python tools/release_gate.py` | Release gate |
| `make migrate`, `make backup`, `make restore-drill`, `make load` | Operations |

Software completeness and empirical validation are separate gates: empirical gates
are not marked passed without real observations. Missing off-host recovery remains a
failing required acceptance scenario.

## Documentation

- [Launch_Visibility_PRD.md](Launch_Visibility_PRD.md) — product requirements (v1.2, authoritative)
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) and [IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md) — milestones T01–T21
- [BUILD_REPORT.md](BUILD_REPORT.md) — executed checks and precise blockers
- [docs/runbook.md](docs/runbook.md) — deployment, operator access, privacy, source limits, recovery
- [VERIFICATION.md](VERIFICATION.md) and [GENERATED_FILES.md](GENERATED_FILES.md) — original spec verification
- [AGENTS.md](AGENTS.md) — instructions for coding agents

## Constraints

Mandatory API/data spend is $0. No paid APIs or maps, no inference APIs, no new
hosting. Source terms, robots rules, 403 and 429 responses are respected without
workarounds.
