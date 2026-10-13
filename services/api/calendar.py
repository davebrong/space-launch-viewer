from __future__ import annotations

from datetime import datetime, timedelta

from packages.visibility.common import utc, digest


def escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\r", "")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def fold(line: str) -> str:
    pieces, current = [], ""
    for char in line:
        if len((current + char).encode("utf-8")) > 75:
            pieces.append(current)
            current = " "
        current += char
    pieces.append(current)
    return "\r\n".join(pieces)


def calendar_snapshot(launch: dict, location: dict, assessment: dict, now: datetime) -> str:
    uid = digest([launch["attempt_id"], location["id"]]) + "@launch-visibility.local"

    def date(d):
        return utc(d).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Launch Visibility//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        "UID:" + uid,
        "SEQUENCE:" + str(launch["revision"]),
        "DTSTAMP:" + date(now),
    ]
    if launch["time_precision"] == "date" and launch["date_label"]:
        day = datetime.fromisoformat(launch["date_label"])
        lines += [
            "DTSTART;VALUE=DATE:" + day.strftime("%Y%m%d"),
            "DTEND;VALUE=DATE:" + (day + timedelta(days=1)).strftime("%Y%m%d"),
        ]
    elif launch["net"]:
        if assessment.get("supported_intervals"):
            start = min(utc(w["start"]) for w in assessment["supported_intervals"])
            end = max(utc(w["end"]) for w in assessment["supported_intervals"])
        elif assessment["windows"]:
            start = min(utc(launch["net"]) + timedelta(seconds=w["t_start_s"]) for w in assessment["windows"])
            end = max(utc(launch["net"]) + timedelta(seconds=w["t_end_s"]) for w in assessment["windows"])
        elif launch["time_precision"] == "window" and launch["window"]:
            start, end = utc(launch["window"]["start"]), utc(launch["window"]["end"])
        elif launch["time_precision"] == "exact":
            start, end = utc(launch["net"]), utc(launch["net"]) + timedelta(minutes=1)
        else:
            raise ValueError("Calendar time unavailable")
        lines += ["DTSTART:" + date(start), "DTEND:" + date(end)]
    else:
        raise ValueError("Calendar time unavailable")
    lines += [
        "SUMMARY:" + escape(launch["name"] + " — " + assessment["advice"]),
        "DESCRIPTION:"
        + escape(
            "Snapshot only. Download again after any schedule or advice change. "
            + (
                "Schedule planning only; no supported viewing interval. "
                if not assessment["windows"]
                else "Approximate viewing opportunity. "
            )
            + "Observer zone: "
            + location["timezone"]
            + ". "
            + " ".join(assessment["limitations"])
        ),
        "STATUS:" + ("CANCELLED" if launch["status"] in ("scrubbed", "cancelled") else "TENTATIVE"),
        "TRANSP:TRANSPARENT",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(fold(line) for line in lines) + "\r\n"
