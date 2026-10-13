# Free-data Cape-to-Maryland vertical slice

Run in dependency order. A blocked external input blocks its evidence gate, not unrelated software tasks. Record pass/fail/blocked separately; no task passes on an empty test suite.

## T01 — Bootstrap locked application and acceptance adapter

- Requirements: R001, R005, R016, R018.
- Affected files/components: `apps/web/`, `services/api/`, `services/worker/`, `packages/visibility/`, `pyproject.toml`, `package.json`, `compose.yaml`, `Makefile`, `implementation/acceptance_adapter.py`.
- Prerequisites: Specification baseline; no implementation prerequisites.
- Acceptance criteria: Inspect maintained dependency source/licenses; pin supported Python/Node/images and package lockfiles. Implement real dev/lint/test/migrate commands and JSON adapter protocol; missing code must fail. No app component performs paid calls.
- Verification commands:

```sh
python tools/check_spec.py
python tests/acceptance/run.py --suite R001
make lint
```

- Completion evidence: `evidence/dependency-locks`, `evidence/license-inventory`, `evidence/bootstrap-test-log`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T02 — Demonstrate real historical Cape-to-Maryland case

- Requirements: R002, R004, R005, R006, R018, R019.
- Affected files/components: `data/registry/`, `data/profiles/`, `packages/visibility/`, `tests/fixtures/real-cape/`.
- Prerequisites: T01.
- Acceptance criteria: Within three-day investigation parse pinned index/series/events/licenses; choose supported Cape historical mission and independently supported route. Document variant/stage/datum/emission compatibility, separate held-out mission from template creation; calculate Maryland and near-pad windows with independent geometry <=0.1deg. Publish uncertainty and data gate result. Synthetic positive/archived telemetry alone cannot pass.
- Verification commands:

```sh
python tests/acceptance/run.py --suite R019
python -m implementation.gates historical-cape
```

- Completion evidence: `evidence/historical-association-manifest`, `evidence/profile-compatibility`, `evidence/heldout-report`, `evidence/geometry-comparison`, `evidence/G-REAL`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T03 — Attempt upcoming Cape mission and re-estimate remaining build

- Requirements: R003, R004, R009, R011, R019.
- Affected files/components: `services/api/adapters/`, `data/registry/`, `evidence/upcoming-attempt.json`.
- Prerequisites: T02.
- Acceptance criteria: After historical demonstration (or explicit blocked historical gate), fetch one upcoming Cape launch within free budgets; exact route/profile association or honest unsupported report. Overlay NWS atfixture-zip and record uncertain source coverage. Record approach viability; continue T04-T21 even when route gate blocks release. No schedule-only completion.
- Verification commands:

```sh
python tests/acceptance/live.py
python -m implementation.gates upcoming-cape
```

- Completion evidence: `evidence/upcoming-attempt`, `evidence/coverage-matrix`, `evidence/reestimate`, `evidence/G-UPCOMING`. Include timestamp, command/exit code, software/input hashes and raw logs.
