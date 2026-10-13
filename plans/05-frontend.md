# Frontend and user journeys

Run in dependency order. A blocked external input blocks its evidence gate, not unrelated software tasks. Record pass/fail/blocked separately; no task passes on an empty test suite.

## T13 — Location and launch browsing

- Requirements: R002, R003, R008, R017.
- Affected files/components: `apps/web/app/`, `apps/web/components/LocationChooser.tsx`, `apps/web/components/LaunchList.tsx`.
- Prerequisites: T10.
- Acceptance criteria: Responsive location confirm/GPS/manual and local-date launch grouping; browser travel zone ignored, DST offsets explicit; exact/window/date/unknown and terminal states; all loading/empty/error/stale/unsupported states accessible.
- Verification commands:

```sh
python -m implementation.checks browser-location
python -m implementation.checks accessibility
```

- Completion evidence: `evidence/Playwright-location-report`, `evidence/mobile-screenshots`, `evidence/axe-report`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T14 — Viewing guidance, sources and conditions

- Requirements: R004, R007, R009, R010, R017.
- Affected files/components: `apps/web/app/launches/[id]/`, `apps/web/components/SkyBand.tsx`.
- Prerequisites: T09, T13.
- Acceptance criteria: SVG approximate union sky band+table; direction/movement/max elevation/source uncertainty; official-only fields source supported; hazard mode no timed path. Sunrise/transitions/weather bins/subintervals, missing/stale explanations and provenance visible.
- Verification commands:

```sh
python -m implementation.checks browser-guidance
python -m implementation.gates official-guidance
```

- Completion evidence: `evidence/responsive-detail-screenshots`, `evidence/G-GUIDANCE`, `evidence/browser-guidance-report`. Include timestamp, command/exit code, software/input hashes and raw logs.

## T15 — Subscriptions, history, privacy and observations UI

- Requirements: R012, R013, R014, R017, R021.
- Affected files/components: `apps/web/app/subscriptions/`, `apps/web/app/notifications/`, `apps/web/app/privacy/`, `apps/web/app/observations/`, `apps/web/app/admin/`.
- Prerequisites: T12, T13, T16, T17.
- Acceptance criteria: Preview local send times/suppression; opt-ins default off, calendar snapshot warning, corrections history, immediate unsubscribe/deletion and admin errors. Observation links archived forecast and allows inconclusive/not_attempted.
- Verification commands:

```sh
python -m implementation.checks browser-subscriptions
python -m implementation.checks accessibility
```

- Completion evidence: `evidence/consent-journey-report`, `evidence/observation-journey-report`. Include timestamp, command/exit code, software/input hashes and raw logs.
