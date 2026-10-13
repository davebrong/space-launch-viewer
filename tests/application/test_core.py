from datetime import datetime, timedelta, timezone

import pytest
from pyproj import Transformer

from packages.visibility.geometry import geometry, ecef
from packages.visibility.ensemble import bearing_sector
from packages.visibility.weather import partition, select, tier
from packages.visibility.time import alternatives, parse_local
from services.api.adapters.nws import valid_interval
from services.worker.ingestion import approved_url


def test_independent_ecef():
    reference = Transformer.from_crs(4979, 4978, always_xy=True)
    for lat, lon, alt in [(39.0, -77.0, 0), (28.5, -80.5, 200000), (90, 0, 10), (-30, 150, 55000)]:
        assert ecef(lat, lon, alt) == pytest.approx(reference.transform(lon, lat, alt), abs=1e-5)


def test_zenith_and_occultation():
    assert geometry([0, 0, 0], [0, 0, 1000])["azimuth_deg"] is None
    assert geometry([39.4, -77.3, 0], [28.5, -80.5, 0])["occulted"]


def test_weather_gap_narrowing():
    view = ["2026-10-13T10:00:00Z", "2026-10-13T10:03:00Z"]
    bins = [{"start": view[0], "end": "2026-10-13T10:01:00Z", "tier": "clear"}]
    result = select(view, bins)
    assert result["tier"] == "clear" and result["narrowed"]
    assert partition(view, bins)[1]["tier"] == "unavailable"
    assert tier(90, 20000)["tier"] == "poor"


def test_clock_transitions():
    with pytest.raises(ValueError):
        parse_local("2026-11-01T01:30:00", "America/New_York")
    a = parse_local("2026-11-01T01:30:00", "America/New_York", "-04:00")
    b = parse_local("2026-11-01T01:30:00", "America/New_York", "-05:00")
    assert (b - a).total_seconds() == 3600


def test_window_refinement():
    start = datetime(2026, 10, 13, tzinfo=timezone.utc)
    values = alternatives(start, start + timedelta(minutes=10), lambda t: t >= start + timedelta(seconds=371))
    changed = [(a, b) for a, b in zip(values, values[1:]) if a["result"] != b["result"]]
    assert len(changed) == 1
    from packages.visibility.common import utc

    assert (utc(changed[0][1]["t0"]) - utc(changed[0][0]["t0"])).total_seconds() <= 60


def test_units_and_source_allowlist():
    a, b = valid_interval("2026-10-13T00:00:00Z/P1DT2H30M")
    assert (b - a).total_seconds() == 95400
    for url in (
        "http://api.weather.gov/points/39,-77",
        "https://127.0.0.1/",
        "https://api.weather.gov@127.0.0.1/",
        "https://api.weather.gov:444/points/39,-77",
        "https://api.weather.gov.evil.test/points/39,-77",
    ):
        assert not approved_url(url)


def test_bearings():
    assert bearing_sector([359, 1]) == {"start_deg": 345, "end_deg": 15, "wraps_north": True}
    assert bearing_sector([]) is None
