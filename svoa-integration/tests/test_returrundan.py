"""Tests for parsing SVOA Returrundan data."""

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from custom_components.svoa.returrundan import (
    ReturrundanParseError,
    parse_returrundan_payload,
)

FIXTURE = Path(__file__).parent / "returrundan-data-snapshot.json"
STOCKHOLM = ZoneInfo("Europe/Stockholm")


@pytest.fixture(scope="module")
def payload() -> dict[str, object]:
    """Load the supplied SVOA response fixture."""
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_parse_snapshot_returns_all_areas_and_locations(
    payload: dict[str, object],
) -> None:
    """Parse all locations from the supplied response."""
    areas = parse_returrundan_payload(payload, year=2026)

    assert len(areas) == 11
    assert sum(len(area.locations) for area in areas) == 89
    assert areas[0].id == "returrundan-225"
    assert areas[0].name == "Bromma"


def test_parse_location_heading_into_name_and_address(
    payload: dict[str, object],
) -> None:
    """Split the display heading into a location name and address."""
    areas = parse_returrundan_payload(payload, year=2026)
    location = areas[0].locations[0]

    assert location.name == "Abrahamsberg"
    assert location.address == "Ritarvägen 30, vid Abrahamsbergsskolan"
    assert location.area_name == "Bromma"


def test_parse_swedish_visit_dates_and_times(payload: dict[str, object]) -> None:
    """Parse Swedish month names and local visit times."""
    areas = parse_returrundan_payload(payload, year=2026)
    visit = areas[0].locations[0].visits[0]

    assert visit.start == datetime(2026, 8, 22, 11, 0, tzinfo=STOCKHOLM)
    assert visit.end == datetime(2026, 8, 22, 12, 0, tzinfo=STOCKHOLM)


def test_cancelled_visits_are_excluded(payload: dict[str, object]) -> None:
    """Ignore schedule entries marked up with HTML strikethrough."""
    areas = parse_returrundan_payload(payload, year=2026)
    södermalm = next(area for area in areas if area.name == "Södermalm")
    cancelled_location = next(
        location
        for location in södermalm.locations
        if "Bohusgatan 28" in location.address
    )

    assert cancelled_location.visits == ()


def test_informational_html_list_items_are_not_visits(
    payload: dict[str, object],
) -> None:
    """Ignore notices and empty list items in the schedule HTML."""
    areas = parse_returrundan_payload(payload, year=2026)
    bromma = areas[0]
    nockeby = next(
        location for location in bromma.locations if location.name == "Nockeby"
    )

    assert len(nockeby.visits) == 3
    assert all(visit.start.month in {9, 10, 12} for visit in nockeby.visits)


def test_reject_invalid_payload() -> None:
    """Reject responses that do not contain the expected structure."""
    with pytest.raises(ReturrundanParseError):
        parse_returrundan_payload({}, year=2026)


def test_next_visit_ignores_visits_that_have_already_started(
    payload: dict[str, object],
) -> None:
    """A visit in progress is not considered a future visit."""
    areas = parse_returrundan_payload(payload, year=2026)
    location = areas[0].locations[0]
    now = datetime(2026, 8, 22, 11, 30, tzinfo=STOCKHOLM)

    next_visit = location.next_visit(now)

    assert next_visit is not None
    assert next_visit.start == datetime(2026, 10, 3, 11, 0, tzinfo=STOCKHOLM)


def test_next_visit_returns_none_when_schedule_is_exhausted(
    payload: dict[str, object],
) -> None:
    """Do not synthesize a visit in the following year."""
    areas = parse_returrundan_payload(payload, year=2026)
    location = areas[0].locations[0]
    now = datetime(2026, 12, 1, 0, 0, tzinfo=STOCKHOLM)

    assert location.next_visit(now) is None


def test_schedule_year_is_explicit_and_deterministic(
    payload: dict[str, object],
) -> None:
    """Assign the supplied year to every date without rolling dates forward."""
    areas = parse_returrundan_payload(payload, year=2027)

    assert areas[0].locations[0].visits[0].start.year == 2027
