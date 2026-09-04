"""Schedule reporting and independent constraint checks."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from unischedule.models import University
from unischedule.scheduler import ScheduleResult


def schedule_records(
    university: University,
    result: ScheduleResult,
) -> list[dict[str, Any]]:
    """Flatten scheduled meetings into one record per occupied period."""
    sections = {section.id: section for section in university.sections}
    schools = {school.id: school for school in university.schools}
    cohorts = {cohort.id: cohort for cohort in university.cohorts}
    staff = {member.id: member for member in university.staff}
    rooms = {room.id: room for room in university.rooms}
    slots = {slot.id: slot for slot in university.slots}
    slot_rank = {slot.id: index for index, slot in enumerate(university.slots)}
    records: list[dict[str, Any]] = []

    for meeting in result.meetings:
        section = sections[meeting.section_id]
        room = rooms[meeting.room_id]
        instructor_names = ", ".join(
            staff[instructor_id].name for instructor_id in section.instructor_ids
        )
        cohort_names = ", ".join(
            cohorts[cohort_id].name for cohort_id in section.cohort_ids
        )
        for slot_id in meeting.slot_ids:
            slot = slots[slot_id]
            records.append(
                {
                    "school": schools[section.school_id].name,
                    "school_id": section.school_id,
                    "section_id": section.id,
                    "course": section.code,
                    "title": section.title,
                    "subject_area": section.subject_area,
                    "program": section.program,
                    "cohorts": cohort_names,
                    "cohort_ids": section.cohort_ids,
                    "instructors": instructor_names,
                    "instructor_ids": section.instructor_ids,
                    "day": slot.day,
                    "period": slot.period,
                    "start": slot.start,
                    "end": slot.end,
                    "slot_id": slot.id,
                    "room": room.name,
                    "room_id": room.id,
                    "building": room.building,
                    "occurrence": meeting.occurrence,
                }
            )
    return sorted(
        records,
        key=lambda row: (slot_rank[row["slot_id"]], row["course"]),
    )


def validate_schedule(university: University, result: ScheduleResult) -> list[str]:
    """Independently verify hard constraints in a generated schedule."""
    if not result.success:
        return ["The scheduler did not produce a complete timetable."]

    sections = {section.id: section for section in university.sections}
    staff = {member.id: member for member in university.staff}
    rooms = {room.id: room for room in university.rooms}
    slots = {slot.id: slot for slot in university.slots}
    violations: list[str] = []
    room_usage: set[tuple[str, str]] = set()
    staff_usage: set[tuple[str, str]] = set()
    cohort_usage: set[tuple[str, str]] = set()
    meeting_counts: Counter[str] = Counter()
    section_days: dict[str, set[str]] = defaultdict(set)

    for meeting in result.meetings:
        section = sections[meeting.section_id]
        room = rooms[meeting.room_id]
        meeting_counts[section.id] += 1
        section_days[section.id].add(slots[meeting.slot_ids[0]].day)

        if room.capacity < section.expected_students:
            violations.append(f"{section.id} exceeds the capacity of {room.id}.")
        if not section.required_room_features <= room.features:
            violations.append(f"{room.id} lacks features required by {section.id}.")

        for slot_id in meeting.slot_ids:
            if slot_id in section.unavailable_slot_ids:
                violations.append(f"{section.id} uses unavailable slot {slot_id}.")

            room_key = (room.id, slot_id)
            if room_key in room_usage:
                violations.append(f"Room {room.id} is double-booked in {slot_id}.")
            room_usage.add(room_key)

            for instructor_id in section.instructor_ids:
                staff_key = (instructor_id, slot_id)
                if staff_key in staff_usage:
                    violations.append(
                        f"Staff member {instructor_id} is double-booked in {slot_id}."
                    )
                staff_usage.add(staff_key)
                availability = staff[instructor_id].available_slot_ids
                if availability and slot_id not in availability:
                    violations.append(
                        f"Staff member {instructor_id} is unavailable in {slot_id}."
                    )

            for cohort_id in section.cohort_ids:
                cohort_key = (cohort_id, slot_id)
                if cohort_key in cohort_usage:
                    violations.append(f"Cohort {cohort_id} has a clash in {slot_id}.")
                cohort_usage.add(cohort_key)

    for section in university.sections:
        if meeting_counts[section.id] != section.meetings_per_week:
            violations.append(
                f"{section.id} has {meeting_counts[section.id]} meetings instead of "
                f"{section.meetings_per_week}."
            )
        if len(section_days[section.id]) != meeting_counts[section.id]:
            violations.append(f"{section.id} has multiple meetings on the same day.")

    return violations


def room_utilization(
    university: University,
    result: ScheduleResult,
) -> list[dict[str, Any]]:
    """Summarize occupied periods and utilization for every room."""
    occupied: Counter[str] = Counter()
    for meeting in result.meetings:
        occupied[meeting.room_id] += len(meeting.slot_ids)
    total_slots = len(university.slots)
    return [
        {
            "room": room.name,
            "building": room.building,
            "capacity": room.capacity,
            "occupied_periods": occupied[room.id],
            "utilization_pct": round(100 * occupied[room.id] / total_slots, 1),
        }
        for room in university.rooms
    ]
