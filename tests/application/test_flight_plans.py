"""Mission flight-plan discovery, evidence semantics and heading-based clear-sky planning."""

from __future__ import annotations

import json
from datetime import timedelta
from uuid import uuid4

import httpx
import jsonschema
import pytest
from sqlalchemy import func, select

from packages.visibility.common import point, stamp
from packages.visibility.planning import calculate_plan, usable_heading
from services.api import db
from services.api.adapters import navcen
from services.api.adapters.flight_plans import mission_key, parse_heading, parse_index, sector
from services.api.flight_plans import KEY, coverage, fingerprint, read_many
from services.api.main import CONTRACT
from services.api.opportunities import summarize
from services.worker.flight_plans import refresh_flight_plans
from tests.application import support as s

FIXTURES = s.ROOT / "tests/fixtures/flight_plans"
INDEX = (FIXTURES / "index.html").read_text(encoding="utf-8")
TEMPLATE = (FIXTURES / "detail-template.html").read_text(encoding="utf-8")
SOLAR = (FIXTURES / "solar.js").read_text(encoding="utf-8")
CAPE = "Cape Canaveral SFS, Florida, USA"
MARYLAND = {"point": point(39.4, -77.2), "timezone": "America/New_York"}  # ZIP md-zip area
FLORIDA = {"point": point(29.0, -81.0), "timezone": "America/New_York"}  # ZIP fl-zip area


def page(mission: str, pad: str = "SLC-40", direction: str | None = "Southeast", site: str = CAPE) -> str:
    trajectory = f"<p>E</p><p>S</p><p>Launching</p><p>{direction}</p>" if direction else ""
    html = TEMPLATE
    for name, value in (("mission", mission), ("pad", pad), ("site", site), ("trajectory", trajectory)):
        html = html.replace("{" + name + "}", value)
    return html


def launch(name: str, pad_name: str = "Space Launch Complex 40", **changes) -> dict:
    return {
        "id": str(uuid4()),
        "name": name,
        "pad_id": "80",
        "pad_name": pad_name,
        "pad_point": point(28.5618, -80.5772),
        "vehicle_variant": "Falcon 9 Block 5",
        "mission_class": "Low Earth Orbit",
        "time_precision": "exact",
        "net": stamp(s.AT + timedelta(days=6)),
        "window": None,
        "date_label": None,
        "actual_liftoff": None,
        "status": "scheduled",
        "disabled": False,
        **changes,
    }


def heading_record(direction: str, state: str = "found") -> dict:
    return {
        "state": state,
        "evidence": [
            {
                "evidence_type": "departure_heading",
                "source_name": "Next Spaceflight",
                "source_url": "https://nextspaceflight.com/launches/details/9001/",
                "source_sha256": "b" * 64,
                "fetched_at": stamp(s.AT),
                "parser_version": "test",
                "departure_direction": direction,
                "departure_sector_deg": sector(direction),
                "trajectory_available": False,
                "note": "test",
            }
        ],
    }


# Source parsing -------------------------------------------------------------


def test_parser_reads_mission_specific_headings_across_vehicle_families():
    cases = (
        ("Falcon 9 Block 5 | Fixture Rideshare-5 (Dedicated Rideshare)", "Space Launch Complex 40", "SLC-40", "Southeast", "southeast"),
        ("Vulcan VC4S | USSF-9999", "Space Launch Complex 41", "SLC-41", "East", "east"),
        ("New Glenn | Fixture Lander Demo", "Launch Complex 36", "LC-36", "Northeast", "northeast"),
        ("Falcon 9 Block 5 | Dragon CRS-2 SpX-99", "Launch Complex 39A", "LC-39A", "Northeast", "northeast"),
    )
    for name, pad_name, pad, word, expected in cases:
        evidence = parse_heading(page(name.split(" | ")[1].split(" (")[0], pad, word), launch(name, pad_name))
        assert evidence["evidence_type"] == "departure_heading"
        assert evidence["departure_direction"] == expected
        assert evidence["trajectory_available"] is False
        assert "calculated separately" in evidence["note"]
    # Quadrant-level: the source's numeric field has only shown 45 or 135.
    assert sector("southeast") == {"start_deg": 90, "end_deg": 180}
    assert sector("north") == {"start_deg": 315, "end_deg": 45}
    embedded = page("Fixture Rideshare-5").replace("</main>", r'<script>push("{\"heading\":45}")</script></main>')
    with pytest.raises(ValueError, match="INCONSISTENT_PUBLISHED_HEADING"):
        parse_heading(embedded, launch("Falcon 9 Block 5 | Fixture Rideshare-5"))


