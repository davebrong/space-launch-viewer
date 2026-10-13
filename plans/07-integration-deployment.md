# Integration testing and deployment

Run in dependency order. A blocked external input blocks its evidence gate, not unrelated software tasks. Record pass/fail/blocked separately; no task passes on an empty test suite.

## T19 — Complete application release regression

- Requirements: R001, R018, R019, R020.
- Affected files/components: `tests/integration/`, `tests/browser/`, `evidence/`.
- Prerequisites: T03, T05, T09, T15, T18.
- Acceptance criteria: Run every112+fixture,16 stories, real independent geometry and sunrise, real historical Cape/profile/route gate and official guidance. Live unavailable =>blocked, not pass; no fake/mock transport release. Trace requirements and missing proof; preserve raw logs.
- Verification commands:

```sh
python tools/check_spec.py
python tests/acceptance/run.py --suite all
python tests/acceptance/live.py
python -m implementation.checks full-release
```

- Completion evidence: `evidence/G-SOFTWARE`, `evidence/full-regression-report`, `evidence/live-provider-report`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T20 — Full ensemble load and release recovery exercise

- Requirements: R015, R016, R020.
- Affected files/components: `tests/load/`, `ops/`, `evidence/load.json`.
- Prerequisites: T19.
- Acceptance criteria: Benchmark100 confirmed points, two-stage15min profiles at5s including all admitted correlated candidates. Measure cached p95<2s after warmup, uncached cost/memory, source budgets and queue lag. Report ensemble size/hardware/data; synthetic load cannot satisfy G-REAL. Re-run restore on deployment artifact.
- Verification commands:

```sh
python -m implementation.checks load-100
python -m implementation.checks release-recovery
python tools/release_gate.py
```

- Completion evidence: `evidence/ensemble-load-report`, `evidence/release-recovery-report`, `evidence/release-manifest`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T21 — Prospective pilot and coverage evaluation

- Requirements: R021, R023, R024.
- Affected files/components: `services/api/observations.py`, `evidence/pilot/`, `docs/coverage.md`.
- Prerequisites: T19.
- Acceptance criteria: Archive actual issued forecasts before launch and forecast-time weather; collect5 launches/30 labeled attempts including misses/inconclusive; publish supported/all-Cape denominators, false positives and missed sightings with evidence limitations. No feedback is not negative; Possible cap remains until separately justified rules change. Optional OCR/multiple profiles only after rights/validation.
- Verification commands:

```sh
python -m implementation.checks pilot-archive
python -m implementation.gates pilot
```

- Completion evidence: `evidence/G-PILOT`, `evidence/coverage-and-observation-report`. Include timestamp, command/exit code, software/input hashes and raw logs.
