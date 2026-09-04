"""Domain models for university timetable generation."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class School:
    id: str
    name: str
    code: str


@dataclass(frozen=True, slots=True)
class Cohort:
    id: str
    name: str
    school_id: str
    program: str
    size: int


@dataclass(frozen=True, slots=True)
class TimeSlot:
    id: str
    day: str
    period: int
    start: str
    end: str


@dataclass(frozen=True, slots=True)
class StaffMember:
    id: str
    name: str
    role: str
    school_ids: tuple[str, ...]
    available_slot_ids: frozenset[str] = field(default_factory=frozenset)
    qualified_subject_areas: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class Room:
    id: str
    name: str
    building: str
    capacity: int
    school_id: str | None = None
    features: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class CourseSection:
    id: str
    code: str
    title: str
    school_id: str
    subject_area: str
    program: str
    cohort_ids: tuple[str, ...]
    instructor_ids: tuple[str, ...]
    meetings_per_week: int
    duration_slots: int
    expected_students: int
    required_room_features: frozenset[str] = field(default_factory=frozenset)
    preferred_slot_ids: frozenset[str] = field(default_factory=frozenset)
    unavailable_slot_ids: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True, slots=True)
class University:
    name: str
    schools: tuple[School, ...]
    cohorts: tuple[Cohort, ...]
    slots: tuple[TimeSlot, ...]
    staff: tuple[StaffMember, ...]
    rooms: tuple[Room, ...]
    sections: tuple[CourseSection, ...]


@dataclass(frozen=True, slots=True)
class ScheduledMeeting:
    section_id: str
    occurrence: int
    slot_ids: tuple[str, ...]
    room_id: str
