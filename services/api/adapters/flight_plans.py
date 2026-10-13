"""Published mission headings. Never infer a trajectory from mission family or hazards."""
import re
from html.parser import HTMLParser
from urllib.parse import urljoin

VERSION = "nextspaceflight-public-heading-v1"
INDEX_URL = "https://nextspaceflight.com/launches/"
DIRECTIONS = {name: i * 45 for i, name in enumerate(
    ("north", "northeast", "east", "southeast", "south", "southwest", "west", "northwest"))}


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

    def handle_data(self, value):
        if self.skip or not value.strip():
            return
        value = value.strip()
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
    return re.sub(r"[^a-z0-9]", "", name)


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
    doc = Document()
    doc.feed(html)
    names = [text for tag, text in doc.headings if tag == "h1"]
    if len(names) != 1 or mission_key(names[0]) != mission_key(launch["name"]):
        raise ValueError("FLIGHT_PLAN_MISSION_MISMATCH")
    text = " ".join(doc.parts)
    # The source's launch site must agree too; launch date is deliberately not required.
    pad = re.search(r"(?:Complex|SLC-|LC-)\s*(\d+[A-Z]?)", launch["pad_name"], re.I)
    if not pad or not re.search(r"\b(?:SLC|LC)-" + re.escape(pad[1]) + r"\b", text, re.I):
        raise ValueError("FLIGHT_PLAN_PAD_MISMATCH")
    if not ("Cape Canaveral" in text or "Kennedy" in text):
        raise ValueError("FLIGHT_PLAN_LOCATION_MISMATCH")
    section = text.partition("General Trajectory")[2].partition("Stats")[0]
    headings = re.findall(r"\bLaunching\s+(north(?:east|west)?|south(?:east|west)?|east|west)\b", section, re.I)
    if len(headings) != 1:
        raise ValueError("NO_PUBLISHED_HEADING")
    return {
        "state": "heading_only",
        "source_name": "Next Spaceflight",
        "evidence_type": "reported_departure_direction",
        "departure_direction": headings[0].lower(),
        "trajectory_available": False,
        "parser_version": VERSION,
        "note": "Published general departure direction, not operator-filed trajectory coordinates. It is not the direction to look from your ZIP.",
    }