def test_parser_rejects_wrong_or_unsupported_association():
    rideshare = launch("Falcon 9 Block 5 | Fixture Rideshare-5")
    failures = (
        (page("Some Other Mission"), "FLIGHT_PLAN_MISSION_MISMATCH"),
        (page("Fixture Rideshare-5", pad="SLC-41"), "FLIGHT_PLAN_PAD_MISMATCH"),
        (page("Fixture Rideshare-5", site="Vandenberg SFB, California, USA"), "FLIGHT_PLAN_LOCATION_MISMATCH"),
        (page("Fixture Rideshare-5", direction=None), "NO_PUBLISHED_HEADING"),
        (page("Fixture Rideshare-5", direction="Retrograde"), "UNSUPPORTED_HEADING_FORMAT"),
        (page("Fixture Rideshare-5", direction="East</p><p>Launching</p><p>South"), "AMBIGUOUS_PUBLISHED_HEADING"),
        ((FIXTURES / "detail-no-trajectory.html").read_text(encoding="utf-8"), "FLIGHT_PLAN_MISSION_MISMATCH"),
    )
    for html, code in failures:
        with pytest.raises(ValueError, match=code):
            parse_heading(html, rideshare)
    lander = launch("New Glenn | Fixture Lander Demo", "Launch Complex 36")
    with pytest.raises(ValueError, match="NO_PUBLISHED_HEADING"):
        parse_heading((FIXTURES / "detail-no-trajectory.html").read_text(encoding="utf-8"), lander)


def test_index_parser_and_explicit_name_equivalence():
    entries = parse_index(INDEX)
    assert len(entries) == 6 and all(e["url"].startswith("https://nextspaceflight.com/launches/details/") for e in entries)
    assert mission_key("Falcon 9 Block 5 | Dragon CRS-2 SpX-99") == mission_key("CRS SpX-99")
    assert mission_key("Falcon 9 Block 5 | Cygnus CRS-2 NG-25") == mission_key("CRS NG-25")
    assert mission_key("Falcon 9 Block 5 | Cygnus CRS-2 NG-25") != mission_key("CRS SpX-25")
    assert mission_key("Nova | AstroForge Autonomy-1 (Demo Flight)") != mission_key("Demo Flight")
    assert mission_key("Falcon 9 Block 5 | Bandwagon 5 (Dedicated Mid-Inclination Rideshare)") == mission_key("Bandwagon-5")
    with pytest.raises(ValueError, match="UNSUPPORTED_FLIGHT_PLAN_INDEX"):
        parse_index("<html><a href='/launches/'>Launches</a></html>")


# Worker discovery ------------------------------------------------------------


