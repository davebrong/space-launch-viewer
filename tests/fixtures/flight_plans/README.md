# Flight-plan source fixtures

Authored structural fixtures for the Next Spaceflight public page parser
(`services/api/adapters/flight_plans.py`) and the US Coast Guard NAVCEN SOLAR hazard
data parser (`services/api/adapters/navcen.py`). The Next Spaceflight fixtures
reproduce only the markup markers the parser relies on — the mission `<h1>`, `/launches/details/<n>/` index cards, the
"Launch Site" pad text and the "General Trajectory … Launching <Direction> … Stats"
sequence — as observed on 2026-10-13 in the retrieved pages listed in
`evidence/build/flight-plan-audit/retrievals.json`.

They are not copies of third-party pages. Downloaded source pages stay in the
git-ignored `.runtime/flight-plan-audit/` directory and are not redistributed.

Mission names, pads and directions here are test inputs. A fixture direction is not
evidence of how any real mission flies. The real Bandwagon-5 page's "Launching
Southeast" was checked separately against the retrieved page; see
`evidence/build/flight-plan-audit/`.

| File | Case |
|---|---|
| `index.html` | Partial upcoming index with Falcon 9, Vulcan, New Glenn and Dragon entries, plus a duplicated name for ambiguity tests. |
| `detail-template.html` | Detail page; tests substitute `{mission}`, `{pad}`, `{site}` and `{trajectory}`. |
| `detail-no-trajectory.html` | Matching page without a General Trajectory panel. |
| `solar.js` | NAVCEN SOLAR structure (`var <name> = {GeoJSON}`): a dated hazard notice plus near-pad `_rna` closure, an earlier attempt's notice with an invalid window, a Vulcan notice, a heading/hazard conflict case, a message ID reused across two missions, and a Pacific notice that must be ignored. Coordinates are invented test geometry. |
