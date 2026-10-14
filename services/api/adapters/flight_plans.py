"""Next Spaceflight public mission pages: reported general departure headings only.

The page's "General Trajectory" panel names one of eight compass directions. That
is a reported departure heading for this mission, not timed trajectory coordinates,
an operator-filed flight plan, or the direction an observer should look. Never infer
a heading from mission family, payload, orbit or hazard areas.
"""

import re
from html.parser import HTMLParser
from urllib.parse import urljoin

VERSION = "nextspaceflight-public-heading-v2"
SOURCE_NAME = "Next Spaceflight"
INDEX_URL = "https://nextspaceflight.com/launches/"
ROBOTS_URL = "https://nextspaceflight.com/robots.txt"
TERMS_NOTE = (
    "Public Next Spaceflight mission page. Only the reported compass direction, page URL, hash and "
    "retrieval time are retained; page content is not redistributed."
)
COMPASS = ("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest")
# The page shows an eight-point word, but its embedded numeric heading was only ever
# 45 or 135 across seven checked Florida missions of five vehicle families
# (2026-10-14). That suggests quadrant-level classification, so the word supports
# a 90-degree quadrant centered on it, not a 45-degree octant or an exact azimuth.
SECTOR_HALF_WIDTH_DEG = 45.0


class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.skip = 0
        self.parts = []
        self.links = []
        self.active = None
        self.headings = []
        self.heading = None

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        if tag == "a":
            self.active = {"url": dict(attrs).get("href", ""), "parts": [], "headings": []}
        if tag in ("h1", "h2", "h3", "h4"):
            self.heading = [tag, []]

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        if self.heading and tag == self.heading[0]:
            text = " ".join(self.heading[1]).strip()
            self.headings.append((tag, text))
            if self.active:
                self.active["headings"].append(text)
            self.heading = None
        if tag == "a" and self.active:
            self.links.append(self.active)
            self.active = None

    def handle_data(self, data):
        if self.skip or not data.strip():
            return
        value = data.strip()
        self.parts.append(value)
        if self.active:
            self.active["parts"].append(value)
        if self.heading:
            self.heading[1].append(value)


def mission_key(name: str) -> str:
    name = name.split(" | ")[-1].lower()
    name = re.sub(r"\((?:dedicated|rideshare)[^)]*\)", "", name)
    # Explicit nomenclature equivalence, not fuzzy matching or a direction rule.
    name = re.sub(r"^(?:dragon\s+)?crs(?:-2)?\s+spx", "crs spx", name)
    name = re.sub(r"^(?:cygnus\s+)?crs(?:-2)?\s+ng", "crs ng", name)
    # Keep a separator between digit groups: "11-1" and "1-11" must stay distinct.
    return re.sub(r"[^a-z0-9.]", "", re.sub(r"(?<=\d)[^a-z0-9]+(?=\d)", ".", name))


def sector(direction: str) -> dict:
    center = COMPASS.index(direction) * 45
    return {
        "start_deg": (center - SECTOR_HALF_WIDTH_DEG) % 360,
        "end_deg": (center + SECTOR_HALF_WIDTH_DEG) % 360,
    }


def parse_index(html: str) -> list[dict]:
    doc = Document()
    doc.feed(html)
    entries = {}
    for link in doc.links:
        if re.fullmatch(r"/launches/details/\d+/", link["url"]) and link["headings"]:
            name = link["headings"][-1]
            entries[link["url"]] = {"name": name, "key": mission_key(name), "url": urljoin(INDEX_URL, link["url"])}
    if not entries:
        raise ValueError("UNSUPPORTED_FLIGHT_PLAN_INDEX")
    return list(entries.values())


def parse_heading(html: str, launch: dict) -> dict:
    """Return heading evidence for this exact mission and pad; launch date is not required."""
    doc = Document()
    doc.feed(html)
    names = [text for tag, text in doc.headings if tag == "h1"]
    if len(names) != 1 or mission_key(names[0]) != mission_key(launch["name"]):
        raise ValueError("FLIGHT_PLAN_MISSION_MISMATCH")
    text = " ".join(doc.parts)
    pad = re.search(r"(?:Complex|SLC-|LC-)\s*(\d+[A-Z]?)", launch.get("pad_name") or "", re.I)
    # "Launch Complex 36" also matches a source's "LC-36A"; a lettered pad must match exactly.
    suffix = "" if pad and pad[1][-1].isalpha() else "[A-Z]?"
    if not pad or not re.search(r"\b(?:SLC|LC)-" + re.escape(pad[1]) + suffix + r"\b", text, re.I):
        raise ValueError("FLIGHT_PLAN_PAD_MISMATCH")
    if not ("Cape Canaveral" in text or "Kennedy" in text):
        raise ValueError("FLIGHT_PLAN_LOCATION_MISMATCH")
    if "General Trajectory" not in text:
        raise ValueError("NO_PUBLISHED_HEADING")
    section = text.partition("General Trajectory")[2].partition("Stats")[0]
    words = re.findall(r"\bLaunching\s+([A-Za-z-]+)", section)
    if len(words) != 1:
        raise ValueError("NO_PUBLISHED_HEADING" if not words else "AMBIGUOUS_PUBLISHED_HEADING")
    direction = words[0].lower()
    if direction not in COMPASS:
        raise ValueError("UNSUPPORTED_HEADING_FORMAT")
    # When the page also embeds its numeric heading, it must agree with the word.
    numeric = set(re.findall(r'\\?"heading\\?":\s*(\d+(?:\.\d+)?)', html))
    if len(numeric) > 1 or (numeric and float(numeric.pop()) % 360 != COMPASS.index(direction) * 45):
        raise ValueError("INCONSISTENT_PUBLISHED_HEADING")
    return {
        "evidence_type": "departure_heading",
        "source_name": SOURCE_NAME,
        "departure_direction": direction,
        "departure_sector_deg": sector(direction),
        "trajectory_available": False,
        "parser_version": VERSION,
        "license_note": TERMS_NOTE,
        "note": "Reported general departure direction from the pad, not timed trajectory coordinates. Your viewing direction is calculated separately from your location.",
    }
