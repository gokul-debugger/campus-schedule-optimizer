"""Conversion helpers for editable university configuration tables."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from math import isnan
from typing import Any

from unischedule.io import UniversityDataError

COLLECTIONS = (
    "schools",
    "cohorts",
    "time_slots",
    "staff",
    "rooms",
    "course_sections",
)
LIST_FIELDS = {
    "staff": (
        "school_ids",
        "available_slot_ids",
        "qualified_subject_areas",
    ),
    "rooms": ("features",),
    "course_sections": (
        "cohort_ids",
        "instructor_ids",
        "required_room_features",
        "preferred_slot_ids",
        "unavailable_slot_ids",
    ),
}


def editor_rows(data: Mapping[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Return mutable rows with list fields suitable for table editors."""
    rows = {name: deepcopy(list(data.get(name, []))) for name in COLLECTIONS}
    for collection, fields in LIST_FIELDS.items():
        for row in rows[collection]:
            for field in fields:
                row[field] = list(row.get(field) or [])
    return rows


def configuration_from_editor(
    university_name: Any,
    tables: Mapping[str, Iterable[Mapping[str, Any]]],
) -> dict[str, Any]:
    """Normalize editable table records into scheduler configuration JSON."""
    name = _required_text(university_name, "University name")
    data: dict[str, Any] = {"university": name}

    data["schools"] = [
        {
            "id": _required_text(row.get("id"), "School ID"),
            "name": _required_text(row.get("name"), "School name"),
            "code": _required_text(row.get("code"), "School code"),
        }
        for row in _active_rows(tables.get("schools", []))
    ]
    data["cohorts"] = [
        {
            "id": _required_text(row.get("id"), "Cohort ID"),
            "name": _required_text(row.get("name"), "Cohort name"),
            "school_id": _required_text(row.get("school_id"), "Cohort school"),
            "program": _required_text(row.get("program"), "Cohort program"),
            "size": _positive_int(row.get("size"), "Cohort size"),
        }
        for row in _active_rows(tables.get("cohorts", []))
    ]
    data["time_slots"] = [
        {
            "id": _required_text(row.get("id"), "Time-slot ID"),
            "day": _required_text(row.get("day"), "Time-slot day"),
            "period": _positive_int(row.get("period"), "Time-slot period"),
            "start": _required_text(row.get("start"), "Time-slot start"),
            "end": _required_text(row.get("end"), "Time-slot end"),
        }
        for row in _active_rows(tables.get("time_slots", []))
    ]
    data["staff"] = [
        {
            "id": _required_text(row.get("id"), "Staff ID"),
            "name": _required_text(row.get("name"), "Staff name"),
            "role": _required_text(row.get("role"), "Staff role"),
            "school_ids": _list_value(row.get("school_ids")),
            "available_slot_ids": _list_value(row.get("available_slot_ids")),
            "qualified_subject_areas": _list_value(
                row.get("qualified_subject_areas")
            ),
        }
        for row in _active_rows(tables.get("staff", []))
    ]
    data["rooms"] = [
        {
            "id": _required_text(row.get("id"), "Room ID"),
            "name": _required_text(row.get("name"), "Room name"),
            "building": _required_text(row.get("building"), "Room building"),
            "capacity": _positive_int(row.get("capacity"), "Room capacity"),
            "school_id": _optional_text(row.get("school_id")),
            "features": _list_value(row.get("features")),
        }
        for row in _active_rows(tables.get("rooms", []))
    ]
    data["course_sections"] = [
        {
            "id": _required_text(row.get("id"), "Course-section ID"),
            "code": _required_text(row.get("code"), "Course code"),
            "title": _required_text(row.get("title"), "Course title"),
            "school_id": _required_text(row.get("school_id"), "Course school"),
            "subject_area": _required_text(
                row.get("subject_area"),
                "Course subject area",
            ),
            "program": _required_text(row.get("program"), "Course program"),
            "cohort_ids": _list_value(row.get("cohort_ids")),
            "instructor_ids": _list_value(row.get("instructor_ids")),
            "meetings_per_week": _positive_int(
                row.get("meetings_per_week"),
                "Meetings per week",
            ),
            "duration_slots": _positive_int(
                row.get("duration_slots"),
                "Course duration",
            ),
            "expected_students": _positive_int(
                row.get("expected_students"),
                "Expected students",
            ),
            "required_room_features": _list_value(
                row.get("required_room_features")
            ),
            "preferred_slot_ids": _list_value(row.get("preferred_slot_ids")),
            "unavailable_slot_ids": _list_value(
                row.get("unavailable_slot_ids")
            ),
        }
        for row in _active_rows(tables.get("course_sections", []))
    ]

    for collection in COLLECTIONS:
        if not data[collection]:
            label = collection.replace("_", " ")
            raise UniversityDataError(f"At least one {label} row is required")
    return data


def _active_rows(rows: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return [row for row in rows if any(not _is_blank(value) for value in row.values())]


def _is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, frozenset)):
        return not value
    try:
        return bool(isnan(value))
    except (TypeError, ValueError):
        return False


def _required_text(value: Any, label: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise UniversityDataError(f"{label} is required")
    return text


def _optional_text(value: Any) -> str | None:
    if _is_blank(value):
        return None
    return str(value).strip()


def _positive_int(value: Any, label: str) -> int:
    if _is_blank(value):
        raise UniversityDataError(f"{label} is required")
    try:
        number = int(value)
    except (TypeError, ValueError) as error:
        raise UniversityDataError(f"{label} must be a whole number") from error
    if number < 1:
        raise UniversityDataError(f"{label} must be positive")
    return number


def _list_value(value: Any) -> list[str]:
    if _is_blank(value):
        return []
    values = value.split(",") if isinstance(value, str) else value
    return [str(item).strip() for item in values if not _is_blank(item)]
