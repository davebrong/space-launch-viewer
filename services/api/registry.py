"""Authenticated, audited admission of supported, reviewed JSON manifests."""

from __future__ import annotations

import base64
import hashlib
import json
from uuid import uuid4

import jsonschema
from sqlalchemy import select, update

from . import db
from .config import ROOT
from .adapters.routes import SUPPORTED_FORMATS
from packages.visibility.common import digest


def import_document(conn, body: dict, at) -> dict:
    kind = body.get("kind")
    if kind not in ("route-evidence", "ascent-profile"):
        raise ValueError("Unsupported registry type")
    if not isinstance(body.get("review_notes"), str) or len(body["review_notes"].strip()) < 10:
        raise ValueError("Document the source permission, association and compatibility review")
    doc = body.get("document", {})
    schema = json.loads((ROOT / "spec/contracts" / (kind + ".schema.json")).read_text())
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(doc)
    json.dumps(doc, allow_nan=False)
    if any(p["kind"] == "synthetic" for p in doc["provenance"]):
        raise ValueError("Synthetic evidence is test-only")
    raw = base64.b64decode(body.get("raw_base64", ""), validate=True)
    sha = hashlib.sha256(raw).hexdigest()
    if not raw or sha not in {p["sha256"] for p in doc["provenance"]}:
        raise ValueError("Raw source must match a provenance SHA256")
    if kind == "route-evidence":
        if doc["source_format"] not in SUPPORTED_FORMATS:
            raise ValueError("Source format has no passing parser fixture")
        launch = conn.scalar(select(db.launches.c.body).where(db.launches.c.id == doc["launch_id"]))
        if not launch or any(
            doc[k] != launch[v] for k, v in (("attempt_id", "attempt_id"), ("pad_id", "pad_id"))
        ):
            raise ValueError("Mission, pad and attempt must match")
        if doc["evidence_type"] == "published_path" and (
            doc["dogleg"] != "absent_supported" or len(doc["path_vertices"]) < 2
        ):
            raise ValueError("Unsupported path structure")
        table = db.routes
    else:
        if set(doc["training_mission_ids"]) & set(doc["held_out_mission_ids"]):
            raise ValueError("Held-out missions overlap template inputs")
        for stage in {s["stage"] for s in doc["samples"]}:
            rows = [s for s in doc["samples"] if s["stage"] == stage]
            if any(
                b["t_s"] <= a["t_s"] or b["downrange_m"] < a["downrange_m"] for a, b in zip(rows, rows[1:])
            ):
                raise ValueError("Stage samples must increase in time and downrange")
        if doc["compatibility"] == "approved" and (
            doc["altitude_datum"] != "WGS84_ELLIPSOID" or not doc["powered_intervals"]
        ):
            raise ValueError("Approved profiles require datum and emission support")
        table = db.profiles
    if conn.scalar(select(table.c.id).where(table.c.id == doc["id"])):
        raise ValueError("Version already exists; import a new immutable ID")
    from services.worker.ingestion import atomic_snapshot

    atomic_snapshot(raw)
    conn.execute(table.insert().values(id=doc["id"], revision=doc["revision"], body=doc, created_at=at))
    pending = update(db.outbox).where(db.outbox.c.state.in_(["pending", "claimed", "retry"]))
    if kind == "route-evidence":
        pending = pending.where(db.outbox.c.launch_id == doc["launch_id"])
    conn.execute(pending.values(state="cancelled", lease_until=None))
    conn.execute(
        db.audit.insert().values(
            id=str(uuid4()),
            revision=1,
            body={
                "actor": "operator",
                "action": "registry_import",
                "target": doc["id"],
                "document_sha256": digest(doc),
                "source_sha256": sha,
                "reason": body["review_notes"],
            },
            created_at=at,
        )
    )
    return {
        "id": doc["id"],
        "sha256": digest(doc),
        "admission": doc.get("admission", doc.get("compatibility")),
    }
