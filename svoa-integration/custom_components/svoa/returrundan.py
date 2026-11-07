"""Typed parser and domain models for SVOA Returrundan data.

This module deliberately has no Home Assistant dependency so the parsing and
schedule logic can be tested independently from the integration runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html.parser import HTMLParser
import re
from zoneinfo import ZoneInfo

STOCKHOLM = ZoneInfo("Europe/Stockholm")
MONTHS: dict[str, int] = {
    "januari": 1,
    "februari": 2,
    "mars": 3,
    "april": 4,
    "maj": 5,
    "juni": 6,
    "juli": 7,
    "augusti": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "december": 12,
}
VISIT_RE = re.compile(
    r"(?:måndag|tisdag|onsdag|torsdag|fredag|lördag|söndag)\s+"
    r"\d{1,2}\s+(?P<month>[a-zåäö]+),\s*klockan\s+"
    r"(?P<start>\d{1,2}\.\d{2})[–—-](?P<end>\d{1,2}\.\d{2})",
    re.IGNORECASE,
)


class ReturrundanParseError(ValueError):
    """Raised when an SVOA response does not match the expected schema."""


@dataclass(frozen=True, slots=True)
class Visit:
    """A scheduled Returrundan collection window."""

    start: datetime
    end: datetime


@dataclass(frozen=True, slots=True)
class Location:
    """A named Returrundan stop and its published schedule."""

    id: str
    name: str
    address: str
    area_id: str
    area_name: str
    visits: tuple[Visit, ...]

    def upcoming_visits(self, now: datetime) -> tuple[Visit, ...]:
        """Return visits whose start time has not passed, in chronological order."""
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        return tuple(visit for visit in self.visits if visit.start > now)

    def next_visit(self, now: datetime) -> Visit | None:
        """Return the next future visit, if one exists."""
        return next(iter(self.upcoming_visits(now)), None)


@dataclass(frozen=True, slots=True)
class Area:
    """An SVOA administrative area containing collection locations."""

    id: str
    name: str
    locations: tuple[Location, ...]


class _ListItemParser(HTMLParser):
    """Extract list item text while retaining strikethrough cancellation state."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[tuple[str, bool]] = []
        self._text: list[str] = []
        self._in_item = False
        self._strike_depth = 0
        self._item_cancelled = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "li":
            self._in_item = True
            self._text = []
            self._item_cancelled = self._strike_depth > 0
        elif tag in {"s", "strike", "del"}:
            self._strike_depth += 1
            if self._in_item:
                self._item_cancelled = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "li" and self._in_item:
            self.items.append((" ".join("".join(self._text).split()), self._item_cancelled))
            self._in_item = False
            self._text = []
        elif tag in {"s", "strike", "del"} and self._strike_depth:
            self._strike_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_item:
            self._text.append(data)


def _parse_time(value: str) -> tuple[int, int]:
    hour, minute = value.split(".", maxsplit=1)
    return int(hour), int(minute)


def _parse_visits(html: str, year: int) -> tuple[Visit, ...]:
    parser = _ListItemParser()
    parser.feed(html)
    visits: list[Visit] = []

    for text, cancelled in parser.items:
        if cancelled:
            continue
        match = VISIT_RE.search(text.casefold())
        if match is None:
            continue
        month_name = match.group("month")
        month = MONTHS.get(month_name)
        if month is None:
            continue

        # The weekday in the source is descriptive; the numeric date is authoritative.
        day_match = re.search(r"\b(\d{1,2})\s+" + re.escape(month_name), text.casefold())
        if day_match is None:
            continue
        day = int(day_match.group(1))
        start_hour, start_minute = _parse_time(match.group("start"))
        end_hour, end_minute = _parse_time(match.group("end"))
        try:
            start = datetime(year, month, day, start_hour, start_minute, tzinfo=STOCKHOLM)
            end = datetime(year, month, day, end_hour, end_minute, tzinfo=STOCKHOLM)
        except ValueError:
            continue
        if end <= start:
            continue
        visits.append(Visit(start=start, end=end))

    return tuple(sorted(set(visits), key=lambda visit: visit.start))


def parse_returrundan_payload(payload: object, *, year: int) -> tuple[Area, ...]:
    """Parse the SVOA MobileStationSearch JSON response into typed models.

    ``year`` is explicit to keep this pure function deterministic. The Home
    Assistant integration supplies the current Stockholm calendar year.
    """
    if not isinstance(payload, dict):
        raise ReturrundanParseError("Response must be a JSON object")
    raw_areas = payload.get("mobileStationAreas")
    if not isinstance(raw_areas, list):
        raise ReturrundanParseError("Response is missing mobileStationAreas")

    areas: list[Area] = []
    for raw_area in raw_areas:
        if not isinstance(raw_area, dict):
            raise ReturrundanParseError("Area entry must be an object")
        area_id = raw_area.get("id")
        area_name = raw_area.get("name")
        raw_locations = raw_area.get("mobileStationFindHits")
        if not isinstance(area_id, str) or not isinstance(area_name, str):
            raise ReturrundanParseError("Area is missing a valid id or name")
        if not isinstance(raw_locations, list):
            raise ReturrundanParseError(f"Area {area_id} is missing its locations")

        locations: list[Location] = []
        for index, raw_location in enumerate(raw_locations):
            if not isinstance(raw_location, dict):
                raise ReturrundanParseError(f"Invalid location in area {area_id}")
            heading = raw_location.get("heading")
            schedule_html = raw_location.get("text")
            if not isinstance(heading, str) or not isinstance(schedule_html, str):
                raise ReturrundanParseError(f"Location in area {area_id} is incomplete")
            heading = " ".join(heading.split())
            if " - " in heading:
                name, address = (part.strip() for part in heading.split(" - ", maxsplit=1))
            else:
                name, address = heading, ""
            locations.append(
                Location(
                    id=f"{area_id}:{index}",
                    name=name,
                    address=address,
                    area_id=area_id,
                    area_name=area_name,
                    visits=_parse_visits(schedule_html, year),
                )
            )
        areas.append(Area(id=area_id, name=area_name, locations=tuple(locations)))

    return tuple(areas)
