"""Validated JSON input and output helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from unischedule.models import (
    Cohort,
    CourseSection,
    Room,
    School,
    StaffMember,
    TimeSlot,
    University,
)


class UniversityDataError(ValueError):
    """Raised when university configuration is inconsistent."""


def _as_tuple(value: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in (value or []))


def _as_set(value: Any) -> frozenset[str]:
    return frozenset(str(item) for item in (value or []))


def load_university(path: str | Path) -> University:
    """Load and validate a university configuration from JSON."""
    source = Path(path)
    with source.open(encoding="utf-8") as file:
        data = json.load(file)

    return university_from_dict(data)


def university_from_dict(data: dict[str, Any]) -> University:
    """Build and validate a university configuration from a dictionary."""

    schools = tuple(School(**item) for item in data["schools"])
    cohorts = tuple(
        Cohort(
            id=item["id"],
            name=item["name"],
            school_id=item["school_id"],
            program=item["program"],
            size=int(item["size"]),
        )
        for item in data["cohorts"]
    )
    slots = tuple(TimeSlot(**item) for item in data["time_slots"])
    staff = tuple(
        StaffMember(
            id=item["id"],
            name=item["name"],
            role=item["role"],
            school_ids=_as_tuple(item["school_ids"]),
            available_slot_ids=_as_set(item.get("available_slot_ids")),
            qualified_subject_areas=_as_set(item.get("qualified_subject_areas")),
        )
        for item in data["staff"]
    )
    rooms = tuple(
        Room(
            id=item["id"],
            name=item["name"],
            building=item["building"],
            capacity=int(item["capacity"]),
            school_id=item.get("school_id"),
            features=_as_set(item.get("features")),
        )
        for item in data["rooms"]
    )
    sections = tuple(
        CourseSection(
            id=item["id"],
            code=item["code"],
            title=item["title"],
            school_id=item["school_id"],
            subject_area=item["subject_area"],
            program=item["program"],
            cohort_ids=_as_tuple(item["cohort_ids"]),
            instructor_ids=_as_tuple(item["instructor_ids"]),
            meetings_per_week=int(item["meetings_per_week"]),
            duration_slots=int(item.get("duration_slots", 1)),
            expected_students=int(item["expected_students"]),
            required_room_features=_as_set(item.get("required_room_features")),
            preferred_slot_ids=_as_set(item.get("preferred_slot_ids")),
            unavailable_slot_ids=_as_set(item.get("unavailable_slot_ids")),
        )
        for item in data["course_sections"]
    )

    university = University(
        name=data["university"],
        schools=schools,
        cohorts=cohorts,
        slots=slots,
        staff=staff,
        rooms=rooms,
        sections=sections,
    )
    validate_university(university)
    return university


def validate_university(university: University) -> None:
    """Validate IDs and references before scheduling begins."""
    collections = {
        "school": university.schools,
        "cohort": university.cohorts,
        "time slot": university.slots,
        "staff member": university.staff,
        "room": university.rooms,
        "course section": university.sections,
    }
    for label, records in collections.items():
        ids = [record.id for record in records]
        if len(ids) != len(set(ids)):
            raise UniversityDataError(f"Duplicate {label} ID found")

    school_ids = {school.id for school in university.schools}
    cohort_ids = {cohort.id for cohort in university.cohorts}
    slot_ids = {slot.id for slot in university.slots}
    staff_ids = {member.id for member in university.staff}
    staff_by_id = {member.id: member for member in university.staff}

    for cohort in university.cohorts:
        if cohort.school_id not in school_ids:
            raise UniversityDataError(
                f"Cohort {cohort.id} refers to an unknown school"
            )
        if cohort.size <= 0:
            raise UniversityDataError(f"Cohort {cohort.id} must have positive size")

    for member in university.staff:
        _require_subset(
            member.school_ids,
            school_ids,
            f"staff member {member.id} schools",
        )
        _require_subset(
            member.available_slot_ids,
            slot_ids,
            f"staff member {member.id} availability",
        )

    for room in university.rooms:
        if room.school_id is not None and room.school_id not in school_ids:
            raise UniversityDataError(f"Room {room.id} refers to an unknown school")
        if room.capacity <= 0:
            raise UniversityDataError(f"Room {room.id} must have positive capacity")

    for section in university.sections:
        if section.school_id not in school_ids:
            raise UniversityDataError(
                f"Section {section.id} refers to an unknown school"
            )
        _require_subset(
            section.instructor_ids,
            staff_ids,
            f"section {section.id} instructors",
        )
        _require_subset(
            section.cohort_ids,
            cohort_ids,
            f"section {section.id} cohorts",
        )
        unauthorized = [
            instructor_id
            for instructor_id in section.instructor_ids
            if section.school_id not in staff_by_id[instructor_id].school_ids
        ]
        if unauthorized:
            names = ", ".join(sorted(unauthorized))
            raise UniversityDataError(
                f"Section {section.id} has instructors outside its school: {names}"
            )
        _require_subset(
            section.preferred_slot_ids | section.unavailable_slot_ids,
            slot_ids,
            f"section {section.id} slot preferences",
        )
        if section.meetings_per_week < 1 or section.duration_slots < 1:
            raise UniversityDataError(
                f"Section {section.id} has an invalid meeting count"
            )
        if not section.cohort_ids:
            raise UniversityDataError(
                f"Section {section.id} must have at least one cohort"
            )

        matching_rooms = [
            room
            for room in university.rooms
            if room.capacity >= section.expected_students
            and section.required_room_features <= room.features
        ]
        if not matching_rooms:
            raise UniversityDataError(
                f"Section {section.id} has no room with enough capacity and features"
            )


def _require_subset(values: Any, valid: set[str], label: str) -> None:
    unknown = set(values) - valid
    if unknown:
        names = ", ".join(sorted(unknown))
        raise UniversityDataError(f"Unknown values in {label}: {names}")