class Upstream:
    """Fake public source. Every request is recorded; nothing reaches the network."""

    def __init__(self, robots=(404, ""), index=(200, INDEX), pages=None, solar=(404, ""), solar_robots=(404, "")):
        self.robots, self.index, self.pages, self.calls = robots, index, pages or {}, []
        self.solar, self.solar_robots = solar, solar_robots

    def __call__(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        self.calls.append(url)
        if request.url.host == "www.navcen.uscg.gov":
            status, body = self.solar_robots if url.endswith("/robots.txt") else self.solar
        elif url.endswith("/robots.txt"):
            status, body = self.robots
        elif url.endswith("/launches/"):
            status, body = self.index
        else:
            status, body = self.pages.get(url, (404, ""))
        headers = {"Retry-After": "7200"} if status == 429 else {}
        return httpx.Response(status, text=body, headers=headers)


def detail(n: int) -> str:
    return f"https://nextspaceflight.com/launches/details/{n}/"


def run(upstream: Upstream, launches: list[dict], at=s.AT) -> dict:
    with httpx.Client(transport=httpx.MockTransport(upstream)) as client:
        return refresh_flight_plans(at, client=client, launches=launches)


def nsf(record: dict) -> dict:
    return next(x for x in record["sources"] if x["source"] == "nextspaceflight")


def records(launches: list[dict], at=s.AT) -> dict:
    with db.engine().connect() as conn:
        return read_many(conn, launches, at)


def test_discovery_covers_every_vehicle_and_date_precision_and_records_missing_states():
    missions = [
        launch("Falcon 9 Block 5 | Fixture Rideshare-5 (Dedicated Rideshare)"),
        launch("Vulcan VC4S | USSF-9999", "Space Launch Complex 41", vehicle_variant="Vulcan VC4S", time_precision="unknown", net=None),
        launch("New Glenn | Fixture Lander Demo", "Launch Complex 36", vehicle_variant="New Glenn", time_precision="date", date_label="2027-01-15"),
        launch("Falcon 9 Block 5 | Twin Name"),
        launch("Falcon 9 Block 5 | Starlink Group 99-1"),
    ]
    upstream = Upstream(
        pages={
            detail(9001): (200, page("Fixture Rideshare-5")),
            detail(9002): (200, page("USSF-9999", "SLC-41", "East")),
            detail(9003): (200, (FIXTURES / "detail-no-trajectory.html").read_text(encoding="utf-8")),
        }
    )
    with s.isolated_database():
        summary = run(upstream, missions)
        assert summary["checked"] == 5
        found = records(missions)
        states = [found[m["id"]]["state"] for m in missions]
        assert states == ["found", "found", "not_found", "ambiguous", "not_found"]
        assert found[missions[1]["id"]]["evidence"][0]["departure_direction"] == "east"
        assert "publishes no general trajectory" in nsf(found[missions[2]["id"]])["detail"]
        assert "index is partial" in nsf(found[missions[4]["id"]])["detail"]
        assert all(r["state"] != "pending" and r["checked_at"] for r in found.values())
        schema = CONTRACT["components"]["schemas"]["flight-plan"]
        for record in found.values():
            jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(record)
            json.dumps(record, allow_nan=False)
        # No request for the ambiguous or unlisted missions' pages.
        assert detail(9005) not in upstream.calls and detail(9006) not in upstream.calls
        totals = coverage(missions, found)
        assert totals["missions"] == 5 and totals["with_route_information"] == 2 and totals["with_timed_path"] == 0
        assert totals["by_vehicle_family"]["Vulcan"] == {"missions": 1, "with_route_information": 1}
        assert totals["by_time_precision"]["unknown"] == {"missions": 1, "with_route_information": 1}
        # Cached results are not refetched before their next check.
        before = len(upstream.calls)
        assert run(upstream, missions, s.AT + timedelta(minutes=5))["checked"] == 0
        assert len(upstream.calls) == before


def test_cached_robots_followed_by_404_does_not_crash_and_allows_crawl():
    mission = launch("Falcon 9 Block 5 | Fixture Rideshare-5")
    upstream = Upstream(robots=(200, "User-agent: *\nAllow: /\n"), pages={detail(9001): (200, page("Fixture Rideshare-5"))})
    with s.isolated_database():
        run(upstream, [mission])
        upstream.robots = (404, "")
        later = s.AT + timedelta(days=2)
        run(upstream, [mission], later)  # Regression: previously UnboundLocalError.
        assert records([mission], later)[mission["id"]]["state"] == "found"


def test_robots_disallow_403_and_429_never_leave_missions_pending():
    mission = launch("Falcon 9 Block 5 | Fixture Rideshare-5")
    for robots, index, page_status, expected in (
        ((200, "User-agent: *\nDisallow: /launches/\n"), (200, INDEX), 200, "blocked"),
        ((403, ""), (200, INDEX), 200, "blocked"),
        ((500, ""), (200, INDEX), 200, "unavailable"),
        ((404, ""), (429, ""), 200, "unavailable"),
        ((404, ""), (200, "<html>redesigned</html>"), 200, "unavailable"),
        ((404, ""), (200, INDEX), 403, "blocked"),
        ((404, ""), (200, INDEX), 429, "unavailable"),
    ):
        upstream = Upstream(robots, index, {detail(9001): (page_status, page("Fixture Rideshare-5"))})
        with s.isolated_database():
            run(upstream, [mission])
            record = records([mission])[mission["id"]]
            assert record["state"] == expected, (robots, index, page_status, record)
            assert record["next_check_at"] and not record["evidence"]
            if robots[0] in (403, 500) or "Disallow" in robots[1]:
                assert not any("/launches/" in c for c in upstream.calls)


def test_retry_after_is_respected_for_rate_limited_pages():
    mission = launch("Falcon 9 Block 5 | Fixture Rideshare-5")
    upstream = Upstream(pages={detail(9001): (429, "")})
    with s.isolated_database():
        run(upstream, [mission])
        upstream.pages[detail(9001)] = (200, page("Fixture Rideshare-5"))
        assert records([mission])[mission["id"]]["state"] == "unavailable"
        # Never sooner than Retry-After (7200 s) or the six-hour source period.
        for hours in (1, 2, 5):
            run(upstream, [mission], s.AT + timedelta(hours=hours, minutes=1))
            assert upstream.calls.count(detail(9001)) == 1
        run(upstream, [mission], s.AT + timedelta(hours=6, minutes=1))
        assert upstream.calls.count(detail(9001)) == 2
        assert records([mission], s.AT + timedelta(hours=6, minutes=1))[mission["id"]]["state"] == "found"


def test_changed_plan_is_recorded_and_changes_the_estimate():
    mission = launch("Falcon 9 Block 5 | Fixture Rideshare-5")
    upstream = Upstream(pages={detail(9001): (200, page("Fixture Rideshare-5", direction="Southeast"))})
    with s.isolated_database():
        run(upstream, [mission])
        first = records([mission])[mission["id"]]
        upstream.pages[detail(9001)] = (200, page("Fixture Rideshare-5", direction="Northeast"))
        later = s.AT + timedelta(hours=7)
        run(upstream, [mission], later)
        second = records([mission], later)[mission["id"]]
        assert second["evidence"][0]["departure_direction"] == "northeast"
        assert second["changes"][-1]["from"] == "southeast" and second["changes"][-1]["to"] == "northeast"
        assert calculate_plan(mission, MARYLAND, [], s.AT, first) != calculate_plan(mission, MARYLAND, [], s.AT, second)


def test_transient_failure_keeps_stale_heading_but_invalid_change_drops_it():
    mission = launch("Falcon 9 Block 5 | Fixture Rideshare-5")
    upstream = Upstream(pages={detail(9001): (200, page("Fixture Rideshare-5"))})
    with s.isolated_database():
        run(upstream, [mission])
        upstream.robots = (503, "")
        with db.engine().begin() as conn:  # Expire the cached robots result.
            conn.execute(db.cache.update().where(db.cache.c.key == "flight-plan:robots").values(next_at=s.AT))
        later = s.AT + timedelta(hours=7)
        run(upstream, [mission], later)
        stale = records([mission], later)[mission["id"]]
        assert stale["state"] == "stale" and stale["evidence"][0]["departure_direction"] == "southeast"
        assert usable_heading(stale) and calculate_plan(mission, MARYLAND, [], later, stale)["route_basis"]["stale"]
        upstream.robots = (404, "")
        upstream.pages[detail(9001)] = (200, page("Fixture Rideshare-5", direction="Retrograde"))
        with db.engine().begin() as conn:
            conn.execute(db.cache.update().where(db.cache.c.key.like("flight-plan:%")).values(next_at=s.AT))
        latest = s.AT + timedelta(hours=14)
        run(upstream, [mission], latest)
        invalid = records([mission], latest)[mission["id"]]
        assert invalid["state"] == "unavailable" and not invalid["evidence"]
        assert usable_heading(invalid) is None


def test_launched_mission_leaving_the_upcoming_index_keeps_its_matched_page():
    mission = launch("Falcon 9 Block 5 | Fixture Rideshare-5")
    upstream = Upstream(pages={detail(9001): (200, page("Fixture Rideshare-5"))})
    with s.isolated_database():
        run(upstream, [mission])
        upstream.index = (200, INDEX.replace("Fixture Rideshare-5", "Unrelated Mission"))
        with db.engine().begin() as conn:
            conn.execute(db.cache.update().where(db.cache.c.key.like("flight-plan:%")).values(next_at=s.AT))
        completed = {**mission, "status": "completed"}
        run(upstream, [completed], s.AT + timedelta(hours=7))
        assert records([completed], s.AT + timedelta(hours=7))[mission["id"]]["state"] == "found"
        # A removed page (404) is missing evidence, not a retained heading.
        upstream.pages[detail(9001)] = (404, "")
        with db.engine().begin() as conn:
            conn.execute(db.cache.update().where(db.cache.c.key.like("flight-plan:%")).values(next_at=s.AT))
        run(upstream, [completed], s.AT + timedelta(hours=14))
        gone = records([completed], s.AT + timedelta(hours=14))[mission["id"]]
        assert gone["state"] == "not_found" and not gone["evidence"]


def test_budget_exhaustion_queues_remaining_missions_without_requests():
    missions = [
        launch("Falcon 9 Block 5 | Fixture Rideshare-5"),
        launch("Vulcan VC4S | USSF-9999", "Space Launch Complex 41", net=stamp(s.AT + timedelta(days=20))),
    ]
    upstream = Upstream(pages={detail(9001): (200, page("Fixture Rideshare-5")), detail(9002): (200, page("USSF-9999", "SLC-41", "East"))})
    with s.isolated_database():
        with db.engine().begin() as conn:
            conn.execute(db.budget.insert(), [{"provider": "flight-plan", "requested_at": s.AT}] * 9)
        summary = run(upstream, missions)
        found = records(missions)
        assert [found[m["id"]]["state"] for m in missions] == ["found", "queued"]
        assert summary["deferred"] == 1 and detail(9002) not in upstream.calls
        with db.engine().connect() as conn:
            assert conn.scalar(select(func.count()).select_from(db.budget).where(db.budget.c.provider == "flight-plan")) == 12
        assert run(upstream, missions, s.AT + timedelta(hours=1, minutes=1))["checked"] == 1
        assert records(missions, s.AT + timedelta(hours=1, minutes=1))[missions[1]["id"]]["state"] == "found"


def test_flight_plan_source_provenance_is_not_ll2():
    mission = launch("Falcon 9 Block 5 | Fixture Rideshare-5")
    with s.isolated_database():
        run(Upstream(pages={detail(9001): (200, page("Fixture Rideshare-5"))}), [mission])
        with db.engine().connect() as conn:
            body = conn.scalar(select(db.cache.c.body).where(db.cache.c.key == "flight-plan:source:" + detail(9001)))
        assert "Next Spaceflight" in body["provenance"]["license"] and "LL2" not in body["provenance"]["license"]


# Planning semantics ------------------------------------------------------------


def test_no_family_based_fallback_can_produce_viewing_advice():
    for name, vehicle in (
        ("Falcon 9 Block 5 | Dragon CRS-2 SpX-35", "Falcon 9 Block 5"),
        ("Falcon 9 Block 5 | Crew-13", "Falcon 9 Block 5"),
        ("Falcon 9 Block 5 | Starlink Group 10-1", "Falcon 9 Block 5"),
        ("Vulcan VC4S | USSF-106", "Vulcan VC4S"),
    ):
        mission = launch(name, vehicle_variant=vehicle, mission_class="International Space Station")
        for record in (None, {"state": "not_found", "evidence": []}, {"state": "pending", "evidence": []}):
            assert calculate_plan(mission, MARYLAND, [], s.AT, record) is None
        hazard = {"state": "found", "evidence": [{"evidence_type": "hazard_corridor"}]}
        assert calculate_plan(mission, MARYLAND, [], s.AT, hazard) is None


def test_same_heading_gives_same_answer_regardless_of_vehicle_or_destination():
    record = heading_record("northeast")
    dragon = launch("Falcon 9 Block 5 | Dragon CRS-2 SpX-35", mission_class="International Space Station")
    vulcan = {**dragon, "name": "Vulcan VC4S | USSF-9999", "vehicle_variant": "Vulcan VC4S", "mission_class": "GTO"}
    assert calculate_plan(dragon, MARYLAND, [], s.AT, record) == calculate_plan(vulcan, MARYLAND, [], s.AT, record)


def test_observer_direction_is_computed_separately_from_departure_direction():
    mission = launch("Falcon 9 Block 5 | Fixture Rideshare-5")
    northeast = calculate_plan(mission, MARYLAND, [], s.AT, heading_record("northeast"))
    assert northeast["route_basis"]["departure_direction"] == "northeast"
    # From Maryland the rocket rises in the south and moves east, not "northeast".
    assert northeast["directions"][0] == "south" and northeast["directions"] != ["northeast"]
    assert northeast["watch_interval"] and northeast["windows"]
    southeast_md = calculate_plan(mission, MARYLAND, [], s.AT, heading_record("southeast"))
    assert southeast_md["watch_interval"] is None and southeast_md["directions"] == []
    assert southeast_md["horizon_grazing"] is True
    southeast_florida = calculate_plan(mission, FLORIDA, [], s.AT, heading_record("southeast"))
    assert southeast_florida["directions"] == ["southeast"] and southeast_florida["watch_interval"]
    northeast_florida = calculate_plan(mission, FLORIDA, [], s.AT, heading_record("northeast"))
    assert northeast_florida["directions"][0] == "southeast"
    for plan in (northeast, southeast_md, southeast_florida):
        assert plan["kind"] == "published_heading_model" and plan["clear_sky_assumed"]
        json.dumps(plan, allow_nan=False)


def test_heading_plans_never_invent_an_absolute_time():
    record = heading_record("northeast")
    for changes in ({"time_precision": "date", "date_label": "2026-10-20"}, {"time_precision": "unknown", "net": None}):
        plan = calculate_plan(launch("Falcon 9 Block 5 | Fixture Rideshare-5", **changes), MARYLAND, [], s.AT, record)
        assert plan["watch_interval"] is None and plan["launch_time"] is None and plan["windows"] == []
        assert plan["relative_window"]["t_end_s"] > plan["relative_window"]["t_start_s"]
        assert plan["directions"]
    window = launch(
        "Falcon 9 Block 5 | Fixture Rideshare-5",
        time_precision="window",
        window={"start": stamp(s.AT), "end": stamp(s.AT + timedelta(hours=2))},
    )
    plan = calculate_plan(window, MARYLAND, [], s.AT, record)
    assert plan["watch_interval"]["start"] <= stamp(s.AT + timedelta(minutes=1))
    assert plan["watch_interval"]["end"] >= stamp(s.AT + timedelta(hours=2, minutes=9))
    assert plan["windows"] == []


def test_list_summaries_keep_missing_coverage_distinct_and_clear_sky_first():
    mission = launch("Falcon 9 Block 5 | Fixture Rideshare-5")
    cloudy = [
        {
            "start": stamp(s.AT + timedelta(days=5)),
            "end": stamp(s.AT + timedelta(days=7)),
            "total": 95,
            "provenance": [{"issued_at": stamp(s.AT), "fetched_at": stamp(s.AT)}],
        }
    ]
    plan = calculate_plan(mission, MARYLAND, cloudy, s.AT, heading_record("northeast"))
    row = summarize(mission, plan=plan, flight_plan=heading_record("northeast"))
    assert row["viewable"] and row["basis"] == "published_heading" and row["label"] == "Clear-sky estimate"
    assert "95" in row["weather_note"]
    below = summarize(mission, plan=calculate_plan(mission, MARYLAND, [], s.AT, heading_record("southeast")))
    assert not below["viewable"] and below["label"].startswith("Grazes your horizon")
    labels = {
        state: summarize(mission, flight_plan={"state": state, "evidence": []})["label"]
        for state in ("pending", "not_found", "unavailable", "blocked", "ambiguous")
    }
    assert labels["pending"] == "Route check pending" and labels["not_found"] == "No published route found"
    assert len(set(labels.values()) | {below["label"], row["label"]}) == 6
    schema = CONTRACT["components"]["schemas"]["ViewingOpportunity"]
    for item in (row, below, summarize(mission, flight_plan={"state": "not_found", "evidence": []})):
        jsonschema.Draft202012Validator(schema).validate(item)


# API contracts -----------------------------------------------------------------


def test_flight_plan_endpoints_assessment_and_viewable_list():
    with s.isolated_database():
        c = s.client()
        loc = s.location(c, "fixture-zip")
        doc = s.launch()
        other = s.launch()
        r = c.get(f"/api/v1/launches/{doc['id']}/flight-plan")
        assert r.status_code == 200 and r.json()["state"] == "pending"
        with db.engine().connect() as conn:
            assert conn.scalar(select(func.count()).select_from(db.jobs)) == 1
        record = {
            "schema_version": "1.0",
            "launch_id": doc["id"],
            "state": "found",
            "checked_at": stamp(s.AT),
            "next_check_at": stamp(s.AT + timedelta(hours=6)),
            "mission_fingerprint": fingerprint(doc),
            "sources": [],
            "changes": [],
            "trajectory_available": False,
            "note": "found",
            **{k: v for k, v in heading_record("northeast").items() if k == "evidence"},
        }
        with db.engine().begin() as conn:
            conn.execute(db.cache.insert().values(key=KEY + doc["id"], body=record, failures=0))
        r = c.get(f"/api/v1/launches/{doc['id']}/flight-plan")
        assert r.json()["evidence"][0]["departure_direction"] == "northeast"
        coverage_doc = c.get("/api/v1/flight-plan-coverage").json()
        jsonschema.Draft202012Validator(CONTRACT["components"]["schemas"]["FlightPlanCoverage"]).validate(coverage_doc)
        assert coverage_doc["missions"] == 2 and coverage_doc["with_route_information"] == 1
        assessment = c.post("/api/v1/assessments", json={"launch_id": doc["id"], "location_id": loc["id"]}).json()
        scenario = assessment["planning_scenario"]
        assert scenario["kind"] == "published_heading_model" and scenario["route_basis"]["departure_direction"] == "northeast"
        jsonschema.Draft202012Validator(CONTRACT["components"]["schemas"]["assessment"]).validate(assessment)
        rows = {r["launch_id"]: r for r in c.get(f"/api/v1/locations/{loc['id']}/viewing-opportunities").json()}
        assert rows[doc["id"]]["basis"] == "published_heading" and rows[doc["id"]]["directions"]
        assert rows[other["id"]]["label"] == "Route check pending" and not rows[other["id"]]["viewable"]
        assert c.get("/api/v1/launches/missing/flight-plan").status_code == 404


# NAVCEN SOLAR hazard corridors ------------------------------------------------------


def test_solar_parser_keeps_downrange_hazard_notices_only():
    notices = navcen.parse_solar(SOLAR)
    ids = {n["msg_id"] for n in notices}
    assert "CGD-SE BNM 9901-26_rna" not in ids and "CGD-SE BNM 9901-26" in ids
    earlier = next(n for n in notices if n["msg_id"] == "CGD-SE BNM 9801-26")
    assert earlier["invalid_windows"] == 1 and len(earlier["windows"]) == 1
    rideshare = next(n for n in notices if n["msg_id"] == "CGD-SE BNM 9901-26")
    assert rideshare["windows"][0] == {"start": "2026-10-19T11:30:00Z", "end": "2026-10-19T12:30:00Z"}
    assert len(rideshare["polygons"]) == 2
    assert sum(n["id_conflict"] for n in notices) == 2
    assert not navcen.east_coast(next(n for n in notices if "SW" in n["msg_id"]))
    for bad in ("alert(1)", "var x = [];", 'var x = {"type":"Feature"};'):
        with pytest.raises(ValueError):
            navcen.parse_solar(bad)


def test_solar_association_is_exact_dated_and_never_a_path():
    notices = navcen.parse_solar(SOLAR)
    rideshare = launch("Falcon 9 Block 5 | Fixture Rideshare-5 (Dedicated Rideshare)", net="2026-10-19T11:45:00Z")
    state, notice, _ = navcen.associate(notices, rideshare)
    assert state == "found" and notice and notice["msg_id"] == "CGD-SE BNM 9901-26"
    evidence = navcen.hazard_evidence(notice, rideshare)
    assert evidence["evidence_type"] == "hazard_corridor" and evidence["trajectory_available"] is False
    bearing = evidence["hazard_bearing_sector_deg"]
    assert 90 <= bearing["start_deg"] < bearing["end_deg"] <= 180
    assert evidence["hazard_distance_km"]["min"] >= 30 and "not the flight path" in evidence["note"]
    # Earlier attempt only: a slipped launch outside every notice window is not matched.
    state, _, detail = navcen.associate(notices, {**rideshare, "net": "2026-12-01T00:00:00Z"})
    assert state == "not_found" and "do not cover" in detail
    # Undated launch: newest notice by issue time, with an explicit unverified-date note.
    state, notice, detail = navcen.associate(notices, {**rideshare, "time_precision": "unknown", "net": None})
    assert state == "found" and notice and notice["msg_id"] == "CGD-SE BNM 9901-26" and "not confirmed" in detail
    reused = launch("Falcon 9 Block 5 | Starlink Group 99-1", net="2026-10-19T12:00:00Z")
    assert navcen.associate(notices, reused)[0] == "ambiguous"
    assert navcen.associate(notices, launch("Falcon 9 Block 5 | Fixture Rideshare-6"))[0] == "not_found"
    for ll2, solar_name in (
        ("Falcon 9 Block 5 | Starlink Group 10-38", "Starlink g10-38"),
        ("Falcon 9 Block 5 | Dragon CRS-2 SpX-35", "CRS-35"),
        ("Falcon 9 Block 5 | Crew-13", "NASA Crew-13"),
        ("Vulcan VC4S | USSF-87", "VULCAN USSF-87"),
        ("Atlas V 551 | Amazon Leo (KA-06)", "ATLAS V KA-06"),
        ("New Glenn | BlueBird 7", "NEW GLENN BLUEBIRD 7"),
    ):
        assert navcen.mission_keys(ll2) & navcen.mission_keys(solar_name), (ll2, solar_name)
    for ll2, solar_name in (
        ("Atlas V 551 | Amazon Leo (KA-06)", "Amazon Leo"),
        ("Falcon 9 Block 5 | Starlink Group 10-3", "Starlink g10-38"),
        ("Falcon 9 Block 5 | Dragon CRS-2 SpX-35", "CRS-34"),
    ):
        assert not navcen.mission_keys(ll2) & navcen.mission_keys(solar_name), (ll2, solar_name)


def test_hazard_only_and_conflicting_sources_give_no_distant_estimate():
    rideshare = launch("Falcon 9 Block 5 | Fixture Rideshare-5", net="2026-10-19T11:45:00Z")
    conflict = launch("Falcon 9 Block 5 | Conflict Demo-1", net="2026-10-19T11:45:00Z")
    hazard_only = launch("Vulcan VC4S | USSF-9999", "Space Launch Complex 41", net="2026-11-02T02:00:00Z")
    upstream = Upstream(
        index=(200, INDEX.replace("<h3>Fixture Lander Demo</h3>", "<h3>Conflict Demo-1</h3>")),
        pages={
            detail(9001): (200, page("Fixture Rideshare-5")),
            detail(9003): (200, page("Conflict Demo-1", direction="Southeast")),
        },
        solar=(200, SOLAR),
    )
    with s.isolated_database():
        run(upstream, [rideshare, conflict, hazard_only])
        found = records([rideshare, conflict, hazard_only])
    agreed = found[rideshare["id"]]
    assert {e["evidence_type"] for e in agreed["evidence"]} == {"departure_heading", "hazard_corridor"}
    assert not agreed["conflict"] and usable_heading(agreed)
    narrowed = calculate_plan(rideshare, FLORIDA, [], s.AT, agreed)
    assert narrowed["kind"] == "published_heading_model"
    # Hazard bearings narrow the swept headings but never become a single centerline.
    basis = narrowed["route_basis"]
    assert basis["narrowed_by_hazard_areas"] and basis["departure_sector_deg"] == {"start_deg": 90, "end_deg": 180}
    assert 90 < basis["swept_sector_deg"]["start_deg"] < basis["swept_sector_deg"]["end_deg"] < 180
    for window in narrowed["windows"]:  # One row per modeled heading, never blended.
        assert len({cid.split(":")[1] for cid in window["candidate_ids"]}) == 1
    disagree = found[conflict["id"]]
    assert disagree["conflict"] and usable_heading(disagree) is None
    assert calculate_plan(conflict, MARYLAND, [], s.AT, disagree) is None
    assert summarize(conflict, flight_plan=disagree)["label"] == "Route sources disagree"
    hazard = found[hazard_only["id"]]
    # The index lists USSF-9999 but its page is missing (404), so only the hazard remains.
    assert [e["evidence_type"] for e in hazard["evidence"]] == ["hazard_corridor"]
    assert calculate_plan(hazard_only, MARYLAND, [], s.AT, hazard) is None
    assert summarize(hazard_only, flight_plan=hazard)["label"] == "Hazard areas only; path unresolved"
    schema = CONTRACT["components"]["schemas"]["flight-plan"]
    for record in found.values():
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(record)


def test_solar_robots_and_http_failures_are_explicit():
    mission = launch("Falcon 9 Block 5 | Fixture Rideshare-5", net="2026-10-19T11:45:00Z")
    for solar_robots, solar, expected in (
        ((200, "User-agent: *\nDisallow: /sites/\n"), (200, SOLAR), "blocked"),
        ((404, ""), (403, ""), "blocked"),
        ((404, ""), (429, ""), "unavailable"),
        ((404, ""), (200, "var chris = 1;"), "unavailable"),
    ):
        upstream = Upstream(index=(200, "<html></html>"), solar=solar, solar_robots=solar_robots)
        with s.isolated_database():
            run(upstream, [mission])
            sources = {x["source"]: x for x in records([mission])[mission["id"]]["sources"]}
        assert sources["navcen-solar"]["state"] == expected, (solar_robots, solar, sources)
        if "Disallow" in solar_robots[1]:
            assert not any(c.endswith("test.js") for c in upstream.calls)
