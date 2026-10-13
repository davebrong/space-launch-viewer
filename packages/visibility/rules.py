from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Inputs:
    status: str
    mode: str
    route: str
    profile: str
    complete: bool
    fresh: bool
    weather: str
    luminous_seconds: float | None
    all_below_horizon: bool
    official_member: bool


def decide(value: Inputs) -> dict:
    advice, reason = "Not enough data", "insufficient_evidence"
    if value.status != "scheduled":
        reason = "nonactionable_" + value.status
    elif value.mode not in ("reconstructed", "official_guidance") or value.route != "approved":
        reason = "route_unavailable"
    elif value.mode == "reconstructed" and value.profile != "compatible":
        reason = "incompatible_profile"
    elif value.mode == "official_guidance" and not value.official_member:
        reason = "observer_membership_unverified"
    elif (
        not value.complete
        or not value.fresh
        or value.weather in ("unavailable", "stale")
        or value.luminous_seconds is None
    ):
        reason = "incomplete_or_stale"
    elif value.mode == "reconstructed" and value.all_below_horizon:
        advice, reason = "Unlikely", "below_horizon_within_model"
    elif value.weather == "poor":
        advice, reason = "Unlikely", "cloud_or_haze"
    elif value.luminous_seconds >= 20:
        advice = (
            "Worth a look" if value.mode == "official_guidance" and value.weather == "clear" else "Possible"
        )
        reason = "official_guidance" if value.mode == "official_guidance" else "approximate_flight_profile"
    return {"advice": advice, "reason_codes": [reason]}


def emission(active_engine: bool, active_plume: bool, sunlit: bool) -> bool:
    # The source establishes active emission; sunlight alone never creates it.
    return active_engine or active_plume


def lighting_flag(continuous_s: float, elevation_deg: float, observer_sun_deg: float, emission: bool) -> bool:
    return continuous_s >= 60 and elevation_deg >= 5 and observer_sun_deg <= -6 and emission
