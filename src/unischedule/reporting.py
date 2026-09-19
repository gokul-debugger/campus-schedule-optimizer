"""Schedule reporting and independent constraint checks."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from unischedule.attendance import groups_by_cohort, learner_resource_ids
from unischedule.graph import students_conflict
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
    student_groups = {group.id: group for group in university.student_groups}
    cohort_groups = groups_by_cohort(university.student_groups)
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
        group_names = ", ".join(
            student_groups[group_id].name for group_id in section.student_group_ids
        )
        learner_ids = learner_resource_ids(section, cohort_groups)
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
                    "student_groups": group_names or "Whole cohort",
                    "student_group_ids": section.student_group_ids,
                    "learner_resource_ids": learner_ids,
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
    sections_by_slot: dict[str, list[str]] = defaultdict(list)
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

            for scheduled_section_id in sections_by_slot[slot_id]:
                scheduled_section = sections[scheduled_section_id]
                if students_conflict(section, scheduled_section):
                    violations.append(
                        f"Students in {section.id} and {scheduled_section.id} "
                        f"have a clash in {slot_id}."
                    )
            sections_by_slot[slot_id].append(section.id)

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
