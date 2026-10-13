# Visibility and astronomy

Run in dependency order. A blocked external input blocks its evidence gate, not unrelated software tasks. Record pass/fail/blocked separately; no task passes on an empty test suite.

## T07 — Geometry and correlated envelopes

- Requirements: R006, R007, R018.
- Affected files/components: `packages/visibility/geometry.py`, `packages/visibility/ensemble.py`.
- Prerequisites: T05.
- Acceptance criteria: WGS84 ECEF/ENU/occultation independently checked;5s samples with<=15s gaps; >=20s luminous duration and first burns only. Circular sectors/rounding/zenith/movement and complete-negative limits; no simulators/return burn/TLE.
- Verification commands:

```sh
python tests/acceptance/run.py --suite geometry
python tests/acceptance/run.py --suite R006
python tests/acceptance/run.py --suite R007
```

- Completion evidence: `evidence/PROJ-comparison`, `evidence/candidate-envelope-report`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T08 — Astronomy, clocks and window alternatives

- Requirements: R008, R011, R018.
- Affected files/components: `packages/visibility/astronomy.py`, `packages/visibility/time.py`, `data/ephemeris/`.
- Prerequisites: T06, T07.
- Acceptance criteria: Pin DE421 asset/hash/coverage, zone data and solar conventions; USNO within120s. Shadow/active emission, twilight, polar nulls, DST/folds/gaps, observer-local dates. Enumerate alternative times and one-minute transitions; slipped launch recomputes.
- Verification commands:

```sh
python tests/acceptance/run.py --suite R008
python tests/acceptance/run.py --suite R011
python -m implementation.checks launch-windows
```

- Completion evidence: `evidence/kernel-manifest`, `evidence/USNO-comparison`, `evidence/window-transition-report`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T09 — Combine weather and advice with provenance

- Requirements: R009, R010, R011, R018.
- Affected files/components: `packages/visibility/rules.py`, `packages/visibility/weather.py`, `services/api/assessment.py`.
- Prerequisites: T04, T06, T07, T08.
- Acceptance criteria: Implement ordered rules and exact thresholds, qualifying subintervals, freshness; recon<=Possible, official inclusion+time+clear/fresh required for Worth. Incomplete data cannot prove negative. Every input revision invalidates cache/jobs and archives old result.
- Verification commands:

```sh
python tests/acceptance/run.py --suite R010
python tests/acceptance/run.py --suite R009
python -m implementation.checks assessment-provenance
```

- Completion evidence: `evidence/decision-table-report`, `evidence/input-digest-reproduction`. Include timestamp, command/exit code, software/input hashes and raw logs.
