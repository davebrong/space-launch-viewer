# Data ingestion and normalization

Run in dependency order. A blocked external input blocks its evidence gate, not unrelated software tasks. Record pass/fail/blocked separately; no task passes on an empty test suite.

## T04 — Schedule adapter, versioning and budgets

- Requirements: R003, R011, R015.
- Affected files/components: `services/api/adapters/ll2.py`, `services/worker/ingestion.py`, `data/supported-pads.json`.
- Prerequisites: T01.
- Acceptance criteria: Normalize actual external2.3 fields and precision/status enums; post-filter Cape pads; completed result from upcoming endpoint never treated as future. Cache central30m/5m, requests<=12 rolling/hour including pages/retries. Unknown status,403/429/timeouts and source changes tested.
- Verification commands:

```sh
python tests/acceptance/run.py --suite R015
python -m implementation.checks ingestion
```

- Completion evidence: `evidence/ll2-adapter-regression`, `evidence/rolling-budget-log`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T05 — Route registry and historical compatibility

- Requirements: R004, R005, R018.
- Affected files/components: `data/registry/`, `data/profiles/`, `services/api/adapters/routes.py`, `services/api/adapters/telemetry.py`.
- Prerequisites: T01, T02.
- Acceptance criteria: Approve only tested source formats; exact mission/pad/attempt+validity, distinguish hazards/path/guidance/observations; block ambiguous branches/doglegs/unknown datum/variant. Pin immutable assets/licenses; retain raw failures. Do not copy conflicted NOTAM parser. Stage switches and absent burns tested.
- Verification commands:

```sh
python tests/acceptance/run.py --suite R004
python tests/acceptance/run.py --suite parse_historical_archive
python -m implementation.checks route-registry
```

- Completion evidence: `evidence/registry-admission-report`, `evidence/source-hashes`, `evidence/license-record`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T06 — NWS and location normalization

- Requirements: R002, R009, R015.
- Affected files/components: `services/api/adapters/nws.py`, `services/api/adapters/census.py`, `data/gazetteer/`, `data/timezones/`.
- Prerequisites: T01.
- Acceptance criteria: Use actual pipe-delimited Census headers, preserve ZIP string, manual/GPS confirm and timezone. NWS points returned grid, ISO durations/units/fetch+issue/valid coverage, daily point and per-cell cache; missing total unsupported, missing visibility disclosed.100-location quota defined.
- Verification commands:

```sh
python tests/acceptance/run.py --suite R002
python tests/acceptance/run.py --suite R009
python -m implementation.checks normalization
```

- Completion evidence: `evidence/provider-normalization-report`, `evidence/gazetteer-license-hash`. Include timestamp, command/exit code, software/input hashes and raw logs.
