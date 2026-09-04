"""RFC 5545 calendar export for generated university timetables."""

from __future__ import annotations

import re
from collections.abc import Collection
from datetime import UTC, date, datetime, time, timedelta

from unischedule.models import University
from unischedule.scheduler import ScheduleResult

MeetingIdentity = tuple[str, int]
DAY_OFFSETS = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}


def build_ics_calendar(
    university: University,
    result: ScheduleResult,
    first_week: date,
    weeks: int,
    meeting_ids: Collection[MeetingIdentity] | None = None,
    calendar_name: str | None = None,
    generated_at: datetime | None = None,
) -> str:
    """Export selected scheduled meetings as recurring calendar events."""
    if not result.success:
        raise ValueError("A successful schedule is required for calendar export")
    if weeks < 1:
        raise ValueError("Teaching weeks must be positive")

    sections = {section.id: section for section in university.sections}
    schools = {school.id: school for school in university.schools}
    cohorts = {cohort.id: cohort for cohort in university.cohorts}
    staff = {member.id: member for member in university.staff}
    rooms = {room.id: room for room in university.rooms}
    slots = {slot.id: slot for slot in university.slots}
    selected = set(meeting_ids) if meeting_ids is not None else None
    first_monday = first_week - timedelta(days=first_week.weekday())
    timestamp = (generated_at or datetime.now(UTC)).astimezone(UTC)
    timestamp_text = timestamp.strftime("%Y%m%dT%H%M%SZ")
    name = calendar_name or f"{university.name} timetable"
    events: list[list[str]] = []

    for meeting in result.meetings:
        identity = (meeting.section_id, meeting.occurrence)
        if selected is not None and identity not in selected:
            continue
        section = sections[meeting.section_id]
        first_slot = slots[meeting.slot_ids[0]]
        last_slot = slots[meeting.slot_ids[-1]]
        if first_slot.day not in DAY_OFFSETS:
            raise ValueError(f"Unsupported calendar day: {first_slot.day}")
        if last_slot.day != first_slot.day:
            raise ValueError("A calendar event cannot span configured weekdays")

        event_date = first_monday + timedelta(days=DAY_OFFSETS[first_slot.day])
        start = datetime.combine(event_date, _parse_time(first_slot.start))
        end = datetime.combine(event_date, _parse_time(last_slot.end))
        instructor_names = ", ".join(
            staff[staff_id].name for staff_id in section.instructor_ids
        )
        cohort_names = ", ".join(
            cohorts[cohort_id].name for cohort_id in section.cohort_ids
        )
        room = rooms[meeting.room_id]
        description = (
            f"School: {schools[section.school_id].name}\n"
            f"Cohorts: {cohort_names}\n"
            f"Teaching staff: {instructor_names}"
        )
        uid_school = re.sub(r"[^a-z0-9]+", "-", university.name.lower()).strip("-")
        events.append(
            [
                "BEGIN:VEVENT",
                f"UID:{section.id}-{meeting.occurrence}@{uid_school}.unischedule",
                f"DTSTAMP:{timestamp_text}",
                f"DTSTART:{start.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND:{end.strftime('%Y%m%dT%H%M%S')}",
                f"RRULE:FREQ=WEEKLY;COUNT={weeks}",
                f"SUMMARY:{_escape(f'{section.code} - {section.title}')}",
                f"DESCRIPTION:{_escape(description)}",
                f"LOCATION:{_escape(f'{room.name}, {room.building}')}",
                f"CATEGORIES:{_escape(schools[section.school_id].name)}",
                "END:VEVENT",
            ]
        )

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Gokul Krishna//UniSchedule 1.0//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_escape(name)}",
    ]
    for event in events:
        lines.extend(event)
    lines.append("END:VCALENDAR")
    return "\r\n".join(folded for line in lines for folded in _fold_line(line)) + "\r\n"


def _parse_time(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"Invalid timetable time: {value}") from error


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(";", "\\;")
        .replace(",", "\\,")
    )


def _fold_line(line: str, limit: int = 75) -> list[str]:
    if len(line.encode()) <= limit:
        return [line]

    folded: list[str] = []
    current = ""
    for character in line:
        if current and len(f"{current}{character}".encode()) > limit:
            folded.append(current)
            current = f" {character}"
        else:
            current += character
    if current:
        folded.append(current)
    return folded
