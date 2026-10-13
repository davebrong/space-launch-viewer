"""Admission of reviewed manifests; arbitrary PDFs and images are never paths."""

from __future__ import annotations

from packages.visibility.common import utc

SUPPORTED_FORMATS = {"reviewed-path-v1", "reviewed-guidance-v1", "reviewed-hazard-v1"}


def admit_route(route: dict, launch: dict, at, now) -> tuple[bool, list[str]]:
    reasons = []
    if route.get("source_format") not in SUPPORTED_FORMATS:
        reasons.append("unsupported_source_format")
    if route.get("admission") != "approved" or route.get("association") != "exact":
        reasons.append("unapproved_or_ambiguous_association")
    if any(
        route.get(k) != launch.get(k if k != "launch_id" else "id")
        for k in ("launch_id", "attempt_id", "pad_id")
    ):
        reasons.append("mission_attempt_pad_mismatch")
    interval = route.get("valid_interval")
    if not interval or not utc(interval["start"]) <= utc(at) < utc(interval["end"]):
        reasons.append("outside_route_validity")
    if not route.get("provenance"):
        reasons.append("missing_provenance")
    else:
        age = (utc(now) - utc(route["provenance"][0]["fetched_at"])).total_seconds()
        if not -300 <= age <= (7200 if (utc(at) - utc(now)).total_seconds() <= 21600 else 43200):
            reasons.append("route_stale")
    if route.get("evidence_type") == "published_path":
        if route.get("dogleg") != "absent_supported" or len(route.get("path_vertices", [])) < 2:
            reasons.append("unsupported_route_structure")
    if route.get("evidence_type") == "official_guidance":
        guidance = route.get("guidance") or {}
        relative = (
            guidance.get("timing_basis") == "liftoff_relative"
            and guidance.get("timing_change_policy") == "source_relative_valid"
        )
        if not relative and route.get("reviewed_schedule_revision") != launch["revision"]:
            reasons.append("guidance_schedule_revision_changed")
    return not reasons, reasons


def compatible(profile: dict, launch: dict) -> tuple[bool, list[str]]:
    reasons = []
    for field in ("vehicle_variant", "mission_class", "recovery_configuration"):
        if not profile.get(field) or not launch.get(field) or profile[field] != launch[field]:
            reasons.append(field + "_mismatch_or_unknown")
    if launch["pad_id"] not in profile.get("compatible_pad_ids", []):
        reasons.append("pad_incompatible")
    if profile.get("compatibility") != "approved" or profile.get("altitude_datum") != "WGS84_ELLIPSOID":
        reasons.append("profile_or_datum_unapproved")
    for field in ("powered_intervals", "stage_identity_notes", "downrange_definition", "provenance"):
        if not profile.get(field):
            reasons.append("missing_" + field)
    if set(profile.get("training_mission_ids", [])) & set(profile.get("held_out_mission_ids", [])):
        reasons.append("heldout_leakage")
    return not reasons, reasons
