"""Operational helpers for staff absence and substitute coverage."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Collection, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from unischedule.models import University
from unischedule.scheduler import ScheduleResult


@dataclass(frozen=True, slots=True)
class StaffAbsence:
    """A temporary staff absence covering one or more timetable periods."""

    id: str
    staff_id: str
    slot_ids: tuple[str, ...]
    reason: str = "Emergency leave"


@dataclass(frozen=True, slots=True)
class CoverageNeed:
    """One scheduled meeting requiring cover for an absent staff member."""

    id: str
    section_id: str
    occurrence: int
    absent_staff_id: str
    slot_ids: tuple[str, ...]
    room_id: str


def update_staff_availability(
    data: Mapping[str, Any],
    staff_id: str,
    available_slot_ids: Collection[str],
) -> dict[str, Any]:
    """Return configuration data with one staff member's availability updated."""
    updated = deepcopy(dict(data))
    matching = [row for row in updated["staff"] if row["id"] == staff_id]
    if not matching:
        raise ValueError(f"Unknown staff member: {staff_id}")
    matching[0]["available_slot_ids"] = list(dict.fromkeys(available_slot_ids))
    return updated


def absence_lookup(absences: Collection[StaffAbsence]) -> dict[str, set[str]]:
    """Combine absence entries into unavailable periods by staff member."""
    lookup: dict[str, set[str]] = defaultdict(set)
    for absence in absences:
        lookup[absence.staff_id].update(absence.slot_ids)
    return dict(lookup)


def find_coverage_needs(
    university: University,
    result: ScheduleResult,
    absences: Collection[StaffAbsence],
) -> tuple[CoverageNeed, ...]:
    """Find scheduled meetings affected by temporary staff absences."""
    if not result.success:
        return ()

    absent_slots = absence_lookup(absences)
    sections = {section.id: section for section in university.sections}
    needs: list[CoverageNeed] = []
    for meeting in result.meetings:
        section = sections[meeting.section_id]
        meeting_slots = set(meeting.slot_ids)
        for staff_id in section.instructor_ids:
            if meeting_slots & absent_slots.get(staff_id, set()):
                needs.append(
                    CoverageNeed(
                        id=f"{section.id}:{meeting.occurrence}:{staff_id}",
                        section_id=section.id,
                        occurrence=meeting.occurrence,
                        absent_staff_id=staff_id,
                        slot_ids=meeting.slot_ids,
                        room_id=meeting.room_id,
                    )
                )
    return tuple(needs)


def eligible_substitutes(
    university: University,
    result: ScheduleResult,
    need: CoverageNeed,
    absences: Collection[StaffAbsence],
) -> tuple[str, ...]:
    """Return qualified and conflict-free substitute IDs in preference order."""
    sections = {section.id: section for section in university.sections}
    staff = {member.id: member for member in university.staff}
    section = sections[need.section_id]
    absent_member = staff[need.absent_staff_id]
    absent_slots = absence_lookup(absences)
    busy_slots: dict[str, set[str]] = defaultdict(set)
    workload: Counter[str] = Counter()

    for meeting in result.meetings:
        meeting_section = sections[meeting.section_id]
        for staff_id in meeting_section.instructor_ids:
            busy_slots[staff_id].update(meeting.slot_ids)
            workload[staff_id] += len(meeting.slot_ids)

    eligible = []
    required_slots = set(need.slot_ids)
    for candidate in university.staff:
        if candidate.id in section.instructor_ids:
            continue
        if section.school_id not in candidate.school_ids:
            continue
        if (
            candidate.qualified_subject_areas
            and section.subject_area not in candidate.qualified_subject_areas
        ):
            continue
        if (
            candidate.available_slot_ids
            and not required_slots <= candidate.available_slot_ids
        ):
            continue
        if required_slots & absent_slots.get(candidate.id, set()):
            continue
        if required_slots & busy_slots.get(candidate.id, set()):
            continue
        eligible.append(candidate)

    return tuple(
        member.id
        for member in sorted(
            eligible,
            key=lambda member: (
                member.role != absent_member.role,
                workload[member.id],
                member.name,
            ),
        )
    )


def validate_coverage_assignments(
    university: University,
    result: ScheduleResult,
    needs: Collection[CoverageNeed],
    absences: Collection[StaffAbsence],
    assignments: Mapping[str, str],
) -> list[str]:
    """Validate completeness, eligibility, and cross-cover collisions."""
    violations: list[str] = []
    substitute_usage: set[tuple[str, str]] = set()

    for need in needs:
        substitute_id = assignments.get(need.id)
        if not substitute_id:
            violations.append(f"No substitute is assigned for {need.id}.")
            continue
        eligible = eligible_substitutes(university, result, need, absences)
        if substitute_id not in eligible:
            violations.append(
                f"Staff member {substitute_id} is not eligible for {need.id}."
            )
            continue
        for slot_id in need.slot_ids:
            usage_key = (substitute_id, slot_id)
            if usage_key in substitute_usage:
                violations.append(
                    f"Substitute {substitute_id} has overlapping cover in {slot_id}."
                )
            substitute_usage.add(usage_key)

    return violations


def propose_coverage_assignments(
    university: University,
    result: ScheduleResult,
    needs: Collection[CoverageNeed],
    absences: Collection[StaffAbsence],
) -> dict[str, str]:
    """Greedily assign scarce substitute candidates without cover collisions."""
    candidates = {
        need.id: eligible_substitutes(university, result, need, absences)
        for need in needs
    }
    assigned: dict[str, str] = {}
    substitute_usage: set[tuple[str, str]] = set()

    for need in sorted(needs, key=lambda item: (len(candidates[item.id]), item.id)):
        for candidate_id in candidates[need.id]:
            usage = {(candidate_id, slot_id) for slot_id in need.slot_ids}
            if usage & substitute_usage:
                continue
            assigned[need.id] = candidate_id
            substitute_usage.update(usage)
            break
    return assigned


def coverage_plan_records(
    university: University,
    needs: Collection[CoverageNeed],
    assignments: Mapping[str, str],
) -> list[dict[str, Any]]:
    """Build readable records for saved substitute assignments."""
    sections = {section.id: section for section in university.sections}
    staff = {member.id: member for member in university.staff}
    rooms = {room.id: room for room in university.rooms}
    slots = {slot.id: slot for slot in university.slots}
    records = []

    for need in needs:
        substitute_id = assignments.get(need.id)
        if not substitute_id:
            continue
        section = sections[need.section_id]
        first_slot = slots[need.slot_ids[0]]
        last_slot = slots[need.slot_ids[-1]]
        records.append(
            {
                "day": first_slot.day,
                "start": first_slot.start,
                "end": last_slot.end,
                "course": section.code,
                "class": section.title,
                "absent_staff": staff[need.absent_staff_id].name,
                "substitute": staff[substitute_id].name,
                "room": rooms[need.room_id].name,
                "status": "Covered",
            }
        )
    return records
