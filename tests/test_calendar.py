from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from unischedule.calendar import build_ics_calendar
from unischedule.io import university_from_dict
from unischedule.scheduler import UniversityScheduler

DEMO_PATH = Path(__file__).resolve().parents[1] / "examples" / "demo_university.json"


def scheduled_demo():
    university = university_from_dict(
        json.loads(DEMO_PATH.read_text(encoding="utf-8"))
    )
    result = UniversityScheduler(university).solve()
    assert result.success
    return university, result


def test_calendar_exports_selected_recurring_meeting() -> None:
    university, result = scheduled_demo()
    meeting = result.meetings[0]

    calendar = build_ics_calendar(
        university,
        result,
        first_week=date(2026, 9, 9),
        weeks=12,
        meeting_ids={(meeting.section_id, meeting.occurrence)},
        calendar_name="Year 2 timetable",
        generated_at=datetime(2026, 9, 5, 10, 30, tzinfo=UTC),
    )

    assert calendar.startswith("BEGIN:VCALENDAR\r\n")
    assert calendar.endswith("END:VCALENDAR\r\n")
    assert calendar.count("BEGIN:VEVENT") == 1
    assert "RRULE:FREQ=WEEKLY;COUNT=12" in calendar
    assert "X-WR-CALNAME:Year 2 timetable" in calendar
    assert "DTSTAMP:20260905T103000Z" in calendar


def test_calendar_normalizes_first_week_to_monday() -> None:
    university, result = scheduled_demo()
    friday_meeting = next(
        meeting
        for meeting in result.meetings
        if any(
            slot.id == meeting.slot_ids[0] and slot.day == "Friday"
            for slot in university.slots
        )
    )

    calendar = build_ics_calendar(
        university,
        result,
        first_week=date(2026, 9, 9),
        weeks=1,
        meeting_ids={(friday_meeting.section_id, friday_meeting.occurrence)},
        generated_at=datetime(2026, 9, 5, tzinfo=UTC),
    )

    assert "DTSTART:20260911T" in calendar


def test_calendar_escapes_content_and_folds_long_lines() -> None:
    university, result = scheduled_demo()

    calendar = build_ics_calendar(
        university,
        result,
        first_week=date(2026, 9, 7),
        weeks=1,
        calendar_name="Science, Engineering; and Computing",
        generated_at=datetime(2026, 9, 5, tzinfo=UTC),
    )

    assert "X-WR-CALNAME:Science\\, Engineering\\; and Computing" in calendar
    assert "\\nCohorts:" in calendar
    assert all(len(line.encode("utf-8")) <= 75 for line in calendar.split("\r\n"))


def test_calendar_rejects_invalid_inputs() -> None:
    university, result = scheduled_demo()

    with pytest.raises(ValueError, match="positive"):
        build_ics_calendar(
            university,
            result,
            first_week=date(2026, 9, 7),
            weeks=0,
        )
