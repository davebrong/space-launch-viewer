# Runnable acceptance contract
This is a specification scaffold, NOT a reference implementation of the application. Run offline spec checks with `python tools/check_spec.py`. Run future application behavior with `python tests/acceptance/run.py --suite all`; missing adapter exits1 MISSING_IMPLEMENTATION. Never replace this with skips or a fake adapter returning fixture.expected.

T01 creates `implementation/acceptance_adapter.py` invoking real application modules and isolated database/browser components. Configure:

```powershell
$env:LV_ACCEPTANCE_COMMAND='[".venv/Scripts/python.exe","-m","implementation.acceptance_adapter"]'
python tests/acceptance/run.py --suite all
```

Linux: `export LV_ACCEPTANCE_COMMAND='[".venv/bin/python","-m","implementation.acceptance_adapter"]'`.

One process per case; stdin is one JSON object `{ "protocol_version":1, "operation":"weather_tier", "input":{...} }` followed by newline. Output is ONE JSON object on stdout, diagnostics stderr; exit0 only successful operation. A domain rejection such as invalid ZIP is a successful operation with `error` code; unexpected failure nonzero. Timeout90s default; operational scenarios allow900s. Adapter cannot read expected fixtures, reference generator or report files to manufacture answers. Runner intentionally sends neither fixture ID nor expected/oracle fields. Injectable clocks/providers are permitted in offline tests, but concurrency must use actual PostgreSQL transactions and browser scenarios actual UI. Public-provider integration separated.

[operations.json](operations.json) inventories all scalar operation inputs/assertions; exact typed vectors in `../fixtures/v1/cases.json` define the conformance examples. A missing optional input in one vector is genuinely absent; do not use another test's input values. `advice` operation inputs are PRECOMPUTED rule facts for unit tests; whole-pipeline/scenario tests must independently derive those facts from normalized models. False/0/null have distinct meanings. Output may contain additional diagnostic fields; expected fields must match. Geometry tolerance0.1degree,1meter; astronomy UTC tolerance120seconds; other fields exact. Circular azimuth delta uses shortest arc.

Scenario operation receives scenario name and ordered steps from [scenarios.json](scenarios.json); it must execute them against real isolated components and return measured counters/results, saving raw evidence under evidence/. Duration-max fields report the required service objective only after measured<=objective; raw actual values must accompany reports. `load-100` must provide ensemble_size, input manifest and raw request timings in evidence; a single-track run does not pass. Actual prospective pilot dataset uses a separate release gate, not the synthetic archive-flow scenario.

Select a story/requirement/operation/scenario with `--suite US-14`, `--suite R009`, `--suite geometry`, `--suite postgres-races`. Empty selection fails. Live integration: `python tests/acceptance/live.py` exits0 for actual HTTP/schema success,1 provider contract failure,2 external access blocked. It performs one LL2 and point+grid NWS requests, no paid credentials/retries. Sequential smoke runs keep a local request ledger; production concurrency uses DB budget. Do not run live probes in ordinary offline tests. A200 missing required fields fails;403/429/network unavailable blocks. Smoke success is neither route proof nor app integration.

Planned `python -m implementation.checks NAME` commands are interfaces to be implemented in T01 and later tasks: dispatch the corresponding scenario or additional named application tests, preserve raw evidence and exit nonzero if absent. `implementation.gates historical-cape/upcoming-cape/official-guidance/pilot` validates actual evidence manifests with source hashes and review; synthetic fixtures cannot satisfy these gates. Never implement a dispatcher that exits0 for unknown names. `tools/release_gate.py` audits release report presence and pass/fail/blocked separation; human/evidence review remains necessary, not just editing status flags.

The complete planned check-name dispatch table is [checks.json](checks.json). Implement it in T01; each alias must run all listed suites. Add focused assertions required by its task (e.g. browser subscription journey), not only broad smoke checks.

Release manifests: `evidence/releases/G-REAL.json` etc contain `reviewed_input_manifest` pointing to a real file plus nonempty `checks` entries with `command`, `exit_code`, `status`, `artifact_path`, `sha256`. Source manifests include immutable URLs, hashes, roles (training/heldout), exact mission/attempt association and reviewer rationale. Do not pass by editing gate status; command evidence is required. Software release checks G-SPEC/G-SOFTWARE/G-REAL/G-UPCOMING/G-GUIDANCE; `--stage pilot` additionally requires G-PILOT.
